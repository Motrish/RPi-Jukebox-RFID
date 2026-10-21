"""Caller-driven arbitration for one injected LOCAL playback provider."""

import math
import threading
import time
import uuid

from jukebox.contracts import ContractValidationError, validate_identifier, validate_media_ref

from .execution_gate import ExecutionGate, GateStateError


class LocalPlaybackService:
    """Advance playback ownership synchronously, one provider call per step."""

    def __init__(self, *, provider, boot_id, monotonic=time.monotonic):
        if not callable(getattr(provider, "start", None)) or not callable(getattr(provider, "stop", None)):
            raise ContractValidationError("provider", "invalid_provider")
        boot_id = validate_identifier(boot_id, "bootId")
        if not callable(monotonic):
            raise ContractValidationError("monotonic", "invalid_clock")
        self._provider = provider
        self._clock = monotonic
        self._gate = ExecutionGate(boot_id=boot_id)
        self._lock = threading.Lock()
        self._pending = None
        self._driving = False
        self._closed = False
        self._last_failure = None
        self._last_execution_intent_id = None
        self._retry_stop = False

    def request_start(self, entry_id, media_ref):
        if type(entry_id) is not str:
            raise ContractValidationError("entryId", "invalid_identifier")
        if type(media_ref) is not dict:
            raise ContractValidationError("mediaRef", "invalid_fields")
        media_snapshot = media_ref.copy()
        if (any(type(key) is not str for key in media_snapshot)
                or any(type(value) is not str for value in media_snapshot.values())):
            raise ContractValidationError("mediaRef", "invalid_fields")
        entry = validate_identifier(entry_id, "entryId")
        ref = validate_media_ref(media_snapshot)
        if ref["kind"] != "LOCAL":
            raise ContractValidationError("mediaRef.kind", "unsupported_source_kind")
        intent_id = uuid.uuid4().hex
        with self._lock:
            if self._closed:
                raise GateStateError("CLOSED")
            self._gate.invalidate()
            self._pending = {"intentId": intent_id, "operation": "START",
                             "entryId": entry, "mediaRef": dict(ref)}
            self._retry_stop = False
        return intent_id

    def request_stop(self):
        intent_id = uuid.uuid4().hex
        with self._lock:
            failed_stop = (self._last_failure is not None
                           and self._last_failure["operation"] == "STOP"
                           and self._last_failure["code"] == "STOP_UNCONFIRMED")
            self._gate.invalidate()
            self._pending = {"intentId": intent_id, "operation": "STOP",
                             "entryId": None, "mediaRef": None}
            self._retry_stop = bool(failed_stop and not self._driving)
        return intent_id

    def run_once(self, *, deadline):
        self._validate_deadline(deadline)
        work = self._claim_work()
        if work is None:
            return self.snapshot()
        operation, intent, permit, lease, media_ref = work
        if operation == "START":
            permit, lease = self._reserve_start(intent)
        safe_receipt, failure = self._call_provider(operation, lease, media_ref, deadline)
        completion = self._gate.complete(permit, safe_receipt)
        result = self._publish(operation, intent, completion, safe_receipt)
        if failure is not None:
            raise failure.with_traceback(failure.__traceback__)
        return result

    def _validate_deadline(self, deadline):
        if type(deadline) not in {int, float} or not _finite(deadline):
            raise ContractValidationError("deadline", "invalid_deadline")
        try:
            now = self._clock()
        except Exception:
            raise GateStateError("CLOCK_UNAVAILABLE") from None
        if type(now) not in {int, float} or not _finite(now):
            raise GateStateError("CLOCK_UNAVAILABLE")
        if float(deadline) <= float(now):
            raise GateStateError("DEADLINE_EXPIRED")

    def _claim_work(self):
        with self._lock:
            if self._driving:
                raise GateStateError("BUSY")
            self._driving = True
            try:
                work = self._prepare_work_locked()
            except Exception:
                self._driving = False
                raise
            if work is None:
                return None
            return work

    def _reserve_start(self, intent):
        try:
            permit = self._gate.reserve_start(intent["entryId"])
            lease = self._gate.lease(permit)
        except BaseException:
            with self._lock:
                self._driving = False
            raise
        with self._lock:
            if (self._closed or self._pending is None
                    or self._pending["intentId"] != intent["intentId"]):
                self._gate.invalidate()
        return permit, lease

    def _call_provider(self, operation, lease, media_ref, deadline):
        failure = None
        try:
            receipt = (self._provider.start(media_ref, lease=lease, deadline=deadline)
                       if operation == "START" else
                       self._provider.stop(lease=lease, deadline=deadline))
            safe_receipt = _plain_receipt(receipt)
        except BaseException as error:
            safe_receipt = None
            failure = error
        return safe_receipt, failure

    def _publish(self, operation, intent, completion, safe_receipt):
        with self._lock:
            return self._publish_locked(operation, intent, completion, safe_receipt)

    def begin_shutdown(self):
        intent_id = uuid.uuid4().hex
        with self._lock:
            preserve_retry = (self._retry_stop and self._pending is not None
                              and self._pending["operation"] == "STOP")
            self._closed = True
            self._gate.invalidate()
            if not preserve_retry:
                self._pending = {"intentId": intent_id, "operation": "STOP",
                                 "entryId": None, "mediaRef": None}
            self._retry_stop = preserve_retry
            return self._snapshot_locked()

    def snapshot(self):
        with self._lock:
            return self._snapshot_locked()

    def _snapshot_locked(self, gate=None):
        gate = self._gate.snapshot() if gate is None else gate
        pending = _copy_pending(self._pending)
        marker = gate["lastExecution"]
        last_execution = (None if marker is None else
                          {**marker, "intentId": self._last_execution_intent_id})
        quiescent = not self._driving and gate["owner"] is None and pending is None
        return {"gate": gate, "pending": pending, "driving": self._driving,
                "closed": self._closed, "quiescent": quiescent,
                "lastFailure": None if self._last_failure is None else dict(self._last_failure),
                "lastExecution": last_execution}

    def _prepare_work_locked(self):
        gate = self._gate.snapshot()
        pending = _copy_pending(self._pending)
        owner = gate["owner"]
        failed = (self._last_failure is not None
                  and self._last_failure["operation"] == "STOP"
                  and self._last_failure["code"] == "STOP_UNCONFIRMED")
        if failed and not self._retry_stop:
            self._driving = False
            return None
        if owner is not None and self._must_stop(gate, pending):
            permit = self._gate.reserve_stop()
            intent = pending if pending is not None and pending["operation"] == "STOP" else None
            return "STOP", intent, permit, self._gate.lease(permit), None
        if owner is None and pending is not None and pending["operation"] == "STOP":
            self._pending = None
            self._last_failure = None
            self._retry_stop = False
            self._driving = False
            return None
        if self._can_start(owner, pending):
            return "START", pending, None, None, dict(pending["mediaRef"])
        self._driving = False
        return None

    def _must_stop(self, gate, pending):
        return (gate["cleanupRequired"]
                or (pending is not None and pending["operation"] == "STOP"))

    def _can_start(self, owner, pending):
        return (owner is None and pending is not None
                and pending["operation"] == "START" and not self._closed)

    def _publish_locked(self, operation, intent, completion, receipt):
        if operation == "START":
            self._publish_start_locked(intent, completion, receipt)
        else:
            self._publish_stop_locked(completion)
        self._last_execution_intent_id = None if intent is None else intent["intentId"]
        self._driving = False
        return self._snapshot_locked()

    def _publish_start_locked(self, intent, gate, receipt):
        if self._pending is not None and self._pending["intentId"] == intent["intentId"]:
            self._pending = None
        if gate["error"] is not None:
            self._last_failure = {"operation": "START", "code": gate["error"]}
        elif receipt is not None and receipt.get("outcome") == "REJECTED":
            self._last_failure = {"operation": "START", "code": "START_REJECTED"}
        else:
            self._last_failure = None

    def _publish_stop_locked(self, gate):
        self._retry_stop = False
        if gate["error"] == "STOP_UNCONFIRMED":
            self._last_failure = {"operation": "STOP", "code": "STOP_UNCONFIRMED"}
        else:
            self._last_failure = None


def _finite(value):
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _copy_pending(value):
    if value is None:
        return None
    return {"intentId": value["intentId"], "operation": value["operation"],
            "entryId": value["entryId"],
            "mediaRef": None if value["mediaRef"] is None else dict(value["mediaRef"])}


def _plain_receipt(value):
    """Copy provider-owned JSON values before gate completion under arbitration."""
    fields = {"provider", "operation", "identity", "outcome", "epoch", "songid", "state",
              "positionMs", "durationMs", "observedAtMonotonic", "error"}
    if type(value) is not dict:
        return None
    try:
        result = value.copy()
        if set(result) != fields or any(type(key) is not str for key in result):
            return None
        ident = result["identity"]
        if type(ident) is dict:
            result["identity"] = ident.copy()
        error = result["error"]
        if type(error) is dict:
            result["error"] = error.copy()
        return result
    except (RuntimeError, TypeError, ValueError):
        return None

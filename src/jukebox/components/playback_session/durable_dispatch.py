"""Internal bridge from durable playlist commands to local playback."""

import math
import json
import threading
import time
import uuid

from jukebox.contracts import ContractValidationError, validate_queue_entry

from .execution_gate import GateStateError
from .local_playback_service import LocalPlaybackService

_MISSING = object()


class _ReplayMiss(GateStateError):
    """No owner-local memo exists for this command."""

    def __init__(self):
        super().__init__("CLOSED")


class DurableDispatch:
    """Admit a command and advance playback once.

    ``admission.action`` is the requested command; ``operation`` is what ran.
    They can differ after a provider crash, when the step performs cleanup STOP.
    A successful ``operation=None`` means this step did no work because it was
    already satisfied. For executed steps exactly one of ``gate``/``failure`` is
    set; rejected or unknown admissions set neither.
    ``executionId`` identifies the executed gate owner and is set only when this
    step performed work; latched/no-op steps report None even if an owner remains.
    Work attribution uses the service's persisted ``lastExecution`` marker.
    Its ``intentId`` is in ``playback["lastExecution"]`` (six fields), not the
    gate's identity-only ``lastExecution`` (five fields); consumers read playback.
    """

    def __init__(self, *, store, provider=_MISSING, boot_id, monotonic=None, service=None,
                 before_execute=None, publish_intent=None, claim_step=None):
        self._store = store
        self._clock = time.monotonic if monotonic is None else monotonic
        if service is None:
            if provider is _MISSING:
                raise TypeError("missing required keyword-only argument: 'provider'")
            options = {"provider": provider, "boot_id": boot_id}
            if monotonic is not None:
                options["monotonic"] = monotonic
            service = LocalPlaybackService(**options)
        elif provider is not _MISSING or not isinstance(service, LocalPlaybackService):
            raise TypeError("service injection requires a LocalPlaybackService and no provider")
        self._service = service
        self._before_execute = before_execute
        self._publish_intent = publish_intent
        self._claim_step = claim_step
        self._lock = threading.Lock()
        self._completed = {}

    def dispatch(self, command, *, deadline, claim_step=None):
        self._validate_deadline(deadline)
        if not self._lock.acquire(blocking=False):
            raise GateStateError("BUSY")
        try:
            command_id = command.get("commandId") if type(command) is dict else None
            prior = self._completed.get(command_id) if type(command_id) is str else None
            if prior is not None and prior[2] == _canonical(command):
                if isinstance(prior[1], BaseException):
                    raise prior[1].with_traceback(prior[1].__traceback__)
                return prior[1]
            admitted = self._store.admit_playback(command)
            return self._dispatch_admitted(command, command_id, admitted, deadline, claim_step)
        finally:
            self._lock.release()

    def _dispatch_admitted(self, command, command_id, admitted, deadline, claim_step):
        if admitted.get("status") != "ACCEPTED":
            return _wrapper(admitted)
        # Admission must be structurally complete before it becomes a replayable
        # dispatch outcome. A malformed store response is not terminal execution.
        action = admitted["action"]
        if action == "PLAYBACK_START":
            self._validate_start_admission(admitted)
        if self._before_execute is not None and not self._before_execute():
            return self._memo(command, command_id, admitted, _wrapper(admitted))
        if action not in {"PLAYBACK_START", "PLAYBACK_STOP"}:
            return _wrapper(admitted)
        step_claimer = self._claim_step if self._claim_step is not None else claim_step
        try:
            execution_id = (uuid.uuid4().hex
                            if action == "PLAYBACK_START" and step_claimer is not None else None)
            intent_id = self._publish_request_intent(action, admitted)
        except GateStateError as error:
            if error.code != "CLOSED":
                self._memo_exception(command, command_id, admitted, error)
                raise
            return self._memo(command, command_id, admitted, _wrapper(admitted))
        except BaseException as error:
            self._memo_exception(command, command_id, admitted, error)
            raise
        try:
            result = self._dispatch_step(command, command_id, admitted, intent_id,
                                         deadline, step_claimer, execution_id)
        except BaseException as error:
            self._memo_exception(command, command_id, admitted, error)
            raise
        return self._memo(command, command_id, admitted, result)

    @staticmethod
    def _validate_start_admission(admitted):
        result = admitted["result"]
        # ``selection`` is the payload this bridge consumes next, so name it
        # before the intent metadata when a result is structurally empty.
        for field in ("selection", "intentId", "intentSequence", "acceptedAt"):
            result[field]
        selection = result["selection"]
        for field in ("queueId", "queueRevision", "entry"):
            selection[field]
        entry = selection["entry"]
        for field in ("entryId", "sourceEntryId", "mediaRef", "title", "position"):
            entry[field]
        if type(entry["entryId"]) is not str or type(entry["mediaRef"]) is not dict:
            raise ContractValidationError("result.selection.entry", "invalid_fields")
        media_ref = entry["mediaRef"]
        if (any(type(key) is not str for key in media_ref)
                or any(type(value) is not str for value in media_ref.values())):
            raise ContractValidationError("mediaRef", "invalid_fields")
        validate_queue_entry(entry, field="selection.entry")

    def _publish_request_intent(self, action, admitted):
        if action == "PLAYBACK_START":
            entry = admitted["result"]["selection"]["entry"]
            if self._publish_intent is not None:
                return self._publish_intent(action, entry["entryId"], entry["mediaRef"])
            return self._service.request_start(entry["entryId"], entry["mediaRef"])
        if self._publish_intent is not None:
            return self._publish_intent(action, None, None)
        return self._service.request_stop()

    def _dispatch_step(self, command, command_id, admitted, intent_id, deadline, claim_step,
                       execution_id):
        pre_run, state = self._run_step(claim_step, intent_id, deadline,
                                        command, command_id, admitted, execution_id)
        if pre_run is None:
            return state
        marker = state["lastExecution"]
        marker_changed = pre_run.get("lastExecution") != marker
        # Preserve existing execution attribution and the request intent.
        operation = marker["operation"] if marker_changed else None
        execution_id = marker["executionId"] if marker_changed else None
        failure = state.get("lastFailure") if marker_changed else None
        if failure is not None:
            return _wrapper(admitted, state, operation, failure=failure,
                            intent_id=intent_id, execution_id=execution_id)
        return _wrapper(admitted, state, operation, gate=state["gate"],
                        intent_id=intent_id, execution_id=execution_id)

    def _run_step(self, step_claimer, intent_id, deadline, command, command_id, admitted,
                  execution_id):
        if step_claimer is None:
            pre_run = self._service.snapshot()
            return pre_run, self._service.run_once(deadline=deadline)
        claim = step_claimer(intent_id, execution_id)
        if claim is None or not claim[0]:
            result = _wrapper(admitted)
            return None, self._memo(command, command_id, admitted, result)
        pre_run = self._service.snapshot()
        if claim[1] is None:
            return pre_run, pre_run
        return pre_run, self._service.run_claimed_step(claim[1], deadline=deadline)

    def _memo(self, command, command_id, admitted, result):
        if type(command_id) is str:
            self._completed[command_id] = (_canonical(admitted), result, _canonical(command))
        return result

    def _memo_exception(self, command, command_id, admitted, error):
        if type(command_id) is str:
            self._completed[command_id] = (_canonical(admitted), error, _canonical(command))

    def replay(self, command):
        """Return only an identical owner-local memo, without store admission."""
        command_id = command.get("commandId") if type(command) is dict else None
        with self._lock:
            prior = self._completed.get(command_id) if type(command_id) is str else None
            if prior is None:
                raise _ReplayMiss()
            if prior[2] != _canonical(command):
                raise GateStateError("COMMAND_ID_REUSED")
            if isinstance(prior[1], BaseException):
                raise prior[1].with_traceback(prior[1].__traceback__)
            return prior[1]

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


def _finite(value):
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _wrapper(admission, playback=None, operation=None, *, gate=None, failure=None,
             intent_id=None, execution_id=None):
    return {"admission": admission, "playback": playback, "operation": operation,
            "gate": gate, "failure": failure, "intentId": intent_id,
            "executionId": execution_id}

"""In-memory authorization and ownership gate for LOCAL playback calls."""
import math
import re
import threading
import uuid

from jukebox.contracts import ContractValidationError, validate_identifier


class GateStateError(RuntimeError):
    """A lifecycle transition cannot be admitted in the current gate state."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


_IDENTITY_FIELDS = {"bootId", "generation", "executionId", "entryId"}
_RECEIPT_FIELDS = {
    "provider", "operation", "identity", "outcome", "epoch", "songid",
    "state", "positionMs", "durationMs", "observedAtMonotonic", "error",
}
_ERROR_FIELDS = {"code", "message", "retryable", "operation"}
_MAX_GENERATION = 9007199254740991
_ERROR_CODES = {
    "STALE_EXECUTION", "EXECUTION_CONFLICT", "MEDIA_UNAVAILABLE", "RESOLUTION_FAILED",
    "CAPABILITY_UNAVAILABLE", "PROVIDER_UNAVAILABLE", "PROVIDER_REJECTED",
    "PROVIDER_STATE_MISMATCH", "OPERATION_TIMEOUT", "SESSION_CHANGED", "STOP_UNCONFIRMED",
}
_SONG_ID = re.compile(r"[0-9]+\Z", re.ASCII)


def _exact_fields(value, expected):
    return type(value) is dict and all(type(key) is str for key in value) and set(value) == expected


def _token(value, field):
    if type(value) is not str:
        raise ContractValidationError(field, "invalid_identifier")
    return validate_identifier(value, field)


def _identity(value):
    if not _exact_fields(value, _IDENTITY_FIELDS):
        raise ValueError
    generation = value["generation"]
    if type(generation) is not int or not 0 <= generation <= _MAX_GENERATION:
        raise ValueError
    return {
        "bootId": _token(value["bootId"], "identity.bootId"),
        "generation": generation,
        "executionId": _token(value["executionId"], "identity.executionId"),
        "entryId": _token(value["entryId"], "identity.entryId"),
    }


def _receipt(value, operation, expected_identity):
    """Return a normalized receipt, or None for any malformed provider value."""
    try:
        value = _receipt_snapshot(value)
        if value is None or not _exact_fields(value, _RECEIPT_FIELDS):
            return None
        ident = _identity(value["identity"])
        if (type(value["provider"]) is not str or value["provider"] != "LOCAL"
                or type(value["operation"]) is not str or value["operation"] != operation
                or ident != expected_identity):
            return None
        if not _valid_receipt_values(value, operation):
            return None
        outcome = value["outcome"]
        epoch = value["epoch"]
        songid = value["songid"]
        return {"operation": operation, "outcome": outcome, "epoch": epoch,
                "songid": songid, "state": value["state"], "error": value["error"],
                "observed": value["observedAtMonotonic"],
                "positionMs": value["positionMs"], "durationMs": value["durationMs"]}
    except (ContractValidationError, TypeError, ValueError, KeyError):
        return None


def _receipt_snapshot(value):
    """Copy the closed receipt and nested maps before validating any fields."""
    if type(value) is not dict:
        return None
    try:
        snapshot = value.copy()
        if not _exact_fields(snapshot, _RECEIPT_FIELDS):
            return None
        identity = snapshot["identity"]
        error = snapshot["error"]
        if type(identity) is dict:
            snapshot["identity"] = identity.copy()
        if type(error) is dict:
            snapshot["error"] = error.copy()
        return snapshot
    except (RuntimeError, TypeError, ValueError):
        return None


def _valid_receipt_values(value, operation):
    outcome = value["outcome"]
    if type(outcome) is not str or outcome not in {"CONFIRMED", "REJECTED", "UNCONFIRMED"}:
        return False
    state = value["state"]
    if type(state) is not str or state not in {"PLAYING", "PAUSED", "STOPPED", "UNKNOWN"}:
        return False
    if not _valid_observation_values(value):
        return False
    error = value["error"]
    if outcome == "CONFIRMED":
        return error is None
    return _valid_provider_error(error, operation)


def _valid_observation_values(value):
    for field in ("epoch", "songid"):
        if value[field] is not None:
            _token(value[field], "receipt." + field)
    if value["songid"] is not None and _SONG_ID.fullmatch(value["songid"]) is None:
        return False
    for field in ("positionMs", "durationMs"):
        item = value[field]
        if item is not None and (type(item) is not int or not 0 <= item <= _MAX_GENERATION):
            return False
    observed = value["observedAtMonotonic"]
    if observed is not None:
        if type(observed) is int:
            if not 0 <= observed <= _MAX_GENERATION:
                return False
        elif type(observed) is float:
            if not math.isfinite(observed) or observed < 0:
                return False
        else:
            return False
    return True


def _valid_provider_error(error, operation):
    if not _exact_fields(error, _ERROR_FIELDS):
        return False
    if type(error["code"]) is not str or error["code"] not in _ERROR_CODES:
        return False
    message = error["message"]
    return (type(message) is str and 1 <= len(message) <= 1024 and bool(message.strip())
            and type(error["retryable"]) is bool and error["retryable"] is False
            and type(error["operation"]) is str and error["operation"] == operation)


class ExecutionGate:
    """Serializes one LOCAL provider invocation and its execution ownership."""

    def __init__(self, *, boot_id):
        boot_id = _token(boot_id, "bootId")
        self._lock = threading.Lock()
        self._boot_id = boot_id
        self._generation = 0
        self._owner = None
        self._permit = None
        self._operation = None
        self._cleanup_required = False
        self._error = None
        self._known_epoch = None
        self._last_execution = None

    def snapshot(self):
        with self._lock:
            return self._snapshot_locked()

    def _snapshot_locked(self):
        return {"bootId": self._boot_id, "generation": self._generation,
                "owner": dict(self._owner) if self._owner is not None else None,
                "inFlight": self._operation, "cleanupRequired": self._cleanup_required,
                "error": self._error,
                "lastExecution": (None if self._last_execution is None
                                  else dict(self._last_execution))}

    def reserve_start(self, entry_id):
        entry_id = _token(entry_id, "entryId")
        execution_id = uuid.uuid4().hex
        with self._lock:
            if self._owner is not None:
                raise GateStateError("OWNER_HELD")
            if self._permit is not None:
                raise GateStateError("BUSY")
            if self._generation >= _MAX_GENERATION:
                raise GateStateError("COUNTER_EXHAUSTED")
            self._generation += 1
            self._owner = {"bootId": self._boot_id, "generation": self._generation,
                           "executionId": execution_id, "entryId": entry_id}
            self._permit = object()
            self._operation = "START"
            self._cleanup_required = False
            self._known_epoch = None
            self._error = None
            return self._permit

    def invalidate(self):
        with self._lock:
            if self._generation >= _MAX_GENERATION:
                raise GateStateError("COUNTER_EXHAUSTED")
            self._generation += 1
            if self._owner is not None:
                self._cleanup_required = True
                self._error = "STALE_EXECUTION"
            return self._generation

    def reserve_stop(self):
        with self._lock:
            if self._owner is None:
                raise GateStateError("OWNER_REQUIRED")
            if self._permit is not None:
                raise GateStateError("BUSY")
            self._permit = object()
            self._operation = "STOP"
            return self._permit

    def lease(self, permit):
        with self._lock:
            if (permit is None or self._permit is not permit or self._owner is None
                    or self._operation not in {"START", "STOP"}):
                raise GateStateError("STALE_PERMIT")
            token, expected, op = self._permit, dict(self._owner), self._operation

        def guard(operation, identity):
            if type(operation) is not str or operation != op or operation not in {"START", "STOP"}:
                return False
            try:
                supplied = _identity(identity)
            except (ContractValidationError, TypeError, ValueError, KeyError):
                return False
            if supplied != expected:
                return False
            with self._lock:
                return (self._permit is token and self._operation == op
                        and self._owner == expected
                        and (op == "STOP" or expected["generation"] == self._generation))
        return {"identity": dict(expected), "guard": guard}

    def complete(self, permit, receipt_or_none):
        with self._lock:
            if (permit is None or self._permit is not permit or self._owner is None
                    or self._operation not in {"START", "STOP"}):
                return self._snapshot_locked()
            operation, expected = self._operation, dict(self._owner)
        normalized = _receipt(receipt_or_none, operation, expected)
        with self._lock:
            if self._permit is not permit or self._owner != expected:
                return self._snapshot_locked()
            self._last_execution = {**expected, "operation": operation}
            self._permit = None
            self._operation = None
            if operation == "START":
                if normalized is not None and normalized["epoch"] is not None:
                    self._known_epoch = normalized["epoch"]
                revoked = expected["generation"] != self._generation
                if normalized is None:
                    self._cleanup_required = True
                    self._error = ("STALE_EXECUTION" if revoked else
                                   "PROVIDER_UNCONFIRMED" if receipt_or_none is None else "INVALID_RECEIPT")
                elif normalized["outcome"] == "REJECTED":
                    self._owner = None
                    self._cleanup_required = False
                    self._known_epoch = None
                    self._error = None
                elif (normalized["outcome"] == "CONFIRMED" and normalized["state"] == "PLAYING"
                      and normalized["epoch"] is not None and normalized["songid"] is not None
                      and normalized["observed"] is not None and not revoked):
                    self._cleanup_required = False
                    self._error = None
                else:
                    self._cleanup_required = True
                    self._error = "STALE_EXECUTION" if revoked else "PROVIDER_UNCONFIRMED"
            else:
                valid_stop = (normalized is not None and normalized["outcome"] == "CONFIRMED"
                              and normalized["state"] == "STOPPED" and normalized["error"] is None
                              and normalized["epoch"] is not None and normalized["observed"] is not None
                              and (self._known_epoch is None or normalized["epoch"] == self._known_epoch))
                if valid_stop:
                    self._owner = None
                    self._cleanup_required = False
                    self._known_epoch = None
                    self._error = None
                else:
                    self._cleanup_required = True
                    self._error = "STOP_UNCONFIRMED"
            return self._snapshot_locked()

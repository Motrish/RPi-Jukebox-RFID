"""Synchronous, transport-free LOCAL playback provider against an injected session."""

import math
import re
from contextlib import contextmanager
from typing import Any, Dict

from jukebox.contracts import ContractValidationError, validate_identifier, validate_media_ref


_MAX_SAFE_INTEGER = 9007199254740991
_SONG_ID_RE = re.compile(r"[0-9]+\Z", re.ASCII)
_STATUS_FIELDS = {
    "state", "songid", "playlistlength", "repeat", "random", "single",
    "consume", "elapsed", "duration", "hasError",
}
_OPTION_FIELDS = {
    "canPause", "canResume", "canSeek", "canConfirmStop", "canIdentifyNaturalEnd",
}
_ERROR_MESSAGES = {
    "STALE_EXECUTION": "The execution lease is no longer current.",
    "EXECUTION_CONFLICT": "Another or unresolved local execution owns the provider.",
    "MEDIA_UNAVAILABLE": "The requested local media is unavailable.",
    "RESOLUTION_FAILED": "The local media reference could not be resolved safely.",
    "CAPABILITY_UNAVAILABLE": "The requested local playback capability is unavailable.",
    "PROVIDER_UNAVAILABLE": "The local playback provider is unavailable.",
    "PROVIDER_REJECTED": "The local playback command was rejected.",
    "PROVIDER_STATE_MISMATCH": "The local playback state did not match the requested execution.",
    "OPERATION_TIMEOUT": "The local playback operation exceeded its deadline.",
    "SESSION_CHANGED": "The local playback session changed during the operation.",
    "STOP_UNCONFIRMED": "The local playback stop could not be confirmed.",
}


class SessionFailure(Exception):
    """Safe normalized failure reported by a provider session fake or gateway."""

    CODES = {"TIMEOUT", "UNAVAILABLE", "COMMAND_REJECTED"}

    def __init__(self, code: str) -> None:
        if code not in self.CODES:
            raise ValueError("Unsupported session failure code.")
        self.code = code
        super().__init__(code)


class _ProviderFault(Exception):
    def __init__(self, code: str, *, effect: bool = False, invalidate: bool = False) -> None:
        self.code = code
        self.effect = effect
        self.invalidate = invalidate
        super().__init__(code)


class LocalProvider:
    """Execute one local track through an injected exclusive session."""

    def __init__(self, *, session: Any, resolver: Any, monotonic: Any,
                 capabilities: Dict[str, Any]) -> None:
        if not callable(getattr(session, "transaction", None)):
            _invalid("session", "invalid_session")
        if not callable(resolver):
            _invalid("resolver", "invalid_resolver")
        if not callable(monotonic):
            _invalid("monotonic", "invalid_clock")
        if not isinstance(capabilities, dict) or set(capabilities) != _OPTION_FIELDS:
            _invalid("capabilities", "invalid_fields")
        if any(type(value) is not bool for value in capabilities.values()):
            _invalid("capabilities", "invalid_boolean")
        if capabilities["canIdentifyNaturalEnd"]:
            _invalid("capabilities.canIdentifyNaturalEnd", "unsupported_capability")

        self.session = session
        self.resolver = resolver
        self.monotonic = monotonic
        self._capabilities = dict(capabilities)
        self._identity = None
        self._library_id = None
        self._epoch = None
        self._songid = None
        self._uncertain = False
        self._confirmed_stopped = False
        self._last_monotonic = None

    @property
    def capabilities(self):
        return dict(self._capabilities)

    def start(self, media_ref: Any, *, lease: Dict[str, Any], deadline: Any) -> dict:
        identity, guard, expiry = _request(lease, deadline)
        ref = validate_media_ref(media_ref)
        if ref["kind"] != "LOCAL":
            return self._failure("START", identity, _ProviderFault("CAPABILITY_UNAVAILABLE"))
        if not self._capabilities["canConfirmStop"]:
            return self._failure("START", identity, _ProviderFault("CAPABILITY_UNAVAILABLE"))

        try:
            self._check_guard_deadline(guard, identity, "START", expiry)
            if self._identity is not None:
                if not self._confirmed_stopped:
                    return self._repeat_start(identity, ref, guard, expiry)
                if identity == self._identity:
                    raise _ProviderFault("EXECUTION_CONFLICT")
            resolved = self._resolve(ref["libraryId"], guard, identity, expiry)
            return self._start_resolved(identity, ref["libraryId"], resolved, guard, expiry)
        except _ProviderFault as fault:
            return self._failure("START", identity, fault)
        except Exception:
            return self._failure(
                "START", identity,
                _ProviderFault("PROVIDER_UNAVAILABLE", effect=self._uncertain),
            )

    def pause(self, *, lease: Dict[str, Any], deadline: Any) -> dict:
        return self._change_state("PAUSE", lease, deadline, "play", "pause", "canPause", 1)

    def resume(self, *, lease: Dict[str, Any], deadline: Any) -> dict:
        return self._change_state("RESUME", lease, deadline, "pause", "play", "canResume", 0)

    def seek(self, position_ms: Any, *, lease: Dict[str, Any], deadline: Any) -> dict:
        identity, guard, expiry = _request(lease, deadline)
        position = _safe_integer(position_ms, "positionMs")
        if not self._capabilities["canSeek"]:
            return self._failure("SEEK", identity, _ProviderFault("CAPABILITY_UNAVAILABLE"))

        evidence = None
        epoch = None
        try:
            self._require_owned(identity, "SEEK")
            with self._session("SEEK", identity, guard, expiry, self._epoch) as (context, epoch):
                evidence = self._status(context, "SEEK", identity, guard, expiry, epoch)
                self._check_active_status(evidence, identity, "SEEK")
                duration_ms = _milliseconds(evidence["duration"])
                if duration_ms is not None and position > duration_ms:
                    raise _ProviderFault("PROVIDER_REJECTED")
                songid = self._songid
                previous_state = evidence["state"]
                self._invoke(
                    context, "seekid", (songid, position / 1000.0), "SEEK",
                    identity, guard, expiry, epoch, before_call=self._mark_uncertain,
                )
                evidence = self._status(context, "SEEK", identity, guard, expiry, epoch)
                if evidence["songid"] != songid or evidence["state"] != previous_state or evidence["hasError"]:
                    raise _ProviderFault("PROVIDER_STATE_MISMATCH", effect=True)
                self._confirmed(guard, identity, "SEEK", expiry, context, epoch)
                self._uncertain = False
                return _receipt("SEEK", identity, "CONFIRMED", epoch, evidence)
        except _ProviderFault as fault:
            return self._failure("SEEK", identity, fault, epoch, evidence)
        except Exception:
            return self._failure(
                "SEEK", identity, _ProviderFault("PROVIDER_UNAVAILABLE", effect=self._uncertain),
                epoch, evidence,
            )

    def stop(self, *, lease: Dict[str, Any], deadline: Any) -> dict:
        identity, guard, expiry = _request(lease, deadline)
        evidence = None
        epoch = None
        try:
            self._require_owned(identity, "STOP", allow_stopped=True)
            if not self._capabilities["canConfirmStop"]:
                raise _ProviderFault("CAPABILITY_UNAVAILABLE")
            with self._session("STOP", identity, guard, expiry, self._epoch) as (context, epoch):
                evidence = self._status(context, "STOP", identity, guard, expiry, epoch)
                if evidence["hasError"]:
                    raise _ProviderFault("STOP_UNCONFIRMED")
                if evidence["state"] != "stop":
                    if self._songid is None or evidence["songid"] != self._songid:
                        raise _ProviderFault("EXECUTION_CONFLICT")
                    self._invoke(
                        context, "stop", (), "STOP", identity, guard, expiry,
                        epoch, before_call=self._mark_uncertain,
                    )
                    evidence = self._status(context, "STOP", identity, guard, expiry, epoch)
                    if evidence["state"] != "stop" or evidence["hasError"]:
                        raise _ProviderFault("STOP_UNCONFIRMED", effect=True)
                self._confirmed(guard, identity, "STOP", expiry, context, epoch)
                self._uncertain = False
                self._confirmed_stopped = True
                return _receipt("STOP", identity, "CONFIRMED", epoch, evidence)
        except _ProviderFault as fault:
            return self._failure("STOP", identity, fault, epoch, evidence)
        except Exception:
            return self._failure(
                "STOP", identity, _ProviderFault("STOP_UNCONFIRMED", effect=self._uncertain),
                epoch, evidence,
            )

    def observe(self, *, lease: Dict[str, Any], deadline: Any) -> dict:
        identity, guard, expiry = _request(lease, deadline)
        evidence = None
        epoch = None
        try:
            self._require_owned(identity, "OBSERVE", allow_stopped=True)
            with self._session("OBSERVE", identity, guard, expiry, self._epoch) as (context, epoch):
                evidence = self._status(context, "OBSERVE", identity, guard, expiry, epoch)
                if evidence["hasError"]:
                    raise _ProviderFault("PROVIDER_STATE_MISMATCH")
                if evidence["state"] in {"play", "pause"}:
                    if self._songid is None or evidence["songid"] != self._songid:
                        raise _ProviderFault("PROVIDER_STATE_MISMATCH")
                self._confirmed(guard, identity, "OBSERVE", expiry, context, epoch)
                return _receipt("OBSERVE", identity, "CONFIRMED", epoch, evidence)
        except _ProviderFault as fault:
            return self._failure("OBSERVE", identity, fault, epoch, evidence)
        except Exception:
            return self._failure(
                "OBSERVE", identity, _ProviderFault("PROVIDER_UNAVAILABLE"),
                epoch, evidence,
            )

    def _change_state(self, operation, lease, deadline, source_state,
                      target_state, capability, pause_value):
        identity, guard, expiry = _request(lease, deadline)
        if not self._capabilities[capability]:
            return self._failure(operation, identity, _ProviderFault("CAPABILITY_UNAVAILABLE"))
        evidence = None
        epoch = None
        try:
            self._require_owned(identity, operation)
            with self._session(operation, identity, guard, expiry, self._epoch) as (context, epoch):
                evidence = self._status(context, operation, identity, guard, expiry, epoch)
                self._check_active_status(evidence, identity, operation, states={source_state, target_state})
                if evidence["state"] != target_state:
                    self._invoke(
                        context, "pause", (pause_value,), operation, identity,
                        guard, expiry, epoch, before_call=self._mark_uncertain,
                    )
                    evidence = self._status(context, operation, identity, guard, expiry, epoch)
                    if evidence["state"] != target_state or evidence["songid"] != self._songid or evidence["hasError"]:
                        raise _ProviderFault("PROVIDER_STATE_MISMATCH", effect=True)
                self._confirmed(guard, identity, operation, expiry, context, epoch)
                self._uncertain = False
                return _receipt(operation, identity, "CONFIRMED", epoch, evidence)
        except _ProviderFault as fault:
            return self._failure(operation, identity, fault, epoch, evidence)
        except Exception:
            return self._failure(
                operation, identity, _ProviderFault("PROVIDER_UNAVAILABLE", effect=self._uncertain),
                epoch, evidence,
            )

    def _repeat_start(self, identity, media_ref, guard, deadline):
        if identity != self._identity or media_ref["libraryId"] != self._library_id or self._confirmed_stopped:
            return self._failure("START", identity, _ProviderFault("EXECUTION_CONFLICT"))
        evidence = None
        epoch = None
        try:
            with self._session("START", identity, guard, deadline, self._epoch) as (context, epoch):
                evidence = self._status(context, "START", identity, guard, deadline, epoch)
                if not self._is_started(evidence, self._songid, allow_paused=True):
                    raise _ProviderFault("PROVIDER_STATE_MISMATCH", effect=self._uncertain)
                self._confirmed(guard, identity, "START", deadline, context, epoch)
                self._uncertain = False
                return _receipt("START", identity, "CONFIRMED", epoch, evidence)
        except _ProviderFault as fault:
            return self._failure("START", identity, fault, epoch, evidence)
        except Exception:
            return self._failure(
                "START", identity, _ProviderFault("PROVIDER_UNAVAILABLE", effect=self._uncertain),
                epoch, evidence,
            )

    def _resolve(self, library_id, guard, identity, deadline):
        self._check_guard_deadline(guard, identity, "START", deadline)
        try:
            resolved = self.resolver(library_id)
        except Exception as exc:
            if isinstance(exc, _ProviderFault):
                raise
            raise _ProviderFault("RESOLUTION_FAILED") from None
        self._check_guard_deadline(guard, identity, "START", deadline)
        if resolved is None:
            raise _ProviderFault("MEDIA_UNAVAILABLE")
        if not _safe_resolution(resolved, library_id):
            raise _ProviderFault("RESOLUTION_FAILED")
        return dict(resolved)

    def _start_resolved(self, identity, library_id, resolved, guard, deadline):
        previous = (
            self._identity, self._library_id, self._epoch, self._songid,
            self._uncertain, self._confirmed_stopped,
        )
        evidence = None
        epoch = None
        try:
            with self._session("START", identity, guard, deadline) as (context, epoch):
                evidence = self._status(context, "START", identity, guard, deadline, epoch)
                if evidence["state"] != "stop" or evidence["hasError"]:
                    raise _ProviderFault("EXECUTION_CONFLICT")

                def reserve_start():
                    if self._identity != identity:
                        self._identity = dict(identity)
                        self._library_id = library_id
                        self._epoch = epoch
                        self._songid = None
                        self._confirmed_stopped = False
                    self._uncertain = True

                for option, value in (
                    ("repeat", 0), ("random", 0), ("single", 1), ("consume", 0),
                ):
                    self._invoke(
                        context, option, (value,), "START", identity, guard,
                        deadline, epoch, before_call=reserve_start,
                    )
                self._invoke(
                    context, "clear", (), "START", identity, guard,
                    deadline, epoch, before_call=reserve_start,
                )
                songid = self._invoke(
                    context, "addid", (resolved["mpdReference"],), "START",
                    identity, guard, deadline, epoch, before_call=reserve_start,
                )
                try:
                    _validate_songid(songid)
                except ContractValidationError:
                    raise _ProviderFault("PROVIDER_STATE_MISMATCH", effect=True) from None
                self._songid = songid
                self._invoke(
                    context, "playid", (songid,), "START", identity, guard,
                    deadline, epoch, before_call=reserve_start,
                )
                evidence = self._status(context, "START", identity, guard, deadline, epoch)
                if not self._is_started(evidence, songid):
                    raise _ProviderFault("PROVIDER_STATE_MISMATCH", effect=True)
                self._confirmed(guard, identity, "START", deadline, context, epoch)
                self._uncertain = False
                return _receipt("START", identity, "CONFIRMED", epoch, evidence)
        except _ProviderFault as fault:
            self._restore_unmutated_start(fault, previous)
            return self._failure("START", identity, fault, epoch, evidence)
        except Exception:
            fault = _ProviderFault("PROVIDER_UNAVAILABLE", effect=self._uncertain)
            self._restore_unmutated_start(fault, previous)
            return self._failure("START", identity, fault, epoch, evidence)

    @contextmanager
    def _session(self, operation, identity, guard, deadline, expected_epoch=None):
        self._check_guard_deadline(guard, identity, operation, deadline)
        try:
            with self.session.transaction(deadline) as context:
                epoch = _epoch(context)
                self._check_guard_deadline(guard, identity, operation, deadline)
                if expected_epoch is not None and epoch != expected_epoch:
                    raise _epoch_fault(operation)
                yield context, epoch
        except _ProviderFault:
            raise
        except SessionFailure as failure:
            raise _session_fault(failure, operation, effect=False) from None
        except Exception:
            raise _ProviderFault("PROVIDER_UNAVAILABLE") from None

    def _status(self, context, operation, identity, guard, deadline, epoch):
        raw = self._invoke(
            context, "status", (), operation, identity, guard, deadline, epoch,
        )
        try:
            status = _normalise_status(raw)
            status["_observedAtMonotonic"] = self._read_clock()
            return status
        except ContractValidationError:
            raise _ProviderFault("PROVIDER_STATE_MISMATCH") from None

    def _invoke(self, context, method, args, operation, identity, guard,
                deadline, epoch, before_call=None):
        self._check_guard_deadline(guard, identity, operation, deadline)
        self._check_epoch(context, epoch, operation)
        try:
            callback = getattr(context, method)
        except Exception:
            raise _ProviderFault("PROVIDER_UNAVAILABLE") from None
        if not callable(callback):
            raise _ProviderFault("PROVIDER_UNAVAILABLE")
        self._check_deadline(operation, deadline)
        was_uncertain = self._uncertain
        if before_call is not None:
            before_call()
        try:
            result = callback(*args)
        except SessionFailure as failure:
            if failure.code == "COMMAND_REJECTED" and before_call is not None:
                self._uncertain = was_uncertain
            raise _session_fault(failure, operation, effect=before_call is not None) from None
        except Exception:
            raise _ProviderFault("PROVIDER_UNAVAILABLE", effect=before_call is not None) from None
        try:
            self._check_epoch(context, epoch, operation)
            self._check_deadline(operation, deadline)
        except _ProviderFault as fault:
            if before_call is not None:
                fault.effect = True
            raise
        return result

    def _check_guard_deadline(self, guard, identity, operation, deadline):
        self._check_deadline(operation, deadline)
        try:
            allowed = guard(operation, identity)
        except Exception:
            raise _ProviderFault("STALE_EXECUTION") from None
        if type(allowed) is not bool or not allowed:
            raise _ProviderFault("STALE_EXECUTION")
        self._check_deadline(operation, deadline)

    def _check_deadline(self, operation, deadline):
        try:
            now = self._read_clock()
        except _ProviderFault:
            raise _ProviderFault("STOP_UNCONFIRMED" if operation == "STOP" else "PROVIDER_UNAVAILABLE") from None
        if now >= deadline:
            raise _ProviderFault("STOP_UNCONFIRMED" if operation == "STOP" else "OPERATION_TIMEOUT")

    def _read_clock(self):
        try:
            value = self.monotonic()
        except Exception:
            raise _ProviderFault("PROVIDER_UNAVAILABLE") from None
        if not _finite_number(value):
            raise _ProviderFault("PROVIDER_UNAVAILABLE")
        current = float(value)
        if self._last_monotonic is not None and current < self._last_monotonic:
            raise _ProviderFault("PROVIDER_UNAVAILABLE")
        self._last_monotonic = current
        return current

    def _check_epoch(self, context, expected, operation):
        actual = _epoch(context)
        if actual != expected:
            raise _epoch_fault(operation)

    def _confirmed(self, guard, identity, operation, deadline, context, epoch):
        self._check_guard_deadline(guard, identity, operation, deadline)
        self._check_epoch(context, epoch, operation)
        self._check_deadline(operation, deadline)

    def _require_owned(self, identity, operation, allow_stopped=False):
        if self._identity is None or identity != self._identity:
            raise _ProviderFault("EXECUTION_CONFLICT")
        if self._confirmed_stopped and not allow_stopped:
            raise _ProviderFault("EXECUTION_CONFLICT")

    def _check_active_status(self, status, identity, operation, states=None):
        if self._songid is None or status["hasError"] or status["songid"] != self._songid:
            raise _ProviderFault("PROVIDER_STATE_MISMATCH")
        allowed = states or {"play", "pause"}
        if status["state"] not in allowed:
            raise _ProviderFault("PROVIDER_STATE_MISMATCH")

    def _is_started(self, status, songid, *, allow_paused=False):
        return (
            songid is not None
            and status["state"] in ({"play", "pause"} if allow_paused else {"play"})
            and status["songid"] == songid
            and status["playlistlength"] == 1
            and status["repeat"] == 0
            and status["random"] == 0
            and status["single"] == 1
            and status["consume"] == 0
            and not status["hasError"]
        )

    def _mark_uncertain(self):
        self._uncertain = True

    def _restore_unmutated_start(self, fault, previous):
        if not fault.effect and not self._uncertain:
            (
                self._identity, self._library_id, self._epoch, self._songid,
                self._uncertain, self._confirmed_stopped,
            ) = previous

    def _failure(self, operation, identity, fault, epoch=None, evidence=None):
        code = fault.code
        stop_failures = {
            "OPERATION_TIMEOUT", "SESSION_CHANGED", "PROVIDER_UNAVAILABLE", "PROVIDER_REJECTED",
        }
        if operation == "STOP" and code in stop_failures:
            code = "STOP_UNCONFIRMED"
        reserved_effect = self._uncertain and identity == self._identity
        outcome = "UNCONFIRMED" if fault.effect or reserved_effect or code == "STOP_UNCONFIRMED" else "REJECTED"
        if fault.invalidate:
            epoch = None
            evidence = None
        return _receipt(operation, identity, outcome, epoch, evidence, code)


def _request(lease, deadline):
    if not _finite_number(deadline):
        _invalid("deadline", "invalid_deadline")
    if not isinstance(lease, dict) or set(lease) != {"identity", "guard"}:
        _invalid("lease", "invalid_lease")
    identity = _validate_identity(lease["identity"])
    guard = lease["guard"]
    if not callable(guard):
        _invalid("lease.guard", "invalid_guard")
    try:
        expiry = float(deadline)
    except (OverflowError, ValueError):
        _invalid("deadline", "invalid_deadline")
    return identity, guard, expiry


def _validate_identity(value):
    if not isinstance(value, dict) or set(value) != {"bootId", "generation", "executionId", "entryId"}:
        _invalid("identity", "invalid_fields")
    try:
        identity = {
            "bootId": validate_identifier(value["bootId"], "identity.bootId"),
            "generation": _safe_integer(value["generation"], "identity.generation"),
            "executionId": validate_identifier(value["executionId"], "identity.executionId"),
            "entryId": validate_identifier(value["entryId"], "identity.entryId"),
        }
    except ContractValidationError:
        raise
    return identity


def _safe_resolution(value, library_id):
    if not isinstance(value, dict) or set(value) != {"libraryId", "mpdReference"}:
        return False
    if value["libraryId"] != library_id:
        return False
    reference = value["mpdReference"]
    if not isinstance(reference, str) or not reference or any(char in reference for char in "\x00\r\n\\"):
        return False
    if reference.startswith("/") or re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", reference):
        return False
    if any(part in {".", ".."} for part in reference.split("/")):
        return False
    return True


def _normalise_status(value):
    if not isinstance(value, dict) or set(value) != _STATUS_FIELDS:
        _invalid("status", "invalid_fields")
    _validate_status_state(value)
    _validate_status_options(value)
    _validate_status_times(value)
    return dict(value)


def _validate_status_state(value):
    if not isinstance(value["state"], str) or value["state"] not in {"play", "pause", "stop"}:
        _invalid("status.state", "invalid_state")
    songid = value["songid"]
    if songid is not None:
        _validate_songid(songid)
    if type(value["hasError"]) is not bool:
        _invalid("status.hasError", "invalid_boolean")


def _validate_status_options(value):
    for name in ("playlistlength", "repeat", "random"):
        if type(value[name]) is not int or value[name] < 0:
            _invalid(f"status.{name}", "invalid_integer")
    for name in ("repeat", "random"):
        if type(value[name]) is not int or value[name] not in {0, 1}:
            _invalid(f"status.{name}", "invalid_option")
    for name in ("single", "consume"):
        if type(value[name]) is int:
            allowed = value[name] in {0, 1}
        else:
            allowed = type(value[name]) is str and value[name] == "oneshot"
        if not allowed:
            _invalid(f"status.{name}", "invalid_option")


def _validate_status_times(value):
    for name in ("elapsed", "duration"):
        if value[name] is not None and (not _finite_number(value[name]) or value[name] < 0):
            _invalid(f"status.{name}", "invalid_time")
        if value[name] is not None and value[name] * 1000 > _MAX_SAFE_INTEGER:
            _invalid(f"status.{name}", "time_out_of_range")


def _validate_songid(value):
    if not isinstance(value, str) or _SONG_ID_RE.fullmatch(value) is None:
        _invalid("songid", "invalid_songid")


def _epoch(context):
    try:
        value = context.epoch
        return validate_identifier(value, "session.epoch")
    except Exception:
        raise _ProviderFault("PROVIDER_STATE_MISMATCH") from None


def _session_fault(failure, operation, effect):
    if failure.code == "COMMAND_REJECTED":
        return _ProviderFault("STOP_UNCONFIRMED" if operation == "STOP" else "PROVIDER_REJECTED",
                              effect=False)
    if failure.code == "TIMEOUT":
        return _ProviderFault("STOP_UNCONFIRMED" if operation == "STOP" else "OPERATION_TIMEOUT",
                              effect=effect)
    return _ProviderFault("STOP_UNCONFIRMED" if operation == "STOP" else "PROVIDER_UNAVAILABLE",
                          effect=effect)


def _epoch_fault(operation):
    return _ProviderFault("STOP_UNCONFIRMED" if operation == "STOP" else "SESSION_CHANGED",
                          effect=True, invalidate=True)


def _receipt(operation, identity, outcome, epoch, status, error_code=None):
    if error_code is not None:
        error_operation = operation
        error = {
            "code": error_code,
            "message": _ERROR_MESSAGES.get(error_code, "The local playback operation failed."),
            "retryable": False,
            "operation": error_operation,
        }
        provider_state = _state_name(status["state"]) if status is not None else "UNKNOWN"
        songid = status["songid"] if status is not None else None
        position = _milliseconds(status["elapsed"]) if status is not None else None
        duration = _milliseconds(status["duration"]) if status is not None else None
        observed_at = status.get("_observedAtMonotonic") if status is not None else None
    else:
        error = None
        provider_state = _state_name(status["state"]) if status is not None else "UNKNOWN"
        songid = status["songid"] if status is not None else None
        position = _milliseconds(status["elapsed"]) if status is not None else None
        duration = _milliseconds(status["duration"]) if status is not None else None
        observed_at = status.get("_observedAtMonotonic") if status is not None else None
    receipt_epoch = epoch
    if error_code in {"SESSION_CHANGED", "STOP_UNCONFIRMED"}:
        receipt_epoch = None
        provider_state = "UNKNOWN"
        songid = None
        position = None
        duration = None
        observed_at = None
    return {
        "provider": "LOCAL",
        "operation": operation,
        "identity": dict(identity),
        "outcome": outcome,
        "epoch": receipt_epoch,
        "songid": songid,
        "state": provider_state,
        "positionMs": position,
        "durationMs": duration,
        "observedAtMonotonic": observed_at,
        "error": error,
    }


def _state_name(state):
    return {"play": "PLAYING", "pause": "PAUSED", "stop": "STOPPED"}.get(state, "UNKNOWN")


def _milliseconds(seconds):
    if seconds is None:
        return None
    milliseconds = math.floor(seconds * 1000)
    if milliseconds < 0 or milliseconds > _MAX_SAFE_INTEGER:
        raise _ProviderFault("PROVIDER_STATE_MISMATCH")
    return milliseconds


def _safe_integer(value, field):
    if type(value) is not int or value < 0 or value > _MAX_SAFE_INTEGER:
        _invalid(field, "invalid_integer")
    return value


def _finite_number(value):
    if type(value) not in {int, float}:
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _invalid(field, reason):
    raise ContractValidationError(field, reason)

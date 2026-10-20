"""Transport-free playback admission contracts, version 1."""

import re
from datetime import date
from typing import Any, Mapping

from .v1 import (ContractValidationError, validate_error, validate_identifier,
                 validate_queue_entry)

_MAX = 9007199254740991
_ACTIONS = {"PLAYBACK_START", "PLAYBACK_STOP"}
_OLD_ERRORS = {"VALIDATION_ERROR", "UNSUPPORTED_VERSION", "NOT_FOUND",
               "REVISION_CONFLICT", "COMMAND_ID_REUSED", "LIMIT_EXCEEDED",
               "REVISION_EXHAUSTED", "STORE_BUSY", "STORE_UNAVAILABLE",
               "INTERNAL_ERROR"}
_STAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z\Z", re.ASCII)

__all__ = (
    "validate_playback_command",
    "validate_playback_command_result",
    "validate_playback_admission_error",
)


def validate_playback_command(value: Any) -> dict:
    obj = _object(value, "command")
    action = _required(obj, "action", "command")
    if not isinstance(action, str) or action not in _ACTIONS:
        _fail("command.action", "unknown_action")
    names = {"contractVersion", "commandId", "action"}
    if action == "PLAYBACK_START":
        names |= {"queueId", "expectedQueueRevision", "entryId"}
    _fields(obj, names, "command")
    version = _version(obj)
    result = {"contractVersion": version,
              "commandId": validate_identifier(_required(obj, "commandId", "command"), "command.commandId"),
              "action": action}
    if action == "PLAYBACK_START":
        result.update(queueId=validate_identifier(obj["queueId"], "command.queueId"),
                      expectedQueueRevision=_integer(obj["expectedQueueRevision"], "command.expectedQueueRevision"),
                      entryId=validate_identifier(obj["entryId"], "command.entryId"))
    return result


def validate_playback_admission_error(value: Any) -> dict:
    obj = _object(value, "error")
    code = _required(obj, "code", "error")
    if not isinstance(code, str):
        _fail("error.code", "unknown_error_code")
    if code in _OLD_ERRORS:
        return validate_error(obj)
    if code != "CAPABILITY_UNAVAILABLE":
        _fail("error.code", "unknown_error_code")
    _fields(obj, {"code", "message", "retryable", "operation", "details"}, "error")
    message = _text(_required(obj, "message", "error"), "error.message", 1024)
    if _required(obj, "retryable", "error") is not False:
        _fail("error.retryable", "retryability_mismatch")
    operation = validate_identifier(_required(obj, "operation", "error"), "error.operation")
    details = _object(_required(obj, "details", "error"), "error.details")
    _fields(details, {"capability"}, "error.details")
    capability = _required(details, "capability", "error.details")
    if capability != "SPOTIFY_PLAYBACK":
        _fail("error.details.capability", "invalid_capability")
    return {"code": code, "message": message, "retryable": False, "operation": operation,
            "details": {"capability": capability}}


def validate_playback_command_result(value: Any) -> dict:
    obj = _object(value, "commandResult")
    action = _required(obj, "action", "commandResult")
    if not isinstance(action, str) or action not in _ACTIONS:
        _fail("commandResult.action", "unknown_action")
    status = _required(obj, "status", "commandResult")
    if not isinstance(status, str) or status not in {"ACCEPTED", "REJECTED"}:
        _fail("commandResult.status", "invalid_status")
    body_key = "result" if status == "ACCEPTED" else "error"
    _fields(obj, {"contractVersion", "commandId", "action", "status", body_key}, "commandResult")
    version = _version(obj)
    cid = validate_identifier(obj["commandId"], "commandResult.commandId")
    if status == "REJECTED":
        body = validate_playback_admission_error(obj["error"])
        if body["operation"] not in {"PLAYBACK_ADMIT", "CONTRACT_VALIDATION"}:
            _fail("commandResult.error.operation", "invalid_operation")
        return {"contractVersion": version, "commandId": cid, "action": action,
                "status": status, "error": body}
    result = _object(obj["result"], "commandResult.result")
    _fields(result, {"intentId", "intentSequence", "acceptedAt", "selection"}, "commandResult.result")
    intent_id = validate_identifier(result["intentId"], "result.intentId")
    sequence = _integer(result["intentSequence"], "result.intentSequence")
    if sequence == 0:
        _fail("result.intentSequence", "invalid_integer")
    stamp = _timestamp(result["acceptedAt"])
    selection = result["selection"]
    if action == "PLAYBACK_STOP":
        if selection is not None:
            _fail("result.selection", "must_be_null")
        parsed_selection = None
    else:
        parsed_selection = _object(selection, "result.selection")
        _fields(parsed_selection, {"queueId", "queueRevision", "entry"}, "result.selection")
        queue_id = validate_identifier(parsed_selection["queueId"], "selection.queueId")
        revision = _integer(parsed_selection["queueRevision"], "selection.queueRevision")
        entry = validate_queue_entry(parsed_selection["entry"], field="selection.entry")
        if entry["mediaRef"]["kind"] != "LOCAL":
            _fail("selection.entry.mediaRef.kind", "local_media_required")
        parsed_selection = {"queueId": queue_id, "queueRevision": revision, "entry": entry}
    body = {"intentId": intent_id, "intentSequence": sequence, "acceptedAt": stamp,
            "selection": parsed_selection}
    return {"contractVersion": version, "commandId": cid, "action": action,
            "status": status, "result": body}


def _timestamp(value: Any) -> str:
    if not isinstance(value, str) or _STAMP.fullmatch(value) is None:
        _fail("result.acceptedAt", "invalid_timestamp")
    try:
        year, month, day = (int(value[0:4]), int(value[5:7]), int(value[8:10]))
        if year == 0:
            raise ValueError
        date(year, month, day)
        hour, minute, second = int(value[11:13]), int(value[14:16]), int(value[17:19])
        if hour > 23 or minute > 59 or second > 59:
            raise ValueError
    except ValueError:
        _fail("result.acceptedAt", "invalid_timestamp")
    return value


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        _fail(field, "invalid_type")
    if any(not isinstance(key, str) for key in value):
        _fail(field, "invalid_field_name")
    return value


def _fields(obj: Mapping[str, Any], expected: set, field: str) -> None:
    if set(obj) - expected:
        _fail(field, "unknown_field")
    missing = expected - set(obj)
    if missing:
        _fail(f"{field}.{sorted(missing)[0]}", "missing_field")


def _required(obj: Mapping[str, Any], key: str, field: str) -> Any:
    if key not in obj:
        _fail(f"{field}.{key}", "missing_field")
    return obj[key]


def _version(obj: Mapping[str, Any]) -> int:
    value = _required(obj, "contractVersion", "document")
    if type(value) is not int:
        _fail("document.contractVersion", "invalid_version_type")
    if value != 1:
        _fail("document.contractVersion", "unsupported_version", "UNSUPPORTED_VERSION")
    return value


def _integer(value: Any, field: str) -> int:
    if type(value) is not int or value < 0 or value > _MAX:
        _fail(field, "invalid_integer")
    return value


def _text(value: Any, field: str, limit: int) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= limit or not value.strip():
        _fail(field, "invalid_text" if field.endswith("details") else "invalid_message")
    return value


def _fail(field: str, reason: str, code: str = "VALIDATION_ERROR") -> None:
    raise ContractValidationError(field, reason, code)

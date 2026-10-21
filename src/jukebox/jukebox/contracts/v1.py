"""Transport-free V1 playlist and queue contracts using JSON-shaped values."""

import re
from typing import Any, Mapping, Optional


_MAX_REVISION = 9007199254740991
_MAX_ENTRIES = 10000
_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{1,128}\Z", re.ASCII)
_SPOTIFY_TRACK_RE = re.compile(r"spotify:track:[A-Za-z0-9]{22}\Z", re.ASCII)


class ContractValidationError(ValueError):
    """A stable, safe contract rejection without echoing untrusted values."""

    def __init__(self, field: str, reason: str, code: str = "VALIDATION_ERROR",
                 supported_versions: Optional[list] = None, details: Optional[dict] = None) -> None:
        self.code = code
        self.field = field
        self.reason = reason
        if details is None:
            details = {"supportedVersions": supported_versions or [1]} if code == "UNSUPPORTED_VERSION" else {
                "field": field, "reason": reason
            }
        self.error = {
            "code": code,
            "message": "The supplied contract value is invalid.",
            "retryable": False,
            "operation": "CONTRACT_VALIDATION",
            "details": details,
        }
        super().__init__(f"{code}: {field} ({reason})")


_COMMAND_FIELDS = {
    "PLAYLIST_CREATE": ("name", "items"),
    "PLAYLIST_RENAME": ("playlistId", "expectedRevision", "name"),
    "PLAYLIST_APPEND": ("playlistId", "expectedRevision", "items"),
    "PLAYLIST_REMOVE": ("playlistId", "expectedRevision", "entryId"),
    "PLAYLIST_MOVE": ("playlistId", "expectedRevision", "entryId", "toPosition"),
    "PLAYLIST_DELETE": ("playlistId", "expectedRevision"),
    "QUEUE_CREATE": ("items",),
    "QUEUE_LOAD_PLAYLIST": ("queueId", "expectedQueueRevision", "playlistId", "expectedPlaylistRevision"),
    "QUEUE_APPEND": ("queueId", "expectedRevision", "items"),
    "QUEUE_REMOVE": ("queueId", "expectedRevision", "entryId"),
    "QUEUE_MOVE": ("queueId", "expectedRevision", "entryId", "toPosition"),
    "QUEUE_SET_MODES": ("queueId", "expectedRevision", "repeatMode", "shuffleMode"),
    "QUEUE_SET_CURRENT": ("queueId", "expectedRevision", "entryId"),
    "QUEUE_SAVE_NEW_PLAYLIST": ("queueId", "expectedQueueRevision", "name"),
    "QUEUE_SAVE_PLAYLIST": ("queueId", "expectedQueueRevision", "playlistId", "expectedPlaylistRevision"),
}

_RESULT_KIND = {
    "PLAYLIST_CREATE": "playlist", "PLAYLIST_RENAME": "playlist",
    "PLAYLIST_APPEND": "playlist", "PLAYLIST_REMOVE": "playlist",
    "PLAYLIST_MOVE": "playlist", "QUEUE_SAVE_NEW_PLAYLIST": "playlist",
    "QUEUE_SAVE_PLAYLIST": "playlist", "QUEUE_CREATE": "queue",
    "QUEUE_LOAD_PLAYLIST": "queue", "QUEUE_APPEND": "queue",
    "QUEUE_REMOVE": "queue", "QUEUE_MOVE": "queue",
    "QUEUE_SET_MODES": "queue", "QUEUE_SET_CURRENT": "queue",
}

_ERROR_RETRYABLE = {
    "VALIDATION_ERROR": False,
    "UNSUPPORTED_VERSION": False,
    "NOT_FOUND": False,
    "COMMAND_NOT_FOUND": False,
    "REVISION_CONFLICT": False,
    "COMMAND_ID_REUSED": False,
    "POSITION_OUT_OF_RANGE": False,
    "LIMIT_EXCEEDED": False,
    "ACTIVE_ENTRY_REQUIRES_CONTROLLER": False,
    "REVISION_EXHAUSTED": False,
    "STORE_BUSY": True,
    "STORE_UNAVAILABLE": True,
    "INTERNAL_ERROR": False,
}
_ERROR_DETAIL_FIELDS = {
    "VALIDATION_ERROR": {"field", "reason"},
    "UNSUPPORTED_VERSION": {"supportedVersions"},
    "NOT_FOUND": {"objectType", "objectId"},
    "COMMAND_NOT_FOUND": {"commandId"},
    "REVISION_CONFLICT": {"conflicts"},
    "COMMAND_ID_REUSED": {"commandId"},
    "POSITION_OUT_OF_RANGE": {"entryId", "minimum", "maximum"},
    "LIMIT_EXCEEDED": {"field", "limit"},
    "ACTIVE_ENTRY_REQUIRES_CONTROLLER": {"queueId", "currentEntryId"},
    "REVISION_EXHAUSTED": {"objectType", "objectId"},
    "STORE_BUSY": {"operation"},
    "STORE_UNAVAILABLE": {"operation"},
    "INTERNAL_ERROR": {"diagnosticId"},
}


def validate_media_ref(value: Any, field: str = "mediaRef") -> dict:
    """Validate a LOCAL or canonical Spotify track reference and return a copy."""
    obj = _object(value, field)
    kind = _required(obj, "kind", field)
    if not isinstance(kind, str):
        _fail(f"{field}.kind", "invalid_type")
    if kind == "LOCAL":
        _fields(obj, {"kind", "libraryId"}, field)
        return {"kind": "LOCAL", "libraryId": _token(_required(obj, "libraryId", field), f"{field}.libraryId")}
    if kind == "SPOTIFY":
        _fields(obj, {"kind", "uri"}, field)
        uri = _required(obj, "uri", field)
        if not isinstance(uri, str) or _SPOTIFY_TRACK_RE.fullmatch(uri) is None:
            _fail(f"{field}.uri", "invalid_spotify_track_uri")
        return {"kind": "SPOTIFY", "uri": uri}
    _fail(f"{field}.kind", "unknown_source_kind")


def validate_identifier(value: Any, field: str = "identifier") -> str:
    """Validate and return an opaque V1 ASCII identifier token."""
    return _token(value, field)


def validate_playlist_entry(value: Any, expected_position: Optional[int] = None,
                            field: str = "entry") -> dict:
    obj = _object(value, field)
    _fields(obj, {"entryId", "mediaRef", "title", "position"}, field)
    entry_id = _token(_required(obj, "entryId", field), f"{field}.entryId")
    media_ref = validate_media_ref(_required(obj, "mediaRef", field), f"{field}.mediaRef")
    title = _title(_required(obj, "title", field), f"{field}.title")
    position = _integer(_required(obj, "position", field), f"{field}.position")
    if expected_position is not None and position != expected_position:
        _fail(f"{field}.position", "position_mismatch")
    return {"entryId": entry_id, "mediaRef": media_ref, "title": title, "position": position}


def validate_queue_entry(value: Any, expected_position: Optional[int] = None,
                         field: str = "entry") -> dict:
    obj = _object(value, field)
    _fields(obj, {"entryId", "sourceEntryId", "mediaRef", "title", "position"}, field)
    entry_id = _token(_required(obj, "entryId", field), f"{field}.entryId")
    source_entry_id = _required(obj, "sourceEntryId", field)
    if source_entry_id is not None:
        source_entry_id = _token(source_entry_id, f"{field}.sourceEntryId")
    media_ref = validate_media_ref(_required(obj, "mediaRef", field), f"{field}.mediaRef")
    title = _title(_required(obj, "title", field), f"{field}.title")
    position = _integer(_required(obj, "position", field), f"{field}.position")
    if expected_position is not None and position != expected_position:
        _fail(f"{field}.position", "position_mismatch")
    return {
        "entryId": entry_id, "sourceEntryId": source_entry_id,
        "mediaRef": media_ref, "title": title, "position": position,
    }


def validate_playlist_snapshot(value: Any) -> dict:
    obj = _object(value, "playlist")
    _fields(obj, {"contractVersion", "playlistId", "name", "revision", "entries"}, "playlist")
    version = _version(obj)
    playlist_id = _token(_required(obj, "playlistId", "playlist"), "playlist.playlistId")
    name = _name(_required(obj, "name", "playlist"), "playlist.name")
    revision = _revision(_required(obj, "revision", "playlist"), "playlist.revision")
    entries = _entry_list(_required(obj, "entries", "playlist"), queue=False, field="playlist.entries")
    return {"contractVersion": version, "playlistId": playlist_id, "name": name,
            "revision": revision, "entries": entries}


def validate_queue_snapshot(value: Any) -> dict:
    obj = _object(value, "queue")
    _fields(obj, {
        "contractVersion", "queueId", "revision", "sourcePlaylistId",
        "sourcePlaylistRevision", "entries", "currentEntryId", "repeatMode", "shuffleMode",
    }, "queue")
    version = _version(obj)
    queue_id = _token(_required(obj, "queueId", "queue"), "queue.queueId")
    revision = _revision(_required(obj, "revision", "queue"), "queue.revision")
    source_id = _required(obj, "sourcePlaylistId", "queue")
    source_revision = _required(obj, "sourcePlaylistRevision", "queue")
    if source_id is None and source_revision is None:
        pass
    elif source_id is None or source_revision is None:
        _fail("queue.sourcePlaylistId", "source_fields_must_be_paired")
    else:
        source_id = _token(source_id, "queue.sourcePlaylistId")
        source_revision = _revision(source_revision, "queue.sourcePlaylistRevision")
    entries = _entry_list(_required(obj, "entries", "queue"), queue=True, field="queue.entries")
    current_id = _required(obj, "currentEntryId", "queue")
    if current_id is not None:
        current_id = _token(current_id, "queue.currentEntryId")
        if current_id not in {entry["entryId"] for entry in entries}:
            _fail("queue.currentEntryId", "selection_not_found")
    repeat = _enum(_required(obj, "repeatMode", "queue"), "queue.repeatMode", {"OFF", "ALL", "ONE"})
    shuffle = _enum(_required(obj, "shuffleMode", "queue"), "queue.shuffleMode", {"OFF", "ON"})
    return {
        "contractVersion": version, "queueId": queue_id, "revision": revision,
        "sourcePlaylistId": source_id, "sourcePlaylistRevision": source_revision,
        "entries": entries, "currentEntryId": current_id,
        "repeatMode": repeat, "shuffleMode": shuffle,
    }


def validate_command(value: Any) -> dict:
    """Validate one of the closed V1 playlist/queue write command frames."""
    obj = _object(value, "command")
    action = _required(obj, "action", "command")
    if not isinstance(action, str) or action not in _COMMAND_FIELDS:
        _fail("command.action", "unknown_action")
    fields = set(_COMMAND_FIELDS[action])
    _fields(obj, {"contractVersion", "commandId", "action"} | fields, "command")
    version = _version(obj)
    command_id = _token(_required(obj, "commandId", "command"), "command.commandId")
    result = {"contractVersion": version, "commandId": command_id, "action": action}
    for name in _COMMAND_FIELDS[action]:
        raw = _required(obj, name, "command")
        field = f"command.{name}"
        if name in {"playlistId", "queueId", "entryId"}:
            if name == "entryId" and action == "QUEUE_SET_CURRENT" and raw is None:
                result[name] = None
            else:
                result[name] = _token(raw, field)
        elif name in {"expectedRevision", "expectedQueueRevision", "expectedPlaylistRevision"}:
            result[name] = _revision(raw, field)
        elif name == "toPosition":
            result[name] = _integer(raw, field)
        elif name == "name":
            result[name] = _name(raw, field)
        elif name == "items":
            result[name] = _command_items(raw, field)
        elif name == "repeatMode":
            result[name] = _enum(raw, field, {"OFF", "ALL", "ONE"})
        elif name == "shuffleMode":
            result[name] = _enum(raw, field, {"OFF", "ON"})
    return result


def validate_error(value: Any) -> dict:
    """Validate a versionless V1 Error object with code-specific closed details."""
    obj = _object(value, "error")
    code = _required(obj, "code", "error")
    if not isinstance(code, str) or code not in _ERROR_DETAIL_FIELDS:
        _fail("error.code", "unknown_error_code")
    _fields(obj, {"code", "message", "retryable", "operation", "details"}, "error")
    message = _message(_required(obj, "message", "error"), "error.message")
    retryable = _required(obj, "retryable", "error")
    if type(retryable) is not bool or retryable is not _ERROR_RETRYABLE[code]:
        _fail("error.retryable", "retryability_mismatch")
    operation = _token(_required(obj, "operation", "error"), "error.operation")
    details = _error_details(code, _required(obj, "details", "error"))
    return {"code": code, "message": message, "retryable": retryable,
            "operation": operation, "details": details}


def validate_command_result(value: Any) -> dict:
    """Validate the exact V1 result arm associated with a write action."""
    obj = _object(value, "commandResult")
    action = _required(obj, "action", "commandResult")
    if not isinstance(action, str) or action not in _COMMAND_FIELDS:
        _fail("commandResult.action", "unknown_action")
    status = _required(obj, "status", "commandResult")
    if not isinstance(status, str) or status not in {"APPLIED", "REJECTED"}:
        _fail("commandResult.status", "invalid_status")
    arm = "result" if status == "APPLIED" else "error"
    _fields(obj, {"contractVersion", "commandId", "action", "status", arm}, "commandResult")
    version = _version(obj)
    command_id = _token(_required(obj, "commandId", "commandResult"), "commandResult.commandId")
    if arm == "error":
        body = validate_error(_required(obj, "error", "commandResult"))
    else:
        body = _command_result_body(action, _required(obj, "result", "commandResult"))
    return {"contractVersion": version, "commandId": command_id,
            "action": action, "status": status, arm: body}


def _command_result_body(action: str, value: Any) -> dict:
    obj = _object(value, "commandResult.result")
    if action == "PLAYLIST_DELETE":
        _fields(obj, {"deletedPlaylistId", "deletedRevision"}, "commandResult.result")
        return {
            "deletedPlaylistId": _token(_required(obj, "deletedPlaylistId", "result"), "result.deletedPlaylistId"),
            "deletedRevision": _revision(_required(obj, "deletedRevision", "result"), "result.deletedRevision"),
        }
    kind = _RESULT_KIND[action]
    _fields(obj, {kind}, "commandResult.result")
    snapshot = _required(obj, kind, "commandResult.result")
    return {kind: validate_playlist_snapshot(snapshot) if kind == "playlist" else validate_queue_snapshot(snapshot)}


def _error_details(code: str, value: Any) -> dict:
    obj = _object(value, "error.details")
    _fields(obj, _ERROR_DETAIL_FIELDS[code], "error.details")
    validators = {
        "VALIDATION_ERROR": _details_validation,
        "UNSUPPORTED_VERSION": _details_versions,
        "NOT_FOUND": _details_object,
        "REVISION_EXHAUSTED": _details_object,
        "COMMAND_NOT_FOUND": _details_command_id,
        "COMMAND_ID_REUSED": _details_command_id,
        "REVISION_CONFLICT": _details_conflicts,
        "POSITION_OUT_OF_RANGE": _details_position,
        "LIMIT_EXCEEDED": _details_limit,
        "ACTIVE_ENTRY_REQUIRES_CONTROLLER": _details_active_entry,
        "STORE_BUSY": _details_operation,
        "STORE_UNAVAILABLE": _details_operation,
        "INTERNAL_ERROR": _details_diagnostic,
    }
    return validators[code](obj)


def _details_validation(obj: Mapping[str, Any]) -> dict:
    return {"field": _safe_text(_required(obj, "field", "details"), "details.field"),
            "reason": _token(_required(obj, "reason", "details"), "details.reason")}


def _details_versions(obj: Mapping[str, Any]) -> dict:
    versions = _required(obj, "supportedVersions", "details")
    if not isinstance(versions, list) or not versions or any(type(v) is not int or v < 1 for v in versions):
        _fail("details.supportedVersions", "invalid_versions")
    return {"supportedVersions": list(versions)}


def _details_object(obj: Mapping[str, Any]) -> dict:
    return {"objectType": _token(_required(obj, "objectType", "details"), "details.objectType"),
            "objectId": _token(_required(obj, "objectId", "details"), "details.objectId")}


def _details_command_id(obj: Mapping[str, Any]) -> dict:
    return {"commandId": _token(_required(obj, "commandId", "details"), "details.commandId")}


def _details_conflicts(obj: Mapping[str, Any]) -> dict:
    conflicts = _required(obj, "conflicts", "details")
    if not isinstance(conflicts, list) or not conflicts:
        _fail("details.conflicts", "invalid_conflicts")
    copied = []
    for index, conflict in enumerate(conflicts):
        field = f"details.conflicts[{index}]"
        item = _object(conflict, field)
        _fields(item, {"objectType", "objectId", "expectedRevision", "actualRevision"}, field)
        copied.append({
            "objectType": _token(_required(item, "objectType", field), f"{field}.objectType"),
            "objectId": _token(_required(item, "objectId", field), f"{field}.objectId"),
            "expectedRevision": _revision(_required(item, "expectedRevision", field), f"{field}.expectedRevision"),
            "actualRevision": _revision(_required(item, "actualRevision", field), f"{field}.actualRevision"),
        })
    return {"conflicts": copied}


def _details_position(obj: Mapping[str, Any]) -> dict:
    minimum = _integer(_required(obj, "minimum", "details"), "details.minimum")
    maximum = _integer(_required(obj, "maximum", "details"), "details.maximum")
    if minimum > maximum:
        _fail("details.minimum", "invalid_range")
    return {"entryId": _token(_required(obj, "entryId", "details"), "details.entryId"),
            "minimum": minimum, "maximum": maximum}


def _details_limit(obj: Mapping[str, Any]) -> dict:
    return {"field": _safe_text(_required(obj, "field", "details"), "details.field"),
            "limit": _integer(_required(obj, "limit", "details"), "details.limit")}


def _details_active_entry(obj: Mapping[str, Any]) -> dict:
    return {"queueId": _token(_required(obj, "queueId", "details"), "details.queueId"),
            "currentEntryId": _token(_required(obj, "currentEntryId", "details"), "details.currentEntryId")}


def _details_operation(obj: Mapping[str, Any]) -> dict:
    return {"operation": _token(_required(obj, "operation", "details"), "details.operation")}


def _details_diagnostic(obj: Mapping[str, Any]) -> dict:
    return {"diagnosticId": _token(_required(obj, "diagnosticId", "details"), "details.diagnosticId")}


def _command_items(value: Any, field: str) -> list:
    if not isinstance(value, list):
        _fail(field, "invalid_type")
    if len(value) > _MAX_ENTRIES:
        _limit_fail(field)
    result = []
    for index, raw in enumerate(value):
        item_field = f"{field}[{index}]"
        obj = _object(raw, item_field)
        _fields(obj, {"mediaRef", "title"}, item_field)
        result.append({
            "mediaRef": validate_media_ref(_required(obj, "mediaRef", item_field), f"{item_field}.mediaRef"),
            "title": _title(_required(obj, "title", item_field), f"{item_field}.title"),
        })
    return result


def _entry_list(value: Any, *, queue: bool, field: str) -> list:
    if not isinstance(value, list):
        _fail(field, "invalid_type")
    if len(value) > _MAX_ENTRIES:
        _limit_fail(field)
    result = []
    seen = set()
    for index, item in enumerate(value):
        item_field = f"{field}[{index}]"
        parsed = validate_queue_entry(item, index, item_field) if queue else validate_playlist_entry(item, index, item_field)
        if parsed["entryId"] in seen:
            _fail(f"{item_field}.entryId", "duplicate_entry_id")
        seen.add(parsed["entryId"])
        result.append(parsed)
    return result


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        _fail(field, "invalid_type")
    if any(not isinstance(key, str) for key in value):
        _fail(field, "invalid_field_name")
    return value


def _fields(obj: Mapping[str, Any], expected: set, field: str) -> None:
    extra = set(obj) - expected
    if extra:
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


def _token(value: Any, field: str) -> str:
    if not isinstance(value, str) or _TOKEN_RE.fullmatch(value) is None:
        _fail(field, "invalid_identifier")
    return value


def _integer(value: Any, field: str) -> int:
    if type(value) is not int or value < 0 or value > _MAX_REVISION:
        _fail(field, "invalid_integer")
    return value


def _revision(value: Any, field: str) -> int:
    return _integer(value, field)


def _name(value: Any, field: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 256 or not value.strip():
        _fail(field, "invalid_name")
    return value


def _title(value: Any, field: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 1024 or not value.strip():
        _fail(field, "invalid_title")
    return value


def _message(value: Any, field: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 1024 or not value.strip():
        _fail(field, "invalid_message")
    return value


def _safe_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 256 or not value.strip():
        _fail(field, "invalid_text")
    return value


def _enum(value: Any, field: str, allowed: set) -> str:
    if not isinstance(value, str) or value not in allowed:
        _fail(field, "invalid_enum")
    return value


def _fail(field: str, reason: str, code: str = "VALIDATION_ERROR") -> None:
    raise ContractValidationError(field, reason, code)


def _limit_fail(field: str) -> None:
    raise ContractValidationError(field, "limit_exceeded", "LIMIT_EXCEEDED",
                                  details={"field": field, "limit": _MAX_ENTRIES})

"""V1 transport validation and safe error mapping for playlist endpoints."""

from jukebox.contracts.v1 import (
    ContractValidationError,
    validate_command,
    validate_command_result,
    validate_identifier,
    validate_playlist_snapshot,
    validate_queue_snapshot,
)
from components.playlists.store import StoreError


PUBLIC_ACTIONS = frozenset({
    "PLAYLIST_CREATE", "PLAYLIST_RENAME", "PLAYLIST_APPEND",
    "PLAYLIST_REMOVE", "PLAYLIST_MOVE", "PLAYLIST_DELETE",
    "QUEUE_CREATE", "QUEUE_LOAD_PLAYLIST", "QUEUE_APPEND", "QUEUE_REMOVE",
    "QUEUE_MOVE", "QUEUE_SET_MODES", "QUEUE_SAVE_NEW_PLAYLIST",
    "QUEUE_SAVE_PLAYLIST",
})


class PlaylistAPIError(Exception):
    def __init__(self, status, code):
        self.status = status
        self.code = code
        super().__init__(code)


def playlist_id(value):
    try:
        return validate_identifier(value, "playlistId")
    except Exception:
        raise ValueError("invalid identifier") from None


def queue_id(value):
    try:
        return validate_identifier(value, "queueId")
    except Exception:
        raise ValueError("invalid identifier") from None


def validate_playlist_list(value, limit):
    if not isinstance(value, dict) or set(value) != {"contractVersion", "playlists", "nextCursor"}:
        raise ValueError("invalid playlist list")
    if type(value["contractVersion"]) is not int or value["contractVersion"] != 1:
        raise ValueError("invalid playlist list")
    records = value["playlists"]
    if not isinstance(records, list) or len(records) > limit:
        raise ValueError("invalid playlist list")
    projected, seen = [], set()
    for record in records:
        if not isinstance(record, dict) or set(record) != {"playlistId", "name", "revision"}:
            raise ValueError("invalid playlist list")
        ident = playlist_id(record["playlistId"])
        snapshot = validate_playlist_snapshot({
            "contractVersion": 1, "playlistId": ident, "name": record["name"],
            "revision": record["revision"], "entries": [],
        })
        if ident in seen or (projected and ident <= projected[-1]["playlistId"]):
            raise ValueError("invalid playlist list")
        seen.add(ident)
        projected.append({"playlistId": ident, "name": snapshot["name"], "revision": snapshot["revision"]})
    cursor = value["nextCursor"]
    if cursor is not None:
        cursor = playlist_id(cursor)
        if not projected or cursor != projected[-1]["playlistId"]:
            raise ValueError("invalid playlist list")
    return {"contractVersion": 1, "playlists": projected, "nextCursor": cursor}


def playlist_snapshot(value, ident):
    result = validate_playlist_snapshot(value)
    if result["playlistId"] != ident:
        raise ValueError("playlist id mismatch")
    return result


def queue_snapshot(value, ident):
    result = validate_queue_snapshot(value)
    if result["queueId"] != ident:
        raise ValueError("queue id mismatch")
    return result


def execute(command, dispatch):
    try:
        parsed = validate_command(command)
        if parsed["action"] not in PUBLIC_ACTIONS:
            raise ContractValidationError("action", "unsupported public action")
    except ContractValidationError:
        raise PlaylistAPIError(400, "INVALID_REQUEST") from None

    try:
        result = validate_command_result(dispatch(parsed))
        if result["commandId"] != parsed["commandId"] or result["action"] != parsed["action"]:
            raise ValueError("command result mismatch")
        if result["status"] == "REJECTED":
            from copy import deepcopy
            result = deepcopy(result)
            result["error"]["message"] = "The playlist command was rejected."
        return result
    except ContractValidationError:
        raise PlaylistAPIError(503, "SERVICE_UNAVAILABLE") from None
    except StoreError as error:
        code = error.error.get("code")
        if code == "NOT_FOUND":
            raise PlaylistAPIError(404, "NOT_FOUND") from None
        if code in {"REVISION_CONFLICT", "COMMAND_ID_REUSED", "POSITION_OUT_OF_RANGE"}:
            raise PlaylistAPIError(409, "CONFLICT") from None
        raise PlaylistAPIError(503, "SERVICE_UNAVAILABLE") from None

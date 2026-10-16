"""Transport-free SQLite store for the first playlist persistence slice."""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional, Union
from uuid import uuid4

from jukebox.contracts.v1 import (
    validate_command,
    validate_command_result,
    validate_error,
    validate_identifier,
    validate_playlist_snapshot,
)


class StoreError(Exception):
    """A safe store/lookup failure carrying the V1 Error mapping."""

    def __init__(self, error: Dict[str, Any]) -> None:
        self.error = validate_error(error)
        super().__init__(self.error["message"])


class PlaylistStore:
    """Persist playlists and command outcomes without transport or playback."""

    def __init__(self, db_path: Union[str, Path]) -> None:
        self._db_path = str(db_path)
        self._initialize()

    def execute(self, command: Dict[str, Any]) -> Dict[str, Any]:
        parsed = validate_command(command)
        if parsed["action"] not in {"PLAYLIST_CREATE", "PLAYLIST_APPEND"}:
            raise NotImplementedError("This store slice supports playlist create and append only.")
        request_json = _canonical_json(parsed)
        conn = self._connect("PLAYLIST_WRITE")
        try:
            conn.execute("BEGIN IMMEDIATE")
            previous = conn.execute(
                "SELECT request_json, result_json FROM command_log WHERE command_id = ?",
                (parsed["commandId"],),
            ).fetchone()
            if previous is not None:
                if previous[0] == request_json:
                    conn.commit()
                    return self._decode_result(previous[1])
                result = self._rejected(
                    parsed,
                    "COMMAND_ID_REUSED",
                    {"commandId": parsed["commandId"]},
                    "This commandId is already bound to a different request.",
                )
                conn.commit()
                return result

            conn.execute(
                "INSERT INTO command_log (command_id, request_json, result_json) VALUES (?, ?, NULL)",
                (parsed["commandId"], request_json),
            )
            try:
                if parsed["action"] == "PLAYLIST_CREATE":
                    result = self._create(conn, parsed)
                else:
                    result = self._append(conn, parsed)
            except _DomainRejection as rejection:
                result = self._rejected(parsed, rejection.code, rejection.details, rejection.message)
            self._write_command_result(conn, parsed["commandId"], result)
            conn.commit()
            return result
        except sqlite3.OperationalError as exc:
            _rollback_quietly(conn)
            raise self._database_error(exc, "PLAYLIST_WRITE") from None
        except sqlite3.DatabaseError:
            _rollback_quietly(conn)
            raise _store_error("STORE_UNAVAILABLE", "PLAYLIST_WRITE") from None
        except Exception:
            _rollback_quietly(conn)
            raise
        finally:
            conn.close()

    def get_playlist(self, playlist_id: str) -> Dict[str, Any]:
        playlist_id = validate_identifier(playlist_id, "playlistId")
        conn = self._connect("PLAYLIST_GET")
        try:
            conn.execute("BEGIN")
            row = conn.execute(
                "SELECT name, revision FROM playlists WHERE playlist_id = ?", (playlist_id,)
            ).fetchone()
            if row is None:
                conn.rollback()
                raise _store_error(
                    "NOT_FOUND", "PLAYLIST_GET",
                    {"objectType": "playlist", "objectId": playlist_id},
                    "The requested playlist was not found.",
                )
            entries = conn.execute(
                "SELECT entry_id, media_ref_json, title, position FROM playlist_entries "
                "WHERE playlist_id = ? ORDER BY position ASC", (playlist_id,),
            ).fetchall()
            snapshot = {
                "contractVersion": 1,
                "playlistId": playlist_id,
                "name": row[0],
                "revision": row[1],
                "entries": [
                    {
                        "entryId": entry[0],
                        "mediaRef": json.loads(entry[1]),
                        "title": entry[2],
                        "position": entry[3],
                    }
                    for entry in entries
                ],
            }
            parsed = validate_playlist_snapshot(snapshot)
            conn.commit()
            return parsed
        except sqlite3.OperationalError as exc:
            _rollback_quietly(conn)
            raise self._database_error(exc, "PLAYLIST_GET") from None
        except sqlite3.DatabaseError:
            _rollback_quietly(conn)
            raise _store_error("STORE_UNAVAILABLE", "PLAYLIST_GET") from None
        except Exception:
            _rollback_quietly(conn)
            raise
        finally:
            conn.close()

    def get_command(self, command_id: str) -> Dict[str, Any]:
        command_id = validate_identifier(command_id, "commandId")
        conn = self._connect("COMMAND_GET")
        try:
            row = conn.execute(
                "SELECT result_json FROM command_log WHERE command_id = ?", (command_id,)
            ).fetchone()
            if row is None:
                raise _store_error(
                    "COMMAND_NOT_FOUND", "COMMAND_GET", {"commandId": command_id},
                    "The requested command result was not found.",
                )
            if row[0] is None:
                raise _store_error("STORE_UNAVAILABLE", "COMMAND_GET")
            return self._decode_result(row[0])
        except sqlite3.OperationalError as exc:
            raise self._database_error(exc, "COMMAND_GET") from None
        except sqlite3.DatabaseError:
            raise _store_error("STORE_UNAVAILABLE", "COMMAND_GET") from None
        finally:
            conn.close()

    def _create(self, conn: sqlite3.Connection, command: Dict[str, Any]) -> Dict[str, Any]:
        playlist_id = _new_id("pl")
        conn.execute(
            "INSERT INTO playlists (playlist_id, name, revision) VALUES (?, ?, 0)",
            (playlist_id, command["name"]),
        )
        for position, item in enumerate(command["items"]):
            self._insert_entry(conn, playlist_id, position, item)
        return self._applied(command, {"playlist": self._snapshot(conn, playlist_id)})

    def _append(self, conn: sqlite3.Connection, command: Dict[str, Any]) -> Dict[str, Any]:
        playlist_id = command["playlistId"]
        row = conn.execute(
            "SELECT name, revision FROM playlists WHERE playlist_id = ?", (playlist_id,)
        ).fetchone()
        if row is None:
            raise _DomainRejection(
                "NOT_FOUND", {"objectType": "playlist", "objectId": playlist_id},
                "The requested playlist was not found.",
            )
        name, revision = row
        if revision != command["expectedRevision"]:
            raise _DomainRejection(
                "REVISION_CONFLICT",
                {"conflicts": [{
                    "objectType": "playlist", "objectId": playlist_id,
                    "expectedRevision": command["expectedRevision"],
                    "actualRevision": revision,
                }]},
                "The playlist changed since it was read.",
            )
        if command["items"]:
            if revision >= 9007199254740991:
                raise _DomainRejection(
                    "REVISION_EXHAUSTED",
                    {"objectType": "playlist", "objectId": playlist_id},
                    "The playlist revision limit has been reached.",
                )
            count = conn.execute(
                "SELECT COUNT(*) FROM playlist_entries WHERE playlist_id = ?", (playlist_id,)
            ).fetchone()[0]
            if count + len(command["items"]) > 10000:
                raise _DomainRejection(
                    "LIMIT_EXCEEDED", {"field": "items", "limit": 10000},
                    "The playlist entry limit would be exceeded.",
                )
            for offset, item in enumerate(command["items"], start=count):
                self._insert_entry(conn, playlist_id, offset, item)
            revision += 1
            conn.execute(
                "UPDATE playlists SET revision = ? WHERE playlist_id = ?", (revision, playlist_id)
            )
        return self._applied(command, {"playlist": self._snapshot(conn, playlist_id)})

    def _insert_entry(self, conn: sqlite3.Connection, playlist_id: str,
                      position: int, item: Dict[str, Any]) -> None:
        conn.execute(
            "INSERT INTO playlist_entries "
            "(entry_id, playlist_id, media_ref_json, title, position) VALUES (?, ?, ?, ?, ?)",
            (_new_id("pe"), playlist_id, _canonical_json(item["mediaRef"]), item["title"], position),
        )

    def _snapshot(self, conn: sqlite3.Connection, playlist_id: str) -> Dict[str, Any]:
        row = conn.execute(
            "SELECT name, revision FROM playlists WHERE playlist_id = ?", (playlist_id,)
        ).fetchone()
        entries = conn.execute(
            "SELECT entry_id, media_ref_json, title, position FROM playlist_entries "
            "WHERE playlist_id = ? ORDER BY position ASC", (playlist_id,),
        ).fetchall()
        return validate_playlist_snapshot({
            "contractVersion": 1,
            "playlistId": playlist_id,
            "name": row[0],
            "revision": row[1],
            "entries": [{
                "entryId": item[0], "mediaRef": json.loads(item[1]),
                "title": item[2], "position": item[3],
            } for item in entries],
        })

    def _write_command_result(self, conn: sqlite3.Connection, command_id: str,
                              result: Dict[str, Any]) -> None:
        validated = validate_command_result(result)
        conn.execute(
            "UPDATE command_log SET result_json = ? WHERE command_id = ?",
            (_canonical_json(validated), command_id),
        )

    def _decode_result(self, value: str) -> Dict[str, Any]:
        try:
            return validate_command_result(json.loads(value))
        except (ValueError, TypeError):
            raise _store_error("STORE_UNAVAILABLE", "COMMAND_GET") from None

    def _connect(self, operation: str) -> sqlite3.Connection:
        try:
            conn = sqlite3.connect(self._db_path, timeout=0.15, isolation_level=None)
            conn.execute("PRAGMA foreign_keys = ON")
            return conn
        except sqlite3.OperationalError as exc:
            if "conn" in locals():
                conn.close()
            raise self._database_error(exc, operation) from None
        except sqlite3.DatabaseError:
            if "conn" in locals():
                conn.close()
            raise _store_error("STORE_UNAVAILABLE", operation) from None

    def _initialize(self) -> None:
        try:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            raise _store_error("STORE_UNAVAILABLE", "STORE_INITIALIZE") from None
        conn = self._connect("STORE_INITIALIZE")
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS playlists (
                    playlist_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    revision INTEGER NOT NULL CHECK (revision >= 0)
                );
                CREATE TABLE IF NOT EXISTS playlist_entries (
                    entry_id TEXT PRIMARY KEY,
                    playlist_id TEXT NOT NULL REFERENCES playlists(playlist_id) ON DELETE CASCADE,
                    media_ref_json TEXT NOT NULL,
                    title TEXT NOT NULL,
                    position INTEGER NOT NULL CHECK (position >= 0),
                    UNIQUE (playlist_id, position)
                );
                CREATE TABLE IF NOT EXISTS command_log (
                    command_id TEXT PRIMARY KEY,
                    request_json TEXT NOT NULL,
                    result_json TEXT
                );
            """)
        except sqlite3.DatabaseError:
            raise _store_error("STORE_UNAVAILABLE", "STORE_INITIALIZE") from None
        finally:
            conn.close()

    def _database_error(self, error: sqlite3.OperationalError, operation: str) -> StoreError:
        if "locked" in str(error).lower() or "busy" in str(error).lower():
            return _store_error("STORE_BUSY", operation)
        return _store_error("STORE_UNAVAILABLE", operation)

    def _applied(self, command: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
        return validate_command_result({
            "contractVersion": 1, "commandId": command["commandId"],
            "action": command["action"], "status": "APPLIED", "result": body,
        })

    def _rejected(self, command: Dict[str, Any], code: str,
                  details: Dict[str, Any], message: str) -> Dict[str, Any]:
        return validate_command_result({
            "contractVersion": 1, "commandId": command["commandId"],
            "action": command["action"], "status": "REJECTED",
            "error": _error(code, command["action"], details, message),
        })


class _DomainRejection(Exception):
    def __init__(self, code: str, details: Dict[str, Any], message: str) -> None:
        self.code = code
        self.details = details
        self.message = message


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _canonical_json(value: Dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _error(code: str, operation: str, details: Dict[str, Any], message: str) -> Dict[str, Any]:
    return validate_error({
        "code": code, "message": message, "retryable": code in {"STORE_BUSY", "STORE_UNAVAILABLE"},
        "operation": operation, "details": details,
    })


def _store_error(code: str, operation: str, details: Optional[Dict[str, Any]] = None,
                 message: Optional[str] = None) -> StoreError:
    if details is None:
        details = {"operation": operation}
    if code == "NOT_FOUND" and message:
        pass
    elif code in {"STORE_BUSY", "STORE_UNAVAILABLE"}:
        message = "The playlist store is temporarily unavailable."
    elif code == "COMMAND_NOT_FOUND":
        message = message or "The requested command result was not found."
    else:
        message = message or "The requested object was not found."
    return StoreError(_error(code, operation, details, message))


def _rollback_quietly(conn: sqlite3.Connection) -> None:
    try:
        conn.rollback()
    except sqlite3.DatabaseError:
        pass

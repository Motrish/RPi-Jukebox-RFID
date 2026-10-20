"""Transport-free SQLite store for the first playlist persistence slice."""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional, Union
from uuid import uuid4
from datetime import datetime, timezone

from jukebox.contracts.v1 import (
    ContractValidationError,
    validate_command,
    validate_command_result,
    validate_error,
    validate_identifier,
    validate_queue_snapshot,
    validate_playlist_snapshot,
    validate_queue_entry,
)
from jukebox.contracts.playback_v1 import validate_playback_command, validate_playback_command_result


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
        handler = {
            "PLAYLIST_CREATE": self._create,
            "PLAYLIST_RENAME": self._rename,
            "PLAYLIST_APPEND": self._append,
            "PLAYLIST_REMOVE": self._remove,
            "PLAYLIST_MOVE": self._move,
            "PLAYLIST_DELETE": self._delete,
            "QUEUE_CREATE": self._queue_create,
            "QUEUE_LOAD_PLAYLIST": self._queue_load_playlist,
            "QUEUE_APPEND": self._queue_append,
            "QUEUE_REMOVE": self._queue_remove,
            "QUEUE_MOVE": self._queue_move,
            "QUEUE_SET_MODES": self._queue_set_modes,
            "QUEUE_SET_CURRENT": self._queue_set_current,
            "QUEUE_SAVE_NEW_PLAYLIST": self._queue_save_new_playlist,
            "QUEUE_SAVE_PLAYLIST": self._queue_save_playlist,
        }.get(parsed["action"])
        if handler is None:
            raise NotImplementedError("This store slice supports playlist and queue write actions only.")
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
                    return self._decode_stored(previous[0], previous[1], parsed["commandId"])
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
                result = handler(conn, parsed)
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

    def get_queue(self, queue_id: str) -> Dict[str, Any]:
        queue_id = validate_identifier(queue_id, "queueId")
        conn = self._connect("QUEUE_GET")
        try:
            conn.execute("BEGIN")
            row = conn.execute(
                "SELECT revision, source_playlist_id, source_playlist_revision, current_entry_id, "
                "repeat_mode, shuffle_mode FROM queues WHERE queue_id = ?", (queue_id,),
            ).fetchone()
            if row is None:
                conn.rollback()
                raise _store_error(
                    "NOT_FOUND", "QUEUE_GET", {"objectType": "queue", "objectId": queue_id},
                    "The requested queue was not found.",
                )
            entries = conn.execute(
                "SELECT entry_id, source_entry_id, media_ref_json, title, position FROM queue_entries "
                "WHERE queue_id = ? ORDER BY position ASC", (queue_id,),
            ).fetchall()
            snapshot = self._queue_snapshot_from_rows(queue_id, row, entries)
            conn.commit()
            return snapshot
        except sqlite3.OperationalError as exc:
            _rollback_quietly(conn)
            raise self._database_error(exc, "QUEUE_GET") from None
        except sqlite3.DatabaseError:
            _rollback_quietly(conn)
            raise _store_error("STORE_UNAVAILABLE", "QUEUE_GET") from None
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
                "SELECT request_json, result_json FROM command_log WHERE command_id = ?", (command_id,)
            ).fetchone()
            if row is None:
                raise _store_error(
                    "COMMAND_NOT_FOUND", "COMMAND_GET", {"commandId": command_id},
                    "The requested command result was not found.",
                )
            if row[0] is None or row[1] is None:
                raise _store_error("STORE_UNAVAILABLE", "COMMAND_GET")
            return self._decode_stored(row[0], row[1], command_id)
        except sqlite3.OperationalError as exc:
            raise self._database_error(exc, "COMMAND_GET") from None
        except sqlite3.DatabaseError:
            raise _store_error("STORE_UNAVAILABLE", "COMMAND_GET") from None
        finally:
            conn.close()

    def admit_playback(self, command: Dict[str, Any]) -> Dict[str, Any]:
        parsed = validate_playback_command(command)
        request_json = _canonical_json(parsed)
        conn = self._connect("PLAYBACK_ADMIT")
        try:
            conn.execute("BEGIN IMMEDIATE")
            previous = conn.execute(
                "SELECT request_json, result_json FROM command_log WHERE command_id = ?",
                (parsed["commandId"],),
            ).fetchone()
            if previous is not None:
                if previous[0] == request_json:
                    result = self._decode_stored(previous[0], previous[1], parsed["commandId"])
                    conn.commit()
                    return result
                result = self._playback_rejected(parsed, "COMMAND_ID_REUSED",
                    {"commandId": parsed["commandId"]},
                    "This commandId is already bound to a different request.",
                )
                conn.commit()
                return result
            conn.execute("INSERT INTO command_log (command_id, request_json, result_json) VALUES (?, ?, NULL)",
                         (parsed["commandId"], request_json))
            try:
                selection = self._admit_start_selection(conn, parsed) if parsed["action"] == "PLAYBACK_START" else None
                sequence = conn.execute("SELECT COALESCE(MAX(intent_sequence), 0) FROM playback_intents").fetchone()[0]
                if sequence >= 9007199254740991:
                    raise _DomainRejection(
                        "LIMIT_EXCEEDED",
                        {"field": "playback.intentSequence", "limit": 9007199254740991},
                        "The playback intent sequence limit has been reached.",
                    )
                if selection is not None:
                    conn.execute("UPDATE queues SET current_entry_id=?,revision=? WHERE queue_id=?",
                        (selection["entry"]["entryId"], selection["queueRevision"], selection["queueId"]))
                sequence += 1
                intent_id = _new_id("pi")
                stamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
                result = validate_playback_command_result({
                    "contractVersion": 1, "commandId": parsed["commandId"], "action": parsed["action"],
                    "status": "ACCEPTED", "result": {"intentId": intent_id, "intentSequence": sequence,
                    "acceptedAt": stamp, "selection": selection}})
                self._write_playback_result(conn, parsed["commandId"], result)
                conn.execute(
                    "INSERT INTO playback_intents "
                    "(command_id,intent_id,intent_sequence,state,queue_id,entry_id) "
                    "VALUES (?,?,?,'PENDING',?,?)",
                    (parsed["commandId"], intent_id, sequence, selection["queueId"] if selection else None,
                     selection["entry"]["entryId"] if selection else None))
            except _DomainRejection as rejection:
                result = self._playback_rejected(parsed, rejection.code, rejection.details, rejection.message)
                self._write_playback_result(conn, parsed["commandId"], result)
            conn.commit()
            return result
        except sqlite3.OperationalError as exc:
            _rollback_quietly(conn)
            raise self._database_error(exc, "PLAYBACK_ADMIT") from None
        except sqlite3.DatabaseError:
            _rollback_quietly(conn)
            raise _store_error("STORE_UNAVAILABLE", "PLAYBACK_ADMIT") from None
        except Exception:
            _rollback_quietly(conn)
            raise
        finally:
            conn.close()

    def _admit_start_selection(self, conn: sqlite3.Connection, command: Dict[str, Any]) -> Dict[str, Any]:
        row = self._queue_header(conn, command["queueId"])
        if row is None:
            raise _DomainRejection(
                "NOT_FOUND", {"objectType": "queue", "objectId": command["queueId"]},
                "The requested queue was not found.",
            )
        if row[0] != command["expectedQueueRevision"]:
            raise _DomainRejection(
                "REVISION_CONFLICT", {"conflicts": [self._revision_conflict(
                    "queue", command["queueId"], command["expectedQueueRevision"], row[0])]},
                "The queue changed since it was read.",
            )
        entries = conn.execute(
            "SELECT entry_id,source_entry_id,media_ref_json,title,position FROM queue_entries "
            "WHERE queue_id=? ORDER BY position", (command["queueId"],),
        ).fetchall()
        found = None
        try:
            for expected_position, stored in enumerate(entries):
                decoded_media = json.loads(stored[2])
                normalized = validate_queue_entry({
                    "entryId": stored[0], "sourceEntryId": stored[1],
                    "mediaRef": decoded_media, "title": stored[3], "position": stored[4],
                }, expected_position=expected_position)
                if stored[0] == command["entryId"]:
                    found = normalized
        except Exception:
            raise _store_error("STORE_UNAVAILABLE", "PLAYBACK_ADMIT") from None
        if found is None:
            raise _DomainRejection(
                "NOT_FOUND", {"objectType": "queueEntry", "objectId": command["entryId"]},
                "The requested queue entry was not found.",
            )
        media = found["mediaRef"]
        if media["kind"] != "LOCAL":
            raise _DomainRejection(
                "CAPABILITY_UNAVAILABLE", {"capability": "SPOTIFY_PLAYBACK"},
                "The selected media source is not available for local playback.",
            )
        revision = row[0]
        if row[3] != command["entryId"]:
            if revision >= 9007199254740991:
                raise _DomainRejection(
                    "REVISION_EXHAUSTED",
                    {"objectType": "queue", "objectId": command["queueId"]},
                    "The queue revision limit has been reached.",
                )
            revision += 1
        return {"queueId": command["queueId"], "queueRevision": revision, "entry": found}

    def list_playlists(self, limit: int = 50, cursor: Optional[str] = None) -> Dict[str, Any]:
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ContractValidationError("limit", "invalid_integer")
        if cursor is not None:
            cursor = validate_identifier(cursor, "cursor")
        conn = self._connect("PLAYLIST_LIST")
        try:
            if cursor is None:
                rows = conn.execute(
                    "SELECT playlist_id, name, revision FROM playlists "
                    "ORDER BY playlist_id ASC LIMIT ?", (limit + 1,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT playlist_id, name, revision FROM playlists "
                    "WHERE playlist_id > ? ORDER BY playlist_id ASC LIMIT ?", (cursor, limit + 1),
                ).fetchall()
            has_more = len(rows) > limit
            page = rows[:limit]
            return {
                "contractVersion": 1,
                "playlists": [
                    {"playlistId": row[0], "name": row[1], "revision": row[2]}
                    for row in page
                ],
                "nextCursor": page[-1][0] if has_more else None,
            }
        except sqlite3.OperationalError as exc:
            raise self._database_error(exc, "PLAYLIST_LIST") from None
        except sqlite3.DatabaseError:
            raise _store_error("STORE_UNAVAILABLE", "PLAYLIST_LIST") from None
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

    def _rename(self, conn: sqlite3.Connection, command: Dict[str, Any]) -> Dict[str, Any]:
        playlist_id = command["playlistId"]
        name, revision = self._playlist_before_edit(conn, command)
        if name != command["name"]:
            self._ensure_revision_available(playlist_id, revision)
            revision += 1
            conn.execute(
                "UPDATE playlists SET name = ?, revision = ? WHERE playlist_id = ?",
                (command["name"], revision, playlist_id),
            )
        return self._applied(command, {"playlist": self._snapshot(conn, playlist_id)})

    def _remove(self, conn: sqlite3.Connection, command: Dict[str, Any]) -> Dict[str, Any]:
        playlist_id = command["playlistId"]
        _, revision = self._playlist_before_edit(conn, command)
        row = conn.execute(
            "SELECT position FROM playlist_entries WHERE playlist_id = ? AND entry_id = ?",
            (playlist_id, command["entryId"]),
        ).fetchone()
        if row is None:
            raise _DomainRejection(
                "NOT_FOUND", {"objectType": "playlistEntry", "objectId": command["entryId"]},
                "The requested playlist entry was not found.",
            )
        self._ensure_revision_available(playlist_id, revision)
        conn.execute("DELETE FROM playlist_entries WHERE entry_id = ?", (command["entryId"],))
        entry_ids = [row[0] for row in conn.execute(
            "SELECT entry_id FROM playlist_entries WHERE playlist_id = ? ORDER BY position ASC",
            (playlist_id,),
        ).fetchall()]
        self._reindex(conn, playlist_id, entry_ids)
        conn.execute(
            "UPDATE playlists SET revision = ? WHERE playlist_id = ?", (revision + 1, playlist_id)
        )
        return self._applied(command, {"playlist": self._snapshot(conn, playlist_id)})

    def _move(self, conn: sqlite3.Connection, command: Dict[str, Any]) -> Dict[str, Any]:
        playlist_id = command["playlistId"]
        _, revision = self._playlist_before_edit(conn, command)
        entry_ids = [row[0] for row in conn.execute(
            "SELECT entry_id FROM playlist_entries WHERE playlist_id = ? ORDER BY position ASC",
            (playlist_id,),
        ).fetchall()]
        try:
            old_position = entry_ids.index(command["entryId"])
        except ValueError:
            raise _DomainRejection(
                "NOT_FOUND", {"objectType": "playlistEntry", "objectId": command["entryId"]},
                "The requested playlist entry was not found.",
            ) from None
        to_position = command["toPosition"]
        if to_position >= len(entry_ids):
            raise _DomainRejection(
                "POSITION_OUT_OF_RANGE",
                {"entryId": command["entryId"], "minimum": 0, "maximum": len(entry_ids) - 1},
                "The requested final playlist position is out of range.",
            )
        if to_position == old_position:
            return self._applied(command, {"playlist": self._snapshot(conn, playlist_id)})
        self._ensure_revision_available(playlist_id, revision)
        moved_id = entry_ids.pop(old_position)
        entry_ids.insert(to_position, moved_id)
        self._reindex(conn, playlist_id, entry_ids)
        conn.execute(
            "UPDATE playlists SET revision = ? WHERE playlist_id = ?", (revision + 1, playlist_id)
        )
        return self._applied(command, {"playlist": self._snapshot(conn, playlist_id)})

    def _delete(self, conn: sqlite3.Connection, command: Dict[str, Any]) -> Dict[str, Any]:
        playlist_id = command["playlistId"]
        _, revision = self._playlist_before_edit(conn, command)
        conn.execute("DELETE FROM playlists WHERE playlist_id = ?", (playlist_id,))
        return self._applied(command, {
            "deletedPlaylistId": playlist_id,
            "deletedRevision": revision,
        })

    def _queue_create(self, conn: sqlite3.Connection, command: Dict[str, Any]) -> Dict[str, Any]:
        queue_id = _new_id("q")
        conn.execute(
            "INSERT INTO queues (queue_id, revision, source_playlist_id, source_playlist_revision, "
            "current_entry_id, repeat_mode, shuffle_mode) VALUES (?, 0, NULL, NULL, NULL, 'OFF', 'OFF')",
            (queue_id,),
        )
        for position, item in enumerate(command["items"]):
            self._insert_queue_entry(conn, queue_id, position, item, None)
        return self._applied(command, {"queue": self._queue_snapshot(conn, queue_id)})

    def _queue_load_playlist(self, conn: sqlite3.Connection, command: Dict[str, Any]) -> Dict[str, Any]:
        queue = self._queue_header(conn, command["queueId"])
        playlist = conn.execute(
            "SELECT name, revision FROM playlists WHERE playlist_id = ?", (command["playlistId"],)
        ).fetchone()
        if queue is None:
            raise _DomainRejection(
                "NOT_FOUND", {"objectType": "queue", "objectId": command["queueId"]},
                "The requested queue was not found.",
            )
        if playlist is None:
            raise _DomainRejection(
                "NOT_FOUND", {"objectType": "playlist", "objectId": command["playlistId"]},
                "The requested playlist was not found.",
            )
        conflicts = []
        if queue[0] != command["expectedQueueRevision"]:
            conflicts.append(self._revision_conflict(
                "queue", command["queueId"], command["expectedQueueRevision"], queue[0]
            ))
        if playlist[1] != command["expectedPlaylistRevision"]:
            conflicts.append(self._revision_conflict(
                "playlist", command["playlistId"], command["expectedPlaylistRevision"], playlist[1]
            ))
        if conflicts:
            raise _DomainRejection(
                "REVISION_CONFLICT", {"conflicts": conflicts},
                "One or more objects changed since they were read.",
            )
        pinned = self._oldest_pin(conn, command["queueId"])
        if pinned is not None:
            raise _DomainRejection(
                "ACTIVE_ENTRY_REQUIRES_CONTROLLER",
                {"queueId": command["queueId"], "currentEntryId": pinned},
                "An admitted playback entry must be resolved by the controller before loading a playlist.",
            )
        if queue[3] is not None:
            raise _DomainRejection("ACTIVE_ENTRY_REQUIRES_CONTROLLER",
                {"queueId": command["queueId"], "currentEntryId": queue[3]},
                "The active queue entry must be cleared by the controller before loading a playlist.",
            )
        self._ensure_revision_available(command["queueId"], queue[0], "queue")
        source_entries = conn.execute(
            "SELECT entry_id, media_ref_json, title FROM playlist_entries "
            "WHERE playlist_id = ? ORDER BY position ASC", (command["playlistId"],),
        ).fetchall()
        conn.execute("DELETE FROM queue_entries WHERE queue_id = ?", (command["queueId"],))
        for position, item in enumerate(source_entries):
            self._insert_queue_entry(
                conn, command["queueId"], position,
                {"mediaRef": json.loads(item[1]), "title": item[2]}, item[0],
            )
        conn.execute(
            "UPDATE queues SET revision = ?, source_playlist_id = ?, source_playlist_revision = ?, "
            "current_entry_id = NULL, repeat_mode = 'OFF', shuffle_mode = 'OFF' WHERE queue_id = ?",
            (queue[0] + 1, command["playlistId"], playlist[1], command["queueId"]),
        )
        return self._applied(command, {"queue": self._queue_snapshot(conn, command["queueId"])})

    def _queue_append(self, conn: sqlite3.Connection, command: Dict[str, Any]) -> Dict[str, Any]:
        queue = self._queue_for_edit(conn, command)
        if command["items"]:
            self._ensure_revision_available(command["queueId"], queue[0], "queue")
            count = conn.execute(
                "SELECT COUNT(*) FROM queue_entries WHERE queue_id = ?", (command["queueId"],)
            ).fetchone()[0]
            if count + len(command["items"]) > 10000:
                raise _DomainRejection(
                    "LIMIT_EXCEEDED", {"field": "items", "limit": 10000},
                    "The queue entry limit would be exceeded.",
                )
            for position, item in enumerate(command["items"], start=count):
                self._insert_queue_entry(conn, command["queueId"], position, item, None)
            conn.execute(
                "UPDATE queues SET revision = ? WHERE queue_id = ?",
                (queue[0] + 1, command["queueId"]),
            )
        return self._applied(command, {"queue": self._queue_snapshot(conn, command["queueId"])})

    def _queue_remove(self, conn: sqlite3.Connection, command: Dict[str, Any]) -> Dict[str, Any]:
        queue = self._queue_for_edit(conn, command)
        entry_id = command["entryId"]
        pinned = self._oldest_pin(conn, command["queueId"], entry_id)
        if pinned is not None or queue[3] == entry_id:
            protected = pinned or queue[3]
            raise _DomainRejection(
                "ACTIVE_ENTRY_REQUIRES_CONTROLLER",
                {"queueId": command["queueId"], "currentEntryId": protected},
                "The active queue entry must be cleared by the controller before removal.",
            )
        exists = conn.execute(
            "SELECT 1 FROM queue_entries WHERE queue_id = ? AND entry_id = ?",
            (command["queueId"], entry_id),
        ).fetchone()
        if exists is None:
            raise _DomainRejection(
                "NOT_FOUND", {"objectType": "queueEntry", "objectId": entry_id},
                "The requested queue entry was not found.",
            )
        self._ensure_revision_available(command["queueId"], queue[0], "queue")
        conn.execute(
            "DELETE FROM queue_entries WHERE queue_id = ? AND entry_id = ?",
            (command["queueId"], entry_id),
        )
        entry_ids = [row[0] for row in conn.execute(
            "SELECT entry_id FROM queue_entries WHERE queue_id = ? ORDER BY position ASC",
            (command["queueId"],),
        ).fetchall()]
        self._reindex_queue(conn, command["queueId"], entry_ids)
        conn.execute(
            "UPDATE queues SET revision = ? WHERE queue_id = ?",
            (queue[0] + 1, command["queueId"]),
        )
        return self._applied(command, {"queue": self._queue_snapshot(conn, command["queueId"])})

    def _queue_move(self, conn: sqlite3.Connection, command: Dict[str, Any]) -> Dict[str, Any]:
        queue = self._queue_for_edit(conn, command)
        entry_ids = [row[0] for row in conn.execute(
            "SELECT entry_id FROM queue_entries WHERE queue_id = ? ORDER BY position ASC",
            (command["queueId"],),
        ).fetchall()]
        try:
            old_position = entry_ids.index(command["entryId"])
        except ValueError:
            raise _DomainRejection(
                "NOT_FOUND", {"objectType": "queueEntry", "objectId": command["entryId"]},
                "The requested queue entry was not found.",
            ) from None
        to_position = command["toPosition"]
        if to_position >= len(entry_ids):
            raise _DomainRejection(
                "POSITION_OUT_OF_RANGE",
                {"entryId": command["entryId"], "minimum": 0, "maximum": len(entry_ids) - 1},
                "The requested final queue position is out of range.",
            )
        if to_position != old_position:
            self._ensure_revision_available(command["queueId"], queue[0], "queue")
            entry_ids.insert(to_position, entry_ids.pop(old_position))
            self._reindex_queue(conn, command["queueId"], entry_ids)
            conn.execute(
                "UPDATE queues SET revision = ? WHERE queue_id = ?",
                (queue[0] + 1, command["queueId"]),
            )
        return self._applied(command, {"queue": self._queue_snapshot(conn, command["queueId"])})

    def _queue_set_modes(self, conn: sqlite3.Connection, command: Dict[str, Any]) -> Dict[str, Any]:
        queue = self._queue_for_edit(conn, command)
        if (queue[4], queue[5]) != (command["repeatMode"], command["shuffleMode"]):
            self._ensure_revision_available(command["queueId"], queue[0], "queue")
            conn.execute(
                "UPDATE queues SET repeat_mode = ?, shuffle_mode = ?, revision = ? WHERE queue_id = ?",
                (command["repeatMode"], command["shuffleMode"], queue[0] + 1, command["queueId"]),
            )
        return self._applied(command, {"queue": self._queue_snapshot(conn, command["queueId"])})

    def _queue_set_current(self, conn: sqlite3.Connection, command: Dict[str, Any]) -> Dict[str, Any]:
        queue = self._queue_for_edit(conn, command)
        entry_id = command["entryId"]
        if entry_id is not None and conn.execute(
            "SELECT 1 FROM queue_entries WHERE queue_id = ? AND entry_id = ?",
            (command["queueId"], entry_id),
        ).fetchone() is None:
            raise _DomainRejection(
                "NOT_FOUND", {"objectType": "queueEntry", "objectId": entry_id},
                "The requested queue entry was not found.",
            )
        if queue[3] != entry_id:
            self._ensure_revision_available(command["queueId"], queue[0], "queue")
            conn.execute(
                "UPDATE queues SET current_entry_id = ?, revision = ? WHERE queue_id = ?",
                (entry_id, queue[0] + 1, command["queueId"]),
            )
        return self._applied(command, {"queue": self._queue_snapshot(conn, command["queueId"])})

    def _queue_save_new_playlist(self, conn: sqlite3.Connection, command: Dict[str, Any]) -> Dict[str, Any]:
        self._queue_for_edit(conn, command, revision_field="expectedQueueRevision")
        playlist_id = _new_id("pl")
        conn.execute(
            "INSERT INTO playlists (playlist_id, name, revision) VALUES (?, ?, 0)",
            (playlist_id, command["name"]),
        )
        for position, item in enumerate(self._queue_copy_rows(conn, command["queueId"])):
            self._insert_entry(conn, playlist_id, position, item)
        return self._applied(command, {"playlist": self._snapshot(conn, playlist_id)})

    def _queue_save_playlist(self, conn: sqlite3.Connection, command: Dict[str, Any]) -> Dict[str, Any]:
        queue = self._queue_header(conn, command["queueId"])
        playlist = conn.execute(
            "SELECT name, revision FROM playlists WHERE playlist_id = ?", (command["playlistId"],)
        ).fetchone()
        if queue is None:
            raise _DomainRejection(
                "NOT_FOUND", {"objectType": "queue", "objectId": command["queueId"]},
                "The requested queue was not found.",
            )
        if playlist is None:
            raise _DomainRejection(
                "NOT_FOUND", {"objectType": "playlist", "objectId": command["playlistId"]},
                "The requested playlist was not found.",
            )
        conflicts = []
        if queue[0] != command["expectedQueueRevision"]:
            conflicts.append(self._revision_conflict(
                "queue", command["queueId"], command["expectedQueueRevision"], queue[0]
            ))
        if playlist[1] != command["expectedPlaylistRevision"]:
            conflicts.append(self._revision_conflict(
                "playlist", command["playlistId"], command["expectedPlaylistRevision"], playlist[1]
            ))
        if conflicts:
            raise _DomainRejection(
                "REVISION_CONFLICT", {"conflicts": conflicts},
                "One or more objects changed since they were read.",
            )
        self._ensure_revision_available(command["playlistId"], playlist[1], "playlist")
        source_entries = self._queue_copy_rows(conn, command["queueId"])
        conn.execute("DELETE FROM playlist_entries WHERE playlist_id = ?", (command["playlistId"],))
        for position, item in enumerate(source_entries):
            self._insert_entry(conn, command["playlistId"], position, item)
        conn.execute(
            "UPDATE playlists SET revision = ? WHERE playlist_id = ?",
            (playlist[1] + 1, command["playlistId"]),
        )
        return self._applied(command, {"playlist": self._snapshot(conn, command["playlistId"])})

    def _queue_header(self, conn: sqlite3.Connection, queue_id: str) -> Optional[tuple]:
        return conn.execute(
            "SELECT revision, source_playlist_id, source_playlist_revision, current_entry_id, "
            "repeat_mode, shuffle_mode FROM queues WHERE queue_id = ?", (queue_id,),
        ).fetchone()

    def _queue_for_edit(self, conn: sqlite3.Connection, command: Dict[str, Any],
                        revision_field: str = "expectedRevision") -> tuple:
        queue = self._queue_header(conn, command["queueId"])
        if queue is None:
            raise _DomainRejection(
                "NOT_FOUND", {"objectType": "queue", "objectId": command["queueId"]},
                "The requested queue was not found.",
            )
        expected = command[revision_field]
        if queue[0] != expected:
            raise _DomainRejection(
                "REVISION_CONFLICT", {"conflicts": [self._revision_conflict(
                    "queue", command["queueId"], expected, queue[0]
                )]}, "The queue changed since it was read.",
            )
        return queue

    @staticmethod
    def _revision_conflict(object_type: str, object_id: str, expected: int, actual: int) -> Dict[str, Any]:
        return {"objectType": object_type, "objectId": object_id,
                "expectedRevision": expected, "actualRevision": actual}

    def _queue_copy_rows(self, conn: sqlite3.Connection, queue_id: str) -> list[Dict[str, Any]]:
        rows = conn.execute(
            "SELECT media_ref_json, title FROM queue_entries WHERE queue_id = ? ORDER BY position ASC",
            (queue_id,),
        ).fetchall()
        return [{"mediaRef": json.loads(row[0]), "title": row[1]} for row in rows]

    def _queue_snapshot(self, conn: sqlite3.Connection, queue_id: str) -> Dict[str, Any]:
        header = self._queue_header(conn, queue_id)
        entries = conn.execute(
            "SELECT entry_id, source_entry_id, media_ref_json, title, position FROM queue_entries "
            "WHERE queue_id = ? ORDER BY position ASC", (queue_id,),
        ).fetchall()
        return self._queue_snapshot_from_rows(queue_id, header, entries)

    def _queue_snapshot_from_rows(self, queue_id: str, header: tuple, entries: list) -> Dict[str, Any]:
        return validate_queue_snapshot({
            "contractVersion": 1,
            "queueId": queue_id,
            "revision": header[0],
            "sourcePlaylistId": header[1],
            "sourcePlaylistRevision": header[2],
            "entries": [{
                "entryId": entry[0], "sourceEntryId": entry[1],
                "mediaRef": json.loads(entry[2]), "title": entry[3], "position": entry[4],
            } for entry in entries],
            "currentEntryId": header[3],
            "repeatMode": header[4],
            "shuffleMode": header[5],
        })

    def _insert_queue_entry(self, conn: sqlite3.Connection, queue_id: str, position: int,
                            item: Dict[str, Any], source_entry_id: Optional[str]) -> None:
        conn.execute(
            "INSERT INTO queue_entries "
            "(entry_id, queue_id, source_entry_id, media_ref_json, title, position) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (_new_id("qe"), queue_id, source_entry_id,
             _canonical_json(item["mediaRef"]), item["title"], position),
        )

    def _reindex_queue(self, conn: sqlite3.Connection, queue_id: str, entry_ids: list[str]) -> None:
        conn.execute(
            "UPDATE queue_entries SET position = position + 10001 WHERE queue_id = ?", (queue_id,)
        )
        conn.executemany(
            "UPDATE queue_entries SET position = ? WHERE queue_id = ? AND entry_id = ?",
            [(position, queue_id, entry_id) for position, entry_id in enumerate(entry_ids)],
        )

    def _playlist_before_edit(self, conn: sqlite3.Connection,
                              command: Dict[str, Any]) -> tuple[str, int]:
        playlist_id = command["playlistId"]
        row = conn.execute(
            "SELECT name, revision FROM playlists WHERE playlist_id = ?", (playlist_id,)
        ).fetchone()
        if row is None:
            raise _DomainRejection(
                "NOT_FOUND", {"objectType": "playlist", "objectId": playlist_id},
                "The requested playlist was not found.",
            )
        if row[1] != command["expectedRevision"]:
            raise _DomainRejection(
                "REVISION_CONFLICT",
                {"conflicts": [{
                    "objectType": "playlist", "objectId": playlist_id,
                    "expectedRevision": command["expectedRevision"],
                    "actualRevision": row[1],
                }]},
                "The playlist changed since it was read.",
            )
        return row[0], row[1]

    def _ensure_revision_available(self, playlist_id: str, revision: int,
                                   object_type: str = "playlist") -> None:
        if revision >= 9007199254740991:
            raise _DomainRejection(
                "REVISION_EXHAUSTED",
                {"objectType": object_type, "objectId": playlist_id},
                f"The {object_type} revision limit has been reached.",
            )

    def _reindex(self, conn: sqlite3.Connection, playlist_id: str, entry_ids: list[str]) -> None:
        # Move all positions out of the valid range first to avoid transient UNIQUE collisions.
        conn.execute(
            "UPDATE playlist_entries SET position = position + 10001 WHERE playlist_id = ?",
            (playlist_id,),
        )
        conn.executemany(
            "UPDATE playlist_entries SET position = ? WHERE playlist_id = ? AND entry_id = ?",
            [(position, playlist_id, entry_id) for position, entry_id in enumerate(entry_ids)],
        )

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

    def _decode_stored(self, request_value: str, result_value: str, command_id: str) -> Dict[str, Any]:
        try:
            request = json.loads(request_value)
            if not isinstance(request, dict) or request.get("commandId") != command_id:
                raise ValueError()
            action = request.get("action")
            if action in {"PLAYBACK_START", "PLAYBACK_STOP"}:
                parsed_request = validate_playback_command(request)
                result = validate_playback_command_result(json.loads(result_value))
            else:
                parsed_request = validate_command(request)
                result = validate_command_result(json.loads(result_value))
            if result["commandId"] != command_id or result["action"] != parsed_request["action"]:
                raise ValueError()
            if action in {"PLAYBACK_START", "PLAYBACK_STOP"}:
                self._validate_intent_link(command_id, result)
            else:
                self._validate_no_intent_link(command_id)
            return result
        except Exception:
            raise _store_error("STORE_UNAVAILABLE", "COMMAND_GET") from None

    def _validate_intent_link(self, command_id: str, result: Dict[str, Any]) -> None:
        conn = self._connect("COMMAND_GET")
        try:
            row = conn.execute(
                "SELECT intent_id,intent_sequence,state,queue_id,entry_id "
                "FROM playback_intents WHERE command_id=?", (command_id,),
            ).fetchone()
            if result["status"] == "REJECTED":
                if row is not None:
                    raise ValueError()
                return
            if row is None:
                raise ValueError()
            body = result["result"]
            selection = body["selection"]
            expected = (
                body["intentId"], body["intentSequence"], "PENDING",
                selection["queueId"] if selection else None,
                selection["entry"]["entryId"] if selection else None,
            )
            if row != expected:
                raise ValueError()
        finally:
            conn.close()

    def _validate_no_intent_link(self, command_id: str) -> None:
        conn = self._connect("COMMAND_GET")
        try:
            row = conn.execute(
                "SELECT 1 FROM playback_intents WHERE command_id=?", (command_id,),
            ).fetchone()
            if row is not None:
                raise ValueError()
        finally:
            conn.close()

    def _oldest_pin(self, conn: sqlite3.Connection, queue_id: str, entry_id: Optional[str] = None) -> Optional[str]:
        sql = "SELECT entry_id FROM playback_intents WHERE queue_id=? AND state='PENDING'"
        args = [queue_id]
        if entry_id is not None:
            sql += " AND entry_id=?"
            args.append(entry_id)
        sql += " ORDER BY intent_sequence LIMIT 1"
        row = conn.execute(sql, args).fetchone()
        return row[0] if row else None

    def _write_playback_result(self, conn: sqlite3.Connection, command_id: str, result: Dict[str, Any]) -> None:
        validated = validate_playback_command_result(result)
        conn.execute(
            "UPDATE command_log SET result_json=? WHERE command_id=?",
            (_canonical_json(validated), command_id),
        )

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
                CREATE TABLE IF NOT EXISTS queues (
                    queue_id TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL CHECK (revision >= 0),
                    source_playlist_id TEXT,
                    source_playlist_revision INTEGER CHECK (
                        source_playlist_revision IS NULL OR source_playlist_revision >= 0
                    ),
                    current_entry_id TEXT,
                    repeat_mode TEXT NOT NULL CHECK (repeat_mode IN ('OFF', 'ALL', 'ONE')),
                    shuffle_mode TEXT NOT NULL CHECK (shuffle_mode IN ('OFF', 'ON')),
                    CHECK ((source_playlist_id IS NULL) = (source_playlist_revision IS NULL))
                );
                CREATE TABLE IF NOT EXISTS queue_entries (
                    entry_id TEXT PRIMARY KEY,
                    queue_id TEXT NOT NULL REFERENCES queues(queue_id) ON DELETE CASCADE,
                    source_entry_id TEXT,
                    media_ref_json TEXT NOT NULL,
                    title TEXT NOT NULL,
                    position INTEGER NOT NULL CHECK (position >= 0),
                    UNIQUE (queue_id, position)
                );
                CREATE TABLE IF NOT EXISTS playback_intents (
                    command_id TEXT PRIMARY KEY REFERENCES command_log(command_id),
                    intent_id TEXT NOT NULL UNIQUE,
                    intent_sequence INTEGER NOT NULL UNIQUE CHECK(intent_sequence BETWEEN 1 AND 9007199254740991),
                    state TEXT NOT NULL CHECK(state='PENDING'),
                    queue_id TEXT,
                    entry_id TEXT,
                    CHECK ((queue_id IS NULL) = (entry_id IS NULL))
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

    def _playback_rejected(self, command: Dict[str, Any], code: str,
                           details: Dict[str, Any], message: str) -> Dict[str, Any]:
        error = {"code": code, "message": message, "retryable": code == "STORE_BUSY",
                 "operation": "PLAYBACK_ADMIT", "details": details}
        return validate_playback_command_result({
            "contractVersion": 1, "commandId": command["commandId"],
            "action": command["action"], "status": "REJECTED", "error": error,
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

"""Independent regressions for additive SQLite schema and queue snapshots."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from components.playlists.store import PlaylistStore


LOCAL = {"kind": "LOCAL", "libraryId": "q01_synthetic_media"}
P03A2_SCHEMA_DDL = """
CREATE TABLE playlists (
    playlist_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 0)
);
CREATE TABLE playlist_entries (
    entry_id TEXT PRIMARY KEY,
    playlist_id TEXT NOT NULL REFERENCES playlists(playlist_id) ON DELETE CASCADE,
    media_ref_json TEXT NOT NULL,
    title TEXT NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    UNIQUE (playlist_id, position)
);
CREATE TABLE command_log (
    command_id TEXT PRIMARY KEY,
    request_json TEXT NOT NULL,
    result_json TEXT
);
"""


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_command(command_id, action, **fields):
    return {"contractVersion": 1, "commandId": command_id, "action": action, **fields}


class StoreRegressionTests(unittest.TestCase):
    def test_p03a2_database_upgrades_additively_and_replays_saved_result(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "legacy.sqlite3"
            playlist_id = "pl_from_p03a2"
            entry_id = "pe_from_p03a2"
            command = write_command(
                "legacy_create_command",
                "PLAYLIST_CREATE",
                name="Legacy synthetic playlist",
                items=[{"mediaRef": LOCAL, "title": "Legacy synthetic title"}],
            )
            snapshot = {
                "contractVersion": 1,
                "playlistId": playlist_id,
                "name": command["name"],
                "revision": 0,
                "entries": [{
                    "entryId": entry_id,
                    "mediaRef": LOCAL,
                    "title": command["items"][0]["title"],
                    "position": 0,
                }],
            }
            result = {
                "contractVersion": 1,
                "commandId": command["commandId"],
                "action": command["action"],
                "status": "APPLIED",
                "result": {"playlist": snapshot},
            }

            with closing(sqlite3.connect(db_path)) as conn:
                conn.executescript(P03A2_SCHEMA_DDL)
                conn.execute(
                    "INSERT INTO playlists (playlist_id, name, revision) VALUES (?, ?, ?)",
                    (playlist_id, snapshot["name"], snapshot["revision"]),
                )
                conn.execute(
                    "INSERT INTO playlist_entries "
                    "(entry_id, playlist_id, media_ref_json, title, position) VALUES (?, ?, ?, ?, ?)",
                    (entry_id, playlist_id, canonical_json(LOCAL), snapshot["entries"][0]["title"], 0),
                )
                conn.execute(
                    "INSERT INTO command_log (command_id, request_json, result_json) VALUES (?, ?, ?)",
                    (command["commandId"], canonical_json(command), canonical_json(result)),
                )
                conn.commit()

            with closing(sqlite3.connect(db_path)) as conn:
                old_tables = {row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )}
            self.assertTrue({"playlists", "playlist_entries", "command_log"}.issubset(old_tables))
            self.assertNotIn("queues", old_tables)
            self.assertNotIn("queue_entries", old_tables)

            store = PlaylistStore(db_path)
            self.assertEqual(snapshot, store.get_playlist(playlist_id))
            self.assertEqual(result, store.get_command(command["commandId"]))
            self.assertEqual(result, store.execute(command))
            self.assertEqual(1, len(store.list_playlists()["playlists"]))

            with closing(sqlite3.connect(db_path)) as conn:
                upgraded_tables = {row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )}
            self.assertTrue({"queues", "queue_entries"}.issubset(upgraded_tables))

            queue_result = store.execute(write_command(
                "queue_after_upgrade", "QUEUE_CREATE", items=[],
            ))
            queue = queue_result["result"]["queue"]
            loaded = store.execute(write_command(
                "load_legacy_playlist", "QUEUE_LOAD_PLAYLIST",
                queueId=queue["queueId"], expectedQueueRevision=0,
                playlistId=playlist_id, expectedPlaylistRevision=snapshot["revision"],
            ))
            loaded_queue = loaded["result"]["queue"]
            self.assertEqual(playlist_id, loaded_queue["sourcePlaylistId"])
            self.assertEqual(["Legacy synthetic title"], [item["title"] for item in loaded_queue["entries"]])

            appended = store.execute(write_command(
                "append_after_upgrade", "QUEUE_APPEND", queueId=queue["queueId"],
                expectedRevision=loaded_queue["revision"],
                items=[{"mediaRef": LOCAL, "title": "Appended synthetic title"}],
            ))
            self.assertEqual("APPLIED", appended["status"])
            self.assertEqual(2, len(store.get_queue(queue["queueId"])["entries"]))

    def test_get_queue_keeps_old_wal_snapshot_when_append_commits_before_entry_read(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "queue_wal.sqlite3"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("PRAGMA journal_mode = WAL")

            store = PlaylistStore(db_path)
            created = store.execute(write_command(
                "wal_queue_create", "QUEUE_CREATE",
                items=[{"mediaRef": LOCAL, "title": "Before append"}],
            ))
            queue = created["result"]["queue"]
            interleavings = []
            writer_errors = []
            original_connect = store._connect

            def interleave_before_entry_query(sql):
                normalized = sql.lstrip().upper()
                if normalized.startswith("SELECT ENTRY_ID, SOURCE_ENTRY_ID, MEDIA_REF_JSON, TITLE, POSITION"):
                    if interleavings:
                        return
                    interleavings.append("entry-query")
                    try:
                        interleavings.append(store.execute(write_command(
                            "wal_concurrent_append", "QUEUE_APPEND",
                            queueId=queue["queueId"], expectedRevision=queue["revision"],
                            items=[{"mediaRef": LOCAL, "title": "Committed during read"}],
                        )))
                    except Exception as exc:
                        writer_errors.append(exc)

            def connect_with_trace(operation):
                conn = original_connect(operation)
                if operation == "QUEUE_GET":
                    conn.set_trace_callback(interleave_before_entry_query)
                return conn

            store._connect = connect_with_trace
            old_snapshot = store.get_queue(queue["queueId"])
            store._connect = original_connect

            self.assertEqual([], writer_errors)
            self.assertEqual("entry-query", interleavings[0])
            self.assertEqual("APPLIED", interleavings[1]["status"])
            self.assertEqual(queue["revision"], old_snapshot["revision"])
            self.assertEqual(["Before append"], [item["title"] for item in old_snapshot["entries"]])

            new_snapshot = store.get_queue(queue["queueId"])
            self.assertEqual(queue["revision"] + 1, new_snapshot["revision"])
            self.assertEqual(
                ["Before append", "Committed during read"],
                [item["title"] for item in new_snapshot["entries"]],
            )


if __name__ == "__main__":
    unittest.main()

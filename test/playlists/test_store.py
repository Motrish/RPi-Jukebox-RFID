"""Behavioral tests for the first transport-free SQLite playlist store slice."""
import copy
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

from components.playlists.store import PlaylistStore, StoreError  # noqa: E402
from jukebox.contracts.v1 import ContractValidationError  # noqa: E402


LOCAL = {"kind": "LOCAL", "libraryId": "synthetic_library"}


def create(command_id="cmd_create", *, name="Stories", items=None):
    return {
        "contractVersion": 1,
        "commandId": command_id,
        "action": "PLAYLIST_CREATE",
        "name": name,
        "items": copy.deepcopy(items if items is not None else [
            {"mediaRef": LOCAL, "title": "First"},
            {"mediaRef": LOCAL, "title": "First again"},
        ]),
    }


def append(command_id, playlist_id, revision, items):
    return {
        "contractVersion": 1,
        "commandId": command_id,
        "action": "PLAYLIST_APPEND",
        "playlistId": playlist_id,
        "expectedRevision": revision,
        "items": copy.deepcopy(items),
    }


class PlaylistStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = PlaylistStore(Path(self.tmp.name) / "playlists.sqlite3")

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_and_append_keep_order_duplicate_media_and_revision(self):
        first = self.store.execute(create())
        self.assertEqual("APPLIED", first["status"])
        snapshot = first["result"]["playlist"]
        playlist_id = snapshot["playlistId"]
        self.assertEqual(0, snapshot["revision"])
        self.assertEqual([0, 1], [entry["position"] for entry in snapshot["entries"]])
        self.assertEqual(2, len({entry["entryId"] for entry in snapshot["entries"]}))
        self.assertEqual(snapshot["entries"][0]["mediaRef"], snapshot["entries"][1]["mediaRef"])

        appended = self.store.execute(append(
            "cmd_append", playlist_id, 0,
            [{"mediaRef": LOCAL, "title": "Third"}],
        ))
        updated = appended["result"]["playlist"]
        self.assertEqual(1, updated["revision"])
        self.assertEqual([0, 1, 2], [entry["position"] for entry in updated["entries"]])
        self.assertEqual("Third", updated["entries"][2]["title"])

        loaded = self.store.get_playlist(playlist_id)
        self.assertEqual(updated, loaded)

    def test_same_command_replays_original_result_and_command_get_returns_it(self):
        command = create()
        original = self.store.execute(command)
        replay = self.store.execute(command)
        self.assertEqual(original, replay)
        self.assertEqual(original, self.store.get_command("cmd_create"))

    def test_concurrent_same_command_id_applies_only_once(self):
        command = create()
        with ThreadPoolExecutor(max_workers=2) as workers:
            first, second = list(workers.map(self.store.execute, (command, command)))

        self.assertEqual(first, second)
        playlist = self.store.get_playlist(first["result"]["playlist"]["playlistId"])
        self.assertEqual(2, len(playlist["entries"]))
        self.assertEqual(first, self.store.get_command("cmd_create"))

    def test_same_command_id_with_different_payload_does_not_mutate(self):
        original = self.store.execute(create())
        altered = self.store.execute(create(name="Changed"))
        self.assertEqual("REJECTED", altered["status"])
        self.assertEqual("COMMAND_ID_REUSED", altered["error"]["code"])
        snapshot = self.store.get_playlist(original["result"]["playlist"]["playlistId"])
        self.assertEqual("Stories", snapshot["name"])
        self.assertEqual(original, self.store.get_command("cmd_create"))

    def test_stale_revision_rejection_is_persisted_and_replayed(self):
        created = self.store.execute(create(items=[]))
        playlist_id = created["result"]["playlist"]["playlistId"]
        self.store.execute(append("cmd_ok", playlist_id, 0, [{"mediaRef": LOCAL, "title": "One"}]))

        stale = append("cmd_stale", playlist_id, 0, [{"mediaRef": LOCAL, "title": "Two"}])
        rejected = self.store.execute(stale)
        self.assertEqual("REJECTED", rejected["status"])
        self.assertEqual("REVISION_CONFLICT", rejected["error"]["code"])
        conflict = rejected["error"]["details"]["conflicts"][0]
        self.assertEqual(0, conflict["expectedRevision"])
        self.assertEqual(1, conflict["actualRevision"])

        self.store.execute(append("cmd_ok2", playlist_id, 1, [{"mediaRef": LOCAL, "title": "Three"}]))
        self.assertEqual(rejected, self.store.execute(stale))
        self.assertEqual(2, self.store.get_playlist(playlist_id)["revision"])

    def test_getters_raise_safe_error_mappings_for_missing_objects(self):
        with self.assertRaises(StoreError) as missing_playlist:
            self.store.get_playlist("missing_playlist")
        self.assertEqual("NOT_FOUND", missing_playlist.exception.error["code"])
        with self.assertRaises(StoreError) as missing_command:
            self.store.get_command("missing_command")
        self.assertEqual("COMMAND_NOT_FOUND", missing_command.exception.error["code"])

    def test_getters_validate_identifier_tokens_before_sqlite(self):
        for invalid in ([], {}, "../bad"):
            with self.subTest(identifier=invalid):
                with self.assertRaises(ContractValidationError):
                    self.store.get_playlist(invalid)
                with self.assertRaises(ContractValidationError):
                    self.store.get_command(invalid)

    def test_playlist_snapshot_uses_one_read_transaction_during_concurrent_append(self):
        created = self.store.execute(create(items=[{"mediaRef": LOCAL, "title": "Initial"}]))
        playlist_id = created["result"]["playlist"]["playlistId"]
        setup = sqlite3.connect(self.store._db_path)
        try:
            setup.execute("PRAGMA journal_mode = WAL")
        finally:
            setup.close()

        original_connect = self.store._connect
        connections = 0
        triggered = False

        class InterleavingConnection:
            def __init__(self, connection):
                self.connection = connection

            def execute(self, sql, parameters=()):
                nonlocal triggered
                if not triggered and "SELECT entry_id, media_ref_json" in sql:
                    triggered = True
                    self.store.execute(append(
                        "cmd_during_read", playlist_id, 0,
                        [{"mediaRef": LOCAL, "title": "Concurrent"}],
                    ))
                return self.connection.execute(sql, parameters)

            def close(self):
                self.connection.close()

            def commit(self):
                self.connection.commit()

            def rollback(self):
                self.connection.rollback()

        def connect_with_writer(operation):
            nonlocal connections
            connections += 1
            connection = original_connect(operation)
            return InterleavingConnection(connection) if connections == 1 else connection

        # Bind the store into the proxy without replacing production DB operations.
        InterleavingConnection.store = self.store
        with mock.patch.object(self.store, "_connect", side_effect=connect_with_writer):
            observed = self.store.get_playlist(playlist_id)

        self.assertTrue(triggered)
        self.assertEqual(0, observed["revision"])
        self.assertEqual(["Initial"], [entry["title"] for entry in observed["entries"]])
        current = self.store.get_playlist(playlist_id)
        self.assertEqual(1, current["revision"])
        self.assertEqual(["Initial", "Concurrent"], [entry["title"] for entry in current["entries"]])

    def test_existing_command_without_result_is_store_unavailable(self):
        self.store.execute(create())
        db = sqlite3.connect(self.store._db_path)
        try:
            db.execute("UPDATE command_log SET result_json = NULL WHERE command_id = ?", ("cmd_create",))
            db.commit()
        finally:
            db.close()

        with self.assertRaises(StoreError) as damaged:
            self.store.get_command("cmd_create")
        self.assertEqual("STORE_UNAVAILABLE", damaged.exception.error["code"])

    def test_exception_during_result_persistence_rolls_back_mutation_and_command_claim(self):
        command = create()
        with mock.patch.object(self.store, "_write_command_result", side_effect=RuntimeError("simulated interruption")):
            with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                self.store.execute(command)

        with self.assertRaises(StoreError) as no_command:
            self.store.get_command("cmd_create")
        self.assertEqual("COMMAND_NOT_FOUND", no_command.exception.error["code"])
        with self.assertRaises(StoreError) as no_playlist:
            self.store.get_playlist("any_generated_id")
        self.assertEqual("NOT_FOUND", no_playlist.exception.error["code"])

    def test_committed_but_lost_response_is_recoverable_by_same_command_id(self):
        command = create()
        durable = self.store.execute(command)  # Caller loses this response.
        recovered = self.store.execute(command)
        self.assertEqual(durable, recovered)
        self.assertEqual(durable["result"]["playlist"], self.store.get_playlist(
            durable["result"]["playlist"]["playlistId"]
        ))


if __name__ == "__main__":
    unittest.main()

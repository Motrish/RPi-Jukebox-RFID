"""Behavioral tests for transport-free SQLite queue persistence."""
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

from components.playlists.store import PlaylistStore, StoreError


LOCAL = {"kind": "LOCAL", "libraryId": "queue_fixture"}


def playlist_create(command_id="pl_create", items=None, name="Stories"):
    if items is None:
        items = [{"mediaRef": LOCAL, "title": title} for title in ("A", "B")]
    return {
        "contractVersion": 1, "commandId": command_id, "action": "PLAYLIST_CREATE",
        "name": name, "items": items,
    }


def queue_create(command_id="queue_create", items=None):
    if items is None:
        items = [{"mediaRef": LOCAL, "title": title} for title in ("A", "B")]
    return {"contractVersion": 1, "commandId": command_id, "action": "QUEUE_CREATE", "items": items}


def queue_command(command_id, action, **fields):
    return {"contractVersion": 1, "commandId": command_id, "action": action, **fields}


class QueueStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "jukebox.sqlite3"
        self.store = PlaylistStore(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def create_playlist(self, command_id="pl_create"):
        return self.store.execute(playlist_create(command_id))["result"]["playlist"]

    def create_queue(self, command_id="queue_create", items=None):
        return self.store.execute(queue_create(command_id, items))["result"]["queue"]

    def test_queue_create_duplicates_modes_revision_command_replay_and_reopen(self):
        items = [{"mediaRef": LOCAL, "title": title} for title in ("Same", "Middle", "Same")]
        command = queue_create("queue_create_dupes", items)
        result = self.store.execute(command)
        queue = result["result"]["queue"]
        self.assertEqual(0, queue["revision"])
        self.assertIsNone(queue["sourcePlaylistId"])
        self.assertIsNone(queue["sourcePlaylistRevision"])
        self.assertIsNone(queue["currentEntryId"])
        self.assertEqual("OFF", queue["repeatMode"])
        self.assertEqual("OFF", queue["shuffleMode"])
        self.assertEqual([0, 1, 2], [item["position"] for item in queue["entries"]])
        self.assertEqual([None, None, None], [item["sourceEntryId"] for item in queue["entries"]])
        self.assertEqual(3, len({item["entryId"] for item in queue["entries"]}))
        self.assertEqual(queue["entries"][0]["mediaRef"], queue["entries"][2]["mediaRef"])
        self.assertEqual(result, self.store.execute(command))
        self.assertEqual(result, self.store.get_command("queue_create_dupes"))

        reopened = PlaylistStore(self.db_path)
        self.assertEqual(queue, reopened.get_queue(queue["queueId"]))
        self.assertEqual(queue, reopened.get_queue(queue["queueId"]))

    def test_playlist_data_and_command_ledger_survive_additive_queue_schema(self):
        playlist_result = self.store.execute(playlist_create("before_queue"))
        original = playlist_result["result"]["playlist"]
        queue = self.create_queue("queue_after_playlist", items=[])
        reopened = PlaylistStore(self.db_path)
        self.assertEqual(original, reopened.get_playlist(original["playlistId"]))
        self.assertEqual(playlist_result, reopened.get_command("before_queue"))
        self.assertEqual(queue, reopened.get_queue(queue["queueId"]))

    def test_get_queue_returns_safe_not_found(self):
        with self.assertRaises(StoreError) as missing:
            self.store.get_queue("q_does_not_exist")
        self.assertEqual("NOT_FOUND", missing.exception.error["code"])
        self.assertEqual("QUEUE_GET", missing.exception.error["operation"])

    def test_append_move_modes_current_keep_selection_and_revision_rules(self):
        queue = self.create_queue(items=[])
        queue_id = queue["queueId"]
        first = self.store.execute(queue_command(
            "q_append", "QUEUE_APPEND", queueId=queue_id, expectedRevision=0,
            items=[{"mediaRef": LOCAL, "title": title} for title in ("A", "B", "A")],
        ))["result"]["queue"]
        entry_ids = [item["entryId"] for item in first["entries"]]
        self.assertEqual(1, first["revision"])
        self.assertEqual([None, None, None], [item["sourceEntryId"] for item in first["entries"]])

        moved = self.store.execute(queue_command(
            "q_move", "QUEUE_MOVE", queueId=queue_id, expectedRevision=1,
            entryId=entry_ids[0], toPosition=2,
        ))["result"]["queue"]
        self.assertEqual([entry_ids[1], entry_ids[2], entry_ids[0]],
                         [item["entryId"] for item in moved["entries"]])
        self.assertEqual([0, 1, 2], [item["position"] for item in moved["entries"]])
        self.assertEqual(2, moved["revision"])

        noop_move = self.store.execute(queue_command(
            "q_move_noop", "QUEUE_MOVE", queueId=queue_id, expectedRevision=2,
            entryId=entry_ids[0], toPosition=2,
        ))["result"]["queue"]
        self.assertEqual(2, noop_move["revision"])
        out_of_range = self.store.execute(queue_command(
            "q_move_range", "QUEUE_MOVE", queueId=queue_id, expectedRevision=2,
            entryId=entry_ids[0], toPosition=3,
        ))
        self.assertEqual("POSITION_OUT_OF_RANGE", out_of_range["error"]["code"])
        self.assertEqual(out_of_range, self.store.get_command("q_move_range"))

        mode_result = self.store.execute(queue_command(
            "q_modes", "QUEUE_SET_MODES", queueId=queue_id, expectedRevision=2,
            repeatMode="ONE", shuffleMode="ON",
        ))["result"]["queue"]
        self.assertEqual(("ONE", "ON", 3),
                         (mode_result["repeatMode"], mode_result["shuffleMode"], mode_result["revision"]))
        selected = self.store.execute(queue_command(
            "q_current", "QUEUE_SET_CURRENT", queueId=queue_id, expectedRevision=3,
            entryId=entry_ids[2],
        ))["result"]["queue"]
        self.assertEqual(entry_ids[2], selected["currentEntryId"])
        self.assertEqual(4, selected["revision"])
        moved_selected = self.store.execute(queue_command(
            "q_move_selected", "QUEUE_MOVE", queueId=queue_id, expectedRevision=4,
            entryId=entry_ids[2], toPosition=0,
        ))["result"]["queue"]
        self.assertEqual(entry_ids[2], moved_selected["currentEntryId"])
        self.assertEqual(5, moved_selected["revision"])

    def test_noop_append_modes_and_current_keep_revision(self):
        queue = self.create_queue(items=[])
        queue_id = queue["queueId"]
        noop_append = self.store.execute(queue_command(
            "q_empty_append", "QUEUE_APPEND", queueId=queue_id, expectedRevision=0, items=[],
        ))["result"]["queue"]
        self.assertEqual(0, noop_append["revision"])
        noop_modes = self.store.execute(queue_command(
            "q_noop_modes", "QUEUE_SET_MODES", queueId=queue_id, expectedRevision=0,
            repeatMode="OFF", shuffleMode="OFF",
        ))["result"]["queue"]
        self.assertEqual(0, noop_modes["revision"])
        entry_id = self.store.execute(queue_command(
            "q_append_one", "QUEUE_APPEND", queueId=queue_id, expectedRevision=0,
            items=[{"mediaRef": LOCAL, "title": "Only"}],
        ))["result"]["queue"]["entries"][0]["entryId"]
        current = self.store.execute(queue_command(
            "q_set_current", "QUEUE_SET_CURRENT", queueId=queue_id, expectedRevision=1,
            entryId=entry_id,
        ))["result"]["queue"]
        repeated = self.store.execute(queue_command(
            "q_set_current_noop", "QUEUE_SET_CURRENT", queueId=queue_id, expectedRevision=2,
            entryId=entry_id,
        ))["result"]["queue"]
        self.assertEqual(2, current["revision"])
        self.assertEqual(2, repeated["revision"])

    def test_remove_one_duplicate_occurrence_reindexes_and_clears_selection(self):
        queue = self.create_queue(items=[
            {"mediaRef": LOCAL, "title": title} for title in ("Same", "Middle", "Same", "Last")
        ])
        ids = [item["entryId"] for item in queue["entries"]]
        selected = self.store.execute(queue_command(
            "remove_select", "QUEUE_SET_CURRENT", queueId=queue["queueId"],
            expectedRevision=0, entryId=ids[0],
        ))["result"]["queue"]
        removed = self.store.execute(queue_command(
            "remove_middle_duplicate", "QUEUE_REMOVE", queueId=queue["queueId"],
            expectedRevision=selected["revision"], entryId=ids[2],
        ))["result"]["queue"]
        self.assertEqual([ids[0], ids[1], ids[3]], [item["entryId"] for item in removed["entries"]])
        self.assertEqual([0, 1, 2], [item["position"] for item in removed["entries"]])
        self.assertEqual(ids[0], removed["currentEntryId"])
        self.assertEqual(2, removed["revision"])

        cleared = self.store.execute(queue_command(
            "remove_clear_selection", "QUEUE_SET_CURRENT", queueId=queue["queueId"],
            expectedRevision=removed["revision"], entryId=None,
        ))["result"]["queue"]
        self.assertIsNone(cleared["currentEntryId"])
        self.assertEqual(3, cleared["revision"])

    def test_active_entry_remove_and_load_are_persisted_rejections(self):
        queue = self.create_queue(items=[{"mediaRef": LOCAL, "title": "A"}])
        entry_id = queue["entries"][0]["entryId"]
        selected = self.store.execute(queue_command(
            "q_select", "QUEUE_SET_CURRENT", queueId=queue["queueId"], expectedRevision=0,
            entryId=entry_id,
        ))["result"]["queue"]
        remove = queue_command(
            "q_remove_active", "QUEUE_REMOVE", queueId=queue["queueId"],
            expectedRevision=selected["revision"], entryId=entry_id,
        )
        rejected_remove = self.store.execute(remove)
        self.assertEqual("ACTIVE_ENTRY_REQUIRES_CONTROLLER", rejected_remove["error"]["code"])
        self.assertEqual(rejected_remove, self.store.execute(remove))
        playlist = self.create_playlist()
        load = queue_command(
            "q_load_active", "QUEUE_LOAD_PLAYLIST", queueId=queue["queueId"],
            expectedQueueRevision=selected["revision"], playlistId=playlist["playlistId"],
            expectedPlaylistRevision=playlist["revision"],
        )
        rejected_load = self.store.execute(load)
        self.assertEqual("ACTIVE_ENTRY_REQUIRES_CONTROLLER", rejected_load["error"]["code"])
        self.assertEqual(rejected_load, self.store.execute(load))
        self.assertEqual(selected, self.store.get_queue(queue["queueId"]))

    def test_load_copies_exact_playlist_snapshot_and_replaces_queue(self):
        playlist = self.create_playlist()
        queue = self.create_queue(items=[{"mediaRef": LOCAL, "title": "discard me"}])
        configured = self.store.execute(queue_command(
            "q_configure_before_load", "QUEUE_SET_MODES", queueId=queue["queueId"],
            expectedRevision=0, repeatMode="ALL", shuffleMode="ON",
        ))["result"]["queue"]
        loaded = self.store.execute(queue_command(
            "q_load", "QUEUE_LOAD_PLAYLIST", queueId=queue["queueId"],
            expectedQueueRevision=configured["revision"],
            playlistId=playlist["playlistId"], expectedPlaylistRevision=playlist["revision"],
        ))["result"]["queue"]
        self.assertEqual(2, loaded["revision"])
        self.assertEqual(playlist["playlistId"], loaded["sourcePlaylistId"])
        self.assertEqual(playlist["revision"], loaded["sourcePlaylistRevision"])
        self.assertIsNone(loaded["currentEntryId"])
        self.assertEqual(("OFF", "OFF"), (loaded["repeatMode"], loaded["shuffleMode"]))
        self.assertEqual([e["title"] for e in playlist["entries"]], [e["title"] for e in loaded["entries"]])
        self.assertEqual([e["entryId"] for e in playlist["entries"]],
                         [e["sourceEntryId"] for e in loaded["entries"]])
        self.assertTrue(all(e["entryId"] != e["sourceEntryId"] for e in loaded["entries"]))
        self.assertEqual(playlist, self.store.get_playlist(playlist["playlistId"]))
        self.assertEqual(loaded, self.store.get_queue(queue["queueId"]))

    def test_load_checks_both_revisions_and_reports_both_conflicts_before_mutation(self):
        playlist = self.create_playlist()
        queue = self.create_queue(items=[])
        self.store.execute(queue_command(
            "bump_q", "QUEUE_APPEND", queueId=queue["queueId"], expectedRevision=0,
            items=[{"mediaRef": LOCAL, "title": "newer queue"}],
        ))
        self.store.execute(queue_command(
            "bump_p", "PLAYLIST_RENAME", playlistId=playlist["playlistId"],
            expectedRevision=playlist["revision"], name="Newer playlist",
        ))
        before_queue = self.store.get_queue(queue["queueId"])
        before_playlist = self.store.get_playlist(playlist["playlistId"])
        command = queue_command(
            "q_load_two_conflicts", "QUEUE_LOAD_PLAYLIST", queueId=queue["queueId"],
            expectedQueueRevision=0, playlistId=playlist["playlistId"], expectedPlaylistRevision=0,
        )
        result = self.store.execute(command)
        self.assertEqual("REVISION_CONFLICT", result["error"]["code"])
        self.assertEqual([
            {"objectType": "queue", "objectId": queue["queueId"], "expectedRevision": 0, "actualRevision": 1},
            {"objectType": "playlist", "objectId": playlist["playlistId"],
             "expectedRevision": 0, "actualRevision": 1},
        ], result["error"]["details"]["conflicts"])
        self.assertEqual(before_queue, self.store.get_queue(queue["queueId"]))
        self.assertEqual(before_playlist, self.store.get_playlist(playlist["playlistId"]))
        self.assertEqual(result, self.store.execute(command))

    def test_save_new_and_replace_playlist_copy_queue_with_fresh_ids(self):
        queue = self.create_queue(items=[{"mediaRef": LOCAL, "title": title} for title in ("X", "X", "Y")])
        new_result = self.store.execute(queue_command(
            "q_save_new", "QUEUE_SAVE_NEW_PLAYLIST", queueId=queue["queueId"],
            expectedQueueRevision=queue["revision"], name="Queue copy",
        ))
        saved = new_result["result"]["playlist"]
        self.assertEqual(0, saved["revision"])
        self.assertEqual([e["title"] for e in queue["entries"]], [e["title"] for e in saved["entries"]])
        self.assertTrue(all(e["entryId"] != source["entryId"]
                            for e, source in zip(saved["entries"], queue["entries"])))
        self.assertEqual(queue, self.store.get_queue(queue["queueId"]))

        target = self.create_playlist("target_playlist")
        replaced = self.store.execute(queue_command(
            "q_save_replace", "QUEUE_SAVE_PLAYLIST", queueId=queue["queueId"],
            expectedQueueRevision=queue["revision"], playlistId=target["playlistId"],
            expectedPlaylistRevision=target["revision"],
        ))["result"]["playlist"]
        self.assertEqual(target["name"], replaced["name"])
        self.assertEqual(target["revision"] + 1, replaced["revision"])
        self.assertEqual([e["title"] for e in queue["entries"]], [e["title"] for e in replaced["entries"]])
        self.assertTrue(all(e["entryId"] != source["entryId"]
                            for e, source in zip(replaced["entries"], queue["entries"])))
        self.assertEqual(queue, self.store.get_queue(queue["queueId"]))

    def test_save_replace_collects_both_revision_conflicts_and_mutates_neither(self):
        queue = self.create_queue(items=[])
        target = self.create_playlist()
        self.store.execute(queue_command(
            "save_bump_q", "QUEUE_APPEND", queueId=queue["queueId"], expectedRevision=0,
            items=[{"mediaRef": LOCAL, "title": "bump"}],
        ))
        self.store.execute(queue_command(
            "save_bump_p", "PLAYLIST_RENAME", playlistId=target["playlistId"],
            expectedRevision=target["revision"], name="bumped",
        ))
        before_q = self.store.get_queue(queue["queueId"])
        before_p = self.store.get_playlist(target["playlistId"])
        command = queue_command(
            "save_two_conflicts", "QUEUE_SAVE_PLAYLIST", queueId=queue["queueId"],
            expectedQueueRevision=0, playlistId=target["playlistId"], expectedPlaylistRevision=0,
        )
        result = self.store.execute(command)
        self.assertEqual("REVISION_CONFLICT", result["error"]["code"])
        self.assertEqual([
            {"objectType": "queue", "objectId": queue["queueId"], "expectedRevision": 0, "actualRevision": 1},
            {"objectType": "playlist", "objectId": target["playlistId"],
             "expectedRevision": 0, "actualRevision": 1},
        ], result["error"]["details"]["conflicts"])
        self.assertEqual(before_q, self.store.get_queue(queue["queueId"]))
        self.assertEqual(before_p, self.store.get_playlist(target["playlistId"]))

    def test_queue_and_playlist_revision_exhaustion_prevent_mutations(self):
        queue = self.create_queue(items=[{"mediaRef": LOCAL, "title": "entry"}])
        target = self.create_playlist()
        max_revision = 9007199254740991
        db = sqlite3.connect(self.db_path)
        try:
            db.execute("UPDATE queues SET revision = ? WHERE queue_id = ?", (max_revision, queue["queueId"]))
            db.execute("UPDATE playlists SET revision = ? WHERE playlist_id = ?",
                       (max_revision, target["playlistId"]))
            db.commit()
        finally:
            db.close()

        queue_change = self.store.execute(queue_command(
            "max_queue_modes", "QUEUE_SET_MODES", queueId=queue["queueId"],
            expectedRevision=max_revision, repeatMode="ALL", shuffleMode="ON",
        ))
        self.assertEqual("REVISION_EXHAUSTED", queue_change["error"]["code"])
        self.assertEqual("queue", queue_change["error"]["details"]["objectType"])
        playlist_change = self.store.execute(queue_command(
            "max_playlist_save", "QUEUE_SAVE_PLAYLIST", queueId=queue["queueId"],
            expectedQueueRevision=max_revision, playlistId=target["playlistId"],
            expectedPlaylistRevision=max_revision,
        ))
        self.assertEqual("REVISION_EXHAUSTED", playlist_change["error"]["code"])
        self.assertEqual("playlist", playlist_change["error"]["details"]["objectType"])

    def test_same_queue_command_id_concurrently_applies_once_and_payload_reuse_is_rejected(self):
        queue = self.create_queue(items=[])
        command = queue_command(
            "same_queue_append", "QUEUE_APPEND", queueId=queue["queueId"], expectedRevision=0,
            items=[{"mediaRef": LOCAL, "title": "Only once"}],
        )
        # Separate store objects share only the persistent database and command ledger.
        other = PlaylistStore(self.db_path)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda store: store.execute(command), (self.store, other)))
        self.assertEqual(results[0], results[1])
        queue_after = self.store.get_queue(queue["queueId"])
        self.assertEqual(1, queue_after["revision"])
        self.assertEqual(1, len(queue_after["entries"]))
        reused = dict(command, items=[{"mediaRef": LOCAL, "title": "Different payload"}])
        rejected = self.store.execute(reused)
        self.assertEqual("COMMAND_ID_REUSED", rejected["error"]["code"])
        self.assertEqual(1, len(self.store.get_queue(queue["queueId"])["entries"]))

    def test_queue_source_history_survives_playlist_deletion(self):
        playlist = self.create_playlist()
        queue = self.create_queue(items=[])
        loaded = self.store.execute(queue_command(
            "load_before_delete", "QUEUE_LOAD_PLAYLIST", queueId=queue["queueId"], expectedQueueRevision=0,
            playlistId=playlist["playlistId"], expectedPlaylistRevision=playlist["revision"],
        ))["result"]["queue"]
        deleted = self.store.execute({
            "contractVersion": 1, "commandId": "delete_source", "action": "PLAYLIST_DELETE",
            "playlistId": playlist["playlistId"], "expectedRevision": playlist["revision"],
        })
        self.assertEqual("APPLIED", deleted["status"])
        after = self.store.get_queue(queue["queueId"])
        self.assertEqual(loaded["sourcePlaylistId"], after["sourcePlaylistId"])
        self.assertEqual(loaded["sourcePlaylistRevision"], after["sourcePlaylistRevision"])
        self.assertEqual(loaded["entries"], after["entries"])

    def test_rollback_load_and_save_when_result_persistence_fails(self):
        playlist = self.create_playlist()
        queue = self.create_queue(items=[])
        original_queue = self.store.get_queue(queue["queueId"])
        load = queue_command(
            "rollback_load", "QUEUE_LOAD_PLAYLIST", queueId=queue["queueId"], expectedQueueRevision=0,
            playlistId=playlist["playlistId"], expectedPlaylistRevision=playlist["revision"],
        )
        with mock.patch.object(self.store, "_write_command_result", side_effect=sqlite3.OperationalError("injected")):
            with self.assertRaises(StoreError):
                self.store.execute(load)
        self.assertEqual(original_queue, self.store.get_queue(queue["queueId"]))
        with self.assertRaises(StoreError):
            self.store.get_command("rollback_load")

        target = self.create_playlist("rollback_target")
        original_target = self.store.get_playlist(target["playlistId"])
        new_save = queue_command(
            "rollback_new_save", "QUEUE_SAVE_NEW_PLAYLIST", queueId=queue["queueId"],
            expectedQueueRevision=0, name="Should rollback",
        )
        with mock.patch.object(self.store, "_write_command_result", side_effect=sqlite3.OperationalError("injected")):
            with self.assertRaises(StoreError):
                self.store.execute(new_save)
        self.assertEqual(original_target, self.store.get_playlist(target["playlistId"]))
        self.assertEqual(2, len(self.store.list_playlists()["playlists"]))
        with self.assertRaises(StoreError):
            self.store.get_command("rollback_new_save")

        save = queue_command(
            "rollback_save", "QUEUE_SAVE_PLAYLIST", queueId=queue["queueId"], expectedQueueRevision=0,
            playlistId=target["playlistId"], expectedPlaylistRevision=target["revision"],
        )
        with mock.patch.object(self.store, "_write_command_result", side_effect=sqlite3.OperationalError("injected")):
            with self.assertRaises(StoreError):
                self.store.execute(save)
        self.assertEqual(original_target, self.store.get_playlist(target["playlistId"]))
        with self.assertRaises(StoreError):
            self.store.get_command("rollback_save")

    def test_move_load_save_replay_preserve_generated_ids(self):
        playlist = self.create_playlist()
        queue = self.create_queue(items=[])
        load = queue_command(
            "replay_load", "QUEUE_LOAD_PLAYLIST", queueId=queue["queueId"], expectedQueueRevision=0,
            playlistId=playlist["playlistId"], expectedPlaylistRevision=playlist["revision"],
        )
        loaded = self.store.execute(load)
        self.assertEqual(loaded, self.store.execute(load))
        self.assertEqual(loaded, self.store.get_command("replay_load"))
        save = queue_command(
            "replay_save", "QUEUE_SAVE_NEW_PLAYLIST", queueId=queue["queueId"],
            expectedQueueRevision=loaded["result"]["queue"]["revision"], name="Replay copy",
        )
        saved = self.store.execute(save)
        self.assertEqual(saved, self.store.execute(save))
        self.assertEqual(saved, self.store.get_command("replay_save"))


if __name__ == "__main__":
    unittest.main()

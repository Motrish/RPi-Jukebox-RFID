"""SQLite-backed playback admission invariants."""
import json
import sqlite3
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

from components.playlists.store import PlaylistStore, StoreError

LOCAL = {"kind": "LOCAL", "libraryId": "test_media"}


def command(cid, action, **fields):
    return {"contractVersion": 1, "commandId": cid, "action": action, **fields}


def admit_from_independent_store(db_path, request):
    return PlaylistStore(db_path).admit_playback(request)


class PlaybackStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "store.sqlite3"
        self.store = PlaylistStore(self.path)
        self.queue_number = 0

    def tearDown(self):
        self.tmp.cleanup()

    def queue(self, items=None):
        self.queue_number += 1
        if items is None:
            items = [
                {"mediaRef": LOCAL, "title": "A"},
                {"mediaRef": LOCAL, "title": "B"},
            ]
        result = self.store.execute(command(
            "make_queue_%d" % self.queue_number, "QUEUE_CREATE", items=items,
        ))
        return result["result"]["queue"]

    def start(self, cid, queue, index=0, expected=None):
        return command(cid, "PLAYBACK_START", queueId=queue["queueId"],
                       expectedQueueRevision=queue["revision"] if expected is None else expected,
                       entryId=queue["entries"][index]["entryId"])

    def intent_rows(self):
        with closing(sqlite3.connect(self.path)) as conn:
            return conn.execute(
                "SELECT command_id,intent_id,intent_sequence,state,queue_id,entry_id "
                "FROM playback_intents ORDER BY intent_sequence",
            ).fetchall()

    def test_concurrent_distinct_admissions_sequence_and_retry(self):
        requests = [command("stop_%d" % n, "PLAYBACK_STOP") for n in range(8)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(
                lambda request: admit_from_independent_store(self.path, request), requests,
            ))
        self.assertTrue(all(r["status"] == "ACCEPTED" for r in results))
        ordered_sequences = [
            result["result"]["intentSequence"]
            for result in sorted(results, key=lambda item: item["result"]["intentSequence"])
        ]
        self.assertEqual(list(range(1, 9)), ordered_sequences)
        self.assertEqual(8, len(self.intent_rows()))
        before = self.intent_rows()
        self.assertEqual(results[0], self.store.admit_playback(requests[0]))
        self.assertEqual(before, self.intent_rows())

    def test_same_id_race_and_command_collision(self):
        request = command("same_id", "PLAYBACK_STOP")
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(
                lambda item: admit_from_independent_store(self.path, item), [request, request],
            ))
        self.assertEqual(results[0], results[1])
        self.assertEqual(1, len(self.intent_rows()))
        queue = self.queue()
        collision = self.store.admit_playback(self.start("same_id", queue, 0))
        self.assertEqual("COMMAND_ID_REUSED", collision["error"]["code"])
        self.assertEqual(results[0], self.store.get_command("same_id"))

    def test_different_requests_race_for_one_command_binding(self):
        queue = self.queue()
        requests = [command("race_id", "PLAYBACK_STOP"), self.start("race_id", queue, 0)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(
                lambda request: admit_from_independent_store(self.path, request), requests,
            ))
        self.assertEqual(["ACCEPTED", "REJECTED"], sorted(r["status"] for r in results))
        rejected = next(r for r in results if r["status"] == "REJECTED")
        self.assertEqual("COMMAND_ID_REUSED", rejected["error"]["code"])
        self.assertEqual(1, len(self.intent_rows()))

    def test_busy_does_not_bind_and_same_id_retry_succeeds(self):
        request = command("busy_retry", "PLAYBACK_STOP")
        blocker = sqlite3.connect(self.path, timeout=1, isolation_level=None)
        blocker.execute("BEGIN IMMEDIATE")
        errors = []
        try:
            try:
                self.store.admit_playback(request)
            except StoreError as exc:
                errors.append(exc)
            time.sleep(0.2)
        finally:
            blocker.rollback()
            blocker.close()
        self.assertEqual(1, len(errors))
        self.assertEqual("STORE_BUSY", errors[0].error["code"])
        self.assertEqual([], self.intent_rows())
        accepted = self.store.admit_playback(request)
        self.assertEqual("ACCEPTED", accepted["status"])

    def test_start_snapshot_selection_and_domain_rejections(self):
        queue = self.queue()
        accepted = self.store.admit_playback(self.start("start_a", queue, 1))
        self.assertEqual("ACCEPTED", accepted["status"])
        self.assertEqual(queue["revision"] + 1, accepted["result"]["selection"]["queueRevision"])
        self.assertEqual(1, accepted["result"]["selection"]["entry"]["position"])
        self.assertEqual(accepted["result"]["selection"]["entry"], self.store.get_queue(queue["queueId"])["entries"][1])
        stale = self.store.admit_playback(self.start("stale", queue, 0))
        self.assertEqual("REVISION_CONFLICT", stale["error"]["code"])
        with closing(sqlite3.connect(self.path)) as conn:
            self.assertEqual(1, conn.execute("SELECT count(*) FROM playback_intents").fetchone()[0])
        self.assertEqual(accepted, self.store.get_command("start_a"))

    def test_spotify_rejection_and_already_selected_start_preserve_revision(self):
        spotify = {
            "kind": "SPOTIFY",
            "uri": "spotify:track:0123456789012345678901",
        }
        queue = self.queue([{"mediaRef": spotify, "title": "Remote"}])
        denied = self.store.admit_playback(self.start("spotify_denied", queue))
        self.assertEqual("CAPABILITY_UNAVAILABLE", denied["error"]["code"])
        self.assertEqual(0, self.store.get_queue(queue["queueId"])["revision"])
        local = self.queue()
        self.store.admit_playback(self.start("select_once", local, 0))
        selected = self.store.get_queue(local["queueId"])
        again = self.store.admit_playback(self.start("select_again", selected, 0))
        self.assertEqual(selected["revision"], again["result"]["selection"]["queueRevision"])
        self.store.admit_playback(command("stop_does_not_clear", "PLAYBACK_STOP"))
        self.assertEqual(selected["currentEntryId"], self.store.get_queue(local["queueId"])["currentEntryId"])

    def test_failure_after_selection_rolls_back_and_retry_binds(self):
        queue = self.queue()
        request = self.start("rollback", queue, 1)
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute(
                "CREATE TRIGGER fail_intent BEFORE INSERT ON playback_intents "
                "BEGIN SELECT RAISE(ABORT,'injected'); END",
            )
            conn.commit()
        with self.assertRaises(StoreError):
            self.store.admit_playback(request)
        current = self.store.get_queue(queue["queueId"])
        self.assertEqual(queue["revision"], current["revision"])
        self.assertIsNone(current["currentEntryId"])
        self.assertEqual([], self.intent_rows())
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("DROP TRIGGER fail_intent")
        accepted = self.store.admit_playback(request)
        self.assertEqual(1, accepted["result"]["intentSequence"])

    def test_failure_writing_playback_result_rolls_back_and_retry_binds(self):
        queue = self.queue()
        request = self.start("fail_result", queue, 1)
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute(
                "CREATE TRIGGER fail_result BEFORE UPDATE OF result_json ON command_log "
                "WHEN NEW.command_id='fail_result' BEGIN SELECT RAISE(ABORT,'injected'); END",
            )
            conn.commit()
        with self.assertRaises(StoreError):
            self.store.admit_playback(request)
        with closing(sqlite3.connect(self.path)) as conn:
            row = conn.execute(
                "SELECT revision,current_entry_id FROM queues WHERE queue_id=?",
                (queue["queueId"],),
            ).fetchone()
            binding = conn.execute(
                "SELECT 1 FROM command_log WHERE command_id='fail_result'",
            ).fetchone()
        self.assertEqual((queue["revision"], None), row)
        self.assertIsNone(binding)
        self.assertEqual([], self.intent_rows())
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("DROP TRIGGER fail_result")
        self.assertEqual("ACCEPTED", self.store.admit_playback(request)["status"])

    def test_all_v1_actions_share_registry_and_cross_family_collisions(self):
        def run(request):
            result = self.store.execute(request)
            self.assertEqual(request["action"], result["action"])
            return result

        local_items = [
            {"mediaRef": LOCAL, "title": "One"},
            {"mediaRef": LOCAL, "title": "Two"},
            {"mediaRef": LOCAL, "title": "Three"},
        ]
        playlist = run(command(
            "data_playlist_create", "PLAYLIST_CREATE", name="Primary", items=local_items,
        ))["result"]["playlist"]
        playlist = run(command(
            "data_playlist_rename", "PLAYLIST_RENAME", playlistId=playlist["playlistId"],
            expectedRevision=playlist["revision"], name="Renamed",
        ))["result"]["playlist"]
        playlist = run(command(
            "data_playlist_append", "PLAYLIST_APPEND", playlistId=playlist["playlistId"],
            expectedRevision=playlist["revision"], items=[{"mediaRef": LOCAL, "title": "Four"}],
        ))["result"]["playlist"]
        playlist = run(command(
            "data_playlist_move", "PLAYLIST_MOVE", playlistId=playlist["playlistId"],
            expectedRevision=playlist["revision"], entryId=playlist["entries"][0]["entryId"],
            toPosition=1,
        ))["result"]["playlist"]
        removed_playlist_entry = playlist["entries"][2]["entryId"]
        playlist = run(command(
            "data_playlist_remove", "PLAYLIST_REMOVE", playlistId=playlist["playlistId"],
            expectedRevision=playlist["revision"], entryId=removed_playlist_entry,
        ))["result"]["playlist"]
        doomed = run(command(
            "data_playlist_for_delete", "PLAYLIST_CREATE", name="Delete me", items=[],
        ))["result"]["playlist"]
        run(command(
            "data_playlist_delete", "PLAYLIST_DELETE", playlistId=doomed["playlistId"],
            expectedRevision=doomed["revision"],
        ))
        queue = run(command(
            "data_queue_create", "QUEUE_CREATE", items=local_items[:2],
        ))["result"]["queue"]
        queue = run(command(
            "data_queue_load", "QUEUE_LOAD_PLAYLIST", queueId=queue["queueId"],
            expectedQueueRevision=queue["revision"], playlistId=playlist["playlistId"],
            expectedPlaylistRevision=playlist["revision"],
        ))["result"]["queue"]
        queue = run(command(
            "data_queue_append", "QUEUE_APPEND", queueId=queue["queueId"],
            expectedRevision=queue["revision"], items=[{"mediaRef": LOCAL, "title": "Five"}],
        ))["result"]["queue"]
        queue = run(command(
            "data_queue_move", "QUEUE_MOVE", queueId=queue["queueId"],
            expectedRevision=queue["revision"], entryId=queue["entries"][-1]["entryId"],
            toPosition=1,
        ))["result"]["queue"]
        queue = run(command(
            "data_queue_modes", "QUEUE_SET_MODES", queueId=queue["queueId"],
            expectedRevision=queue["revision"], repeatMode="ALL", shuffleMode="ON",
        ))["result"]["queue"]
        queue = run(command(
            "data_queue_current", "QUEUE_SET_CURRENT", queueId=queue["queueId"],
            expectedRevision=queue["revision"], entryId=queue["entries"][0]["entryId"],
        ))["result"]["queue"]
        removable = next(item["entryId"] for item in queue["entries"] if item["entryId"] != queue["currentEntryId"])
        queue = run(command(
            "data_queue_remove", "QUEUE_REMOVE", queueId=queue["queueId"],
            expectedRevision=queue["revision"], entryId=removable,
        ))["result"]["queue"]
        run(command(
            "data_queue_save_new", "QUEUE_SAVE_NEW_PLAYLIST", queueId=queue["queueId"],
            expectedQueueRevision=queue["revision"], name="Saved new",
        ))
        playlist = self.store.get_playlist(playlist["playlistId"])
        run(command(
            "data_queue_save", "QUEUE_SAVE_PLAYLIST", queueId=queue["queueId"],
            expectedQueueRevision=queue["revision"], playlistId=playlist["playlistId"],
            expectedPlaylistRevision=playlist["revision"],
        ))

        data_ids = [
            "data_playlist_create", "data_playlist_rename", "data_playlist_append",
            "data_playlist_move", "data_playlist_remove", "data_playlist_delete",
            "data_queue_create", "data_queue_load", "data_queue_append", "data_queue_move",
            "data_queue_modes", "data_queue_current", "data_queue_remove",
            "data_queue_save_new", "data_queue_save",
        ]
        self.assertEqual(15, len(data_ids))
        for command_id in data_ids:
            original = self.store.get_command(command_id)
            with closing(sqlite3.connect(self.path)) as conn:
                raw_before = conn.execute(
                    "SELECT request_json,result_json FROM command_log WHERE command_id=?",
                    (command_id,),
                ).fetchone()
            collision = self.store.admit_playback(command(command_id, "PLAYBACK_STOP"))
            self.assertEqual("COMMAND_ID_REUSED", collision["error"]["code"])
            self.assertEqual(original, self.store.get_command(command_id))
            with closing(sqlite3.connect(self.path)) as conn:
                raw_after = conn.execute(
                    "SELECT request_json,result_json FROM command_log WHERE command_id=?",
                    (command_id,),
                ).fetchone()
            self.assertEqual(raw_before, raw_after)

        bad_data = self.store.execute(command(
            "data_bound_rejection", "PLAYLIST_RENAME", playlistId="absent_playlist",
            expectedRevision=0, name="Missing",
        ))
        bad_playback = self.store.admit_playback(command(
            "playback_bound_rejection", "PLAYBACK_START", queueId="absent_queue",
            expectedQueueRevision=0, entryId="absent_entry",
        ))
        self.assertEqual("REJECTED", bad_data["status"])
        self.assertEqual("REJECTED", bad_playback["status"])
        playback_collision = self.store.admit_playback(command("data_bound_rejection", "PLAYBACK_STOP"))
        data_collision = self.store.execute(command(
            "playback_bound_rejection", "QUEUE_CREATE", items=[],
        ))
        self.assertEqual("COMMAND_ID_REUSED", playback_collision["error"]["code"])
        self.assertEqual("COMMAND_ID_REUSED", data_collision["error"]["code"])
        self.assertEqual(bad_data, self.store.get_command("data_bound_rejection"))
        self.assertEqual(bad_playback, self.store.get_command("playback_bound_rejection"))
        self.assertEqual([], self.intent_rows())

    def test_accepted_playback_ids_reject_v1_writes_without_mutating_originals(self):
        queue = self.queue()
        requests = [
            self.start("accepted_start_collision", queue, 0),
            command("accepted_stop_collision", "PLAYBACK_STOP"),
        ]
        for request in requests:
            with self.subTest(action=request["action"]):
                original = self.store.admit_playback(request)
                self.assertEqual("ACCEPTED", original["status"])
                with closing(sqlite3.connect(self.path)) as conn:
                    raw_before = conn.execute(
                        "SELECT request_json,result_json FROM command_log WHERE command_id=?",
                        (request["commandId"],),
                    ).fetchone()
                rows_before = self.intent_rows()

                attempted = self.store.execute(command(
                    request["commandId"], "QUEUE_CREATE", items=[],
                ))
                self.assertEqual("REJECTED", attempted["status"])
                self.assertEqual("COMMAND_ID_REUSED", attempted["error"]["code"])
                self.assertEqual("QUEUE_CREATE", attempted["action"])
                self.assertEqual(original, self.store.get_command(request["commandId"]))
                self.assertEqual(original, self.store.admit_playback(request))

                with closing(sqlite3.connect(self.path)) as conn:
                    raw_after = conn.execute(
                        "SELECT request_json,result_json FROM command_log WHERE command_id=?",
                        (request["commandId"],),
                    ).fetchone()
                self.assertEqual(raw_before, raw_after)
                self.assertEqual(rows_before, self.intent_rows())

    def test_pending_pin_survives_selection_changes_and_replacement(self):
        queue = self.queue()
        first = self.store.admit_playback(self.start("pin_a", queue, 0))
        selected = self.store.get_queue(queue["queueId"])
        clear = self.store.execute(command(
            "clear_selection", "QUEUE_SET_CURRENT", queueId=queue["queueId"],
            expectedRevision=selected["revision"], entryId=None,
        ))
        selected = clear["result"]["queue"]
        remove = self.store.execute(command(
            "remove_pinned", "QUEUE_REMOVE", queueId=queue["queueId"],
            expectedRevision=selected["revision"], entryId=queue["entries"][0]["entryId"],
        ))
        self.assertEqual("ACTIVE_ENTRY_REQUIRES_CONTROLLER", remove["error"]["code"])
        load = self.store.execute(command(
            "replace_queue", "QUEUE_LOAD_PLAYLIST", queueId=queue["queueId"],
            expectedQueueRevision=selected["revision"], playlistId="missing_playlist",
            expectedPlaylistRevision=0,
        ))
        # Missing playlist is checked before replacement guard by contract ordering.
        self.assertEqual("NOT_FOUND", load["error"]["code"])
        self.assertEqual(first, self.store.get_command("pin_a"))

    def test_multiple_pins_report_oldest_before_and_after_clearing_selection(self):
        queue = self.queue()
        first = self.store.admit_playback(self.start("old_pin", queue, 0))
        selected = self.store.get_queue(queue["queueId"])
        second = self.store.admit_playback(self.start("new_pin", selected, 1))
        self.assertEqual(2, second["result"]["intentSequence"])
        self.store.admit_playback(command("stop_keeps_pins", "PLAYBACK_STOP"))
        selected = self.store.get_queue(queue["queueId"])
        playlist = self.store.execute(command(
            "pin_target_playlist", "PLAYLIST_CREATE", name="Replacement target", items=[],
        ))["result"]["playlist"]
        for clear_selection in (False, True):
            if clear_selection:
                selected = self.store.execute(command(
                    "clear_new_pin", "QUEUE_SET_CURRENT", queueId=queue["queueId"],
                    expectedRevision=selected["revision"], entryId=None,
                ))["result"]["queue"]
            replacement = self.store.execute(command(
                "try_replace_%s" % clear_selection, "QUEUE_LOAD_PLAYLIST",
                queueId=queue["queueId"], expectedQueueRevision=selected["revision"],
                playlistId=playlist["playlistId"], expectedPlaylistRevision=playlist["revision"],
            ))
            self.assertEqual("ACTIVE_ENTRY_REQUIRES_CONTROLLER", replacement["error"]["code"])
            self.assertEqual(first["result"]["selection"]["entry"]["entryId"],
                             replacement["error"]["details"]["currentEntryId"])

    def test_pin_blocks_valid_replacement_and_sequence_exhaustion_is_durable(self):
        queue = self.queue()
        self.store.admit_playback(self.start("pin_replace", queue, 0))
        selected = self.store.get_queue(queue["queueId"])
        cleared = self.store.execute(command(
            "clear_for_replace", "QUEUE_SET_CURRENT", queueId=queue["queueId"],
            expectedRevision=selected["revision"], entryId=None,
        ))["result"]["queue"]
        playlist = self.store.execute(command(
            "replacement_playlist", "PLAYLIST_CREATE", name="Replacement", items=[],
        ))["result"]["playlist"]
        replacement = self.store.execute(command(
            "attempt_replace", "QUEUE_LOAD_PLAYLIST", queueId=queue["queueId"],
            expectedQueueRevision=cleared["revision"], playlistId=playlist["playlistId"],
            expectedPlaylistRevision=playlist["revision"],
        ))
        self.assertEqual("ACTIVE_ENTRY_REQUIRES_CONTROLLER", replacement["error"]["code"])
        self.assertEqual(queue["entries"][0]["entryId"], replacement["error"]["details"]["currentEntryId"])
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("UPDATE playback_intents SET intent_sequence=9007199254740991 WHERE command_id='pin_replace'")
            conn.commit()
        before = self.store.get_queue(queue["queueId"])
        start_exhausted = self.store.admit_playback(self.start("start_at_limit", before, 1))
        self.assertEqual("LIMIT_EXCEEDED", start_exhausted["error"]["code"])
        after = self.store.get_queue(queue["queueId"])
        self.assertEqual((before["revision"], before["currentEntryId"]), (after["revision"], after["currentEntryId"]))
        exhausted = self.store.admit_playback(command("at_limit", "PLAYBACK_STOP"))
        self.assertEqual("LIMIT_EXCEEDED", exhausted["error"]["code"])
        self.assertEqual(
            {"field": "playback.intentSequence", "limit": 9007199254740991},
            exhausted["error"]["details"],
        )
        self.assertEqual(exhausted, self.store.get_command("at_limit"))

    def test_additive_migration_and_corrupt_intent_link_fail_closed(self):
        queue = self.queue()
        accepted = self.store.admit_playback(self.start("corrupt_link", queue, 0))
        self.assertEqual(accepted, PlaylistStore(self.path).get_command("corrupt_link"))
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("UPDATE playback_intents SET intent_sequence=2 WHERE command_id='corrupt_link'")
            conn.commit()
        with self.assertRaises(StoreError) as caught:
            self.store.get_command("corrupt_link")
        self.assertEqual("STORE_UNAVAILABLE", caught.exception.error["code"])

    def test_mixed_start_stop_concurrency_and_replay(self):
        queues = [self.queue(), self.queue()]
        requests = [
            self.start("mixed_start_a", queues[0], 1),
            command("mixed_stop_a", "PLAYBACK_STOP"),
            self.start("mixed_start_b", queues[1], 0),
            command("mixed_stop_b", "PLAYBACK_STOP"),
        ]
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(
                lambda request: admit_from_independent_store(self.path, request), requests,
            ))
        self.assertTrue(all(item["status"] == "ACCEPTED" for item in results))
        self.assertEqual([1, 2, 3, 4], sorted(item["result"]["intentSequence"] for item in results))
        for request, result in zip(requests, results):
            self.assertEqual(result, self.store.admit_playback(request))
        for index in (0, 2):
            result = results[index]
            snapshot = result["result"]["selection"]
            queue = self.store.get_queue(snapshot["queueId"])
            self.assertEqual(snapshot["queueRevision"], queue["revision"])
            self.assertEqual(snapshot["entry"], queue["entries"][snapshot["entry"]["position"]])
            self.assertEqual(snapshot["entry"]["entryId"], queue["currentEntryId"])
        self.assertEqual(4, len(self.intent_rows()))

    def test_playlist_source_snapshot_is_historical_across_queue_data_edits(self):
        playlist = self.store.execute(command(
            "source_playlist", "PLAYLIST_CREATE", name="Source",
            items=[
                {"mediaRef": LOCAL, "title": "Original A"},
                {"mediaRef": LOCAL, "title": "Original B"},
                {"mediaRef": LOCAL, "title": "Original C"},
            ],
        ))["result"]["playlist"]
        queue_result = self.store.execute(command("source_queue", "QUEUE_CREATE", items=[]))
        queue = queue_result["result"]["queue"]
        loaded = self.store.execute(command(
            "load_source", "QUEUE_LOAD_PLAYLIST", queueId=queue["queueId"],
            expectedQueueRevision=0, playlistId=playlist["playlistId"],
            expectedPlaylistRevision=playlist["revision"],
        ))["result"]["queue"]
        first = loaded["entries"][0]
        self.assertIsNotNone(first["sourceEntryId"])
        accepted = self.store.admit_playback(self.start("historical_start", loaded, 0))
        snapshot = accepted["result"]["selection"]["entry"]
        self.assertEqual(first, snapshot)

        appended = self.store.execute(command(
            "append_after_start", "QUEUE_APPEND", queueId=queue["queueId"],
            expectedRevision=self.store.get_queue(queue["queueId"])["revision"],
            items=[{"mediaRef": LOCAL, "title": "Later D"}],
        ))["result"]["queue"]
        moved = self.store.execute(command(
            "move_after_start", "QUEUE_MOVE", queueId=queue["queueId"],
            expectedRevision=appended["revision"], entryId=appended["entries"][2]["entryId"],
            toPosition=1,
        ))["result"]["queue"]
        modes = self.store.execute(command(
            "modes_after_start", "QUEUE_SET_MODES", queueId=queue["queueId"],
            expectedRevision=moved["revision"], repeatMode="ALL", shuffleMode="ON",
        ))["result"]["queue"]
        unrelated = modes["entries"][-1]["entryId"]
        removed = self.store.execute(command(
            "remove_unrelated", "QUEUE_REMOVE", queueId=queue["queueId"],
            expectedRevision=modes["revision"], entryId=unrelated,
        ))
        self.assertEqual("APPLIED", removed["status"])
        self.assertEqual(accepted, self.store.get_command("historical_start"))

        current = self.store.get_queue(queue["queueId"])
        saved_new = self.store.execute(command(
            "save_new_after_start", "QUEUE_SAVE_NEW_PLAYLIST", queueId=queue["queueId"],
            expectedQueueRevision=current["revision"], name="Saved queue",
        ))
        self.assertEqual("APPLIED", saved_new["status"])
        current = self.store.get_queue(queue["queueId"])
        saved = self.store.execute(command(
            "save_after_start", "QUEUE_SAVE_PLAYLIST", queueId=queue["queueId"],
            expectedQueueRevision=current["revision"], playlistId=playlist["playlistId"],
            expectedPlaylistRevision=playlist["revision"],
        ))
        self.assertEqual("APPLIED", saved["status"])
        self.assertEqual(snapshot, self.store.get_command("historical_start")["result"]["selection"]["entry"])

    def test_sequence_last_value_and_consistent_retry_at_exhaustion(self):
        prior = self.store.admit_playback(command("prior_sequence", "PLAYBACK_STOP"))
        prior["result"]["intentSequence"] = 9007199254740990
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute(
                "UPDATE command_log SET result_json=? WHERE command_id='prior_sequence'",
                (json.dumps(prior, sort_keys=True, separators=(",", ":")),),
            )
            conn.execute(
                "UPDATE playback_intents SET intent_sequence=9007199254740990 "
                "WHERE command_id='prior_sequence'",
            )
            conn.commit()
        self.assertEqual(prior, self.store.get_command("prior_sequence"))
        last_request = command("last_sequence", "PLAYBACK_STOP")
        last = self.store.admit_playback(last_request)
        self.assertEqual(9007199254740991, last["result"]["intentSequence"])
        self.assertEqual(last, self.store.admit_playback(last_request))
        self.assertEqual(last, self.store.get_command("last_sequence"))
        overflow = self.store.admit_playback(command("overflow_sequence", "PLAYBACK_STOP"))
        self.assertEqual("LIMIT_EXCEEDED", overflow["error"]["code"])
        self.assertEqual(last, self.store.admit_playback(last_request))

    def test_persisted_start_rows_fail_safely_without_binding(self):
        corruptions = [
            ("not-json", "not JSON"),
            ("null-media", "null"),
            ("scalar-media", '"LOCAL"'),
            ("unknown-kind", '{"kind":"OTHER"}'),
            ("invalid-local", '{"kind":"LOCAL","libraryId":"bad value"}'),
        ]
        for name, media_json in corruptions:
            with self.subTest(name=name):
                queue = self.queue()
                entry_id = queue["entries"][1]["entryId"]
                with closing(sqlite3.connect(self.path)) as conn:
                    conn.execute(
                        "UPDATE queue_entries SET media_ref_json=? WHERE entry_id=?",
                        (media_json, entry_id),
                    )
                    conn.commit()
                request = self.start("corrupt_" + name, queue, 1)
                with self.assertRaises(StoreError) as caught:
                    self.store.admit_playback(request)
                self.assertEqual("STORE_UNAVAILABLE", caught.exception.error["code"])
                with closing(sqlite3.connect(self.path)) as conn:
                    current = conn.execute(
                        "SELECT revision,current_entry_id FROM queues WHERE queue_id=?",
                        (queue["queueId"],),
                    ).fetchone()
                    binding = conn.execute(
                        "SELECT 1 FROM command_log WHERE command_id=?",
                        (request["commandId"],),
                    ).fetchone()
                self.assertEqual((queue["revision"], None), current)
                self.assertIsNone(binding)
                self.assertEqual([], self.intent_rows())

    def test_missing_objects_and_selection_revision_exhaustion_are_durable(self):
        missing_queue = self.store.admit_playback(command(
            "missing_queue", "PLAYBACK_START", queueId="absent_queue",
            expectedQueueRevision=0, entryId="absent_entry",
        ))
        self.assertEqual("NOT_FOUND", missing_queue["error"]["code"])
        queue = self.queue()
        missing_entry = self.store.admit_playback(command(
            "missing_entry", "PLAYBACK_START", queueId=queue["queueId"],
            expectedQueueRevision=0, entryId="absent_entry",
        ))
        self.assertEqual("NOT_FOUND", missing_entry["error"]["code"])
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute(
                "UPDATE queues SET revision=9007199254740991 WHERE queue_id=?",
                (queue["queueId"],),
            )
            conn.commit()
        exhausted = self.store.admit_playback(self.start(
            "selection_revision_exhausted", queue, 1, expected=9007199254740991,
        ))
        self.assertEqual("REVISION_EXHAUSTED", exhausted["error"]["code"])
        self.assertEqual(3, len([missing_queue, missing_entry, exhausted]))
        with closing(sqlite3.connect(self.path)) as conn:
            self.assertEqual(0, conn.execute("SELECT count(*) FROM playback_intents").fetchone()[0])
            self.assertEqual(9007199254740991, conn.execute(
                "SELECT revision FROM queues WHERE queue_id=?", (queue["queueId"],),
            ).fetchone()[0])

    def test_linked_intent_decode_corruption_matrix(self):
        mutations = {
            "null_request": ("UPDATE command_log SET request_json='null' WHERE command_id=?", ()),
            "bad_request_json": ("UPDATE command_log SET request_json='{' WHERE command_id=?", ()),
            "request_identity": (
                "UPDATE command_log SET request_json=? WHERE command_id=?",
                (json.dumps(command("other_id", "PLAYBACK_STOP")),),
            ),
            "request_action": (
                "UPDATE command_log SET request_json=? WHERE command_id=?",
                (json.dumps(command("decode_case", "PLAYBACK_START", queueId="q", expectedQueueRevision=0, entryId="e")),),
            ),
            "null_result": ("UPDATE command_log SET result_json=NULL WHERE command_id=?", ()),
            "bad_result_json": ("UPDATE command_log SET result_json='{' WHERE command_id=?", ()),
            "result_identity": ("UPDATE command_log SET result_json=? WHERE command_id=?", ()),
            "result_action": ("UPDATE command_log SET result_json=? WHERE command_id=?", ()),
        }
        for name, (sql, extra) in mutations.items():
            with self.subTest(name=name):
                path = self.path.parent / (name + ".sqlite3")
                store = PlaylistStore(path)
                accepted = store.admit_playback(command("decode_case", "PLAYBACK_STOP"))
                values = extra
                if name == "request_identity":
                    values = (json.dumps(command("other_id", "PLAYBACK_STOP")),)
                elif name == "request_action":
                    values = (json.dumps(command(
                        "decode_case", "PLAYBACK_START", queueId="q",
                        expectedQueueRevision=0, entryId="e",
                    )),)
                elif name == "result_identity":
                    accepted["commandId"] = "other_id"
                    values = (json.dumps(accepted),)
                elif name == "result_action":
                    accepted["action"] = "PLAYBACK_START"
                    values = (json.dumps(accepted),)
                with closing(sqlite3.connect(path)) as conn:
                    conn.execute(sql, values + ("decode_case",))
                    conn.commit()
                with self.assertRaises(StoreError) as caught:
                    store.get_command("decode_case")
                self.assertEqual("STORE_UNAVAILABLE", caught.exception.error["code"])

        for name, sql in (
            ("missing_link", "DELETE FROM playback_intents WHERE command_id='decode_case'"),
            ("wrong_sequence", "UPDATE playback_intents SET intent_sequence=8 WHERE command_id='decode_case'"),
            ("wrong_intent_id", "UPDATE playback_intents SET intent_id='other_intent' WHERE command_id='decode_case'"),
            ("unknown_state", "UPDATE playback_intents SET state='BROKEN' WHERE command_id='decode_case'"),
        ):
            with self.subTest(link=name):
                path = self.path.parent / (name + ".sqlite3")
                store = PlaylistStore(path)
                store.admit_playback(command("decode_case", "PLAYBACK_STOP"))
                with closing(sqlite3.connect(path)) as conn:
                    if name == "unknown_state":
                        conn.execute("PRAGMA ignore_check_constraints=ON")
                    conn.execute(sql)
                    conn.commit()
                with self.assertRaises(StoreError) as caught:
                    store.get_command("decode_case")
                self.assertEqual("STORE_UNAVAILABLE", caught.exception.error["code"])

    def test_noncanonical_position_fails_without_binding(self):
        queue = self.queue()
        entry_id = queue["entries"][1]["entryId"]
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("UPDATE queue_entries SET position=7 WHERE entry_id=?", (entry_id,))
            conn.commit()
        request = self.start("wrong_position", queue, 1)
        with self.assertRaises(StoreError) as caught:
            self.store.admit_playback(request)
        self.assertEqual("STORE_UNAVAILABLE", caught.exception.error["code"])
        with closing(sqlite3.connect(self.path)) as conn:
            current = conn.execute(
                "SELECT revision,current_entry_id FROM queues WHERE queue_id=?",
                (queue["queueId"],),
            ).fetchone()
            binding = conn.execute(
                "SELECT 1 FROM command_log WHERE command_id=?", (request["commandId"],),
            ).fetchone()
        self.assertEqual((queue["revision"], None), current)
        self.assertIsNone(binding)
        self.assertEqual([], self.intent_rows())

    def test_v1_results_reject_linked_rows_and_playback_rejections_reject_links(self):
        data = self.store.execute(command("data_result", "PLAYLIST_CREATE", name="Data", items=[]))
        rejected_data = self.store.execute(command(
            "data_rejection", "PLAYLIST_RENAME", playlistId="missing_playlist",
            expectedRevision=0, name="No playlist",
        ))
        self.store.admit_playback(command("accepted_stop", "PLAYBACK_STOP"))
        rejected_stop = self.store.admit_playback(self.start("rejected_start", {
            "queueId": "missing_queue", "revision": 0,
            "entries": [{"entryId": "missing_entry"}],
        }))
        self.assertEqual("NOT_FOUND", rejected_stop["error"]["code"])
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute(
                "INSERT INTO playback_intents "
                "(command_id,intent_id,intent_sequence,state,queue_id,entry_id) "
                "VALUES ('rejected_start','bogus_intent',90,'PENDING',NULL,NULL)",
            )
            conn.commit()
        with self.assertRaises(StoreError) as caught:
            self.store.get_command("rejected_start")
        self.assertEqual("STORE_UNAVAILABLE", caught.exception.error["code"])
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("DELETE FROM playback_intents WHERE command_id='rejected_start'")
            conn.commit()
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.execute(
                "UPDATE playback_intents SET command_id='data_result' "
                "WHERE command_id='accepted_stop'",
            )
            conn.commit()
        with self.assertRaises(StoreError) as caught:
            self.store.get_command("data_result")
        self.assertEqual("STORE_UNAVAILABLE", caught.exception.error["code"])
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("UPDATE playback_intents SET command_id='accepted_stop' WHERE command_id='data_result'")
            conn.execute(
                "INSERT INTO playback_intents "
                "(command_id,intent_id,intent_sequence,state,queue_id,entry_id) "
                "VALUES ('data_rejection','bogus_data_intent',91,'PENDING',NULL,NULL)",
            )
            conn.commit()
        with self.assertRaises(StoreError) as caught:
            self.store.get_command("data_rejection")
        self.assertEqual("STORE_UNAVAILABLE", caught.exception.error["code"])
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("DELETE FROM playback_intents WHERE command_id='data_rejection'")
            conn.commit()
        with closing(sqlite3.connect(self.path)) as conn:
            conn.execute("DELETE FROM playback_intents WHERE command_id='accepted_stop'")
            conn.commit()
        with self.assertRaises(StoreError):
            self.store.get_command("accepted_stop")
        self.assertEqual(data, self.store.get_command("data_result"))
        self.assertEqual(rejected_data, self.store.get_command("data_rejection"))

    def test_populated_pre_c3b_database_migrates_without_rewriting_legacy_json(self):
        queue = self.queue()
        data = self.store.execute(command("legacy_queue", "QUEUE_CREATE", items=[
            {"mediaRef": LOCAL, "title": "Legacy"},
        ]))
        request = command("legacy_data", "PLAYLIST_CREATE", name="History", items=[])
        result = self.store.execute(request)
        with closing(sqlite3.connect(self.path)) as conn:
            raw_before = conn.execute(
                "SELECT request_json,result_json FROM command_log WHERE command_id='legacy_data'",
            ).fetchone()
            raw_queue_before = conn.execute(
                "SELECT request_json,result_json FROM command_log WHERE command_id='legacy_queue'",
            ).fetchone()
            conn.execute("DROP TABLE playback_intents")
            conn.commit()
        reopened = PlaylistStore(self.path)
        self.assertEqual(result, reopened.get_command("legacy_data"))
        self.assertEqual(result, reopened.execute(request))
        for _ in range(2):
            reopened = PlaylistStore(self.path)
        self.assertEqual(data["result"]["queue"], reopened.get_queue(data["result"]["queue"]["queueId"]))
        with closing(sqlite3.connect(self.path)) as conn:
            raw_after = conn.execute(
                "SELECT request_json,result_json FROM command_log WHERE command_id='legacy_data'",
            ).fetchone()
            raw_queue_after = conn.execute(
                "SELECT request_json,result_json FROM command_log WHERE command_id='legacy_queue'",
            ).fetchone()
        self.assertEqual(raw_before, raw_after)
        self.assertEqual(raw_queue_before, raw_queue_after)
        self.assertEqual("ACCEPTED", reopened.admit_playback(self.start("after_migration", queue, 0))["status"])


if __name__ == "__main__":
    unittest.main()

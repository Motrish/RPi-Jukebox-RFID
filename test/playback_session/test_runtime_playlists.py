"""Runtime boundary for durable playlist and queue operations."""

import tempfile
import threading
import time
import unittest
from pathlib import Path

from components.playlists.store import PlaylistStore
from components.playback_session.execution_gate import GateStateError
from components.playback_session.runtime import LocalPlaybackRuntime
from jukebox.contracts import ContractValidationError


class RuntimePlaylistTests(unittest.TestCase):
    def runtime(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        runtime = LocalPlaybackRuntime(
            database_path="/tmp/library.sqlite",
            library_root="/srv/audio",
            credential_path="/etc/mpd.secret",
            playlist_database_path="/tmp/playlists.sqlite",
        )
        runtime._phase, runtime._ready = "READY", True
        runtime._playlist_store = PlaylistStore(
            Path(temporary.name) / "playlists.sqlite"
        )
        return runtime

    def call(self, runtime, command):
        return runtime.playlist_dispatch(command, deadline=time.monotonic() + 3.0)

    def test_create_list_get_and_idempotent_replay(self):
        runtime = self.runtime()
        command = {"contractVersion": 1, "commandId": "make-playlist-1",
                   "action": "PLAYLIST_CREATE", "name": "Favorites", "items": []}
        first = self.call(runtime, command)
        again = self.call(runtime, command)
        self.assertEqual(first, again)
        playlist_id = first["result"]["playlist"]["playlistId"]
        self.assertEqual(playlist_id, runtime.playlist_get(
            playlist_id, deadline=time.monotonic() + 3.0
        )["playlistId"])
        listed = runtime.playlist_list(limit=50, cursor=None,
                                       deadline=time.monotonic() + 3.0)
        self.assertIn(playlist_id, [item["playlistId"] for item in listed["playlists"]])
        self.assertEqual(0, runtime._playlist_store.get_playlist(playlist_id)["revision"])

    def test_list_rejects_name_longer_than_v1_limit_and_releases_dispatch(self):
        runtime = self.runtime()

        class InvalidSummaryStore:
            def list_playlists(self, *, limit, cursor):
                return {"contractVersion": 1, "playlists": [{
                    "playlistId": "playlist-1", "name": "x" * 257, "revision": 0,
                }], "nextCursor": None}

        runtime._playlist_store = InvalidSummaryStore()
        with self.assertRaises((ContractValidationError, ValueError)):
            runtime.playlist_list(limit=50, cursor=None, deadline=time.monotonic() + 3.0)
        self.assertFalse(runtime._dispatch_active)

    def test_list_name_validation_matches_v1_whitespace_and_unicode_rules(self):
        runtime = self.runtime()
        playlist_id = self.call(runtime, {
            "contractVersion": 1, "commandId": "make-unicode-name",
            "action": "PLAYLIST_CREATE", "name": "  Café 音楽  ", "items": [],
        })["result"]["playlist"]["playlistId"]
        self.assertEqual("  Café 音楽  ", next(
            item["name"] for item in runtime.playlist_list(
                limit=50, cursor=None, deadline=time.monotonic() + 3.0
            )["playlists"] if item["playlistId"] == playlist_id
        ))

    def test_queue_create_and_get(self):
        runtime = self.runtime()
        result = self.call(runtime, {
            "contractVersion": 1, "commandId": "make-queue-1", "action": "QUEUE_CREATE",
            "items": [{"mediaRef": {"kind": "LOCAL", "libraryId": "track-1"},
                       "title": "Track"}],
        })
        queue_id = result["result"]["queue"]["queueId"]
        self.assertEqual(queue_id, runtime.queue_get(
            queue_id, deadline=time.monotonic() + 3.0
        )["queueId"])

    def test_internal_and_playback_actions_are_rejected_without_store_mutation(self):
        runtime = self.runtime()
        for action in ("QUEUE_SET_CURRENT", "PLAYBACK_START", "PLAYBACK_STOP"):
            with self.subTest(action=action):
                with self.assertRaises((GateStateError, ValueError)):
                    self.call(runtime, {"contractVersion": 1, "commandId": "blocked-" + action,
                                        "action": action})
        with self.assertRaises(Exception) as missing:
            runtime._playlist_store.get_command("blocked-QUEUE_SET_CURRENT")
        self.assertEqual("COMMAND_NOT_FOUND", missing.exception.error["code"])

    def test_missing_store_and_gate_states(self):
        runtime = self.runtime()
        runtime._playlist_store = None
        with self.assertRaises(GateStateError):
            runtime.playlist_list(limit=50, cursor=None, deadline=time.monotonic() + 2)
        runtime._playlist_store = PlaylistStore(
            Path(tempfile.mkdtemp()) / "unused.sqlite"
        )
        runtime._ready = False
        with self.assertRaises(GateStateError) as not_ready:
            runtime.playlist_list(limit=50, cursor=None, deadline=time.monotonic() + 2)
        self.assertEqual("NOT_READY", not_ready.exception.code)
        runtime._ready, runtime._phase = True, "CLOSING"
        with self.assertRaises(GateStateError) as closing:
            runtime.playlist_list(limit=50, cursor=None, deadline=time.monotonic() + 2)
        self.assertEqual("CLOSED", closing.exception.code)

    def test_expired_deadline_and_busy_admission(self):
        runtime = self.runtime()
        with self.assertRaises(GateStateError):
            runtime.playlist_list(limit=50, cursor=None, deadline=time.monotonic() - 1)
        runtime._dispatch_active = True
        with self.assertRaises(GateStateError) as busy:
            self.call(runtime, {"contractVersion": 1, "commandId": "busy-1",
                                "action": "PLAYLIST_CREATE", "name": "Busy", "items": []})
        self.assertEqual("BUSY", busy.exception.code)

    def test_shutdown_waits_for_active_store_io_and_io_does_not_hold_lock(self):
        runtime = self.runtime()
        entered, release, shutdown_done = threading.Event(), threading.Event(), threading.Event()
        store = runtime._playlist_store

        class BlockingStore:
            def execute(self, command):
                entered.set()
                if not release.wait(2):
                    raise AssertionError("store operation was not released")
                return store.execute(command)

            def __getattr__(self, name):
                return getattr(store, name)

        runtime._playlist_store = BlockingStore()
        outcome = {}

        def dispatch():
            try:
                outcome["result"] = self.call(runtime, {
                    "contractVersion": 1, "commandId": "barrier-1",
                    "action": "PLAYLIST_CREATE", "name": "Barrier", "items": [],
                })
            except Exception as error:
                outcome["error"] = error

        worker = threading.Thread(target=dispatch)
        worker.start()
        try:
            self.assertTrue(entered.wait(1))
            shutdown = threading.Thread(
                target=lambda: (runtime.begin_shutdown(), shutdown_done.set())
            )
            shutdown.start()
            self.assertTrue(shutdown_done.wait(1), "shutdown blocked on store I/O")
            self.assertTrue(runtime._dispatch_active)
            state = runtime.finish_shutdown(deadline=time.monotonic() + 0.05)
            self.assertNotEqual("CLOSED", state["phase"])
            release.set()
            worker.join(2)
            shutdown.join(2)
        finally:
            release.set()
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertNotIn("error", outcome)
        self.assertFalse(runtime._dispatch_active)


if __name__ == "__main__":
    unittest.main()

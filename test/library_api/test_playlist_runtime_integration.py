"""Real HTTP-to-runtime-to-SQLite playlist integration and drain tests."""

import http.client
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src" / "jukebox"))

from components.library_api.runtime_http import LocalPlaybackHTTP  # noqa: E402
from components.library_api.server import make_read_authorizer  # noqa: E402
from components.playback_session.runtime import LocalPlaybackRuntime  # noqa: E402
from components.playback_session.execution_gate import GateStateError  # noqa: E402
from components.playlists.store import PlaylistStore, StoreError  # noqa: E402

_READ = "R" * 43
_WRITE = "W" * 43


class _Catalog:
    def list_media(self, limit=50, cursor=None):
        return {"items": [], "nextCursor": None}

    def get_media(self, library_id):
        raise AssertionError("catalog should not be used for playlists")

    def close(self):
        pass


class PlaylistRuntimeHTTPIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.runtime = LocalPlaybackRuntime(
            database_path="/tmp/library.sqlite", library_root="/srv/audio",
            credential_path="/etc/mpd.secret",
            playlist_database_path="/tmp/playlists.sqlite",
        )
        self.runtime._phase, self.runtime._ready = "READY", True
        self.store = PlaylistStore(Path(self._temporary.name) / "playlists.sqlite")
        self.runtime._playlist_store = self.store
        self.http = LocalPlaybackHTTP(
            self.runtime, _Catalog(), make_read_authorizer(_READ), 0,
            write_authorizer=lambda token: token == _WRITE,
        )
        self.addCleanup(self._finish)
        self.http.start()

    def _finish(self):
        self.runtime.begin_shutdown()
        self.http.begin_shutdown()
        self.assertTrue(self.http.finish_shutdown(deadline=time.monotonic() + 3))
        result = self.runtime.finish_shutdown(deadline=time.monotonic() + 3)
        self.assertEqual("CLOSED", result["phase"])
        thread = self.http._thread
        if thread is not None:
            thread.join(3)
            self.assertFalse(thread.is_alive())

    def _request(self, method, path, payload=None, token=_READ):
        host, port = self.http.address
        connection = http.client.HTTPConnection(host, port, timeout=4)
        body = b"" if payload is None else json.dumps(payload).encode("utf-8")
        try:
            connection.request(method, path, body=body, headers={
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json",
            })
            response = connection.getresponse()
            raw = response.read()
            return response.status, json.loads(raw.decode("utf-8")) if raw else None
        finally:
            connection.close()

    @staticmethod
    def _create(command_id="playlist-create"):
        return {"contractVersion": 1, "commandId": command_id,
                "action": "PLAYLIST_CREATE", "name": "Integration",
                "items": [{"mediaRef": {"kind": "LOCAL", "libraryId": "track-1"},
                           "title": "Track one"}]}

    def test_http_playlist_create_list_snapshot_and_replay_use_same_store(self):
        status, first = self._request("POST", "/api/playlist-commands",
                                      self._create(), _WRITE)
        self.assertEqual(200, status)
        playlist_id = first["result"]["playlist"]["playlistId"]
        status, listed = self._request("GET", "/api/playlists")
        self.assertEqual(200, status)
        self.assertIn(playlist_id, [row["playlistId"] for row in listed["playlists"]])
        status, snapshot = self._request("GET", "/api/playlists/" + playlist_id)
        self.assertEqual(200, status)
        self.assertEqual(playlist_id, snapshot["playlistId"])
        status, replay = self._request("POST", "/api/playlist-commands",
                                       self._create(), _WRITE)
        self.assertEqual(200, status)
        self.assertEqual(first, replay)
        self.assertEqual(0, self.store.get_playlist(playlist_id)["revision"])

    def test_http_queue_create_and_get_and_write_auth_boundary(self):
        command = {"contractVersion": 1, "commandId": "queue-create",
                   "action": "QUEUE_CREATE", "items": [
                       {"mediaRef": {"kind": "LOCAL", "libraryId": "track-1"}, "title": "One"},
                       {"mediaRef": {"kind": "LOCAL", "libraryId": "track-2"}, "title": "Two"},
                   ]}
        status, denied = self._request("POST", "/api/playlist-commands", command, _READ)
        self.assertEqual(401, status)
        status, created = self._request("POST", "/api/playlist-commands", command, _WRITE)
        self.assertEqual(200, status)
        queue_id = created["result"]["queue"]["queueId"]
        status, queue = self._request("GET", "/api/queues/" + queue_id)
        self.assertEqual(200, status)
        self.assertEqual(queue_id, queue["queueId"])
        self.assertEqual(2, len(queue["entries"]))

    def test_shutdown_drains_blocked_http_store_before_owner_release(self):
        entered, release = threading.Event(), threading.Event()
        original = self.store.execute

        def blocked(command):
            entered.set()
            if not release.wait(4):
                raise AssertionError("blocked store operation was not released")
            return original(command)

        self.store.execute = blocked
        outcome = {}

        def post():
            try:
                outcome["response"] = self._request(
                    "POST", "/api/playlist-commands", self._create("blocked-create"), _WRITE
                )
            except Exception as error:
                outcome["error"] = error

        worker = threading.Thread(target=post)
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            self.runtime.begin_shutdown()
            self.http.begin_shutdown()
            self.assertFalse(self.http.finish_shutdown(deadline=time.monotonic() + 0.05))
            self.assertNotEqual("CLOSED", self.runtime.snapshot().get("phase"))
            closing_command = self._create("closing-rejected")
            with self.assertRaises(GateStateError) as raised:
                self.runtime.playlist_dispatch(closing_command, deadline=time.monotonic() + 1)
            self.assertEqual("CLOSED", raised.exception.code)
            with self.assertRaises(StoreError) as missing:
                self.store.get_command("closing-rejected")
            self.assertEqual("COMMAND_NOT_FOUND", missing.exception.error["code"])
            self.assertNotEqual("CLOSED", self.runtime.finish_shutdown(
                deadline=time.monotonic() + 0.05)["phase"])
        finally:
            release.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertNotIn("error", outcome)
        self.assertEqual(401, outcome["response"][0])
        self.assertEqual("UNAUTHORIZED", outcome["response"][1]["error"]["code"])
        committed = self.store.get_command("blocked-create")
        playlist_id = committed["result"]["playlist"]["playlistId"]
        snapshot = self.store.get_playlist(playlist_id)
        self.assertEqual("Integration", snapshot["name"])
        self.assertEqual(0, snapshot["revision"])
        self.assertEqual(committed, self.store.execute(self._create("blocked-create")))
        self.assertTrue(self.http.finish_shutdown(deadline=time.monotonic() + 3))
        self.assertEqual("CLOSED", self.runtime.finish_shutdown(
            deadline=time.monotonic() + 3)["phase"])


if __name__ == "__main__":
    unittest.main()

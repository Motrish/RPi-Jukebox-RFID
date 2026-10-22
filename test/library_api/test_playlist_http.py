"""Black-box HTTP coverage for the playlist and queue API."""

import http.client
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "jukebox"))

from components.library_api.server import make_read_authorizer, make_server  # noqa: E402
from components.playlists.store import PlaylistStore  # noqa: E402

READ = "r" * 43
WRITE = "w" * 43
ITEM = {"mediaRef": {"kind": "LOCAL", "libraryId": "lib_test"}, "title": "Track"}


class PlaylistHTTP:
    def __init__(self, store, *, read_token=READ, write_token=WRITE,
                 write_authorizer=True, callbacks=None):
        self.store = store
        self.read_auth = make_read_authorizer(read_token)
        self.write_auth = (make_read_authorizer(write_token)
                           if write_authorizer else None)
        callbacks = callbacks or {}
        self.server = make_server(
            catalog=object(), read_authorizer=self.read_auth, port=0,
            playlist_list=callbacks.get("list", store.list_playlists),
            playlist_get=callbacks.get("get", store.get_playlist),
            queue_get=callbacks.get("queue", store.get_queue),
            playlist_dispatch=callbacks.get("dispatch", store.execute),
            write_authorizer=self.write_auth,
        )
        self.authority = "127.0.0.1:{}".format(self.server.server_address[1])
        self.origin = "http://" + self.authority
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method, target, token=READ, body=None, origin=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=3)
        try:
            data = None if body is None else json.dumps(body).encode("utf-8")
            headers = {"Host": self.authority, "Authorization": "Bearer " + token}
            if origin is not None:
                headers["Origin"] = origin
            if data is not None:
                headers["Content-Type"] = "application/json"
                headers["Content-Length"] = str(len(data))
            conn.request(method, target, body=data, headers=headers)
            response = conn.getresponse()
            payload = response.read()
            return response.status, json.loads(payload) if payload else None
        finally:
            conn.close()


class PlaylistHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = PlaylistStore(Path(self.temp.name) / "store.sqlite3")
        self.app = PlaylistHTTP(self.store)

    def tearDown(self):
        self.app.close()
        self.temp.cleanup()

    def post(self, command, token=WRITE):
        return self.app.request("POST", "/api/playlist-commands", token, command)

    @staticmethod
    def command(action, command_id, **fields):
        return {"contractVersion": 1, "commandId": command_id,
                "action": action, **fields}

    def test_write_and_read_tokens_are_separate_and_default_writer_is_denied(self):
        create = self.command("PLAYLIST_CREATE", "cmd_create", name="Mix", items=[])
        self.assertEqual(401, self.post(create, READ)[0])
        status, result = self.post(create)
        self.assertEqual(200, status)
        pid = result["result"]["playlist"]["playlistId"]
        self.assertEqual(401, self.app.request("GET", "/api/playlists", WRITE)[0])
        status, listing = self.app.request("GET", "/api/playlists")
        self.assertEqual(200, status)
        self.assertEqual(pid, listing["playlists"][0]["playlistId"])

        denied = PlaylistHTTP(self.store, write_authorizer=False)
        try:
            self.assertEqual(403, denied.request(
                "POST", "/api/playlist-commands", WRITE, create)[0])
        finally:
            denied.close()

    def test_create_list_get_and_same_command_replay_do_not_duplicate(self):
        command = self.command("PLAYLIST_CREATE", "cmd_once", name="Mix", items=[ITEM])
        status, first = self.post(command)
        self.assertEqual(200, status)
        snapshot = first["result"]["playlist"]
        self.assertEqual(first, self.post(command)[1])
        self.assertEqual(1, len(self.store.list_playlists()["playlists"]))
        self.assertEqual(snapshot, self.app.request(
            "GET", "/api/playlists/" + snapshot["playlistId"])[1])
        self.assertEqual(404, self.app.request("GET", "/api/queues/q_missing")[0])

    def test_public_v1_playlist_and_queue_actions_over_http(self):
        def send(action, **fields):
            command_id = "cmd_" + action.lower()
            status, response = self.post(self.command(action, command_id, **fields))
            self.assertEqual(200, status, action)
            self.assertEqual("APPLIED", response["status"], action)
            return response["result"]

        first_item = {**ITEM, "title": "First"}
        second_item = {**ITEM, "title": "Second"}
        third_item = {**ITEM, "title": "Third"}

        playlist = send("PLAYLIST_CREATE", name="Mix", items=[first_item, second_item])["playlist"]
        playlist_id = playlist["playlistId"]
        playlist = send("PLAYLIST_RENAME", playlistId=playlist_id,
                        expectedRevision=playlist["revision"], name="Renamed")["playlist"]
        playlist = send("PLAYLIST_APPEND", playlistId=playlist_id,
                        expectedRevision=playlist["revision"], items=[third_item])["playlist"]
        moved_playlist_entry = playlist["entries"][2]["entryId"]
        playlist = send("PLAYLIST_MOVE", playlistId=playlist_id,
                        expectedRevision=playlist["revision"], entryId=moved_playlist_entry,
                        toPosition=0)["playlist"]
        playlist = send("PLAYLIST_REMOVE", playlistId=playlist_id,
                        expectedRevision=playlist["revision"],
                        entryId=playlist["entries"][1]["entryId"])["playlist"]

        queue = send("QUEUE_CREATE", items=[first_item, second_item, third_item])["queue"]
        queue_id = queue["queueId"]
        queue = send("QUEUE_LOAD_PLAYLIST", queueId=queue_id,
                     expectedQueueRevision=queue["revision"], playlistId=playlist_id,
                     expectedPlaylistRevision=playlist["revision"])["queue"]
        queue = send("QUEUE_APPEND", queueId=queue_id, expectedRevision=queue["revision"],
                     items=[third_item])["queue"]
        moved_queue_entry = queue["entries"][2]["entryId"]
        queue = send("QUEUE_MOVE", queueId=queue_id, expectedRevision=queue["revision"],
                     entryId=moved_queue_entry, toPosition=0)["queue"]
        queue = send("QUEUE_REMOVE", queueId=queue_id, expectedRevision=queue["revision"],
                     entryId=queue["entries"][1]["entryId"])["queue"]
        queue = send("QUEUE_SET_MODES", queueId=queue_id, expectedRevision=queue["revision"],
                     repeatMode="ALL", shuffleMode="ON")["queue"]
        saved_playlist = send("QUEUE_SAVE_NEW_PLAYLIST", queueId=queue_id,
                              expectedQueueRevision=queue["revision"],
                              name="Queue copy")["playlist"]
        send("QUEUE_SAVE_PLAYLIST", queueId=queue_id,
             expectedQueueRevision=queue["revision"], playlistId=saved_playlist["playlistId"],
             expectedPlaylistRevision=saved_playlist["revision"])

        deleted = send("PLAYLIST_DELETE", playlistId=playlist_id,
                       expectedRevision=playlist["revision"])
        self.assertEqual(playlist_id, deleted["deletedPlaylistId"])
        self.assertEqual(playlist["revision"], deleted["deletedRevision"])

    def test_revision_conflict_is_a_stable_rejected_command_result(self):
        created = self.store.execute(self.command(
            "PLAYLIST_CREATE", "cmd_base", name="Mix", items=[]))
        playlist = created["result"]["playlist"]
        rename = self.command("PLAYLIST_RENAME", "cmd_stale", playlistId=playlist["playlistId"],
                              expectedRevision=9, name="stale")
        status, result = self.post(rename)
        self.assertEqual(200, status)
        self.assertEqual("REJECTED", result["status"])
        self.assertEqual(result, self.post(rename)[1])

    def test_invalid_body_query_and_origin_rejected_without_store_mutation(self):
        before = self.store.list_playlists()
        for target in ("/api/playlists?limit=01", "/api/playlists?limit=201",
                       "/api/playlists?limit=1&limit=2", "/api/playlists?unexpected=x"):
            self.assertEqual(400, self.app.request("GET", target)[0], target)
        self.assertEqual(400, self.app.request(
            "GET", "/api/playlists", origin="http://localhost")[0])
        self.assertEqual(400, self.app.request(
            "POST", "/api/playlist-commands", WRITE, {"action": "bad"})[0])
        self.assertEqual(before, self.store.list_playlists())

    def test_non_public_action_and_mismatched_dispatch_result_are_rejected(self):
        hidden = self.command("QUEUE_SET_CURRENT", "cmd_internal", queueId="q_missing",
                              expectedRevision=0, entryId=None)
        self.assertEqual(400, self.post(hidden)[0])
        app = PlaylistHTTP(self.store, callbacks={
            "dispatch": lambda command: {"contractVersion": 1, "commandId": "wrong",
                                         "action": command["action"], "status": "REJECTED",
                                         "error": {"code": "NOT_FOUND", "message": "missing",
                                                   "retryable": False,
                                                   "operation": command["action"], "details": {}}}
        })
        try:
            command = self.command("PLAYLIST_CREATE", "cmd_mismatch", name="x", items=[])
            self.assertEqual(503, app.request("POST", "/api/playlist-commands", WRITE, command)[0])
        finally:
            app.close()


if __name__ == "__main__":
    unittest.main()

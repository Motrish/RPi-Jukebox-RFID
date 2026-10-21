"""End-to-end loopback tests for HTTP-driven local playback dispatch."""

import http.client
import json
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from contextlib import closing
from pathlib import Path

_STAGE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_STAGE_ROOT / "src" / "jukebox"))

from components.library_api.runtime_http import LocalPlaybackHTTP  # noqa: E402
from components.library_api.server import make_read_authorizer  # noqa: E402
from components.playback_session.durable_dispatch import DurableDispatch  # noqa: E402
from components.playback_session.local_playback_service import (  # noqa: E402
    LocalPlaybackService,
)
from components.playback_session.runtime import LocalPlaybackRuntime  # noqa: E402
from components.playlists.store import PlaylistStore  # noqa: E402

_TOKEN = "A" * 43
_LOCAL = {"kind": "LOCAL", "libraryId": "test_media"}
_ITEMS = [
    {
        "libraryId": "lib_alpha",
        "displayName": "same-name.mp3",
        "availability": "AVAILABLE",
    },
]
_RESULT_KEYS = {"admission", "playback", "operation", "gate", "failure",
                "intentId", "executionId"}


class _Catalog:
    """Minimal valid read catalog fixture shaped like test_server.py."""

    def list_media(self, limit=50, cursor=None):
        return {"items": [dict(item) for item in _ITEMS], "nextCursor": None}

    def get_media(self, library_id):
        return dict(_ITEMS[0])

    def close(self):
        return None


class _Provider:
    """In-process playback provider; no MPD, no hardware."""

    def __init__(self):
        self.calls = []

    def start(self, media_ref, *, lease, deadline):
        self.calls.append("START")
        return self._receipt("START", lease["identity"], "CONFIRMED", "PLAYING", "1")

    def stop(self, *, lease, deadline):
        self.calls.append("STOP")
        return self._receipt("STOP", lease["identity"], "CONFIRMED", "STOPPED", None)

    @staticmethod
    def _receipt(operation, identity, outcome, state, songid):
        return {"provider": "LOCAL", "operation": operation,
                "identity": dict(identity), "outcome": outcome, "epoch": "ep1",
                "songid": songid, "state": state, "positionMs": None,
                "durationMs": None, "observedAtMonotonic": time.monotonic(),
                "error": None}


class _CleanupFailure(AssertionError):
    """Teardown defect: reported, never converted into a passing test."""


class PlaybackHttpIntegrationTests(unittest.TestCase):
    """Real runtime/service/bridge/store behind the real HTTP helper."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store_path = str(Path(self._tmp.name) / "store.sqlite3")
        self.store = PlaylistStore(self.store_path)
        self.provider = _Provider()
        self.service = LocalPlaybackService(provider=self.provider,
                                            boot_id="e2e_boot",
                                            monotonic=time.monotonic)
        self.runtime = LocalPlaybackRuntime(database_path="/tmp/library.sqlite",
                                            library_root="/srv/audio",
                                            credential_path="/etc/mpd.secret",
                                            monotonic=time.monotonic)
        # Fake bootstrap exactly like test_runtime.py: runtime.start() is
        # Linux-only, everything below is real runtime/service/bridge/store.
        self.runtime._phase = "READY"
        self.runtime._ready = True
        self.runtime._boot_id = "e2e_boot"
        self.runtime._service = self.service
        self.runtime._timer = None
        self.runtime._durable_dispatch = DurableDispatch(
            store=self.store, service=self.service, boot_id="e2e_boot",
            monotonic=time.monotonic,
            before_execute=self.runtime._dispatch_may_execute,
            publish_intent=self.runtime._publish_dispatch_intent)
        # Real authorizer behind a thin wrapper: the event proves that the
        # first successful header authentication happened before we close.
        self.auth_event = threading.Event()
        authorizer = make_read_authorizer(_TOKEN)

        def authorizing(credential):
            outcome = authorizer(credential)
            if outcome is True:
                self.auth_event.set()
            return outcome

        self.http = LocalPlaybackHTTP(self.runtime, _Catalog(), authorizing, 0)
        # Cleanup registered before start(): a partial bind/start failure must
        # still run the drain path for the already constructed helper.
        self.assertIsNone(self.http.address)
        self.addCleanup(self._close_everything)
        self.http.start()

    def _close_everything(self):
        # Deliberately no try/except: a raised error here is a cleanup defect,
        # never a success. Runtime admission closes first, HTTP drain second,
        # the final runtime owner release happens only after a confirmed drain.
        self.runtime.begin_shutdown()
        self.http.begin_shutdown()
        drained = self.http.finish_shutdown(deadline=time.monotonic() + 5.0)
        if drained is not True:
            raise _CleanupFailure(
                "http drain incomplete (finish_shutdown -> {!r}); final "
                "runtime owner release not executed".format(drained))
        snapshot = self.runtime.finish_shutdown(deadline=time.monotonic() + 5.0)
        if snapshot["phase"] != "CLOSED":
            raise _CleanupFailure(
                "runtime not closed after HTTP drain: {!r}".format(snapshot))

    def _queue(self):
        created = self.store.execute({
            "contractVersion": 1, "commandId": "make_queue_e2e",
            "action": "QUEUE_CREATE",
            "items": [{"mediaRef": dict(_LOCAL), "title": "A"},
                      {"mediaRef": dict(_LOCAL), "title": "B"}],
        })
        return created["result"]["queue"]

    @staticmethod
    def _start_command(queue, entry_index=0):
        return {"contractVersion": 1, "commandId": "cmd_e2e_start",
                "action": "PLAYBACK_START", "queueId": queue["queueId"],
                "expectedQueueRevision": queue["revision"],
                "entryId": queue["entries"][entry_index]["entryId"]}

    def _post(self, payload):
        address = self.http.address
        self.assertIsInstance(address, tuple)
        self.assertEqual(2, len(address))
        host, port = address
        self.assertEqual("127.0.0.1", host)
        self.assertRegex(host, r"^(?:\d{1,3}\.){3}\d{1,3}$")
        self.assertIs(type(port), int)
        self.assertTrue(0 < port <= 65535)
        body = json.dumps(payload).encode("utf-8")
        connection = http.client.HTTPConnection(host, port, timeout=5)
        try:
            connection.putrequest("POST", "/api/playback/commands",
                                  skip_host=True)
            connection.putheader("Host", "{}:{}".format(host, port))
            connection.putheader("Authorization", "Bearer " + _TOKEN)
            connection.putheader("Content-Length", str(len(body)))
            connection.endheaders()
            connection.send(body)
            response = connection.getresponse()
            raw = response.read()
            return response.status, json.loads(raw.decode("utf-8"))
        finally:
            connection.close()

    def _command_log_rows(self):
        with closing(sqlite3.connect(self.store_path)) as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM command_log").fetchone()
        return row[0]

    def test_valid_start_post_admits_durably_and_replay_never_restarts(self):
        queue = self._queue()
        command = self._start_command(queue)

        status, first = self._post(command)
        self.assertEqual(200, status)
        self.assertEqual(_RESULT_KEYS, set(first))
        self.assertEqual("ACCEPTED", first["admission"]["status"])
        self.assertEqual("PLAYBACK_START", first["admission"]["action"])
        self.assertIsNotNone(first["intentId"])
        self.assertIsNotNone(first["executionId"])
        self.assertEqual(["START"], self.provider.calls)

        stored = self.store.get_command("cmd_e2e_start")
        self.assertEqual("ACCEPTED", stored["status"])
        rows_before = self._command_log_rows()
        self.assertGreaterEqual(rows_before, 2)

        replay_status, replay = self._post(command)
        self.assertEqual(200, replay_status)
        self.assertEqual(first, replay)
        self.assertEqual(["START"], self.provider.calls)
        self.assertEqual(rows_before, self._command_log_rows())

    def test_same_command_id_with_other_payload_is_reused_from_real_store(self):
        queue = self._queue()
        status, first = self._post(self._start_command(queue))
        self.assertEqual(200, status)
        self.assertEqual("ACCEPTED", first["admission"]["status"])
        self.assertEqual(["START"], self.provider.calls)
        rows_before = self._command_log_rows()

        altered = {"contractVersion": 1, "commandId": "cmd_e2e_start",
                   "action": "PLAYBACK_STOP"}
        status, second = self._post(altered)
        self.assertEqual(200, status)
        self.assertEqual(_RESULT_KEYS, set(second))
        self.assertEqual("REJECTED", second["admission"]["status"])
        self.assertEqual("COMMAND_ID_REUSED",
                         second["admission"]["error"]["code"])
        self.assertIsNone(second["intentId"])
        self.assertIsNone(second["executionId"])
        self.assertEqual(["START"], self.provider.calls)
        self.assertEqual(rows_before, self._command_log_rows())

    def test_closing_between_header_auth_and_body_denies_without_admission(self):
        body = json.dumps({"contractVersion": 1, "commandId": "cmd_e2e_close",
                           "action": "PLAYBACK_STOP"}).encode("utf-8")
        self.assertEqual(0, self._command_log_rows())
        address = self.http.address
        self.assertIsInstance(address, tuple)
        self.assertEqual(2, len(address))
        host, port = address
        self.assertEqual("127.0.0.1", host)
        self.assertIs(type(port), int)
        self.assertTrue(0 < port <= 65535)

        connection = http.client.HTTPConnection(host, port, timeout=5)
        try:
            connection.putrequest("POST", "/api/playback/commands",
                                  skip_host=True)
            connection.putheader("Host", "{}:{}".format(host, port))
            connection.putheader("Authorization", "Bearer " + _TOKEN)
            connection.putheader("Content-Length", str(len(body)))
            # Headers only: the server must now be parked on the body read.
            connection.endheaders()
            self.assertTrue(self.auth_event.wait(5.0))
            self.http.begin_shutdown()
            connection.send(body)
            response = connection.getresponse()
            payload = json.loads(response.read().decode("utf-8"))
        finally:
            connection.close()
        # Contract: gated authorization answers 401. A reset, closed socket
        # or timeout here is a contract violation, never a passing outcome.
        self.assertEqual(401, response.status)
        self.assertEqual("UNAUTHORIZED", payload["error"]["code"])
        self.assertEqual([], self.provider.calls)
        self.assertEqual(0, self._command_log_rows())


if __name__ == "__main__":
    unittest.main()

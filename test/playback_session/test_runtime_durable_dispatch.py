"""Runtime ownership of durable dispatch."""

import unittest
import threading
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from components.playback_session.execution_gate import GateStateError
from components.playback_session.runtime import LocalPlaybackRuntime
from components.playback_session.local_playback_service import LocalPlaybackService
from components.playback_session.durable_dispatch import DurableDispatch


class RuntimeDurableDispatchTests(unittest.TestCase):
    def runtime(self, **kwargs):
        return LocalPlaybackRuntime(database_path="/tmp/library.sqlite",
                                     library_root="/srv/audio",
                                     credential_path="/etc/mpd.secret", **kwargs)

    def test_default_runtime_has_no_durable_dispatch(self):
        runtime = self.runtime()
        self.assertIsNone(runtime._durable_dispatch)
        with self.assertRaises(GateStateError) as raised:
            runtime.dispatch({}, deadline=20.0)
        self.assertEqual("NOT_READY", raised.exception.code)

    def test_configured_runtime_does_not_create_store_before_start(self):
        runtime = self.runtime(playlist_database_path="/tmp/playlists.sqlite")
        self.assertIsNone(runtime._durable_dispatch)

    def test_optional_database_path_is_validated(self):
        with self.assertRaisesRegex(Exception, "playlist_database_path"):
            self.runtime(playlist_database_path="relative.sqlite")

    def test_dispatch_claim_returns_busy_before_durable_admission(self):
        runtime = self.runtime()
        runtime._phase = "READY"
        runtime._ready = True
        runtime._driving = True
        store = _MemoStore()
        runtime._durable_dispatch = DurableDispatch(store=store, provider=_NoopProvider(),
                                                   boot_id="boot1")
        with self.assertRaises(GateStateError) as raised:
            runtime.dispatch({"commandId": "cmd1"}, deadline=20.0)
        self.assertEqual("BUSY", raised.exception.code)
        self.assertEqual([], store.commands)

    def test_shutdown_closes_dispatch_admission_but_allows_identical_memo_replay(self):
        runtime = self.runtime(playlist_database_path="/tmp/playlists.sqlite")
        runtime._phase = "READY"
        runtime._ready = True
        runtime._boot_id = "boot1"
        runtime._service = LocalPlaybackService(provider=_NoopProvider(), boot_id="boot1")
        store = _MemoStore()
        bridge = DurableDispatch(store=store, service=runtime._service, boot_id="boot1")
        runtime._durable_dispatch = bridge
        command = {"commandId": "cmd1"}
        memo = {"admission": {"commandId": "cmd1", "status": "REJECTED"},
                "playback": None, "operation": None, "gate": None, "failure": None,
                "intentId": None, "executionId": None}
        bridge._completed["cmd1"] = (memo["admission"], memo,
                                     '{"commandId":"cmd1"}')
        runtime.begin_shutdown()
        self.assertEqual(memo, runtime.dispatch(command, deadline=20.0))
        self.assertEqual([], store.commands)
        with self.assertRaises(GateStateError) as raised:
            runtime.dispatch({"commandId": "new1"}, deadline=20.0)
        self.assertEqual("CLOSED", raised.exception.code)

    def test_timer_cannot_drive_service_during_dispatch_admission(self):
        runtime, service, store, command, provider = self.configured_runtime("stop")
        runtime.request_start("preexisting", {"kind": "LOCAL", "libraryId": "m1"})
        store.block = True
        thread, outcome = self.launch_dispatch(runtime, command)
        try:
            self.assertTrue(store.entered.wait(1.0))
            runtime._tick()
            self.assertEqual([], provider.calls)
            self.assertTrue(runtime.snapshot()["ready"])
        finally:
            store.release.set()
            thread.join(2.0)
        self.assertFalse(thread.is_alive())

    def test_timer_does_not_reenter_service_during_dispatch_provider_call(self):
        runtime, _service, _store, command, provider = self.configured_runtime("start")
        provider.block = True
        thread, outcome = self.launch_dispatch(runtime, command)
        try:
            self.assertTrue(provider.entered.wait(1.0))
            runtime._tick()
            self.assertTrue(runtime.snapshot()["ready"])
            self.assertEqual(["START"], provider.calls)
        finally:
            provider.release.set()
            thread.join(2.0)
        self.assertFalse(thread.is_alive())
        self.assertNotIn("error", outcome)

    def test_shutdown_drain_includes_dispatch_admission_until_memo(self):
        runtime, _service, store, command, provider = self.configured_runtime("stop")
        store.block = True
        thread, outcome = self.launch_dispatch(runtime, command)
        try:
            self.assertTrue(store.entered.wait(1.0))
            runtime.begin_shutdown()
            state = runtime.finish_shutdown(deadline=time.monotonic() + 0.05)
            self.assertNotEqual("CLOSED", state["phase"])
            self.assertFalse(state["quiescent"])
            store.release.set()
            thread.join(2.0)
        finally:
            store.release.set()
            thread.join(2.0)

    def test_blocked_execution_id_preparation_does_not_hold_runtime_or_service_locks(self):
        runtime, _service, store, command, provider = self.configured_runtime("start")
        store.block = True
        thread, outcome = self.launch_dispatch(runtime, command)
        uuid_entered, uuid_release = threading.Event(), threading.Event()
        shutdown_done = threading.Event()
        import components.playback_session.execution_gate as gate_module
        original_uuid4 = gate_module.uuid.uuid4
        calls = []

        def blocked_second_uuid():
            calls.append(True)
            if len(calls) == 2:
                uuid_entered.set()
                if not uuid_release.wait(3.0):
                    raise AssertionError("test did not release execution-id preparation")
            return original_uuid4()

        try:
            self.assertTrue(store.entered.wait(1.0))
            with patch.object(gate_module.uuid, "uuid4", side_effect=blocked_second_uuid):
                store.release.set()
                self.assertTrue(uuid_entered.wait(1.0))
                shutdown = threading.Thread(
                    target=lambda: (runtime.begin_shutdown(), shutdown_done.set()))
                shutdown.start()
                try:
                    self.assertTrue(shutdown_done.wait(1.0),
                                    "shutdown blocked behind UUID preparation locks")
                    self.assertEqual("CLOSING", runtime.snapshot()["phase"])
                finally:
                    uuid_release.set()
                    shutdown.join(2.0)
            thread.join(2.0)
            self.assertFalse(thread.is_alive())
            self.assertNotIn("error", outcome)
            self.assertEqual("ACCEPTED", outcome["result"]["admission"]["status"])
            self.assertIsNone(outcome["result"]["operation"])
            self.assertEqual([], provider.calls)
        finally:
            store.release.set()
            uuid_release.set()
            thread.join(2.0)

    def configured_runtime(self, action):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        database = Path(temporary.name) / "playlists.sqlite"
        from components.playlists.store import PlaylistStore
        real_store = PlaylistStore(database)
        if action == "start":
            queue = real_store.execute({"contractVersion": 1, "commandId": "makeq",
                                        "action": "QUEUE_CREATE",
                                        "items": [{"mediaRef": {"kind": "LOCAL", "libraryId": "m1"},
                                                   "title": "Track"}]})["result"]["queue"]
            command = {"contractVersion": 1, "commandId": "start1",
                       "action": "PLAYBACK_START", "queueId": queue["queueId"],
                       "expectedQueueRevision": queue["revision"],
                       "entryId": queue["entries"][0]["entryId"]}
        else:
            command = {"contractVersion": 1, "commandId": "stop1", "action": "PLAYBACK_STOP"}
        store = _BlockingStore(real_store)
        provider = _EventProvider()
        runtime = self.runtime(playlist_database_path="/tmp/playlists.sqlite")
        runtime._phase, runtime._ready, runtime._boot_id = "READY", True, "boot1"
        service = LocalPlaybackService(provider=provider, boot_id="boot1")
        runtime._service = service
        runtime._durable_dispatch = DurableDispatch(
            store=store, service=service, boot_id="boot1",
            before_execute=runtime._dispatch_may_execute,
            publish_intent=runtime._publish_dispatch_intent,
            claim_step=runtime._claim_dispatch_step)
        return runtime, service, store, command, provider

    def launch_dispatch(self, runtime, command):
        outcome = {}

        def dispatch():
            try:
                outcome["result"] = runtime.dispatch(command, deadline=time.monotonic() + 5.0)
            except BaseException as error:
                outcome["error"] = error

        thread = threading.Thread(target=dispatch)
        thread.start()
        return thread, outcome


if __name__ == "__main__":
    unittest.main()


class _NoopProvider:
    def start(self, *_args, **_kwargs):
        raise AssertionError("unexpected provider start")

    def stop(self, *_args, **_kwargs):
        raise AssertionError("unexpected provider stop")


class _MemoStore:
    def __init__(self):
        self.commands = []

    def admit_playback(self, command):
        self.commands.append(command)
        raise AssertionError("memo replay must not admit")


class _BlockingStore:
    def __init__(self, store):
        self.store = store
        self.block = False
        self.entered = threading.Event()
        self.release = threading.Event()

    def admit_playback(self, command):
        result = self.store.admit_playback(command)
        if self.block:
            self.entered.set()
            if not self.release.wait(3.0):
                raise AssertionError("test did not release blocked admission")
        return result


class _EventProvider(_NoopProvider):
    def __init__(self):
        self.calls = []
        self.block = False
        self.entered = threading.Event()
        self.release = threading.Event()

    def start(self, media_ref, *, lease, deadline):
        self.calls.append("START")
        if self.block:
            self.entered.set()
            if not self.release.wait(3.0):
                raise AssertionError("test did not release blocked provider")
        return self.receipt("START", lease)

    def stop(self, *, lease, deadline):
        self.calls.append("STOP")
        return self.receipt("STOP", lease)

    def receipt(self, operation, lease):
        return {"provider": "LOCAL", "operation": operation,
                "identity": dict(lease["identity"]), "outcome": "CONFIRMED",
                "epoch": "ep1", "songid": "1" if operation == "START" else None,
                "state": "PLAYING" if operation == "START" else "STOPPED",
                "positionMs": None, "durationMs": None,
                "observedAtMonotonic": time.monotonic(), "error": None}

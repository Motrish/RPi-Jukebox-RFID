"""Durable regressions for the independently reproduced C5B core probes."""

import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from components.playback_session.durable_dispatch import DurableDispatch
from components.playback_session.execution_gate import GateStateError
from components.playback_session.local_playback_service import LocalPlaybackService
from components.playback_session.runtime import LocalPlaybackRuntime
from components.playlists.store import PlaylistStore


LOCAL = {"kind": "LOCAL", "libraryId": "m1"}


def command(command_id, action, **values):
    return {
        "contractVersion": 1,
        "commandId": command_id,
        "action": action,
        **values,
    }


class Provider:
    def __init__(self):
        self.calls = []
        self.crash = None
        self.reject = False

    def start(self, media, *, lease, deadline):
        self.calls.append("START")
        if self.crash:
            raise self.crash
        if self.reject:
            return self.receipt(
                "START",
                lease,
                "REJECTED",
                "UNKNOWN",
                None,
                {
                    "code": "PROVIDER_REJECTED",
                    "message": "Rejected.",
                    "retryable": False,
                    "operation": "START",
                },
            )
        return self.receipt("START", lease, "CONFIRMED", "PLAYING", "1")

    def stop(self, *, lease, deadline):
        self.calls.append("STOP")
        return self.receipt("STOP", lease, "CONFIRMED", "STOPPED", None)

    @staticmethod
    def receipt(operation, lease, outcome, state, songid, error=None):
        return {
            "provider": "LOCAL",
            "operation": operation,
            "identity": dict(lease["identity"]),
            "outcome": outcome,
            "epoch": "ep1",
            "songid": songid,
            "state": state,
            "positionMs": None,
            "durationMs": None,
            "observedAtMonotonic": time.monotonic(),
            "error": error,
        }


class BlockingStore:
    """Block only after the real SQLite admission has committed."""

    def __init__(self, store):
        self.store = store
        self.calls = 0
        self.entered = threading.Event()
        self.release = threading.Event()
        self.block = False

    def admit_playback(self, cmd):
        self.calls += 1
        outcome = self.store.admit_playback(cmd)
        if self.block:
            self.entered.set()
            if not self.release.wait(5):
                raise AssertionError("test did not release blocked admission")
        return outcome


class LinuxPlatformOS:
    """Override only runtime's platform check, retaining real host OS calls."""

    name = "posix"

    def __init__(self, host_os):
        self._host_os = host_os

    def __getattr__(self, name):
        return getattr(self._host_os, name)


class InertTimer:
    def __init__(self, **_kwargs):
        self.started = False

    def start(self):
        self.started = True

    def cancel(self):
        self.started = False

    def is_alive(self):
        return self.started


class RuntimeDispatchRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = PlaylistStore(Path(self.tmp.name) / "playlists.sqlite")
        queue = self.store.execute(
            command(
                "make-queue",
                "QUEUE_CREATE",
                items=[{"mediaRef": LOCAL, "title": "A"}],
            )
        )["result"]["queue"]
        self.start = command(
            "start-1",
            "PLAYBACK_START",
            queueId=queue["queueId"],
            expectedQueueRevision=queue["revision"],
            entryId=queue["entries"][0]["entryId"],
        )
        self.stop = command("stop-1", "PLAYBACK_STOP")
        self.provider = Provider()
        self.service = LocalPlaybackService(provider=self.provider, boot_id="b1")
        self.runtime = LocalPlaybackRuntime(
            database_path="/tmp/catalog.sqlite",
            library_root="/srv/audio",
            credential_path="/etc/mpd.secret",
            playlist_database_path="/tmp/playlists.sqlite",
        )
        self.runtime._phase, self.runtime._ready = "READY", True
        self.runtime._service = self.service
        self.blocking_store = BlockingStore(self.store)
        self.bridge = DurableDispatch(
            store=self.blocking_store,
            service=self.service,
            boot_id="b1",
            before_execute=self.runtime._dispatch_may_execute,
            publish_intent=self.runtime._publish_dispatch_intent,
        )
        self.runtime._durable_dispatch = self.bridge
        self.thread_result = {}

    def _dispatch_in_thread(self, cmd):
        def run():
            try:
                self.thread_result["result"] = self.runtime.dispatch(
                    cmd, deadline=time.monotonic() + 5
                )
            except BaseException as error:  # surfaced in the joining test thread
                self.thread_result["error"] = error

        thread = threading.Thread(target=run)
        thread.start()
        return thread

    def _release_and_join(self, thread):
        self.blocking_store.release.set()
        thread.join(2)
        self.assertFalse(thread.is_alive(), "dispatch thread did not terminate")

    def test_configured_start_imports_playlist_store_and_becomes_ready(self):
        import components.playlists.store as playlist_store_module

        runtime_module = __import__(
            "components.playback_session.runtime", fromlist=["runtime"]
        )
        windows_database = Path(self.tmp.name) / "configured-playlists.sqlite"
        original_store = playlist_store_module.PlaylistStore

        runtime = LocalPlaybackRuntime(
            database_path="/tmp/catalog-start.sqlite",
            library_root="/srv/audio",
            credential_path="/etc/mpd.secret",
            playlist_database_path="/configured-playlists.sqlite",
        )

        def bootstrap(_deadline):
            runtime._owner_fd = os.open(os.devnull, os.O_RDONLY)
            runtime._catalog = SimpleNamespace(
                resolve=lambda value: value, close=lambda: None
            )

        runtime._bootstrap_core = bootstrap

        def real_temp_store(_configured_path):
            return original_store(windows_database)

        with (
            patch.object(
                runtime_module, "os", LinuxPlatformOS(os)
            ),
            patch.object(runtime_module.sys, "platform", "linux"),
            patch.object(runtime_module, "LocalProvider", return_value=self.provider),
            patch.object(playlist_store_module, "PlaylistStore", real_temp_store),
            patch.dict(
                sys.modules,
                {"jukebox.multitimer": SimpleNamespace(
                    GenericEndlessTimerClass=InertTimer
                )},
            ),
        ):
            state = runtime.start(deadline=time.monotonic() + 5)

        self.assertTrue(state["ready"], "configured start failed: " + repr(state))
        self.assertTrue(windows_database.exists())
        runtime.begin_shutdown()
        runtime.finish_shutdown(deadline=time.monotonic() + 1)

    def test_timer_cannot_drive_preexisting_start_during_dispatch_admission(self):
        self.runtime.request_start("preexisting", LOCAL)
        self.blocking_store.block = True
        thread = self._dispatch_in_thread(self.stop)
        try:
            self.assertTrue(self.blocking_store.entered.wait(2))
            self.runtime._tick()
            self.assertEqual([], self.provider.calls)
        finally:
            self._release_and_join(thread)
        self.assertNotIn("error", self.thread_result)

    def test_timer_busy_during_provider_call_does_not_mark_runtime_unavailable(self):
        entered, release = threading.Event(), threading.Event()
        original = self.provider.start

        def blocked_start(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise AssertionError("test did not release blocked provider")
            return original(*args, **kwargs)

        self.provider.start = blocked_start
        thread = self._dispatch_in_thread(self.start)
        try:
            self.assertTrue(entered.wait(2))
            self.runtime._tick()
            self.assertTrue(self.runtime.snapshot()["ready"])
        finally:
            release.set()
            self._release_and_join(thread)
        self.assertNotIn("error", self.thread_result)

    def test_shutdown_does_not_close_until_committed_admission_drains(self):
        self.blocking_store.block = True
        thread = self._dispatch_in_thread(self.start)
        try:
            self.assertTrue(self.blocking_store.entered.wait(2))
            self.runtime.begin_shutdown()
            state = self.runtime.finish_shutdown(deadline=time.monotonic() + 0.05)
            self.assertNotEqual("CLOSED", state["phase"])
        finally:
            self._release_and_join(thread)
        self.assertNotIn("error", self.thread_result)

    def test_shutdown_stop_is_not_attributed_to_request_dispatch(self):
        self.runtime.request_start("preexisting", LOCAL)
        self.runtime._tick()
        entered, release = threading.Event(), threading.Event()
        original = self.service.run_once

        def paused_run_once(*, deadline):
            entered.set()
            if not release.wait(5):
                raise AssertionError("test did not release paused service")
            return original(deadline=deadline)

        self.service.run_once = paused_run_once
        thread = self._dispatch_in_thread(self.stop)
        try:
            self.assertTrue(entered.wait(2))
            self.runtime.begin_shutdown()
        finally:
            release.set()
            self._release_and_join(thread)
        self.assertNotIn("error", self.thread_result)
        result = self.thread_result["result"]
        self.assertEqual(
            result["intentId"], result["playback"]["lastExecution"]["intentId"]
        )

    def test_provider_crash_latches_runtime_and_replay_returns_unavailable_memo(self):
        crash = RuntimeError("provider crashed")
        self.provider.crash = crash
        with self.assertRaises(RuntimeError) as first:
            self.runtime.dispatch(self.start, deadline=time.monotonic() + 5)

        self.assertIs(first.exception, crash)
        self.assertFalse(self.runtime.snapshot()["ready"])
        with self.assertRaises(RuntimeError) as replay:
            self.runtime.dispatch(self.start, deadline=time.monotonic() + 5)
        self.assertIs(replay.exception, crash)
        self.assertEqual(1, self.blocking_store.calls)
        self.assertEqual(["START"], self.provider.calls)

    def test_expired_claim_retires_driving_and_permit_before_shutdown(self):
        now = [time.monotonic()]
        self.runtime._clock = lambda: now[0]
        self.service._clock = lambda: now[0]
        deadline = now[0] + 5
        original_claim = self.runtime._claim_dispatch_step

        def claim_then_expire(intent_id, execution_id):
            claim = original_claim(intent_id, execution_id)
            now[0] = deadline + 1
            return claim

        with patch.object(
            self.runtime, "_claim_dispatch_step", side_effect=claim_then_expire
        ):
            with self.assertRaises(GateStateError) as raised:
                self.runtime.dispatch(self.start, deadline=deadline)

        self.assertEqual("DEADLINE_EXPIRED", raised.exception.code)
        state = self.service.snapshot()
        self.assertFalse(state["driving"])
        self.assertIsNone(state["gate"]["inFlight"])
        self.assertEqual([], self.provider.calls)
        now[0] = time.monotonic()
        self.runtime.begin_shutdown()
        closed = self.runtime.finish_shutdown(deadline=time.monotonic() + 2)
        self.assertEqual("CLOSED", closed["phase"])

    def test_deadline_between_claimed_step_and_run_once_entry_aborts_claim(self):
        deadline = time.monotonic() + 5
        clock_reads = []

        def counting_clock():
            clock_reads.append(None)
            return deadline - 1 if len(clock_reads) == 1 else deadline + 1

        self.service._clock = counting_clock
        gate = self.service._gate
        original_complete = gate.complete
        completions = []

        def counting_complete(permit, receipt):
            completions.append(receipt)
            return original_complete(permit, receipt)

        gate.complete = counting_complete
        run_once_entries = []
        original_run_once = self.service.run_once

        def tracked_run_once(*, deadline):
            run_once_entries.append(len(clock_reads))
            return original_run_once(deadline=deadline)

        self.service.run_once = tracked_run_once
        with self.assertRaises(GateStateError) as raised:
            self.runtime.dispatch(self.start, deadline=deadline)

        self.assertEqual("DEADLINE_EXPIRED", raised.exception.code)
        # run_claimed_step() passed its own check (read 1), then run_once()
        # expired the deadline on entry (read 2) while the claim was held.
        self.assertEqual([1], run_once_entries)
        self.assertEqual(2, len(clock_reads))
        self.assertEqual(1, len(completions))
        state = self.service.snapshot()
        self.assertFalse(state["driving"])
        self.assertIsNone(state["gate"]["inFlight"])
        self.assertEqual([], self.provider.calls)

        self.service._clock = time.monotonic
        self.runtime.begin_shutdown()
        closed = self.runtime.finish_shutdown(deadline=time.monotonic() + 2)
        self.assertEqual("CLOSED", closed["phase"])
        self.assertEqual(["STOP"], self.provider.calls)

    def test_execution_uuid_failure_is_terminal_and_timer_cannot_start(self):
        import components.playback_session.local_playback_service as service_module

        original_uuid4 = service_module.uuid.uuid4
        calls = []
        failure = RuntimeError("execution UUID preparation failed")

        def fail_execution_uuid():
            calls.append(None)
            if len(calls) == 2:
                raise failure
            return original_uuid4()

        with patch.object(
            service_module.uuid, "uuid4", side_effect=fail_execution_uuid
        ):
            with self.assertRaises(RuntimeError) as first:
                self.runtime.dispatch(self.start, deadline=time.monotonic() + 5)
            self.assertIs(first.exception, failure)

            with self.assertRaises(RuntimeError) as replay:
                self.runtime.dispatch(self.start, deadline=time.monotonic() + 5)
            self.assertIs(replay.exception, failure)

        self.assertEqual([], self.provider.calls)
        self.runtime._tick()
        self.assertEqual([], self.provider.calls)
        self.assertEqual(1, self.blocking_store.calls)

    def test_default_claim_intent_step_does_not_deadlock(self):
        root = Path.cwd()
        script = r"""
import sys
from components.playback_session.local_playback_service import LocalPlaybackService

class Provider:
    def start(self, *_args, **_kwargs):
        raise AssertionError('claim must not run provider')
    def stop(self, *_args, **_kwargs):
        raise AssertionError('claim must not run provider')

service = LocalPlaybackService(provider=Provider(), boot_id='b1')
intent_id = service.request_start('entry', {'kind': 'LOCAL', 'libraryId': 'm1'})
try:
    service.claim_intent_step(intent_id)
except TypeError as error:
    if 'execution_id' not in str(error):
        raise
    print('required execution_id')
else:
    print('returned')
"""
        environment = os.environ.copy()
        source_path = str(root / "src" / "jukebox")
        environment["PYTHONPATH"] = os.pathsep.join(
            part for part in (source_path, environment.get("PYTHONPATH", "")) if part
        )
        try:
            completed = subprocess.run(
                [sys.executable, "-c", script],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except subprocess.TimeoutExpired:
            self.fail("claim_intent_step(intent_id) deadlocked past subprocess timeout")

        self.assertEqual(
            0,
            completed.returncode,
            "claim subprocess failed: " + completed.stderr,
        )
        self.assertIn(completed.stdout.strip(), {"returned", "required execution_id"})

    def test_unavailable_result_memo_remains_replayable_after_timer_latches(self):
        self.provider.reject = True
        first = self.runtime.dispatch(self.start, deadline=time.monotonic() + 5)
        self.assertEqual("START_REJECTED", first["failure"]["code"])

        self.runtime._tick()
        self.assertFalse(self.runtime.snapshot()["ready"])
        replay = self.runtime.dispatch(self.start, deadline=time.monotonic() + 5)
        self.assertEqual(first, replay)
        self.assertEqual(1, self.blocking_store.calls)


if __name__ == "__main__":
    unittest.main(verbosity=2)

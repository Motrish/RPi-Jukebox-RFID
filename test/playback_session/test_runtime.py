"""Contract checks for the inactive exclusive LOCAL runtime owner."""

import math
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from contextlib import contextmanager
from unittest.mock import patch

from jukebox.contracts import ContractValidationError
from components.local_provider import LocalProvider
from components.playback_session.execution_gate import GateStateError
from components.playback_session.local_playback_service import LocalPlaybackService
from components.playback_session.runtime import LocalPlaybackRuntime
from components.local_provider.adapter import SessionFailure
from components.local_provider.mpd_session import MpdSession

_STAGE = Path(__file__).resolve().parents[2]
_SERVER_FILE = _STAGE / "test" / "local_provider" / "test_mpd_session.py"
_SERVER_SPEC = importlib.util.spec_from_file_location("runtime_mpd_support", _SERVER_FILE)
_SERVER_MODULE = importlib.util.module_from_spec(_SERVER_SPEC)
_SERVER_SPEC.loader.exec_module(_SERVER_MODULE)
_ADAPTER_FILE = _STAGE / "test" / "local_provider" / "test_adapter.py"
_ADAPTER_SPEC = importlib.util.spec_from_file_location("runtime_adapter_support", _ADAPTER_FILE)
_ADAPTER_MODULE = importlib.util.module_from_spec(_ADAPTER_SPEC)
_ADAPTER_SPEC.loader.exec_module(_ADAPTER_MODULE)
with (_STAGE / "test" / "local_provider" / "fixtures" / "v1.json").open(encoding="utf-8") as _fixture_stream:
    _PROVIDER_FIXTURE = json.load(_fixture_stream)


class RuntimeContractTests(unittest.TestCase):
    def valid(self, **overrides):
        values = {"database_path": "/tmp/library.sqlite", "library_root": "/srv/audio",
                  "credential_path": "/etc/mpd.secret"}
        values.update(overrides)
        return LocalPlaybackRuntime(**values)

    def test_constructor_only_copies_valid_configuration(self):
        calls = []
        runtime = self.valid(monotonic=lambda: calls.append("clock"))
        self.assertEqual([], calls)
        self.assertEqual("NEW", runtime.snapshot()["phase"])
        self.assertFalse(runtime.snapshot()["ready"])

    def test_path_inputs_are_exact_absolute_posix_strings(self):
        for field in ("database_path", "library_root", "credential_path", "lock_directory"):
            for value in ("", ".", "relative/path", "/", "/a/./b", "/a/../b", "/a//b", "/a/"):
                with self.subTest(field=field, value=value):
                    kwargs = {field: value}
                    if field == "lock_directory":
                        kwargs["lock_directory"] = value
                    with self.assertRaises(ContractValidationError) as raised:
                        self.valid(**kwargs)
                    self.assertEqual(field, raised.exception.field)
                    self.assertEqual("invalid_path", raised.exception.reason)
        with self.assertRaises(ContractValidationError):
            self.valid(database_path=PathLikeFixture())

    def test_host_port_clock_and_deadline_types_are_strict(self):
        with self.assertRaises(ContractValidationError) as raised:
            self.valid(mpd_host="localhost")
        self.assertEqual(("mpd_host", "invalid_host"), (raised.exception.field, raised.exception.reason))
        for port in (True, 0, 65536, "6601"):
            with self.subTest(port=port):
                with self.assertRaises(ContractValidationError) as raised:
                    self.valid(mpd_port=port)
                self.assertEqual("invalid_port", raised.exception.reason)
        with self.assertRaises(ContractValidationError) as raised:
            self.valid(monotonic=1)
        self.assertEqual("invalid_clock", raised.exception.reason)
        runtime = self.valid()
        for deadline in (True, math.inf, math.nan, "later"):
            with self.subTest(deadline=deadline):
                with self.assertRaises(ContractValidationError) as raised:
                    runtime.start(deadline=deadline)
                self.assertEqual(("deadline", "invalid_deadline"),
                                 (raised.exception.field, raised.exception.reason))

    def test_snapshot_is_exact_defensive_safe_mapping(self):
        runtime = self.valid()
        state = runtime.snapshot()
        self.assertEqual({"phase", "ready", "bootId", "ownerLockHeld", "bootstrapActive",
                          "driverAlive", "quiescent", "service", "failure"}, set(state))
        state["failure"] = {"code": "secret"}
        self.assertIsNone(runtime.snapshot()["failure"])

    def test_start_argument_validation_precedes_readiness(self):
        runtime = self.valid()
        for entry_id, media_ref, field in (("bad id", _PROVIDER_FIXTURE["mediaRef"], "entryId"),
                                           ("entry_ok", {}, "mediaRef.kind")):
            with self.subTest(field=field):
                with self.assertRaises(ContractValidationError) as raised:
                    runtime.request_start(entry_id, media_ref)
                self.assertEqual(field, raised.exception.field)

    def test_concurrent_start_returns_busy_and_expired_new_shutdown_is_nonquiescent(self):
        runtime = self.valid()
        entered, release = threading.Event(), threading.Event()

        def block_bootstrap(_deadline):
            entered.set()
            release.wait(1.0)
            raise RuntimeError("stop after concurrency observation")

        runtime._bootstrap_core = block_bootstrap
        with patch("components.playback_session.runtime.sys.platform", "linux"), \
                patch("components.playback_session.runtime.os.name", "posix"):
            starter = threading.Thread(target=lambda: runtime.start(deadline=time.monotonic() + 2.0))
            starter.start()
            self.assertTrue(entered.wait(1.0))
            with self.assertRaises(GateStateError) as raised:
                runtime.start(deadline=time.monotonic() + 2.0)
            self.assertEqual("BUSY", raised.exception.code)
            release.set()
            starter.join(1.0)
            self.assertFalse(starter.is_alive())

        fresh = self.valid()
        expired = fresh.finish_shutdown(deadline=time.monotonic() - 1.0)
        self.assertEqual("SHUTDOWN_INCOMPLETE", expired["failure"]["code"])
        self.assertFalse(expired["quiescent"])


class _ManualTimer:
    def __init__(self):
        self.triggers = 0
        self.timer_thread = None
        self.running = True

    def is_alive(self):
        return self.running

    def trigger(self):
        self.triggers += 1

    def cancel(self):
        self.running = False


class RuntimeLifecycleRegressionTests(unittest.TestCase):
    def make_runtime(self):
        clock = _ADAPTER_MODULE.FakeClock()
        session = _ADAPTER_MODULE.FakeSession(_PROVIDER_FIXTURE["initialStatus"])
        session.clock = clock
        provider = LocalProvider(session=session,
                                 resolver=lambda _library_id: _PROVIDER_FIXTURE["resolvedMedia"],
                                 monotonic=clock,
                                 capabilities=_PROVIDER_FIXTURE["capabilities"])
        service = LocalPlaybackService(provider=provider, boot_id="runtime_regression_boot",
                                       monotonic=clock)
        runtime = LocalPlaybackRuntime(database_path="/tmp/library.sqlite", library_root="/srv/audio",
                                       credential_path="/etc/mpd.secret", monotonic=clock)
        runtime._phase = "READY"
        runtime._ready = True
        runtime._boot_id = "runtime_regression_boot"
        runtime._service = service
        runtime._timer = _ManualTimer()
        return runtime, service, provider, session, clock

    def test_stop_failure_latches_without_timer_retrigger_until_explicit_stop(self):
        runtime, service, _provider, session, clock = self.make_runtime()
        service.request_start("runtime_entry", _PROVIDER_FIXTURE["mediaRef"])
        runtime._drive_once(clock.value + 1.0)
        session.stop_ack_without_stopping = True
        runtime.request_stop()
        runtime._tick()
        state = runtime.snapshot()
        self.assertEqual("UNAVAILABLE", state["phase"])
        self.assertFalse(state["ready"])
        self.assertEqual({"code": "STOP_UNCONFIRMED"}, state["failure"])
        self.assertEqual(1, sum(event[0] == "stop" for event in session.events))
        trigger_count = runtime._timer.triggers
        runtime._tick()
        self.assertEqual(trigger_count, runtime._timer.triggers)
        self.assertEqual(1, sum(event[0] == "stop" for event in session.events))
        with self.assertRaises(GateStateError):
            runtime.request_start("blocked_entry", _PROVIDER_FIXTURE["mediaRef"])

        session.stop_ack_without_stopping = False
        runtime.request_stop()
        runtime._tick()
        self.assertEqual(2, sum(event[0] == "stop" for event in session.events),
                         (service.snapshot(), session.events))
        self.assertIsNone(service.snapshot()["gate"]["owner"])
        runtime._tick()  # retire P04b's pending, already-confirmed STOP
        self.assertTrue(service.snapshot()["quiescent"])
        self.assertEqual("UNAVAILABLE", runtime.snapshot()["phase"])

    def test_failed_start_and_baseexception_close_admission(self):
        runtime, service, provider, _session, clock = self.make_runtime()
        provider.resolver = lambda _library_id: (_ for _ in ()).throw(RuntimeError("resolver failure"))
        service.request_start("failed_entry", _PROVIDER_FIXTURE["mediaRef"])
        runtime._tick()
        self.assertEqual("UNAVAILABLE", runtime.snapshot()["phase"])
        self.assertFalse(runtime.snapshot()["ready"])
        with self.assertRaises(GateStateError):
            runtime.request_start("later_entry", _PROVIDER_FIXTURE["mediaRef"])
        runtime.request_stop()
        runtime._tick()
        self.assertTrue(service.snapshot()["quiescent"])

        runtime2, service2, provider2, _session2, _clock2 = self.make_runtime()

        def interrupt_resolver(_library_id):
            raise KeyboardInterrupt()

        provider2.resolver = interrupt_resolver
        service2.request_start("fatal_entry", _PROVIDER_FIXTURE["mediaRef"])
        runtime2._tick()
        self.assertEqual("UNAVAILABLE", runtime2.snapshot()["phase"])
        self.assertEqual({"code": "DRIVER_FAILED"}, runtime2.snapshot()["failure"])
        self.assertFalse(runtime2.snapshot()["ready"])

    def test_replacement_during_start_keeps_latest_intent_after_stale_completion(self):
        runtime, service, provider, session, clock = self.make_runtime()
        entered, release = threading.Event(), threading.Event()

        def blocked_resolver(_library_id):
            entered.set()
            release.wait(2.0)
            return _PROVIDER_FIXTURE["resolvedMedia"]

        provider.resolver = blocked_resolver
        runtime.request_start("superseded_entry", _PROVIDER_FIXTURE["mediaRef"])
        driver = threading.Thread(target=runtime._tick)
        driver.start()
        self.assertTrue(entered.wait(1.0))
        runtime.request_start("successor_entry", _PROVIDER_FIXTURE["mediaRef"])
        release.set()
        driver.join(1.0)
        self.assertFalse(driver.is_alive())

        state = runtime.snapshot()
        service_state = service.snapshot()
        self.assertEqual("READY", state["phase"], (state, service_state))
        self.assertTrue(state["ready"])
        self.assertEqual("successor_entry", service_state["pending"]["entryId"])
        self.assertEqual("START_REJECTED", service_state["lastFailure"]["code"])

        provider.resolver = lambda _library_id: _PROVIDER_FIXTURE["resolvedMedia"]
        runtime._tick()  # Drive the newest request after safe cancellation.
        runtime._tick()
        self.assertEqual("READY", runtime.snapshot()["phase"])
        self.assertIsNone(service.snapshot()["pending"])
        self.assertEqual("successor_entry", service.snapshot()["gate"]["owner"]["entryId"])
        self.assertEqual(0, sum(event[0] == "stop" for event in session.events))

    def test_replacement_after_possible_start_effect_drains_before_successor(self):
        runtime, service, _provider, session, clock = self.make_runtime()
        entered, release = threading.Event(), threading.Event()

        def block_after_playid(command):
            if command == "playid":
                entered.set()
                release.wait(2.0)

        session.on_command = block_after_playid
        runtime.request_start("possibly_playing", _PROVIDER_FIXTURE["mediaRef"])
        driver = threading.Thread(target=runtime._tick)
        driver.start()
        self.assertTrue(entered.wait(1.0))
        runtime.request_start("successor_after_effect", _PROVIDER_FIXTURE["mediaRef"])
        release.set()
        driver.join(1.0)
        self.assertFalse(driver.is_alive())

        service_state = service.snapshot()
        self.assertEqual("READY", runtime.snapshot()["phase"])
        self.assertEqual("successor_after_effect", service_state["pending"]["entryId"])
        self.assertTrue(service_state["gate"]["cleanupRequired"])

        session.on_command = None
        runtime._tick()  # Confirm cleanup of the possibly playing superseded request.
        runtime._tick()  # Only then start its successor.
        self.assertEqual("successor_after_effect", service.snapshot()["gate"]["owner"]["entryId"])
        self.assertEqual(1, sum(event[0] == "stop" for event in session.events))

    def test_explicit_stop_retry_published_before_failure_latch_is_preserved(self):
        runtime, service, _provider, session, clock = self.make_runtime()
        service.request_start("retry_entry", _PROVIDER_FIXTURE["mediaRef"])
        runtime._drive_once(clock.value + 1.0)
        session.stop_ack_without_stopping = True
        entered, release = threading.Event(), threading.Event()
        original_latch = runtime._latch_service_failure

        def blocked_latch(*args, **kwargs):
            entered.set()
            release.wait(2.0)
            return original_latch(*args, **kwargs)

        runtime._latch_service_failure = blocked_latch
        runtime.request_stop()
        driver = threading.Thread(target=runtime._tick)
        driver.start()
        self.assertTrue(entered.wait(1.0))

        session.stop_ack_without_stopping = False
        retry_id = runtime.request_stop()
        self.assertEqual(retry_id, service.snapshot()["pending"]["intentId"])
        release.set()
        driver.join(1.0)
        self.assertFalse(driver.is_alive())

        state = runtime.snapshot()
        self.assertEqual("UNAVAILABLE", state["phase"])
        self.assertTrue(runtime._cleanup_driver_enabled)
        self.assertFalse(service.snapshot()["closed"])
        self.assertEqual(retry_id, service.snapshot()["pending"]["intentId"])

        runtime._latch_service_failure = original_latch
        runtime._tick()
        self.assertIsNone(service.snapshot()["gate"]["owner"])
        runtime._tick()
        self.assertTrue(service.snapshot()["quiescent"])

    def test_explicit_retry_cannot_be_overwritten_by_service_shutdown_publication(self):
        runtime, service, _provider, session, clock = self.make_runtime()
        service.request_start("retry_gap_entry", _PROVIDER_FIXTURE["mediaRef"])
        runtime._drive_once(clock.value + 1.0)
        session.stop_ack_without_stopping = True
        entered, release = threading.Event(), threading.Event()
        original_shutdown = service.begin_shutdown

        def blocked_shutdown():
            entered.set()
            release.wait(2.0)
            return original_shutdown()

        service.begin_shutdown = blocked_shutdown
        runtime.request_stop()
        driver = threading.Thread(target=runtime._tick)
        driver.start()
        self.assertTrue(entered.wait(1.0))

        session.stop_ack_without_stopping = False
        retry_result = {}
        retry = threading.Thread(target=lambda: retry_result.setdefault(
            "id", runtime.request_stop()))
        retry.start()
        expires = time.monotonic() + 1.0
        while time.monotonic() < expires:
            with runtime._lock:
                published = runtime._stop_request_generation >= 2
            if published:
                break
            time.sleep(0.005)
        self.assertTrue(published, "explicit Stop did not publish its authorization")
        release.set()
        driver.join(1.0)
        retry.join(1.0)
        self.assertFalse(driver.is_alive())
        self.assertFalse(retry.is_alive())

        service.begin_shutdown = original_shutdown
        retry_id = retry_result["id"]
        self.assertEqual(retry_id, service.snapshot()["pending"]["intentId"])
        runtime._tick()
        self.assertEqual(2, sum(event[0] == "stop" for event in session.events))
        self.assertIsNone(service.snapshot()["gate"]["owner"])

    def test_shutdown_after_published_retry_drives_that_retry_to_completion(self):
        runtime, service, _provider, session, clock = self.make_runtime()
        service.request_start("shutdown_retry_entry", _PROVIDER_FIXTURE["mediaRef"])
        runtime._drive_once(clock.value + 1.0)
        session.stop_ack_without_stopping = True
        entered, release = threading.Event(), threading.Event()
        original_latch = runtime._latch_service_failure

        def blocked_latch(*args, **kwargs):
            entered.set()
            release.wait(2.0)
            return original_latch(*args, **kwargs)

        runtime._latch_service_failure = blocked_latch
        runtime.request_stop()
        driver = threading.Thread(target=runtime._tick)
        driver.start()
        self.assertTrue(entered.wait(1.0))
        session.stop_ack_without_stopping = False
        retry_id = runtime.request_stop()
        release.set()
        driver.join(1.0)
        self.assertFalse(driver.is_alive())
        runtime._latch_service_failure = original_latch

        self.assertEqual("UNAVAILABLE", runtime.snapshot()["phase"])
        self.assertEqual(retry_id, service.snapshot()["pending"]["intentId"])
        begin_count = []
        original_begin_shutdown = service.begin_shutdown

        def count_begin_shutdown():
            begin_count.append(True)
            return original_begin_shutdown()

        service.begin_shutdown = count_begin_shutdown
        runtime.begin_shutdown()
        state = runtime.finish_shutdown(deadline=clock.value + 3.0)
        self.assertEqual("CLOSED", state["phase"])
        self.assertEqual(1, len(begin_count))
        self.assertEqual(2, sum(event[0] == "stop" for event in session.events))
        self.assertTrue(service.snapshot()["quiescent"])

    def test_service_control_and_uuid_callbacks_run_without_runtime_state_lock(self):
        runtime, service, _provider, _session, _clock = self.make_runtime()
        original_uuid4 = uuid.uuid4
        original_request_stop = service.request_stop
        original_begin_shutdown = service.begin_shutdown
        observations = []

        def checked_uuid4():
            observations.append(("uuid", runtime._lock.locked(), service._lock.locked(),
                                 runtime._service_control_active))
            return original_uuid4()

        def checked_request_stop():
            observations.append(("request_stop", runtime._lock.locked(), service._lock.locked(),
                                 runtime._service_control_active))
            return original_request_stop()

        def checked_begin_shutdown():
            observations.append(("begin_shutdown", runtime._lock.locked(), service._lock.locked(),
                                 runtime._service_control_active))
            return original_begin_shutdown()

        service.request_stop = checked_request_stop
        service.begin_shutdown = checked_begin_shutdown
        with patch("components.playback_session.local_playback_service.uuid.uuid4",
                   side_effect=checked_uuid4):
            runtime.request_stop()
            runtime._begin_service_shutdown(service)

        self.assertCountEqual(["uuid", "request_stop", "uuid", "begin_shutdown"],
                              [item[0] for item in observations])
        self.assertTrue(all(not runtime_locked and not service_locked and control_active
                            for _name, runtime_locked, service_locked, control_active
                            in observations), observations)

    def test_shutdown_waits_for_blocked_start_then_drains_without_overlap(self):
        runtime, service, provider, session, clock = self.make_runtime()
        entered, release = threading.Event(), threading.Event()

        def blocked_resolver(_library_id):
            entered.set()
            release.wait(2.0)
            return _PROVIDER_FIXTURE["resolvedMedia"]

        provider.resolver = blocked_resolver
        service.request_start("blocked_entry", _PROVIDER_FIXTURE["mediaRef"])
        driver = threading.Thread(target=runtime._tick)
        driver.start()
        self.assertTrue(entered.wait(1.0))
        closing = runtime.begin_shutdown()
        self.assertFalse(closing["ready"])
        result = {}
        finisher = threading.Thread(target=lambda: result.setdefault(
            "state", runtime.finish_shutdown(deadline=time.monotonic() + 2.0)))
        finisher.start()
        time.sleep(0.03)
        self.assertTrue(finisher.is_alive())
        release.set()
        driver.join(1.0)
        finisher.join(1.0)
        self.assertFalse(driver.is_alive())
        self.assertFalse(finisher.is_alive())
        self.assertEqual("CLOSED", result["state"]["phase"])
        self.assertTrue(service.snapshot()["quiescent"])
        self.assertFalse(runtime.snapshot()["driverAlive"])
        self.assertEqual([], session.events)

    def test_finish_drives_successful_stop_through_pending_retirement(self):
        runtime, service, _provider, session, clock = self.make_runtime()
        service.request_start("runtime_entry", _PROVIDER_FIXTURE["mediaRef"])
        runtime._drive_once(clock.value + 1.0)
        state = runtime.finish_shutdown(deadline=clock.value + 3.0)
        self.assertEqual("CLOSED", state["phase"])
        self.assertTrue(service.snapshot()["quiescent"])
        self.assertEqual(1, sum(event[0] == "stop" for event in session.events))

    def test_stop_timeout_stays_owned_until_explicit_retry_then_finishes(self):
        runtime, service, _provider, session, clock = self.make_runtime()
        service.request_start("runtime_entry", _PROVIDER_FIXTURE["mediaRef"])
        runtime._drive_once(clock.value + 1.0)

        def expire_after_stop(command):
            if command == "stop":
                clock.value = session.deadline

        session.on_command = expire_after_stop
        failed = runtime.finish_shutdown(deadline=clock.value + 0.5)
        self.assertEqual("CLOSING", failed["phase"])
        self.assertEqual({"code": "SHUTDOWN_INCOMPLETE"}, failed["failure"])
        self.assertTrue(failed["ownerLockHeld"] is False)  # fixture owns no OS lock
        self.assertEqual(1, sum(event[0] == "stop" for event in session.events))
        session.on_command = None
        runtime.request_stop()
        closed = runtime.finish_shutdown(deadline=clock.value + 2.0)
        self.assertEqual("CLOSED", closed["phase"])
        self.assertEqual(1, sum(event[0] == "stop" for event in session.events))
        self.assertEqual(3, sum(event[0] == "transaction" for event in session.events))

    def test_bootstrap_failure_keeps_active_flag_until_cleanup_returns(self):
        runtime = LocalPlaybackRuntime(database_path="/tmp/library.sqlite", library_root="/srv/audio",
                                       credential_path="/etc/mpd.secret")
        runtime._phase = "STARTING"
        runtime._bootstrap_active = True
        entered, release = threading.Event(), threading.Event()
        cleanup_calls = []

        class BlockingClient:
            def disconnect(self):
                cleanup_calls.append("cleanup")
                entered.set()
                release.wait(2.0)

        runtime._client = BlockingClient()
        bootstrap = threading.Thread(target=lambda: runtime._fail_bootstrap("BOOTSTRAP_FAILED"))
        bootstrap.start()
        self.assertTrue(entered.wait(1.0))
        self.assertTrue(runtime.snapshot()["bootstrapActive"])
        with self.assertRaises(GateStateError) as raised:
            runtime.start(deadline=time.monotonic() + 2.0)
        self.assertEqual("BUSY", raised.exception.code)
        result = {}
        finisher = threading.Thread(target=lambda: result.setdefault(
            "state", runtime.finish_shutdown(deadline=time.monotonic() + 2.0)))
        finisher.start()
        time.sleep(0.03)
        self.assertTrue(finisher.is_alive())
        release.set()
        bootstrap.join(1.0)
        finisher.join(1.0)
        self.assertFalse(bootstrap.is_alive())
        self.assertFalse(finisher.is_alive())
        self.assertEqual(["cleanup"], cleanup_calls)
        self.assertEqual("CLOSED", result["state"]["phase"])

    def test_concurrent_expired_finish_returns_busy_while_first_finish_is_active(self):
        runtime = LocalPlaybackRuntime(database_path="/tmp/library.sqlite", library_root="/srv/audio",
                                       credential_path="/etc/mpd.secret")
        entered, release = threading.Event(), threading.Event()
        original_finish_until = runtime._finish_until

        def blocked_finish(deadline):
            entered.set()
            release.wait(2.0)
            return original_finish_until(deadline)

        runtime._finish_until = blocked_finish
        first_result = {}
        first = threading.Thread(target=lambda: first_result.setdefault(
            "state", runtime.finish_shutdown(deadline=time.monotonic() + 2.0)))
        first.start()
        self.assertTrue(entered.wait(1.0))
        with self.assertRaises(GateStateError) as raised:
            runtime.finish_shutdown(deadline=time.monotonic() - 1.0)
        self.assertEqual("BUSY", raised.exception.code)
        release.set()
        first.join(1.0)
        self.assertFalse(first.is_alive())
        self.assertEqual("CLOSED", first_result["state"]["phase"])


@unittest.skipUnless(sys.platform.startswith("linux"), "runtime owner requires Linux flock/catalog semantics")
class RuntimeMpdIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "music"
        self.root.mkdir()
        (self.root / "track.flac").write_bytes(b"fixture audio")
        self.database = self.base / "catalog.sqlite3"
        from components.library_catalog.catalog import LibraryCatalog
        catalog = LibraryCatalog(str(self.database), str(self.root))
        self.entry = catalog.register_file("track.flac")
        catalog.close()
        self.credential = self.base / "mpd.secret"
        self.credential.write_text("9876\n", encoding="utf-8")
        self.credential.chmod(0o600)
        self.lock_directory = self.base / "owner-lock"
        self.lock_directory.mkdir(mode=0o700)
        self.lock_directory.chmod(0o700)
        self.server = _SERVER_MODULE.MPDServer()
        self.addCleanup(self.server.close)

    def runtime(self):
        return LocalPlaybackRuntime(database_path=str(self.database), library_root=str(self.root),
                                    credential_path=str(self.credential), mpd_port=self.server.port,
                                    lock_directory=str(self.lock_directory))

    def wait_for(self, predicate):
        expires = time.monotonic() + 2.0
        while time.monotonic() < expires:
            if predicate():
                return
            time.sleep(0.01)
        self.fail("runtime state did not reach expected condition")

    def _run_in_bounded_subprocess(self, test_name):
        environment = os.environ.copy()
        environment["PHONIEBOX_ISOLATED_RUNTIME_TEST"] = test_name
        pytest_config = _STAGE / "pytest.ini"
        if not pytest_config.is_file():
            pytest_config = _STAGE / "context" / "pytest.ini"
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-c",
             str(pytest_config), "-q", "-o",
             "addopts=-rf --import-mode=importlib",
             "test/playback_session/test_runtime.py::RuntimeMpdIntegrationTests::" + test_name],
            cwd=str(_STAGE), env=environment, capture_output=True, text=True, timeout=15.0)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_real_catalog_client_provider_service_and_timer_lifecycle(self):
        runtime = self.runtime()
        started = runtime.start(deadline=time.monotonic() + 3.0)
        self.assertTrue(started["ready"])
        self.assertEqual(["password \"9876\"", "status", "status"], self.server.commands)
        timer = runtime._timer
        started_again = runtime.start(deadline=time.monotonic() + 3.0)
        self.assertIs(timer, runtime._timer)
        self.assertTrue(started_again["ready"])
        ref = {"kind": "LOCAL", "libraryId": self.entry["libraryId"]}
        runtime.request_start("runtime_entry", ref)
        self.wait_for(lambda: (runtime.snapshot()["service"]["gate"]["owner"] or {}).get("entryId")
                      == "runtime_entry"
                      and runtime.snapshot()["service"]["gate"]["inFlight"] is None
                      and runtime.snapshot()["service"]["pending"] is None)
        self.assertIn('playid "0007"', self.server.commands)
        runtime.request_stop()
        self.wait_for(lambda: runtime.snapshot()["service"]["quiescent"])
        stopped = runtime.finish_shutdown(deadline=time.monotonic() + 3.0)
        self.assertEqual("CLOSED", stopped["phase"])
        self.assertFalse(stopped["ownerLockHeld"])
        self.assertFalse(stopped["driverAlive"])
        self.assertEqual(1, self.server.commands.count("stop"))

    def test_playing_and_paused_bootstrap_reconcile_before_readiness(self):
        for initial_state in ("play", "pause"):
            with self.subTest(initial_state=initial_state):
                self.server.state = initial_state
                self.server.songid = "0003"
                self.server.playlistlength = 1
                runtime = self.runtime()
                state = runtime.start(deadline=time.monotonic() + 3.0)
                self.assertTrue(state["ready"])
                self.assertEqual(["password \"9876\"", "status", "stop", "status"],
                                 self.server.commands)
                self.assertEqual("stop", self.server.state)
                self.assertEqual("CLOSED", runtime.finish_shutdown(
                    deadline=time.monotonic() + 3.0)["phase"])
                self.server.commands.clear()
                self.server.state = "stop"
                self.server.songid = None
                self.server.playlistlength = 0

    def test_password_ack_and_malformed_bootstrap_status_fail_closed(self):
        runtime = self.runtime()
        self.server.ack_command = "password"
        rejected = runtime.start(deadline=time.monotonic() + 3.0)
        self.assertFalse(rejected["ready"])
        self.assertEqual("BOOTSTRAP_FAILED", rejected["failure"]["code"])
        self.assertFalse(rejected["ownerLockHeld"])
        self.assertEqual(["password \"9876\""], self.server.commands)

        self.server.ack_command = None
        self.server.commands.clear()
        self.server.invalid_status = True
        malformed = self.runtime().start(deadline=time.monotonic() + 3.0)
        self.assertFalse(malformed["ready"])
        self.assertEqual("BOOTSTRAP_FAILED", malformed["failure"]["code"])
        self.assertFalse(malformed["ownerLockHeld"])

    def test_bootstrap_stop_ack_that_keeps_audio_playing_retains_owner(self):
        if os.environ.get("PHONIEBOX_ISOLATED_RUNTIME_TEST") != self._testMethodName:
            self._run_in_bounded_subprocess(self._testMethodName)
            return
        self.server.state = "play"
        self.server.songid = "0003"
        self.server.playlistlength = 1
        self.server.stop_ack_without_stopping = True
        runtime = self.runtime()
        state = runtime.start(deadline=time.monotonic() + 3.0)
        self.assertFalse(state["ready"])
        self.assertEqual({"code": "STOP_UNCONFIRMED"}, state["failure"])
        self.assertTrue(state["ownerLockHeld"])
        self.assertIsNone(runtime._timer)
        self.assertEqual("play", self.server.state)
        incomplete = runtime.finish_shutdown(deadline=time.monotonic() + 1.0)
        self.assertEqual("STOP_UNCONFIRMED", incomplete["failure"]["code"])
        self.assertTrue(incomplete["ownerLockHeld"])

    def test_runtime_stop_ack_failure_is_dormant_until_explicit_retry(self):
        runtime = self.runtime()
        self.assertTrue(runtime.start(deadline=time.monotonic() + 3.0)["ready"])
        runtime.request_start("runtime_entry", {"kind": "LOCAL", "libraryId": self.entry["libraryId"]})
        self.wait_for(lambda: runtime.snapshot()["service"]["gate"]["owner"] is not None)
        self.server.ack_command = "stop"
        runtime.request_stop()
        self.wait_for(lambda: runtime.snapshot()["failure"] == {"code": "STOP_UNCONFIRMED"})
        self.assertFalse(runtime.snapshot()["ready"])
        failed_stop_count = self.server.commands.count("stop")
        time.sleep(0.35)
        self.assertEqual(failed_stop_count, self.server.commands.count("stop"))
        self.server.ack_command = None
        runtime.request_stop()
        self.wait_for(lambda: runtime.snapshot()["service"]["quiescent"])
        self.assertEqual(2, self.server.commands.count("stop"))
        self.assertEqual("CLOSED", runtime.finish_shutdown(
            deadline=time.monotonic() + 3.0)["phase"])

    def test_shutdown_preserves_explicit_stop_retry_on_real_mpd_session(self):
        runtime = self.runtime()
        self.assertTrue(runtime.start(deadline=time.monotonic() + 3.0)["ready"])
        runtime.request_start("shutdown_retry_tcp", {
            "kind": "LOCAL", "libraryId": self.entry["libraryId"]})
        self.wait_for(lambda: (runtime.snapshot()["service"]["gate"]["owner"] or {}).get("entryId")
                      == "shutdown_retry_tcp"
                      and runtime.snapshot()["service"]["gate"]["inFlight"] is None
                      and runtime.snapshot()["service"]["pending"] is None)

        self.server.ack_command = "stop"
        runtime.request_stop()
        self.wait_for(lambda: runtime.snapshot()["failure"] == {"code": "STOP_UNCONFIRMED"})
        failed_stops = self.server.commands.count("stop")
        self.server.ack_command = None
        retry_id = runtime.request_stop()
        runtime.begin_shutdown()
        self.assertEqual(retry_id, runtime.snapshot()["service"]["pending"]["intentId"])

        closed = runtime.finish_shutdown(deadline=time.monotonic() + 3.0)
        self.assertEqual("CLOSED", closed["phase"])
        self.assertEqual(failed_stops + 1, self.server.commands.count("stop"))
        self.assertFalse(closed["ownerLockHeld"])

    def test_runtime_replacement_confirms_stop_before_successor_start(self):
        runtime = self.runtime()
        self.assertTrue(runtime.start(deadline=time.monotonic() + 3.0)["ready"])
        ref = {"kind": "LOCAL", "libraryId": self.entry["libraryId"]}
        runtime.request_start("entry_first", ref)
        self.wait_for(lambda: (runtime.snapshot()["service"]["gate"]["owner"] or {}).get("entryId")
                      == "entry_first"
                      and runtime.snapshot()["service"]["gate"]["inFlight"] is None
                      and runtime.snapshot()["service"]["pending"] is None)
        runtime.request_start("entry_second", ref)
        self.wait_for(lambda: (runtime.snapshot()["service"]["gate"]["owner"] or {}).get("entryId")
                      == "entry_second"
                      and runtime.snapshot()["service"]["gate"]["inFlight"] is None
                      and runtime.snapshot()["service"]["pending"] is None)
        commands = list(self.server.commands)
        stops = [index for index, command in enumerate(commands) if command == "stop"]
        plays = [index for index, command in enumerate(commands) if command.startswith("playid ")]
        self.assertEqual(1, len(stops))
        self.assertEqual(2, len(plays))
        self.assertLess(plays[0], stops[0])
        self.assertLess(stops[0], plays[1])
        runtime.request_stop()
        self.wait_for(lambda: runtime.snapshot()["service"]["quiescent"])
        self.assertEqual("CLOSED", runtime.finish_shutdown(
            deadline=time.monotonic() + 3.0)["phase"])

    def test_transport_loss_during_start_closes_admission_and_keeps_owner(self):
        if os.environ.get("PHONIEBOX_ISOLATED_RUNTIME_TEST") != self._testMethodName:
            self._run_in_bounded_subprocess(self._testMethodName)
            return
        runtime = self.runtime()
        self.assertTrue(runtime.start(deadline=time.monotonic() + 3.0)["ready"])
        self.server.no_ack_command = "playid"
        runtime.request_start("disconnect_entry", {"kind": "LOCAL", "libraryId": self.entry["libraryId"]})
        self.wait_for(lambda: runtime.snapshot()["phase"] == "UNAVAILABLE")
        self.assertFalse(runtime.snapshot()["ready"])
        with self.assertRaises(GateStateError):
            runtime.request_start("blocked_entry", {"kind": "LOCAL", "libraryId": self.entry["libraryId"]})
        self.server.no_ack_command = None
        runtime.request_stop()
        self.wait_for(lambda: runtime.snapshot()["failure"] == {"code": "STOP_UNCONFIRMED"})
        incomplete = runtime.finish_shutdown(deadline=time.monotonic() + 1.0)
        self.assertEqual("SHUTDOWN_INCOMPLETE", incomplete["failure"]["code"])
        self.assertTrue(incomplete["ownerLockHeld"])
        self.assertTrue(runtime._stop_timer(deadline=time.monotonic() + 1.0))
        self.assertFalse(runtime.snapshot()["driverAlive"])

    def test_unsafe_owner_path_and_credential_fail_before_readiness(self):
        unsafe = self.runtime()
        self.lock_directory.chmod(0o755)
        rejected = unsafe.start(deadline=time.monotonic() + 3.0)
        self.assertEqual({"code": "OWNER_PATH_UNSAFE"}, rejected["failure"])
        self.assertEqual([], self.server.commands)
        self.lock_directory.chmod(0o700)

        self.credential.chmod(0o644)
        rejected_credential = self.runtime().start(deadline=time.monotonic() + 3.0)
        self.assertEqual({"code": "CREDENTIAL_UNAVAILABLE"}, rejected_credential["failure"])
        self.assertFalse(rejected_credential["ownerLockHeld"])
        self.credential.chmod(0o600)

    def test_bootstrap_status_timeout_cleans_owner_without_claiming_ready(self):
        self.server.status_delay = 0.4
        runtime = self.runtime()
        state = runtime.start(deadline=time.monotonic() + 0.15)
        self.assertFalse(state["ready"])
        self.assertEqual("BOOTSTRAP_FAILED", state["failure"]["code"])
        self.assertFalse(state["ownerLockHeld"])

    def test_bootstrap_context_exit_and_epoch_change_fail_before_ready(self):
        original_transaction = MpdSession.transaction
        for mode in ("exit", "epoch"):
            with self.subTest(mode=mode):
                def injected_transaction(session, deadline, mode=mode):
                    @contextmanager
                    def transaction_context():
                        with original_transaction(session, deadline) as transaction:
                            yield transaction
                            if mode == "epoch":
                                session.client._session_epoch = "rotated_bootstrap_epoch"
                        if mode == "exit":
                            raise SessionFailure("TIMEOUT")
                    return transaction_context()

                with patch.object(MpdSession, "transaction", injected_transaction):
                    state = self.runtime().start(deadline=time.monotonic() + 3.0)
                self.assertFalse(state["ready"])
                self.assertEqual("BOOTSTRAP_FAILED", state["failure"]["code"])
                self.assertFalse(state["ownerLockHeld"])
                self.server.commands.clear()

    def test_blocked_bootstrap_and_finish_share_teardown_barrier(self):
        runtime = self.runtime()
        entered, release = threading.Event(), threading.Event()
        original_command = self.server._command

        def block_after_status(conn, line):
            original_command(conn, line)
            if line == "status" and not entered.is_set():
                entered.set()
                release.wait(2.0)

        self.server._command = block_after_status
        started = {}
        starter = threading.Thread(target=lambda: started.setdefault(
            "state", runtime.start(deadline=time.monotonic() + 4.0)))
        starter.start()
        self.assertTrue(entered.wait(1.0))
        finished = {}
        finisher = threading.Thread(target=lambda: finished.setdefault(
            "state", runtime.finish_shutdown(deadline=time.monotonic() + 4.0)))
        finisher.start()
        time.sleep(0.03)
        self.assertTrue(finisher.is_alive())
        release.set()
        starter.join(2.0)
        finisher.join(2.0)
        self.assertFalse(starter.is_alive())
        self.assertFalse(finisher.is_alive())
        self.assertEqual("CLOSING", started["state"]["phase"])
        self.assertEqual("CLOSED", finished["state"]["phase"])
        self.assertFalse(finished["state"]["ownerLockHeld"])

    def test_shutdown_during_mutated_blocked_start_drains_before_disconnect(self):
        runtime = self.runtime()
        self.assertTrue(runtime.start(deadline=time.monotonic() + 3.0)["ready"])
        entered, release = threading.Event(), threading.Event()
        original_command = self.server._command

        def block_after_playid(conn, line):
            original_command(conn, line)
            if line.startswith("playid "):
                entered.set()
                release.wait(2.0)

        self.server._command = block_after_playid
        runtime.request_start("blocked_play", {"kind": "LOCAL", "libraryId": self.entry["libraryId"]})
        self.assertTrue(entered.wait(1.0))
        runtime.begin_shutdown()
        finished = {}
        finisher = threading.Thread(target=lambda: finished.setdefault(
            "state", runtime.finish_shutdown(deadline=time.monotonic() + 4.0)))
        finisher.start()
        time.sleep(0.03)
        self.assertTrue(finisher.is_alive())
        release.set()
        finisher.join(3.0)
        self.assertFalse(finisher.is_alive())
        self.assertEqual("CLOSED", finished["state"]["phase"])
        commands = list(self.server.commands)
        play_index = next(index for index, item in enumerate(commands) if item.startswith("playid "))
        self.assertIn("stop", commands[play_index + 1:])

    def test_second_runtime_cannot_acquire_same_process_owner_lock(self):
        owner = self.runtime()
        contender = self.runtime()
        self.assertTrue(owner.start(deadline=time.monotonic() + 3.0)["ready"])
        state = contender.start(deadline=time.monotonic() + 3.0)
        self.assertEqual({"code": "OWNER_BUSY"}, state["failure"])
        self.assertFalse(state["ownerLockHeld"])
        closed = owner.finish_shutdown(deadline=time.monotonic() + 3.0)
        self.assertEqual("CLOSED", closed["phase"])


class PathLikeFixture:
    def __fspath__(self):
        return "/tmp/pathlike"


if __name__ == "__main__":
    unittest.main()

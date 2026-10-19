"""Real TCP MPD integration for service and injected LOCAL provider."""

import importlib.util
import json
import threading
import time
import unittest
from pathlib import Path

from components.local_provider import LocalProvider
from components.local_provider.mpd_session import MpdSession, TrackedMPDClient
from components.playback_session.local_playback_service import LocalPlaybackService


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "local_provider" / "fixtures" / "v1.json"
SERVER_SOURCE = ROOT / "local_provider" / "test_mpd_session.py"
SPEC = importlib.util.spec_from_file_location("mpd_session_test_support", SERVER_SOURCE)
SERVER_SUPPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SERVER_SUPPORT)
ADAPTER_SOURCE = ROOT / "local_provider" / "test_adapter.py"
ADAPTER_SPEC = importlib.util.spec_from_file_location("local_provider_test_support", ADAPTER_SOURCE)
ADAPTER_SUPPORT = importlib.util.module_from_spec(ADAPTER_SPEC)
ADAPTER_SPEC.loader.exec_module(ADAPTER_SUPPORT)


class ServiceMpdIntegrationTests(unittest.TestCase):
    def setUp(self):
        with FIXTURE.open(encoding="utf-8") as stream:
            self.fixture = json.load(stream)
        self.server = SERVER_SUPPORT.MPDServer()
        self.client = TrackedMPDClient()
        self.client.timeout = None
        self.client.idletimeout = None
        self.client.connect("127.0.0.1", self.server.port)
        self.session = MpdSession(self.client)
        self.clock = time.monotonic
        self.provider = LocalProvider(
            session=self.session,
            resolver=lambda library_id: self.fixture["resolvedMedia"],
            monotonic=self.clock,
            capabilities=self.fixture["capabilities"],
        )
        self.service = LocalPlaybackService(provider=self.provider, boot_id="integration_boot",
                                            monotonic=self.clock)

    def tearDown(self):
        try:
            self.client.disconnect()
        finally:
            self.server.close()
        self.assertTrue(self.server.assert_stopped)

    def step(self):
        return self.service.run_once(deadline=time.monotonic() + 3.0)

    def test_start_replace_stop_start_command_order_is_real(self):
        ref = self.fixture["mediaRef"]
        self.service.request_start("entry_a", ref)
        first = self.step()
        self.assertEqual(first["gate"]["owner"]["entryId"], "entry_a")
        self.service.request_start("entry_b", ref)
        self.step()  # confirmed STOP only
        commands_after_cleanup = list(self.server.commands)
        self.assertEqual(commands_after_cleanup[-3:], ["status", "stop", "status"])
        self.assertEqual(self.service.snapshot()["gate"]["owner"], None)
        self.step()
        self.assertEqual(self.service.snapshot()["gate"]["owner"]["entryId"], "entry_b")
        self.service.request_stop()
        self.step()
        self.assertEqual(self.service.snapshot()["gate"]["owner"], None)
        self.assertEqual(self.server.commands.count('playid "0007"'), 2)
        self.assertEqual(self.server.commands.count("stop"), 2)

    def test_stop_ack_while_playing_latches_until_later_confirmed_stop(self):
        self.service.request_start("ack_entry", self.fixture["mediaRef"])
        self.step()
        self.server.ack_command = "stop"
        self.service.request_stop()
        failed = self.step()
        self.assertEqual(failed["lastFailure"], {"operation": "STOP", "code": "STOP_UNCONFIRMED"})
        self.assertEqual(self.server.state, "play")
        call_count = len(self.server.commands)
        self.step()
        self.assertEqual(len(self.server.commands), call_count)
        self.server.ack_command = None
        self.service.request_stop()
        self.step()
        self.assertEqual(self.server.state, "stop")
        self.assertIsNone(self.service.snapshot()["gate"]["owner"])

    def test_tcp_disconnect_after_playid_retains_uncertain_service_owner(self):
        self.server.no_ack_command = "playid"
        self.service.request_start("disconnect_entry", self.fixture["mediaRef"])
        state = self.step()
        self.assertEqual(state["gate"]["owner"]["entryId"], "disconnect_entry")
        self.assertTrue(state["gate"]["cleanupRequired"])
        self.assertFalse(state["quiescent"])

    def test_tcp_stop_during_mutated_start_requires_correlated_cleanup_first(self):
        entered, release = threading.Event(), threading.Event()
        original_command = self.server._command

        def block_after_wire_mutation(conn, line):
            original_command(conn, line)
            if line.startswith("playid "):
                entered.set()
                if not release.wait(2.0):
                    raise RuntimeError("MPD command barrier timed out")

        self.server._command = block_after_wire_mutation
        self.service.request_start("wire_entry_a", self.fixture["mediaRef"])
        failures = []

        def drive_start():
            try:
                self.service.run_once(deadline=time.monotonic() + 3.0)
            except BaseException as error:
                failures.append(error)

        thread = threading.Thread(target=drive_start)
        thread.start()
        try:
            self.assertTrue(entered.wait(1.0))
            self.service.request_stop()
        finally:
            release.set()
            thread.join(2.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        state = self.service.snapshot()
        self.assertEqual(state["gate"]["owner"]["entryId"], "wire_entry_a")
        self.assertTrue(state["gate"]["cleanupRequired"])
        self.assertNotEqual(state["gate"]["error"], None)
        self.server._command = original_command
        self.step()  # correlated STOP completes before any successor is admitted
        self.assertIsNone(self.service.snapshot()["gate"]["owner"])
        commands = list(self.server.commands)
        playid_position = next(i for i, item in enumerate(commands) if item.startswith("playid "))
        stop_position = commands.index("stop")
        self.assertLess(playid_position, stop_position)
        self.service.request_start("wire_entry_b", self.fixture["mediaRef"])
        self.step()
        later_playids = [i for i, item in enumerate(self.server.commands) if item.startswith("playid ")]
        self.assertEqual(len(later_playids), 2)
        self.assertGreater(later_playids[1], stop_position)
        self.assertEqual(self.service.snapshot()["gate"]["owner"]["entryId"], "wire_entry_b")

    def make_fake_session_service(self, resolver, session=None):
        fixture = self.fixture
        clock = ADAPTER_SUPPORT.FakeClock()
        session = session or ADAPTER_SUPPORT.FakeSession(fixture["initialStatus"])
        session.clock = clock
        provider = LocalProvider(session=session, resolver=resolver, monotonic=clock,
                                 capabilities=fixture["capabilities"])
        service = LocalPlaybackService(provider=provider, boot_id="fake_session_boot", monotonic=clock)
        return service, session, clock

    def test_resolver_blocked_then_stop_suppresses_possible_start_mutation(self):
        entered, release = threading.Event(), threading.Event()

        def resolver(library_id):
            entered.set()
            if not release.wait(2.0):
                raise RuntimeError("resolver release timed out")
            return self.fixture["resolvedMedia"]

        service, session, clock = self.make_fake_session_service(resolver)
        service.request_start("resolver_entry", self.fixture["mediaRef"])
        failures = []

        def drive():
            try:
                service.run_once(deadline=clock.value + 5.0)
            except BaseException as error:
                failures.append(error)

        thread = threading.Thread(target=drive)
        thread.start()
        try:
            self.assertTrue(entered.wait(1.0))
            service.request_stop()
        finally:
            release.set()
            thread.join(2.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(session.events, [])
        self.assertFalse(service.snapshot()["driving"])
        self.assertIsNone(service.snapshot()["gate"]["owner"])
        service.run_once(deadline=clock.value + 5.0)  # settle unowned STOP wish
        self.assertTrue(service.snapshot()["quiescent"])

    def test_shutdown_returns_while_resolver_blocked_then_drains(self):
        entered, release = threading.Event(), threading.Event()

        def resolver(library_id):
            entered.set()
            if not release.wait(2.0):
                raise RuntimeError("resolver release timed out")
            return self.fixture["resolvedMedia"]

        service, session, clock = self.make_fake_session_service(resolver)
        service.request_start("shutdown_entry", self.fixture["mediaRef"])
        failures = []

        def drive():
            try:
                service.run_once(deadline=clock.value + 5.0)
            except BaseException as error:
                failures.append(error)

        thread = threading.Thread(target=drive)
        thread.start()
        try:
            self.assertTrue(entered.wait(1.0))
            state = service.begin_shutdown()
            self.assertTrue(state["closed"])
            self.assertFalse(state["quiescent"])
        finally:
            release.set()
            thread.join(2.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(session.events, [])
        service.run_once(deadline=clock.value + 5.0)
        self.assertTrue(service.snapshot()["quiescent"])

    def test_blocked_playid_invalidation_retains_owner_until_provider_stop(self):
        entered, release = threading.Event(), threading.Event()
        service, session, clock = self.make_fake_session_service(
            lambda library_id: self.fixture["resolvedMedia"])

        def block_after_playid(command):
            if command == "playid":
                entered.set()
                if not release.wait(2.0):
                    raise RuntimeError("protocol release timed out")

        session.on_command = block_after_playid
        service.request_start("mutated_entry", self.fixture["mediaRef"])
        failures = []

        def drive():
            try:
                service.run_once(deadline=clock.value + 5.0)
            except BaseException as error:
                failures.append(error)

        thread = threading.Thread(target=drive)
        thread.start()
        try:
            self.assertTrue(entered.wait(1.0))
            service.request_stop()
        finally:
            release.set()
            thread.join(2.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        state = service.snapshot()
        self.assertEqual(state["gate"]["owner"]["entryId"], "mutated_entry")
        self.assertTrue(state["gate"]["cleanupRequired"])
        self.assertEqual([item[0] for item in session.events if item[0] in {"playid", "stop"}],
                         ["playid"])
        session.on_command = None
        service.run_once(deadline=clock.value + 5.0)
        self.assertIsNone(service.snapshot()["gate"]["owner"])

    def test_context_exit_and_epoch_change_publish_uncertainty(self):
        service, session, clock = self.make_fake_session_service(
            lambda library_id: self.fixture["resolvedMedia"])
        session.fail_on_exit = "TIMEOUT"
        service.request_start("exit_entry", self.fixture["mediaRef"])
        state = service.run_once(deadline=clock.value + 5.0)
        self.assertTrue(state["gate"]["cleanupRequired"])
        self.assertIsNotNone(state["gate"]["owner"])

        service2, session2, clock2 = self.make_fake_session_service(
            lambda library_id: self.fixture["resolvedMedia"])

        def change_epoch(command):
            if command == "playid":
                session2.epoch = "epoch_changed"

        session2.on_command = change_epoch
        service2.request_start("epoch_entry", self.fixture["mediaRef"])
        state2 = service2.run_once(deadline=clock2.value + 5.0)
        self.assertTrue(state2["gate"]["cleanupRequired"])
        self.assertEqual(state2["gate"]["owner"]["entryId"], "epoch_entry")


if __name__ == "__main__":
    unittest.main()

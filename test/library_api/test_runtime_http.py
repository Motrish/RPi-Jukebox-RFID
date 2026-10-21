"""Black-box tests for the bounded HTTP lifecycle of local playback.

The helper owns only the loopback listener and its worker thread. Every
runtime double below exposes exactly the public pair the helper may use:
``snapshot()`` and ``dispatch(command, *, deadline)``. Any other runtime
attribute access fails the test loudly.

Test rules that keep this suite honest:

- Runtime doubles never block unless a test asks for it explicitly.
- Clock doubles are mutable, so a test that arms a clock failure restores it
  before the final drain; teardown drains every helper in its own clock
  domain and is bounded, so a failing assertion can never leak a worker.
"""

import http.client
import importlib
import json
import socket
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock


_STAGE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_STAGE_ROOT / "src" / "jukebox"))

_runtime_http = importlib.import_module("components.library_api.runtime_http")
LocalPlaybackHTTP = _runtime_http.LocalPlaybackHTTP
from components.library_api.server import make_read_authorizer  # noqa: E402
from components.playback_session.execution_gate import GateStateError  # noqa: E402


_TOKEN = "A" * 43
_COMMAND = {"commandId": "c1", "action": "PLAYBACK_START"}
_COMMAND_BODY = json.dumps(_COMMAND).encode("utf-8")
_RESULT = {
    "admission": {"status": "ACCEPTED"},
    "playback": {"lastExecution": {"intentId": "i1"}},
    "operation": "START", "gate": {"owner": None},
    "failure": None, "intentId": "i1", "executionId": "e1",
}
_ITEMS = [{
    "libraryId": "lib_alpha",
    "displayName": "same-name.mp3",
    "availability": "AVAILABLE",
}]


def _free_port():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]
    finally:
        listener.close()


class FakeClock:
    """Mutable monotonic double that fails only while a test arms it."""

    def __init__(self, value=100.0):
        self.value = value
        self.raises = False
        self.broken = False
        self.invalid = None

    def __call__(self):
        if self.raises:
            raise RuntimeError("synthetic clock failure")
        if self.broken:
            return self.invalid
        return self.value

    def restore(self):
        self.raises = False
        self.broken = False


class FakeRuntime:
    """Public-only runtime double: dispatch and snapshot, nothing else."""

    def __init__(self, ready=True, result=None, dispatch=None, block=False):
        self.calls = []
        self.result = _RESULT if result is None else result
        self.block = block
        self.entered = threading.Event()
        self.release = threading.Event()
        self._ready = ready
        self._dispatch = dispatch

    def snapshot(self):
        self.calls.append(("snapshot",))
        return {"ready": self._ready}

    def dispatch(self, command, *, deadline):
        self.calls.append(("dispatch", command, deadline))
        self.entered.set()
        if self._dispatch is not None:
            return self._dispatch(command, deadline)
        if self.block and not self.release.wait(10):
            raise AssertionError("test never released the runtime dispatch")
        return self.result

    def __getattr__(self, name):
        raise AssertionError(
            "runtime must only be reached through dispatch/snapshot: " + name
        )


class FakeCatalog:
    """Record only the two permitted catalog reads."""

    def __init__(self):
        self.calls = []
        self.list_result = {"items": _ITEMS, "nextCursor": None}

    def list_media(self, limit=50, cursor=None):
        self.calls.append(("list_media", limit, cursor))
        return self.list_result

    def get_media(self, library_id):
        self.calls.append(("get_media", library_id))
        if library_id != "lib_alpha":
            return None
        return _ITEMS[0]


class LoopbackClient:
    """Minimal loopback client with a two-phase header and body send."""

    def __init__(self, port):
        self.connection = http.client.HTTPConnection(
            "127.0.0.1", port, timeout=5
        )

    def send_headers(self, method="GET", target="/api/library/media",
                     headers=None, body=None):
        self.connection.putrequest(method, target, skip_host=True)
        for name, value in (headers or {}).items():
            self.connection.putheader(name, value)
        if body is not None:
            self.connection.putheader("Content-Length", str(len(body)))
        self.connection.endheaders()

    def send_body(self, body):
        self.connection.send(body)

    def response(self):
        result = self.connection.getresponse()
        return result.status, result.read()

    def close(self):
        self.connection.close()


class _LifecycleTestCase(unittest.TestCase):
    """Track every helper, runtime and client for fail-closed teardown."""

    def setUp(self):
        self.auth_calls = []
        self.auth_event = threading.Event()
        self.runtimes = []
        self.helpers = []
        self.clients = []
        self.thread_count = threading.active_count()

    def tearDown(self):
        leaked = []
        try:
            for runtime in self.runtimes:
                runtime.release.set()
            for client in self.clients:
                client.close()
        finally:
            for helper, monotonic in self.helpers:
                leaked.append(self.drain(helper, monotonic))
        self.assertEqual(
            [helper for helper in leaked if helper is not None], [],
            "HTTP worker leaked out of the test",
        )

    def drain(self, helper, monotonic):
        """Bounded stop; the last resort unblocks a stuck listener."""
        helper.begin_shutdown()
        for attempt in range(3):
            if helper.finish_shutdown(deadline=self.now(monotonic) + 10.0):
                break
            if attempt == 2:
                helper._close_server()
        if not helper.worker_active:
            return None
        return helper

    @staticmethod
    def now(monotonic):
        try:
            value = monotonic()
        except Exception:
            return 0.0
        return value if type(value) in (int, float) else 0.0

    def authorize(self, credential):
        self.auth_calls.append(credential)
        self.auth_event.set()
        return credential == _TOKEN

    def make_runtime(self, **kwargs):
        runtime = FakeRuntime(**kwargs)
        self.runtimes.append(runtime)
        return runtime

    def make_helper(self, runtime=None, catalog=None, port=0,
                    read_authorizer=None, monotonic=time.monotonic, **kwargs):
        if runtime is None:
            runtime = self.make_runtime()
        if catalog is None:
            catalog = FakeCatalog()
        if read_authorizer is None:
            read_authorizer = self.authorize
        helper = LocalPlaybackHTTP(
            runtime, catalog, read_authorizer, port, monotonic=monotonic,
            **kwargs
        )
        self.helpers.append((helper, monotonic))
        return helper

    def open_client(self, port):
        client = LoopbackClient(port)
        self.clients.append(client)
        return client

    def request(self, port, method="GET", target="/api/library/media",
                headers=None, body=None):
        client = self.open_client(port)
        client.send_headers(method, target, headers, body)
        if body is not None:
            client.send_body(body)
        return client.response()

    def post_command(self, port, headers=None, body=_COMMAND_BODY):
        if headers is None:
            headers = self.valid_headers(port)
        return self.request(
            port, "POST", "/api/playback/commands", headers, body
        )

    def stop(self, helper):
        monotonic = time.monotonic
        for tracked, clock in self.helpers:
            if tracked is helper:
                monotonic = clock
        deadline = self.now(monotonic) + 5.0
        self.assertTrue(helper.finish_shutdown(deadline=deadline))
        self.assertFalse(helper.worker_active)

    @staticmethod
    def valid_headers(port):
        return {
            "Host": "127.0.0.1:{}".format(port),
            "Authorization": "Bearer " + _TOKEN,
        }

    def assert_listener_closed(self, port):
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.assertNotEqual(probe.connect_ex(("127.0.0.1", port)), 0)
        finally:
            probe.close()


class ConstructorValidationTests(_LifecycleTestCase):
    def test_constructor_never_touches_runtime_clock_or_threads(self):
        runtime = self.make_runtime()
        LocalPlaybackHTTP(
            runtime, FakeCatalog(), self.authorize, 0,
            monotonic=lambda: (_ for _ in ()).throw(
                AssertionError("clock ran during construction")
            ),
        )
        self.assertEqual(runtime.calls, [])
        self.assertEqual(threading.active_count(), self.thread_count)

    def test_constructor_rejects_invalid_budget_and_clock(self):
        runtime = self.make_runtime()
        budgets = (True, False, "10", None, object(), 0, -1,
                   float("nan"), float("inf"))
        for budget in budgets:
            with self.subTest(budget=budget):
                with self.assertRaises((TypeError, ValueError)):
                    LocalPlaybackHTTP(
                        runtime, FakeCatalog(), self.authorize, 0,
                        command_budget_seconds=budget,
                    )
        for clock in (None, 5, "monotonic"):
            with self.subTest(clock=clock):
                with self.assertRaises(TypeError):
                    LocalPlaybackHTTP(
                        runtime, FakeCatalog(), self.authorize, 0,
                        monotonic=clock,
                    )
        self.assertEqual(runtime.calls, [])
        self.assertEqual(threading.active_count(), self.thread_count)

    def test_constructor_rejects_invalid_transport_parameters(self):
        runtime = self.make_runtime()
        invalid = (
            {"port": True},
            {"port": -1},
            {"port": 65536},
            {"origin_host": "0.0.0.0"},
            {"read_authorizer": None},
            {"catalog": None},
        )
        for overrides in invalid:
            with self.subTest(overrides=overrides):
                arguments = {
                    "runtime": runtime,
                    "catalog": FakeCatalog(),
                    "read_authorizer": self.authorize,
                    "port": 0,
                }
                arguments.update(overrides)
                with self.assertRaises((TypeError, ValueError)):
                    LocalPlaybackHTTP(**arguments)
        self.assertEqual(runtime.calls, [])
        self.assertEqual(threading.active_count(), self.thread_count)


class StartFailureTests(_LifecycleTestCase):
    def test_unready_runtime_never_binds_or_starts_a_thread(self):
        helper = self.make_helper(runtime=self.make_runtime(ready=False))
        with mock.patch.object(
            _runtime_http._library_server, "make_server"
        ) as make_server:
            with self.assertRaises(RuntimeError) as raised:
                helper.start()
        self.assertIn("not ready", str(raised.exception))
        make_server.assert_not_called()
        self.assertIsNone(helper.address)
        self.assertFalse(helper.worker_active)
        self.assertEqual(threading.active_count(), self.thread_count)
        self.stop(helper)

    def test_missing_or_broken_runtime_never_binds(self):
        helper = LocalPlaybackHTTP(None, FakeCatalog(), self.authorize, 0)
        self.helpers.append((helper, time.monotonic))
        with self.assertRaises(RuntimeError):
            helper.start()
        self.assertEqual(threading.active_count(), self.thread_count)

        broken = self.make_runtime()
        broken.snapshot = lambda: (_ for _ in ()).throw(
            RuntimeError("synthetic snapshot failure")
        )
        helper = self.make_helper(runtime=broken)
        with self.assertRaises(RuntimeError):
            helper.start()
        self.assertIsNone(helper.address)
        self.assertEqual(threading.active_count(), self.thread_count)

    def test_bind_failure_is_visible_and_leaks_no_listener_or_thread(self):
        port = _free_port()
        blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        blocker.bind(("127.0.0.1", port))
        blocker.listen(1)
        try:
            helper = self.make_helper(port=port)
            with self.assertRaises(RuntimeError) as raised:
                helper.start()
        finally:
            blocker.close()
        self.assertIn("listener", str(raised.exception))
        self.assertIsNone(helper.address)
        self.assertFalse(helper.worker_active)
        self.assertEqual(threading.active_count(), self.thread_count)

    def test_thread_start_failure_closes_the_bound_listener(self):
        port = _free_port()

        class FailingThread(threading.Thread):
            def start(self):
                raise RuntimeError("synthetic thread failure")

        helper = self.make_helper(port=port)
        with mock.patch.object(
            _runtime_http.threading, "Thread", FailingThread
        ):
            with self.assertRaises(RuntimeError) as raised:
                helper.start()
        self.assertIn("listener", str(raised.exception))
        self.assertIsNone(helper.address)
        self.assertFalse(helper.worker_active)
        self.assertEqual(threading.active_count(), self.thread_count)
        self.assert_listener_closed(port)

    def test_start_is_single_shot_and_refused_after_shutdown_begin(self):
        helper = self.make_helper()
        helper.start()
        with self.assertRaises(RuntimeError):
            helper.start()
        helper.begin_shutdown()
        with self.assertRaises(RuntimeError):
            helper.start()


class LoopbackDispatchTests(_LifecycleTestCase):
    def test_dispatch_reaches_only_public_runtime_with_budget_deadline(self):
        runtime = self.make_runtime()
        helper = self.make_helper(runtime=runtime, command_budget_seconds=7)
        helper.start()
        before = time.monotonic()
        status, payload = self.post_command(helper.address[1])
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(payload.decode("utf-8")), _RESULT)
        self.assertEqual(len(runtime.calls), 2)
        self.assertEqual(runtime.calls[0], ("snapshot",))
        self.assertEqual(runtime.calls[1][0], "dispatch")
        self.assertEqual(runtime.calls[1][1], _COMMAND)
        self.assertGreaterEqual(runtime.calls[1][2] - before, 7.0)
        self.assertLess(runtime.calls[1][2] - before, 8.0)
        self.stop(helper)

    def test_default_budget_is_ten_seconds_of_injected_clock(self):
        clock = FakeClock(value=250.0)
        runtime = self.make_runtime()
        helper = self.make_helper(runtime=runtime, monotonic=clock)
        helper.start()
        status, _ = self.post_command(helper.address[1])
        self.assertEqual(status, 200)
        self.assertEqual(runtime.calls[-1], ("dispatch", _COMMAND, 260.0))
        self.stop(helper)

    def test_clock_failures_map_to_clock_unavailable_without_dispatch(self):
        for broken in ("raise", float("nan"), float("inf"), "12.0", None):
            with self.subTest(broken=broken):
                clock = FakeClock()
                if broken == "raise":
                    clock.raises = True
                else:
                    clock.broken = True
                    clock.invalid = broken
                runtime = self.make_runtime()
                helper = self.make_helper(runtime=runtime, monotonic=clock)
                helper.start()
                status, payload = self.post_command(helper.address[1])
                self.assertEqual(status, 503)
                self.assertEqual(
                    json.loads(payload.decode("utf-8"))["error"]["code"],
                    "PLAYBACK_SERVICE_UNAVAILABLE",
                )
                self.assertNotIn(b"synthetic clock failure", payload)
                self.assertEqual(runtime.calls, [("snapshot",)])
                clock.restore()
                self.stop(helper)

    def test_clock_unavailable_code_is_the_gate_state_error(self):
        clock = FakeClock()
        clock.raises = True
        helper = self.make_helper(monotonic=clock)
        try:
            with self.assertRaises(GateStateError) as raised:
                helper._dispatch(_COMMAND)
            self.assertEqual(raised.exception.code, "CLOCK_UNAVAILABLE")
        finally:
            clock.restore()

    def test_existing_http_and_authorization_semantics_are_unchanged(self):
        runtime = self.make_runtime()
        catalog = FakeCatalog()
        helper = self.make_helper(
            runtime=runtime, catalog=catalog,
            read_authorizer=make_read_authorizer(_TOKEN),
        )
        helper.start()
        port = helper.address[1]
        self.assertGreater(port, 0)
        headers = self.valid_headers(port)

        status, _ = self.post_command(port, headers={"Host": headers["Host"]})
        self.assertEqual(status, 401)
        self.assertEqual(runtime.calls, [("snapshot",)])

        status, _ = self.request(port, headers={"Host": headers["Host"]})
        self.assertEqual(status, 401)
        self.assertEqual(catalog.calls, [])

        status, payload = self.request(port, headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(
            json.loads(payload.decode("utf-8")),
            {"items": _ITEMS, "nextCursor": None},
        )
        self.assertEqual(catalog.calls, [("list_media", 50, None)])

        status, _ = self.request(
            port, method="PUT", target="/api/library/media", headers=headers
        )
        self.assertEqual(status, 405)
        status, payload = self.request(
            port, target="/api/library/media/lib_alpha/extra",
            headers=headers,
        )
        self.assertEqual(status, 400)
        self.assertEqual(
            json.loads(payload.decode("utf-8"))["error"]["code"],
            "INVALID_REQUEST",
        )
        status, _ = self.request(
            port, target="/api/library/media/lib_missing",
            headers=headers,
        )
        self.assertEqual(status, 404)
        status, _ = self.request(
            port,
            headers={"Host": "example.invalid",
                     "Authorization": "Bearer " + _TOKEN},
        )
        self.assertEqual(status, 400)
        self.stop(helper)

    def test_runtime_gate_errors_keep_the_existing_status_mapping(self):
        runtime = self.make_runtime(
            dispatch=lambda command, deadline: (_ for _ in ()).throw(
                GateStateError("BUSY")
            )
        )
        helper = self.make_helper(runtime=runtime)
        helper.start()
        status, payload = self.post_command(helper.address[1])
        self.assertEqual(status, 409)
        self.assertEqual(
            json.loads(payload.decode("utf-8"))["error"]["code"], "CONFLICT"
        )
        self.stop(helper)

    def test_worker_thread_is_not_daemon(self):
        helper = self.make_helper()
        helper.start()
        self.assertFalse(helper._thread.daemon)
        self.assertTrue(helper.worker_active)
        self.stop(helper)

    def test_address_is_none_before_start_and_exact_tuple_after(self):
        helper = self.make_helper()
        self.assertIsNone(helper.address)
        helper.start()
        self.assertEqual(helper.address[0], "127.0.0.1")
        status, payload = self.post_command(helper.address[1])
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(payload.decode("utf-8")), _RESULT)
        self.stop(helper)
        self.assertIsNone(helper.address)


class ShutdownTests(_LifecycleTestCase):
    def test_accepted_request_is_unauthorized_after_closing(self):
        runtime = self.make_runtime()
        catalog = FakeCatalog()
        helper = self.make_helper(runtime=runtime, catalog=catalog)
        helper.start()
        port = helper.address[1]
        client = self.open_client(port)
        client.send_headers(
            "POST", "/api/playback/commands",
            self.valid_headers(port), _COMMAND_BODY,
        )
        self.assertTrue(self.auth_event.wait(5))

        helper.begin_shutdown()
        client.send_body(_COMMAND_BODY)
        status, payload = client.response()
        self.assertEqual(status, 401)
        self.assertEqual(
            json.loads(payload.decode("utf-8"))["error"]["code"],
            "UNAUTHORIZED",
        )
        self.assertEqual(len(self.auth_calls), 1)
        self.assertEqual(runtime.calls, [("snapshot",)])
        self.assertEqual(catalog.calls, [])
        self.stop(helper)

    def test_no_new_requests_are_accepted_after_closing_and_drain(self):
        runtime = self.make_runtime()
        catalog = FakeCatalog()
        helper = self.make_helper(runtime=runtime, catalog=catalog)
        helper.start()
        port = helper.address[1]
        helper.begin_shutdown()
        self.stop(helper)
        self.assert_listener_closed(port)
        self.assertEqual(runtime.calls, [("snapshot",)])
        self.assertEqual(catalog.calls, [])

    def test_finish_shutdown_is_bounded_and_false_during_body_read(self):
        runtime = self.make_runtime()
        helper = self.make_helper(runtime=runtime)
        helper.start()
        port = helper.address[1]
        client = self.open_client(port)
        client.send_headers(
            "POST", "/api/playback/commands",
            self.valid_headers(port), _COMMAND_BODY,
        )
        self.assertTrue(self.auth_event.wait(5))

        helper.begin_shutdown()
        started = time.monotonic()
        self.assertFalse(helper.finish_shutdown(deadline=started + 0.2))
        self.assertLess(time.monotonic() - started, 3.0)
        self.assertTrue(helper.worker_active)

        client.send_body(_COMMAND_BODY)
        status, payload = client.response()
        self.assertEqual(status, 401)
        self.assertEqual(runtime.calls, [("snapshot",)])
        self.stop(helper)

    def test_blocked_dispatch_blocks_drain_until_the_provider_returns(self):
        clock = FakeClock(value=100.0)
        runtime = self.make_runtime(block=True)
        helper = self.make_helper(runtime=runtime, monotonic=clock)
        helper.start()
        port = helper.address[1]
        client = self.open_client(port)
        client.send_headers(
            "POST", "/api/playback/commands",
            self.valid_headers(port), _COMMAND_BODY,
        )
        client.send_body(_COMMAND_BODY)
        self.assertTrue(runtime.entered.wait(5))

        helper.begin_shutdown()
        self.assertFalse(helper.finish_shutdown(deadline=clock.value + 0.2))
        self.assertTrue(helper.worker_active)

        runtime.release.set()
        status, payload = client.response()
        self.assertEqual(status, 401)
        self.assertNotIn(b"intentId", payload)
        self.assertEqual(
            runtime.calls,
            [("snapshot",), ("dispatch", _COMMAND, clock.value + 10.0)],
        )
        self.stop(helper)

    def test_finish_shutdown_is_idempotent_and_refuses_late_start(self):
        helper = self.make_helper()
        self.stop(helper)
        deadline = time.monotonic() + 2.0
        self.assertTrue(helper.finish_shutdown(deadline=deadline))
        with self.assertRaises(RuntimeError):
            helper.start()

    def test_finish_shutdown_validates_the_deadline_argument(self):
        helper = self.make_helper()
        for deadline in (None, "1", True, 0.0, -1.0, float("nan"),
                         float("inf")):
            with self.subTest(deadline=deadline):
                with self.assertRaises(ValueError):
                    helper.finish_shutdown(deadline=deadline)


if __name__ == "__main__":
    unittest.main()

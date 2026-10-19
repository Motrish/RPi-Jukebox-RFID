"""Contract and real TCP coverage for the shared MPD session."""

import json
import os
import shlex
import subprocess
import sys
import socket
import threading
import time
import unittest
from unittest.mock import patch

import mpd

from components.local_provider.adapter import LocalProvider, SessionFailure
from components.local_provider.mpd_session import MpdLock, MpdSession, TrackedMPDClient


class MPDServer:
    """Small MPD protocol peer for exercising python-mpd2 over real TCP."""

    def __init__(self, *, status_delay=0.0, trickle=False, stop_reading=False):
        self.status_delay = status_delay
        self.trickle = trickle
        self.stop_reading = stop_reading
        self.ack_command = None
        self.no_ack_command = None
        self.invalid_status = False
        self.commands = []
        self.state = "stop"
        self.songid = None
        self.playlistlength = 0
        self.elapsed = 0
        self.option = {"repeat": 0, "random": 0, "single": 0, "consume": 0}
        self.listener = socket.socket()
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen()
        self.listener.settimeout(0.1)
        self.port = self.listener.getsockname()[1]
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _send(self, conn, data):
        if self.trickle:
            for byte in data:
                try:
                    conn.sendall(bytes((byte,)))
                except OSError:
                    return
                time.sleep(0.015)
        else:
            conn.sendall(data)

    def _status(self):
        fields = [
            ("state", self.state), ("playlistlength", str(self.playlistlength)),
            ("repeat", str(self.option["repeat"])), ("random", str(self.option["random"])),
            ("single", str(self.option["single"])), ("consume", str(self.option["consume"])),
        ]
        if self.songid is not None:
            fields.append(("songid", self.songid))
        if self.state in {"play", "pause"}:
            fields.extend((("elapsed", str(self.elapsed)), ("duration", "120")))
        if self.invalid_status:
            fields = [pair for pair in fields if pair[0] != "state"]
        return "".join("%s: %s\n" % pair for pair in fields) + "OK\n"

    def _command(self, conn, line):
        self.commands.append(line)
        parts = shlex.split(line)
        command = parts[0]
        argument = parts[1] if len(parts) > 1 else ""
        if command == self.no_ack_command:
            conn.shutdown(socket.SHUT_RDWR)
            return
        if command == self.ack_command:
            self._send(conn, b"ACK [5@0] {} fixture rejection\n")
            return
        if command == "status":
            if self.status_delay:
                time.sleep(self.status_delay)
            self._send(conn, self._status().encode("utf-8"))
        elif command in self.option:
            self.option[command] = int(argument)
            self._send(conn, b"OK\n")
        elif command == "clear":
            self.state, self.songid, self.playlistlength = "stop", None, 0
            self._send(conn, b"OK\n")
        elif command == "addid":
            self.playlistlength += 1
            self.songid = "0007"
            self._send(conn, b"Id: 0007\nOK\n")
        elif command == "playid":
            self.songid, self.state = argument, "play"
            self._send(conn, b"OK\n")
        elif command == "pause":
            self.state = "pause" if argument == "1" else "play"
            self._send(conn, b"OK\n")
        elif command == "seekid":
            self.elapsed = float(parts[2])
            self._send(conn, b"OK\n")
        elif command == "stop":
            self.state = "stop"
            self._send(conn, b"OK\n")
        else:
            self._send(conn, b"ACK [5@0] {} unknown command\n")

    def _serve(self):
        while not self.stopping.is_set():
            try:
                conn, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            if self._serve_connection(conn):
                return

    def _serve_connection(self, conn):
        with conn:
            conn.settimeout(0.1)
            try:
                self._send(conn, b"OK MPD 0.23.12\n")
                if self.stop_reading:
                    self.stopping.wait(10.0)
                    return True
                return self._read_commands(conn)
            except OSError:
                return False

    def _read_commands(self, conn):
        data = b""
        while not self.stopping.is_set():
            try:
                chunk = conn.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                break
            data += chunk
            while b"\n" in data:
                raw, data = data.split(b"\n", 1)
                line = raw.decode("utf-8")
                if line == "close":
                    return True
                self._command(conn, line)
        return False

    def close(self):
        self.stopping.set()
        self.listener.close()
        self.thread.join(1.0)
        self.assert_stopped = not self.thread.is_alive()


class MPDSessionTests(unittest.TestCase):
    def setUp(self):
        self.server = MPDServer()
        self.client = TrackedMPDClient()
        self.client.timeout = None
        self.client.idletimeout = None
        self.client.connect("127.0.0.1", self.server.port)
        self.session = MpdSession(self.client)

    def tearDown(self):
        try:
            self.client.disconnect()
        except Exception:
            pass
        self.server.close()
        self.assertTrue(self.server.assert_stopped)

    def test_client_is_real_python_mpd_and_session_shares_one_lock(self):
        self.assertIsInstance(self.client, mpd.MPDClient)
        lock = MpdLock(self.client, "127.0.0.1", self.server.port, shared_lock=self.client.shared_lock)
        self.assertIs(lock._lock, self.client.shared_lock)
        self.assertIs(self.session.lock, lock._lock)

    def test_transaction_reads_fresh_status_and_context_cannot_write_after_exit(self):
        with self.session.transaction(time.monotonic() + 1.0) as context:
            epoch = context.epoch
            result = context.status()
        self.assertEqual("stop", result["state"])
        self.assertEqual(epoch, context.epoch)
        with self.assertRaises(SessionFailure) as raised:
            context.stop()
        self.assertEqual("UNAVAILABLE", raised.exception.code)
        self.assertEqual(["status"], self.server.commands)

    def test_foreign_context_exit_cannot_disarm_owner_deadline(self):
        self.server.status_delay = 0.45
        entered = threading.Event()
        owner_context = []
        owner_result = {}
        foreign_result = []

        def run_owner():
            started = time.monotonic()
            deadline = started + 0.12
            try:
                with self.session.transaction(deadline) as context:
                    owner_context.append(context)
                    entered.set()
                    context.status()
            except SessionFailure as failure:
                owner_result["code"] = failure.code
            except Exception as failure:
                owner_result["exception"] = type(failure).__name__
            owner_result["elapsed"] = time.monotonic() - started

        owner = threading.Thread(target=run_owner)
        owner.start()
        self.assertTrue(entered.wait(1.0))
        command_deadline = time.monotonic() + 1.0
        while "status" not in self.server.commands and time.monotonic() < command_deadline:
            time.sleep(0.005)
        self.assertIn("status", self.server.commands)
        context = owner_context[0]
        try:
            context.__exit__(None, None, None)
            foreign_result.append("returned")
        except SessionFailure as failure:
            foreign_result.append(failure.code)
        except Exception as failure:
            foreign_result.append(type(failure).__name__)
        watchdog_state = context._watchdog._state
        owner.join(1.0)

        self.assertFalse(owner.is_alive())
        self.assertEqual(["UNAVAILABLE"], foreign_result)
        self.assertEqual("active", watchdog_state)
        self.assertEqual("TIMEOUT", owner_result.get("code"))
        if os.name != "nt":
            self.assertLess(owner_result["elapsed"], 0.35)
        self.assertTrue(self.client.shared_lock.acquire(timeout=0.1))
        self.client.shared_lock.release()

    def test_retained_context_rejects_foreign_thread_without_protocol_write(self):
        outcomes = []
        with self.session.transaction(time.monotonic() + 1.0) as context:
            thread = threading.Thread(target=lambda: self._foreign_stop(context, outcomes))
            thread.start()
            thread.join(1.0)
            self.assertFalse(thread.is_alive())
        self.assertEqual(["UNAVAILABLE"], outcomes)
        self.assertEqual([], self.server.commands)

    @staticmethod
    def _foreign_stop(context, outcomes):
        try:
            context.stop()
        except SessionFailure as failure:
            outcomes.append(failure.code)

    def test_status_is_one_protocol_command_and_addid_keeps_digit_string(self):
        with self.session.transaction(time.monotonic() + 1.0) as context:
            self.assertEqual("stop", context.status()["state"])
            self.assertEqual("0007", context.addid("albums/demo/track.mp3"))
        self.assertEqual(["status", 'addid "albums/demo/track.mp3"'], self.server.commands)

    def test_disconnected_transaction_does_not_reconnect(self):
        self.client.disconnect()
        before = len(self.server.commands)
        with self.assertRaises(SessionFailure) as raised:
            with self.session.transaction(time.monotonic() + 0.2):
                self.fail("disconnected transaction was entered")
        self.assertEqual("UNAVAILABLE", raised.exception.code)
        self.assertEqual(before, len(self.server.commands))

    def test_lock_contention_expires_without_command_or_reconnect(self):
        acquired = threading.Event()
        release = threading.Event()

        def hold_lock():
            with self.client.shared_lock:
                acquired.set()
                release.wait(1.0)

        holder = threading.Thread(target=hold_lock)
        holder.start()
        self.assertTrue(acquired.wait(1.0))
        try:
            with self.assertRaises(SessionFailure) as raised:
                with self.session.transaction(time.monotonic() + 0.08):
                    self.fail("lock contention transaction entered")
            self.assertEqual("TIMEOUT", raised.exception.code)
        finally:
            release.set()
            holder.join(1.0)
        self.assertFalse(holder.is_alive())
        self.assertEqual([], self.server.commands)

    def test_invalid_deadlines_and_nested_transactions_are_rejected(self):
        for deadline in (True, float("inf"), float("nan"), "soon"):
            with self.subTest(deadline=deadline):
                with self.assertRaises(ValueError):
                    with self.session.transaction(deadline):
                        self.fail("invalid deadline was accepted")
        with self.session.transaction(time.monotonic() + 1.0):
            for nested_session in (self.session, MpdSession(self.client)):
                with self.assertRaises(SessionFailure) as raised:
                    with nested_session.transaction(time.monotonic() + 1.0):
                        self.fail("nested transaction was accepted")
                self.assertEqual("UNAVAILABLE", raised.exception.code)

    def test_trickled_status_is_interrupted_at_absolute_deadline(self):
        self.server.trickle = True
        started = time.monotonic()
        with self.assertRaises(SessionFailure) as raised:
            with self.session.transaction(started + 0.12) as context:
                context.status()
        self.assertEqual("TIMEOUT", raised.exception.code)
        self.assertLess(time.monotonic() - started, 0.6)

    def _provider(self, resolver_result=None):
        with open("test/local_provider/fixtures/v1.json", encoding="utf-8") as stream:
            fixture = json.load(stream)
        provider = LocalProvider(
            session=self.session,
            resolver=lambda library_id: resolver_result if resolver_result is not None else fixture["resolvedMedia"],
            monotonic=time.monotonic,
            capabilities=fixture["capabilities"],
        )
        lease = {"identity": fixture["identity"], "guard": lambda operation, identity: True}
        return provider, fixture, lease

    def test_local_provider_start_then_pause_resume_seek_stop_uses_real_client(self):
        provider, fixture, lease = self._provider()
        deadline = time.monotonic() + 3.0
        started = provider.start(fixture["mediaRef"], lease=lease, deadline=deadline)
        self.assertEqual("CONFIRMED", started["outcome"])
        self.assertEqual("0007", started["songid"])
        self.assertEqual(
            ["status", 'repeat "0"', 'random "0"', 'single "1"',
             'consume "0"', "clear", 'addid "albums/demo/track-01.mp3"',
             'playid "0007"', "status"],
            self.server.commands,
        )
        self.assertEqual("CONFIRMED", provider.pause(lease=lease, deadline=deadline)["outcome"])
        self.assertEqual("CONFIRMED", provider.resume(lease=lease, deadline=deadline)["outcome"])
        self.assertEqual("CONFIRMED", provider.seek(1250, lease=lease, deadline=deadline)["outcome"])
        self.assertEqual("CONFIRMED", provider.stop(lease=lease, deadline=deadline)["outcome"])
        self.assertEqual(1, self.server.commands.count('playid "0007"'))
        self.assertEqual(1, self.server.commands.count("stop"))

    def test_repeated_start_only_reads_fresh_status(self):
        provider, fixture, lease = self._provider()
        deadline = time.monotonic() + 3.0
        self.assertEqual("CONFIRMED", provider.start(fixture["mediaRef"], lease=lease, deadline=deadline)["outcome"])
        before = list(self.server.commands)
        self.assertEqual("CONFIRMED", provider.start(fixture["mediaRef"], lease=lease, deadline=deadline)["outcome"])
        self.assertEqual(before + ["status"], self.server.commands)

    def test_ack_rejection_is_safe_and_not_replayed(self):
        provider, fixture, lease = self._provider()
        self.server.ack_command = "clear"
        receipt = provider.start(fixture["mediaRef"], lease=lease, deadline=time.monotonic() + 2.0)
        self.assertNotEqual("CONFIRMED", receipt["outcome"])
        self.assertEqual(1, self.server.commands.count("clear"))
        self.assertNotIn("fixture rejection", repr(receipt))

    def test_missing_mutation_ack_cannot_confirm_or_retry(self):
        provider, fixture, lease = self._provider()
        self.server.no_ack_command = "playid"
        receipt = provider.start(fixture["mediaRef"], lease=lease, deadline=time.monotonic() + 2.0)
        self.assertNotEqual("CONFIRMED", receipt["outcome"])
        self.assertEqual(1, self.server.commands.count('playid "0007"'))

    def test_carriage_return_resolver_reference_is_rejected_before_mpd_io(self):
        with open("test/local_provider/fixtures/v1.json", encoding="utf-8") as stream:
            fixture = json.load(stream)
        result = dict(fixture["resolvedMedia"])
        result["mpdReference"] = "albums/demo/carriage" + chr(13) + "return.mp3"
        provider, fixture, lease = self._provider(result)

        receipt = provider.start(
            fixture["mediaRef"], lease=lease, deadline=time.monotonic() + 1.0,
        )

        self.assertEqual("REJECTED", receipt["outcome"])
        self.assertEqual("RESOLUTION_FAILED", receipt["error"]["code"])
        self.assertEqual([], self.server.commands)

    def test_malformed_real_status_maps_to_state_mismatch(self):
        provider, fixture, lease = self._provider()
        self.server.invalid_status = True
        receipt = provider.start(fixture["mediaRef"], lease=lease, deadline=time.monotonic() + 2.0)
        self.assertEqual("PROVIDER_STATE_MISMATCH", receipt["error"]["code"])
        self.assertEqual(["status"], self.server.commands)

    def test_already_connected_connect_failure_keeps_epoch_and_socket(self):
        epoch = self.client.session_epoch
        with self.assertRaises(mpd.base.ConnectionError):
            self.client.connect("127.0.0.1", self.server.port)
        self.assertEqual(epoch, self.client.session_epoch)
        with self.session.transaction(time.monotonic() + 1.0) as context:
            self.assertEqual("stop", context.status()["state"])

    def test_explicit_reconnect_rotates_epoch_and_old_context_cannot_write(self):
        with self.session.transaction(time.monotonic() + 1.0) as old:
            old_epoch = old.epoch
        self.client.disconnect()
        self.client.connect("127.0.0.1", self.server.port)
        self.assertNotEqual(old_epoch, self.client.session_epoch)
        self.assertEqual(self.client.session_epoch, old.epoch)
        before = list(self.server.commands)
        with self.assertRaises(SessionFailure) as raised:
            old.stop()
        self.assertEqual("UNAVAILABLE", raised.exception.code)
        self.assertEqual(before, self.server.commands)
        with self.session.transaction(time.monotonic() + 1.0) as current:
            self.assertEqual("stop", current.status()["state"])

    def test_epoch_read_during_disconnect_cannot_overwrite_reconnected_token(self):
        self.client.disconnect()
        self.client._session_epoch = "stale_epoch"
        entered = threading.Event()
        resume = threading.Event()
        original_fileno = self.client.fileno
        values = []

        def delayed_disconnected_fileno():
            entered.set()
            resume.wait(1.0)
            raise mpd.base.ConnectionError("simulated disconnected descriptor")

        self.client.fileno = delayed_disconnected_fileno
        reader = threading.Thread(target=lambda: values.append(self.client.session_epoch))
        reader.start()
        self.assertTrue(entered.wait(1.0))
        self.client.fileno = original_fileno
        self.client.connect("127.0.0.1", self.server.port)
        new_epoch = self.client.session_epoch
        resume.set()
        reader.join(1.0)
        self.assertFalse(reader.is_alive())
        self.assertEqual([None], values)
        self.assertEqual(new_epoch, self.client.session_epoch)

    def test_epoch_rotation_during_context_prevents_success(self):
        old_epoch = self.client.session_epoch
        with self.assertRaises(SessionFailure) as raised:
            with self.session.transaction(time.monotonic() + 1.0):
                self.client._session_epoch = "replacement_epoch"
        self.assertEqual("UNAVAILABLE", raised.exception.code)
        self.assertNotEqual(old_epoch, self.client.session_epoch)
        with self.session.transaction(time.monotonic() + 1.0) as context:
            self.assertEqual("stop", context.status()["state"])

    def test_duplicate_creation_failure_preserves_original_connection(self):
        epoch = self.client.session_epoch
        with patch("components.local_provider.mpd_session.socket.socket", side_effect=OSError("dup fixture")):
            with self.assertRaises(SessionFailure) as raised:
                with self.session.transaction(time.monotonic() + 1.0):
                    self.fail("duplicate failure entered transaction")
        self.assertEqual("UNAVAILABLE", raised.exception.code)
        self.assertEqual(epoch, self.client.session_epoch)
        with self.session.transaction(time.monotonic() + 1.0) as context:
            self.assertEqual("stop", context.status()["state"])

    def test_context_exit_at_deadline_cannot_succeed(self):
        clock = [100.0]
        session = MpdSession(self.client, monotonic=lambda: clock[0])
        with self.assertRaises(SessionFailure) as raised:
            with session.transaction(101.0) as context:
                self.assertEqual("stop", context.status()["state"])
                clock[0] = 101.0
        self.assertEqual("TIMEOUT", raised.exception.code)
        self.assertIsNone(self.client.session_epoch)

    def test_expiry_after_lock_acquisition_preserves_unused_connection(self):
        clock = [100.0]
        session = MpdSession(self.client, monotonic=lambda: clock[0])
        acquired = threading.Event()
        release = threading.Event()

        def hold_lock():
            with self.client.shared_lock:
                acquired.set()
                release.wait(1.0)

        holder = threading.Thread(target=hold_lock)
        holder.start()
        self.assertTrue(acquired.wait(1.0))
        threading.Timer(0.03, lambda: (clock.__setitem__(0, 101.0), release.set())).start()
        try:
            with self.assertRaises(SessionFailure) as raised:
                with session.transaction(101.0):
                    self.fail("expired transaction entered")
            self.assertEqual("TIMEOUT", raised.exception.code)
        finally:
            release.set()
            holder.join(1.0)
        self.assertFalse(holder.is_alive())
        self.assertIsNotNone(self.client.session_epoch)
        with session.transaction(102.0) as context:
            self.assertEqual("stop", context.status()["state"])

    def test_cancelled_watchdog_cannot_interrupt_a_later_transaction(self):
        deadline = time.monotonic() + 0.12
        with self.session.transaction(deadline) as first:
            self.assertEqual("stop", first.status()["state"])
        time.sleep(max(0.0, deadline - time.monotonic()) + 0.03)
        with self.session.transaction(time.monotonic() + 1.0) as second:
            self.assertEqual("stop", second.status()["state"])
        self.assertEqual(["status", "status"], self.server.commands)

    @unittest.skipIf(os.name == "nt", "Windows does not interrupt this blocked send reliably")
    def test_blocked_large_write_is_interrupted_by_owned_socket_shutdown(self):
        marker = "P01A3_BLOCKED_WRITE_CHILD"
        if sys.platform.startswith("linux") and os.environ.get(marker) != "1":
            env = os.environ.copy()
            env[marker] = "1"
            inherited_paths = [os.path.abspath(item or os.getcwd()) for item in sys.path]
            inherited_paths.extend(filter(None, env.get("PYTHONPATH", "").split(os.pathsep)))
            env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(inherited_paths))
            try:
                completed = subprocess.run(
                    [sys.executable, "-m", "unittest",
                     "test_mpd_session.MPDSessionTests.test_blocked_large_write_is_interrupted_by_owned_socket_shutdown"],
                    cwd=os.path.dirname(__file__), env=env, capture_output=True, text=True,
                    timeout=10.0,
                )
            except subprocess.TimeoutExpired:
                self.fail("blocked-write subprocess exceeded its 10 second safety bound")
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            return
        self.client.disconnect()
        self.server.close()
        self.server = MPDServer(stop_reading=True)
        self.client.connect("127.0.0.1", self.server.port)
        self.session = MpdSession(self.client)
        started = time.monotonic()
        with self.assertRaises(SessionFailure) as raised:
            with self.session.transaction(started + 0.15) as context:
                context.addid("x" * (8 * 1024 * 1024))
        self.assertEqual("TIMEOUT", raised.exception.code)
        self.assertLess(time.monotonic() - started, 1.5)
        self.assertEqual([], self.server.commands)

    def test_shutdown_precedes_disconnect_and_disconnect_failure_keeps_session_poisoned(self):
        original_disconnect = self.client.disconnect
        observed = []

        def fail_after_observing_shutdown():
            try:
                observed.append(self._owned.recv(1))
            except OSError:
                observed.append("shutdown")
            raise OSError("simulated cleanup failure")

        self.client.disconnect = fail_after_observing_shutdown
        try:
            with self.assertRaises(SessionFailure) as raised:
                with self.session.transaction(time.monotonic() + 1.0) as context:
                    self._owned = context._socket
                    context._invalidate_transport()
                    self.assertTrue(self.client._session_poisoned)
                    with self.assertRaises(SessionFailure) as inner:
                        context.status()
                    self.assertEqual("UNAVAILABLE", inner.exception.code)
            self.assertEqual("UNAVAILABLE", raised.exception.code)
        finally:
            self.client.disconnect = original_disconnect
        self.assertIn(observed, ([b""], ["shutdown"]))

    def test_resolver_carriage_return_is_rejected_before_any_mpd_command(self):
        provider, fixture, lease = self._provider()
        provider.resolver = lambda library_id: {"libraryId": library_id, "mpdReference": f"relative/path{chr(13)}"}
        receipt = provider.start(fixture["mediaRef"], lease=lease, deadline=time.monotonic() + 1.0)
        self.assertEqual("REJECTED", receipt["outcome"])
        self.assertEqual("RESOLUTION_FAILED", receipt["error"]["code"])
        self.assertEqual([], self.server.commands)

    def test_foreign_exit_preserves_owner_deadline_and_watchdog(self):
        self.server.status_delay = 0.6
        outcomes = {"errors": [], "status_arrived": False, "context": None}
        start_time = time.monotonic()
        deadline_ts = time.monotonic() + 0.12

        def foreign_exit_helper(commands_ref):
            wait_deadline = time.monotonic() + 1.0
            while time.monotonic() < wait_deadline:
                if any("status" in cmd for cmd in commands_ref):
                    outcomes["status_arrived"] = True
                    try:
                        outcomes["context"].__exit__(None, None, None)
                    except SessionFailure as e:
                        outcomes["errors"].append(e.code)
                    except Exception as e:
                        outcomes["errors"].append(type(e).__name__)
                    return
                time.sleep(0.001)
            outcomes["errors"].append("NO_STATUS_ARRIVED")

        helper = threading.Thread(target=foreign_exit_helper, args=(self.server.commands,), daemon=True)

        try:
            with self.assertRaises(SessionFailure) as cm:
                with self.session.transaction(deadline_ts) as context:
                    outcomes["context"] = context
                    helper.start()
                    context.status()

            elapsed = time.monotonic() - start_time
            self.assertEqual(outcomes["errors"], ["UNAVAILABLE"])
            self.assertTrue(outcomes["status_arrived"])
            self.assertEqual(cm.exception.code, "TIMEOUT")
            if os.name != "nt":
                self.assertLess(elapsed, 0.4)
        except Exception as e:
            outcomes["errors"].append(type(e).__name__)
            raise
        finally:
            if helper.ident is not None:
                helper.join(timeout=1.0)
                self.assertFalse(helper.is_alive())


if __name__ == "__main__":
    unittest.main()

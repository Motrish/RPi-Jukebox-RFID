"""Safety and protocol tests for the private hardware probe."""

import importlib.util
import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TEST_DIR = Path(__file__).resolve().parent
STAGE_ROOT = TEST_DIR.parents[1]
sys_path = str(STAGE_ROOT / "src" / "jukebox")
root_path = str(STAGE_ROOT)
if root_path not in os.sys.path:
    os.sys.path.insert(0, root_path)
if sys_path not in os.sys.path:
    os.sys.path.insert(0, sys_path)

TrackedMPDClient = importlib.import_module("components.local_provider.mpd_session").TrackedMPDClient
probe_module = importlib.import_module("tools.hardware.local_provider_probe")
run_probe = probe_module.run_probe


def load_fixture_module():
    fixture_path = TEST_DIR / "test_mpd_session.py"
    spec = importlib.util.spec_from_file_location("p01a4_mpd_fixture", fixture_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MPDServer = load_fixture_module().MPDServer


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "music"
        self.root.mkdir()
        (self.root / "lokal.mp3").write_bytes(b"synthetic protocol fixture")
        self.server = MPDServer()
        self.waits = []

    def tearDown(self):
        self.server.close()
        self.temp.cleanup()

    def run_private_probe(self):
        return run_probe(
            music_root=self.root,
            port=self.server.port,
            wait=lambda seconds: self.waits.append(seconds),
            emit=lambda _receipt: None,
        )

    def test_protocol_sequence_has_one_playid_and_fresh_deadlines(self):
        receipts = self.run_private_probe()
        self.assertEqual(["START", "PAUSE", "RESUME", "SEEK", "STOP"],
                         [receipt["operation"] for receipt in receipts])
        self.assertTrue(all(receipt["outcome"] == "CONFIRMED" for receipt in receipts))
        self.assertEqual([2, 1, 2, 1], self.waits)
        self.assertEqual(1, self.server.commands.count('playid "0007"'))
        self.assertEqual(1, self.server.commands.count("stop"))
        self.assertIn('addid "lokal.mp3"', self.server.commands)

    def test_missing_file_and_symlink_escape_fail_before_client_creation(self):
        track = self.root / "lokal.mp3"
        track.unlink()
        with patch("tools.hardware.local_provider_probe.TrackedMPDClient") as client:
            with self.assertRaises((FileNotFoundError, ValueError)):
                self.run_private_probe()
            client.assert_not_called()
        external = Path(self.temp.name) / "outside.mp3"
        external.write_bytes(b"outside")
        track.symlink_to(external)
        with patch("tools.hardware.local_provider_probe.TrackedMPDClient") as client:
            with self.assertRaises(ValueError):
                self.run_private_probe()
            client.assert_not_called()
        self.assertEqual([], self.server.commands)

    def test_non_stopped_preflight_does_not_mutate_existing_playback(self):
        self.server.state = "play"
        with self.assertRaisesRegex(RuntimeError, "preflight"):
            self.run_private_probe()
        self.assertEqual(["status"], self.server.commands)

    def test_failed_start_ack_uses_same_lease_cleanup_and_no_reconnect(self):
        self.server.ack_command = "playid"
        with patch("tools.hardware.local_provider_probe.TrackedMPDClient.connect",
                   autospec=True, side_effect=TrackedMPDClient.connect) as connect:
            receipts = self.run_private_probe()
        self.assertNotEqual("CONFIRMED", receipts[0]["outcome"])
        self.assertEqual("STOP", receipts[-1]["operation"])
        self.assertEqual(1, connect.call_count)
        self.assertNotIn("PAUSE", [receipt["operation"] for receipt in receipts])
        self.assertEqual(1, self.server.commands.count('playid "0007"'))

    def test_missing_start_response_does_not_reconnect_or_issue_later_actions(self):
        self.server.no_ack_command = "playid"
        with patch("tools.hardware.local_provider_probe.TrackedMPDClient.connect",
                   autospec=True, side_effect=TrackedMPDClient.connect) as connect:
            receipts = self.run_private_probe()
        self.assertNotEqual("CONFIRMED", receipts[0]["outcome"])
        self.assertEqual("STOP", receipts[-1]["operation"])
        self.assertEqual(1, connect.call_count)
        self.assertNotIn("PAUSE", [receipt["operation"] for receipt in receipts])
        self.assertEqual(1, self.server.commands.count('playid "0007"'))

    def test_wait_interruption_attempts_owned_cleanup_and_preserves_failure(self):
        def interrupt(_seconds):
            raise KeyboardInterrupt("interrupted wait")
        with self.assertRaisesRegex(KeyboardInterrupt, "interrupted wait"):
            run_probe(music_root=self.root, port=self.server.port, wait=interrupt, emit=lambda _: None)
        self.assertEqual(1, self.server.commands.count("stop"))

    def test_primary_output_failure_survives_cleanup_output_failure_and_disconnects(self):
        original_disconnect = TrackedMPDClient.disconnect

        def fail_output(_receipt):
            raise BrokenPipeError("closed output")

        with patch("tools.hardware.local_provider_probe.TrackedMPDClient.disconnect",
                   autospec=True, side_effect=original_disconnect) as disconnect:
            with self.assertRaisesRegex(BrokenPipeError, "closed output"):
                run_probe(music_root=self.root, port=self.server.port, emit=fail_output)
        self.assertEqual(1, disconnect.call_count)

    def test_cleanup_stop_failure_preserves_interrupted_wait_and_disconnects(self):
        def interrupt(_seconds):
            raise KeyboardInterrupt("primary interrupt")

        with patch.object(probe_module.LocalProvider, "stop", autospec=True,
                          side_effect=OSError("cleanup failed")) as stop:
            with self.assertRaisesRegex(KeyboardInterrupt, "primary interrupt"):
                run_probe(music_root=self.root, port=self.server.port, wait=interrupt,
                          emit=lambda _receipt: None)
        self.assertEqual(1, stop.call_count)

    def test_deadlines_refresh_after_more_than_five_cumulative_wait_seconds(self):
        class Clock:
            value = 100.0

            def __call__(self):
                return self.value

            def advance(self, seconds):
                self.value += seconds

        clock = Clock()
        observed = []
        original_transaction = probe_module.MpdSession.transaction

        def capture_transaction(session, deadline):
            observed.append((clock(), deadline))
            return original_transaction(session, deadline)

        with patch.object(probe_module.MpdSession, "transaction", autospec=True,
                          side_effect=capture_transaction):
            receipts = run_probe(music_root=self.root, port=self.server.port,
                                 wait=clock.advance, emit=lambda _receipt: None, monotonic=clock)
        self.assertTrue(all(item[1] - item[0] == 5.0 for item in observed))
        self.assertGreater(observed[-1][0] - observed[1][0], 5.0)
        self.assertEqual("CONFIRMED", receipts[-1]["outcome"])


if __name__ == "__main__":
    unittest.main()

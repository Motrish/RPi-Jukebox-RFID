"""Real OS-SIGTERM coordination checks for the opt-in daemon profile.

The child runs the real JukeBox and LocalPlaybackRuntime against the existing
real-TCP MPD fixture. Fixture barriers let the parent deliver SIGTERM while
the main thread is inside bootstrap or while the driver is draining a START.
"""

import importlib.util
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import threading
import unittest

_STAGE = Path(__file__).resolve().parents[2]
_SOURCE = _STAGE / "src" / "jukebox"
_SERVER_FILE = _STAGE / "test" / "local_provider" / "test_mpd_session.py"
_SERVER_SPEC = importlib.util.spec_from_file_location(
    "daemon_sigterm_mpd_support", _SERVER_FILE)
_SERVER_MODULE = importlib.util.module_from_spec(_SERVER_SPEC)
_SERVER_SPEC.loader.exec_module(_SERVER_MODULE)

_CHILD = r'''
import os, sys, time
from components.playback_session.runtime import LocalPlaybackRuntime
from jukebox.daemon import JukeBox

config_path, port, lock_dir, mode, library_id = sys.argv[1:]
import jukebox.daemon as daemon
daemon._LOCAL_SIGNAL_BUDGET_SECONDS = 1.0
daemon._LOCAL_START_BUDGET_SECONDS = 3.0
JukeBox._make_local_runtime = staticmethod(lambda config: LocalPlaybackRuntime(
    database_path=config.getn("local_playback", "database_path"),
    library_root=config.getn("local_playback", "library_root"),
    credential_path=config.getn("local_playback", "credential_path"),
    mpd_port=int(port), lock_directory=lock_dir))
instance = JukeBox(config_path, False)
handler = instance.signal_handler
def observed_signal(signum, frame):
    handler(signum, frame)
    print("sigterm-handled", flush=True)
import signal
signal.signal(signal.SIGTERM, observed_signal)
if mode == "drain":
    def submit_start():
        print("daemon-ready", flush=True)
        instance._local_runtime.request_start(
            "sigterm_blocked_start",
            {"kind": "LOCAL", "libraryId": library_id})
    instance._load_local_modules = submit_start
else:
    instance._load_local_modules = lambda: None
instance._close_local_modules = lambda: None
sys.exit(instance.run())
'''


@unittest.skipUnless(sys.platform.startswith("linux"),
                     "OS SIGTERM delivery test requires Linux")
class DaemonOsSigtermTests(unittest.TestCase):
    """Exercise Python's main-thread OS signal delivery."""

    def _read_child_line(self, child, timeout):
        selector = selectors.DefaultSelector()
        try:
            selector.register(child.stdout, selectors.EVENT_READ)
            self.assertTrue(selector.select(timeout),
                            "daemon child did not reach its barrier")
            line = child.stdout.readline()
            self.assertTrue(line,
                            "daemon child closed stdout before its barrier")
            return line.rstrip("\n")
        finally:
            selector.close()

    def _run_signal_case(self, mode):
        server = _SERVER_MODULE.MPDServer()
        self.addCleanup(server.close)
        entered, release = threading.Event(), threading.Event()
        original_command = server._command

        def barrier_command(conn, line):
            if ((mode == "startup" and line == "status")
                    or (mode == "drain" and line.startswith("playid "))):
                entered.set()
                if not release.wait(5.0):
                    raise RuntimeError(
                        "parent did not release MPD fixture barrier")
            original_command(conn, line)

        server._command = barrier_command
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = root / "library"
            library.mkdir()
            (library / "track.flac").write_bytes(b"fixture audio")
            database = root / "library.sqlite3"
            credential = root / "mpd.secret"
            credential.write_text("9876\n", encoding="utf-8")
            credential.chmod(0o600)
            lock = root / "owner-lock"
            lock.mkdir(mode=0o700)
            lock.chmod(0o700)

            from components.library_catalog.catalog import LibraryCatalog
            catalog = LibraryCatalog(str(database), str(library))
            entry = catalog.register_file("track.flac")
            catalog.close()

            config = root / "jukebox.yaml"
            config.write_text(
                "local_playback:\n"
                "  enabled: true\n"
                "  database_path: {!r}\n"
                "  library_root: {!r}\n"
                "  credential_path: {!r}\n"
                "modules:\n  named: {{}}\n  others: []\n".format(
                    str(database), str(library), str(credential)),
                encoding="utf-8")
            env = os.environ.copy()
            env["PYTHONPATH"] = os.pathsep.join(
                filter(None, [str(_SOURCE), env.get("PYTHONPATH", "")]))
            child = subprocess.Popen(
                [sys.executable, "-c", _CHILD, str(config), str(server.port),
                 str(lock), mode, entry["libraryId"]],
                cwd=str(_STAGE), env=env, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, bufsize=1)
            try:
                if mode == "drain":
                    self.assertEqual(
                        "daemon-ready", self._read_child_line(child, 5.0))
                self.assertTrue(
                    entered.wait(5.0), "daemon did not reach the MPD barrier")
                child.send_signal(signal.SIGTERM)
                self.assertEqual(
                    "sigterm-handled", self._read_child_line(child, 2.0))
                release.set()
                returncode = child.wait(timeout=5.0)
                stderr = child.stderr.read()
                self.assertEqual(0, returncode, stderr)
                if mode == "drain":
                    self.assertGreaterEqual(
                        server.commands.count("stop"), 1, server.commands)
                    self.assertLess(
                        next(i for i, command in enumerate(server.commands)
                             if command.startswith("playid ")),
                        max(i for i, command in enumerate(server.commands)
                            if command == "stop"),
                        server.commands)
                else:
                    self.assertFalse(
                        any(command.startswith("playid ")
                            for command in server.commands),
                        server.commands)
            finally:
                release.set()
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=2.0)

    def test_os_sigterm_during_blocked_runtime_startup_finishes_cleanly(self):
        self._run_signal_case("startup")

    def test_os_sigterm_during_blocked_start_drain_finishes_cleanly(self):
        self._run_signal_case("drain")


if __name__ == "__main__":
    unittest.main()

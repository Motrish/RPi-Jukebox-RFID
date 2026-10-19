"""Cross-process coverage for the Linux playback owner lock."""

import importlib.util
import json
import os
from pathlib import Path
import selectors
import stat
import subprocess
import sys
import tempfile
import unittest

_STAGE = Path(__file__).resolve().parents[2]
if sys.platform.startswith("linux"):
    _SERVER_FILE = _STAGE / "test" / "local_provider" / "test_mpd_session.py"
    _SERVER_SPEC = importlib.util.spec_from_file_location("runtime_process_lock_mpd_support", _SERVER_FILE)
    _SERVER_MODULE = importlib.util.module_from_spec(_SERVER_SPEC)
    _SERVER_SPEC.loader.exec_module(_SERVER_MODULE)


_CHILD = r"""
import json, os, socket, sys, time
from components.playback_session.runtime import LocalPlaybackRuntime

config = json.loads(os.environ["RUNTIME_LOCK_CONFIG"])
os.chdir(config["cwd"])
attempts = []
original_connect = socket.socket.connect
def observed_connect(sock, address):
    if isinstance(address, tuple) and address[:2] == ("127.0.0.1", config["port"]):
        attempts.append(address)
    return original_connect(sock, address)
socket.socket.connect = observed_connect
runtime = LocalPlaybackRuntime(
    database_path=config["database"], library_root=config["library"],
    credential_path=config["credential"], mpd_port=config["port"],
    lock_directory=config["lock"],
)
state = runtime.start(deadline=time.monotonic() + 5.0)
print(json.dumps({"event": "started", "state": state, "connectAttempts": len(attempts)}), flush=True)
if config["hold"] and state["ready"]:
    sys.stdin.readline()
    closed = runtime.finish_shutdown(deadline=time.monotonic() + 3.0)
    print(json.dumps({"event": "closed", "state": closed}), flush=True)
"""


@unittest.skipUnless(sys.platform.startswith("linux"), "process owner flock semantics require Linux")
class RuntimeProcessLockTests(unittest.TestCase):
    def test_helper_acquires_and_releases_exclusive_descriptor(self):
        from components.playback_session.runtime import (
            _OwnerBusy, _acquire_audio_owner_descriptor,
        )

        with tempfile.TemporaryDirectory() as temporary:
            lock = Path(temporary) / "owner-lock"
            lock.mkdir(mode=0o700)
            lock.chmod(0o700)
            descriptor = _acquire_audio_owner_descriptor(lock_directory=str(lock))
            try:
                info = os.fstat(descriptor)
                self.assertTrue(stat.S_ISREG(info.st_mode))
                self.assertEqual(0o600, stat.S_IMODE(info.st_mode))
                with self.assertRaises(_OwnerBusy):
                    _acquire_audio_owner_descriptor(lock_directory=str(lock))
            finally:
                os.close(descriptor)

            released = _acquire_audio_owner_descriptor(lock_directory=str(lock))
            os.close(released)

    def test_helper_rejects_unsafe_and_missing_directories(self):
        from components.playback_session.runtime import (
            _OwnerUnsafe, _acquire_audio_owner_descriptor,
        )

        with tempfile.TemporaryDirectory() as temporary:
            unsafe = Path(temporary) / "unsafe-lock"
            unsafe.mkdir(mode=0o755)
            unsafe.chmod(0o755)
            with self.assertRaises(_OwnerUnsafe):
                _acquire_audio_owner_descriptor(lock_directory=str(unsafe))
            self.assertFalse((unsafe / "audio-owner.lock").exists())

            missing = Path(temporary) / "missing-lock"
            with self.assertRaises(_OwnerUnsafe):
                _acquire_audio_owner_descriptor(lock_directory=str(missing))
            self.assertFalse(missing.exists())

    def test_different_cwds_contend_before_mpd_connect_and_preserve_lock_inode(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            library = base / "library"
            library.mkdir()
            (library / "track.flac").write_bytes(b"fixture audio")
            database = base / "catalog.sqlite3"
            credential = base / "mpd.secret"
            credential.write_text("9876\n", encoding="utf-8")
            credential.chmod(0o600)
            lock = base / "owner-lock"
            lock.mkdir(mode=0o700)
            lock.chmod(0o700)
            owner_cwd, contender_cwd = base / "owner-cwd", base / "contender-cwd"
            owner_cwd.mkdir()
            contender_cwd.mkdir()

            from components.library_catalog.catalog import LibraryCatalog
            catalog = LibraryCatalog(str(database), str(library))
            catalog.register_file("track.flac")
            catalog.close()

            server = _SERVER_MODULE.MPDServer()
            self.addCleanup(server.close)
            source_paths = (str(_STAGE / "src" / "jukebox"),)
            pythonpath = os.pathsep.join(filter(None, [*source_paths, os.environ.get("PYTHONPATH", "")]))

            def launch(cwd, hold):
                config = {"cwd": str(cwd), "database": str(database), "library": str(library),
                          "credential": str(credential), "lock": str(lock),
                          "port": server.port, "hold": hold}
                env = os.environ.copy()
                env["PYTHONPATH"] = pythonpath
                env["RUNTIME_LOCK_CONFIG"] = json.dumps(config)
                return subprocess.Popen([sys.executable, "-c", _CHILD], cwd=str(cwd), env=env,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True, bufsize=1)

            def read_line(process, timeout):
                selector = selectors.DefaultSelector()
                try:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    if not selector.select(timeout):
                        self.fail("runtime child did not report before its deadline")
                    line = process.stdout.readline()
                    if not line:
                        returncode = process.poll()
                        if returncode is None:
                            self.fail("runtime child closed stdout without exiting")
                        stderr = process.stderr.read()
                        self.fail("runtime child exited with code {} without a result; stderr: {}"
                                   .format(returncode, stderr))
                    return json.loads(line)
                finally:
                    selector.close()

            owner = launch(owner_cwd, True)
            contender = None
            try:
                owner_result = read_line(owner, 8.0)
                self.assertTrue(owner_result["state"]["ready"], owner_result)
                self.assertEqual(1, owner_result["connectAttempts"])
                lock_path = lock / "audio-owner.lock"
                inode_before = lock_path.stat().st_ino

                contender = launch(contender_cwd, False)
                contender_result = read_line(contender, 8.0)
                self.assertEqual({"code": "OWNER_BUSY"}, contender_result["state"]["failure"])
                self.assertEqual(0, contender_result["connectAttempts"],
                                 "contender attempted the MPD socket before reporting OWNER_BUSY")
                self.assertEqual(0, contender.wait(timeout=3.0))
                self.assertEqual(inode_before, lock_path.stat().st_ino)
            finally:
                if contender is not None and contender.poll() is None:
                    contender.kill()
                    contender.wait(timeout=2.0)
                if owner.poll() is None:
                    try:
                        owner.stdin.write("release\n")
                        owner.stdin.flush()
                        closed = read_line(owner, 5.0)
                        self.assertEqual("CLOSED", closed["state"]["phase"])
                    finally:
                        try:
                            owner.stdin.close()
                        except OSError:
                            pass
                        try:
                            owner.wait(timeout=5.0)
                        except subprocess.TimeoutExpired:
                            owner.kill()
                            owner.wait(timeout=2.0)
                if owner.returncode not in (None, 0):
                    self.fail(owner.stderr.read())
                if "inode_before" in locals():
                    self.assertTrue((lock / "audio-owner.lock").exists())
                    self.assertEqual(inode_before, (lock / "audio-owner.lock").stat().st_ino)


if __name__ == "__main__":
    unittest.main()

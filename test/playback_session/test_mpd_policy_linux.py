"""Exercise the staged MPD policy against an isolated real MPD process.

Run on Linux with MPD 0.24.x installed:
    python3 -m unittest -v test/playback_session/test_mpd_policy_linux.py
"""

import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import wave
from pathlib import Path


TIMEOUT = float(os.environ.get("MPD_POLICY_TEST_TIMEOUT", "3.0"))
EXAMPLE = (
    Path(__file__).resolve().parents[2]
    / "resources"
    / "default-settings"
    / "mpd.local-playback.example.conf"
)


def mpd_version(binary):
    result = subprocess.run(
        [binary, "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=TIMEOUT,
        check=False,
    )
    return parse_mpd_version(result.stdout)


def parse_mpd_version(output):
    """Return the major/minor pair from MPD's actual --version banner."""
    match = re.search(r"^Music Player Daemon (\d+)\.(\d+)(?:\.|\s)", output, re.M)
    return tuple(map(int, match.groups())) if match else None


def free_loopback_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def quote_mpd(value):
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


class MpdPolicyAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not sys.platform.startswith("linux"):
            raise unittest.SkipTest("requires Linux")
        cls.mpd = shutil.which("mpd")
        if cls.mpd is None:
            raise unittest.SkipTest("requires installed MPD 0.24.x")
        cls.version = mpd_version(cls.mpd)
        if not cls.version or cls.version[:2] != (0, 24):
            raise unittest.SkipTest("requires installed MPD 0.24.x")

    def test_default_read_and_owner_permissions(self):
        with tempfile.TemporaryDirectory(prefix="mpd-policy-") as temporary:
            owner_password = secrets.token_urlsafe(32)
            wrong_password = secrets.token_urlsafe(32)
            bootstrap_password = secrets.token_urlsafe(32)
            root = Path(temporary)
            music = root / "music"
            music.mkdir()
            (root / "playlists").mkdir()
            self._write_silent_track(music / "fixture.wav")
            port = free_loopback_port()
            config = self._private_config(root, port, owner_password)

            # MPD's local music database must contain the fixture before the
            # sample's deliberately non-admin owner can add it to the queue.
            # Build that private database with a short-lived isolated process,
            # then stop it before starting the policy process under test.
            bootstrap_config = root / "mpd-bootstrap.conf"
            bootstrap_config.write_text(
                config.read_text(encoding="utf-8")
                + f'\npassword "{bootstrap_password}@admin,read,add,control"\n',
                encoding="utf-8",
            )
            bootstrap = subprocess.Popen(
                [self.mpd, "--no-daemon", "--stderr", str(bootstrap_config)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                self._wait_ready(bootstrap, port)
                self.assert_command_ok(port, "update", password=bootstrap_password)
                deadline = time.monotonic() + TIMEOUT * 4
                while time.monotonic() < deadline:
                    ok, lines = self._exchange(port, "listall", password=bootstrap_password)
                    if ok and any(line == b"file: fixture.wav\n" for line in lines):
                        break
                    time.sleep(0.05)
                else:
                    self.fail("isolated MPD did not index the private fixture track")
            finally:
                self._stop_owned_child(bootstrap)

            # The subprocess is created by this test and is the only process
            # this fixture may terminate. Its logs are discarded to avoid
            # leaking the temporary credential through config echoes.
            child = subprocess.Popen(
                [self.mpd, "--no-daemon", "--stderr", str(config)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                self._wait_ready(child, port)

                ok, indexed_lines = self._exchange(port, "listall", password=owner_password)
                self.assertTrue(ok, "owner could not read the private MPD database")
                self.assertTrue(
                    any(line == b"file: fixture.wav\n" for line in indexed_lines),
                    "owner could not find the indexed private fixture track",
                )
                self.assert_command_ok(port, "status")
                self.assert_permission_denied(port, "clear")
                self.assert_permission_denied(port, 'addid "fixture.wav"')
                self.assert_permission_denied(port, "pause 1")

                self.assert_wrong_password_gets_no_write_grant(
                    port, wrong_password
                )
                ok, added = self._exchange(
                    port, 'addid "fixture.wav"', password=owner_password
                )
                self.assertTrue(ok, "owner could not add the fixture track")
                song_id = self._added_song_id(added)
                self.assert_command_ok(port, f"playid {song_id}", password=owner_password)
                self.assert_command_ok(port, "pause 1", password=owner_password)
                self.assert_command_ok(port, "stop", password=owner_password)
            finally:
                self._stop_owned_child(child)

    @staticmethod
    def _stop_owned_child(child):
        if child.poll() is not None:
            child.wait()
            return
        child.terminate()
        try:
            child.wait(timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            # This handle belongs only to the child created by this fixture.
            child.kill()
            child.wait(timeout=TIMEOUT)

    @staticmethod
    def _write_silent_track(path):
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(8000)
            output.writeframes(b"\0\0" * 800)

    def _private_config(self, root, port, owner_password):
        source = EXAMPLE.read_text(encoding="utf-8")
        replacements = {
            'music_directory "/home/pi/RPi-Jukebox-RFID/shared/audiofolders"':
                f"music_directory {quote_mpd(str(root / 'music'))}",
            'playlist_directory "/var/lib/mpd/playlists"':
                f"playlist_directory {quote_mpd(str(root / 'playlists'))}",
            'db_file "/var/lib/mpd/tag_cache"':
                f"db_file {quote_mpd(str(root / 'tag_cache'))}",
            'state_file "/var/lib/mpd/state"':
                f"state_file {quote_mpd(str(root / 'state'))}",
            'sticker_file "/var/lib/mpd/sticker.sql"':
                f"sticker_file {quote_mpd(str(root / 'sticker.sql'))}",
            'port "6601"': f'port "{port}"',
            'password "REPLACE_WITH_A_LONG_RANDOM_SECRET@read,add,control"':
                f'password "{owner_password}@read,add,control"',
        }
        for original, replacement in replacements.items():
            if source.count(original) != 1:
                self.fail("staged MPD example did not contain one expected policy line")
            source = source.replace(original, replacement, 1)
        source += '\naudio_output {\n    type "null"\n    name "isolated policy test"\n}\n'
        path = root / "mpd.conf"
        path.write_text(source, encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
        return path

    def _wait_ready(self, child, port):
        deadline = time.monotonic() + TIMEOUT * 4
        while time.monotonic() < deadline:
            if child.poll() is not None:
                self.fail(f"isolated MPD exited before ready (exit {child.returncode})")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.25) as peer:
                    peer.settimeout(0.25)
                    greeting = peer.makefile("rb").readline()
                    if greeting.startswith(b"OK MPD ") and self._owns_listener(child, port):
                        return
            except (OSError, TimeoutError):
                pass
            time.sleep(0.05)
        self.fail("isolated MPD did not accept its loopback connection before deadline")

    @staticmethod
    def _owns_listener(child, port):
        """Avoid sending commands unless this exact child owns the listener."""
        expected_port = f"{port:04X}"
        inodes = set()
        for table in (Path("/proc/net/tcp"), Path("/proc/net/tcp6")):
            try:
                rows = table.read_text(encoding="ascii").splitlines()[1:]
            except OSError:
                continue
            for row in rows:
                fields = row.split()
                if len(fields) > 9 and fields[1].rsplit(":", 1)[-1].upper() == expected_port:
                    inodes.add(fields[9])
        if not inodes:
            return False
        try:
            descriptors = Path(f"/proc/{child.pid}/fd").iterdir()
            for descriptor in descriptors:
                match = re.fullmatch(r"socket:\[(\d+)\]", os.readlink(descriptor))
                if match and match.group(1) in inodes:
                    return True
            return False
        except OSError:
            return False

    def _command(self, port, command, password=None):
        return self._exchange(port, command, password)[0]

    def _added_song_id(self, lines):
        for line in lines:
            match = re.fullmatch(rb"Id: (\d+)\n", line)
            if match:
                return int(match.group(1))
        self.fail("MPD accepted addid without returning a song id")

    def _exchange(self, port, command, password=None):
        # Read only protocol replies. Never include command text or server text
        # in assertion messages, since an MPD error may echo sensitive values.
        with socket.create_connection(("127.0.0.1", port), timeout=TIMEOUT) as peer:
            peer.settimeout(TIMEOUT)
            stream = peer.makefile("rwb")
            greeting = stream.readline()
            if not greeting.startswith(b"OK MPD "):
                self.fail("isolated MPD sent an invalid protocol greeting")
            if password is not None:
                stream.write(f"password {quote_mpd(password)}\n".encode("utf-8"))
                stream.flush()
                auth_reply = stream.readline()
                if not (auth_reply == b"OK\n" or auth_reply.startswith(b"ACK ")):
                    self.fail("isolated MPD sent an invalid authentication reply")
                if auth_reply.startswith(b"ACK "):
                    return False, [auth_reply]
            stream.write((command + "\n").encode("utf-8"))
            stream.flush()
            lines = []
            while True:
                line = stream.readline()
                if not line:
                    self.fail("isolated MPD closed the protocol connection unexpectedly")
                if line == b"OK\n":
                    return True, lines
                if line.startswith(b"ACK "):
                    return False, lines + [line]
                lines.append(line)

    def assert_command_ok(self, port, command, password=None):
        self.assertTrue(self._command(port, command, password), "MPD command was rejected")

    def assert_permission_denied(self, port, command, password=None):
        ok, lines = self._exchange(port, command, password)
        self.assertFalse(ok, "MPD unexpectedly accepted a command without its required permission")
        self.assertTrue(
            any(re.match(rb"ACK \[4@\d+\]", line) for line in lines),
            "MPD rejected a write for a reason other than missing permission",
        )

    def assert_wrong_password_gets_no_write_grant(self, port, password):
        # Verify the failed-authentication state on one connection, including
        # retained read access and denial of each write permission class.
        with socket.create_connection(("127.0.0.1", port), timeout=TIMEOUT) as peer:
            peer.settimeout(TIMEOUT)
            stream = peer.makefile("rwb")
            self.assertTrue(stream.readline().startswith(b"OK MPD "), "invalid MPD greeting")
            stream.write(f"password {quote_mpd(password)}\n".encode("utf-8"))
            stream.flush()
            auth_reply = stream.readline()
            self.assertRegex(
                auth_reply,
                rb"^ACK \[3@\d+\]",
                "MPD did not return the password-rejected protocol error",
            )
            self._assert_stream_command(stream, b"status\n", permission_code=None)
            self._assert_stream_command(stream, b"clear\n", permission_code=4)
            self._assert_stream_command(
                stream, b'addid "fixture.wav"\n', permission_code=4
            )
            self._assert_stream_command(stream, b"pause 1\n", permission_code=4)

    def _assert_stream_command(self, stream, command, permission_code):
        stream.write(command)
        stream.flush()
        while True:
            reply = stream.readline()
            if not reply:
                self.fail("MPD closed the connection during a protocol command")
            if reply == b"OK\n":
                self.assertIsNone(permission_code, "MPD accepted a forbidden write")
                return
            if reply.startswith(b"ACK "):
                if permission_code is None:
                    self.fail("MPD rejected read access after the wrong password")
                self.assertRegex(
                    reply,
                    rf"^ACK \[{permission_code}@\d+\]".encode("ascii"),
                    "MPD returned the wrong protocol error for a denied write",
                )
                return


class MpdVersionParser(unittest.TestCase):
    def test_actual_version_banner_and_unrecognized_output(self):
        self.assertEqual(
            parse_mpd_version("Music Player Daemon 0.24.4 (0.24.4)\n"), (0, 24)
        )
        self.assertIsNone(parse_mpd_version("unrecognized output\n"))


if __name__ == "__main__":
    unittest.main()

"""Safety and compatibility checks for the opt-in daemon owner profile."""

import importlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import textwrap
from types import SimpleNamespace
from unittest.mock import Mock, patch

_STAGE = Path(__file__).resolve().parents[2]
_SOURCE = _STAGE / "src" / "jukebox"
if str(_SOURCE) not in sys.path:
    sys.path.insert(0, str(_SOURCE))

from jukebox.daemon import (  # noqa: E402
    JukeBox,
    _local_profile_enabled,
    _validate_local_modules,
)


class LocalProfileValidationTests(unittest.TestCase):
    class Config:
        def __init__(self, data):
            self.data = data

        def getn(self, *keys, default=None):
            value = self.data
            for key in keys:
                if not isinstance(value, dict) or key not in value:
                    return default
                value = value[key]
            return value

        def get(self, key, default=None):
            return self.data.get(key, default)

    def test_profile_is_absent_by_default_and_requires_boolean(self):
        self.assertFalse(_local_profile_enabled(self.Config({})))
        self.assertFalse(_local_profile_enabled(self.Config({"local_playback": {"enabled": False}})))
        with self.assertRaises(ValueError):
            _local_profile_enabled(self.Config({"local_playback": {"enabled": "true"}}))

    def test_checked_in_example_loads_through_actual_ruamel_config_handler(self):
        import jukebox.cfghandler as cfghandler
        config = cfghandler.ConfigHandler("local-profile-regression")
        example = _STAGE / "resources" / "default-settings" / "jukebox.local-playback.example.yaml"
        cfghandler.load_yaml(config, str(example))
        self.assertTrue(_local_profile_enabled(config))
        _validate_local_modules(config)
        with patch("components.playback_session.runtime.LocalPlaybackRuntime") as runtime:
            JukeBox._make_local_runtime(config)
        runtime.assert_called_once_with(
            database_path="/home/pi/RPi-Jukebox-RFID/data/library.sqlite",
            library_root="/home/pi/RPi-Jukebox-RFID/shared/audiofolders",
            credential_path="/etc/phoniebox/mpd-owner.password",
        )

    def test_allowed_diagnostic_aliases_sources_and_unnamed_modules(self):
        config = self.Config({"modules": {
            "named": {"publishing": "publishing"},
            "others": ["misc"],
        }})
        _validate_local_modules(config)

    def test_forbidden_alias_source_and_others_fail_before_import(self):
        declarations = (
            {"named": {"player": "playermpd"}, "others": []},
            {"named": {"publishing": "player"}, "others": []},
            {"named": {"publishing": "misc"}, "others": []},
            {"named": {}, "others": ["rfid.reader"]},
            {"named": {}, "others": ["hostif.linux"]},
            {"named": {}, "others": ["publishing", "volume"]},
        )
        for modules in declarations:
            with self.subTest(modules=modules):
                with self.assertRaises(ValueError):
                    _validate_local_modules(self.Config({"modules": modules}))

    def test_bad_modules_container_fails_closed(self):
        for modules in (None, [], {"named": [], "others": []}, {"named": {}, "others": {}}):
            with self.subTest(modules=modules):
                with self.assertRaises(ValueError):
                    _validate_local_modules(self.Config({"modules": modules}))

    def test_invalid_opt_in_config_fails_before_runtime_or_legacy_import(self):
        import jukebox.daemon as daemon_module

        invalid = self.Config({
            "local_playback": {"enabled": True},
            "modules": {"named": {"player": "playermpd"}, "others": []},
        })
        with (
            patch.object(daemon_module, "cfg", invalid),
            patch("jukebox.cfghandler.load_yaml"),
            patch.object(JukeBox, "_make_local_runtime") as make_runtime,
            patch.object(daemon_module, "_load_legacy_modules") as load_legacy,
        ):
            with self.assertRaisesRegex(ValueError, "forbidden"):
                JukeBox("unused.yaml", False)
        make_runtime.assert_not_called()
        load_legacy.assert_not_called()

    def test_missing_opt_in_selects_legacy_profile(self):
        import jukebox.daemon as daemon_module

        fd = os.open(os.devnull, os.O_RDONLY)
        legacy_modules = (
            SimpleNamespace(nv_manager=lambda: "legacy-nvm"),
            object(), object(), object(),
            SimpleNamespace(get_git_state=lambda: "legacy-git-state"),
            lambda value: value,
        )
        config = self.Config({})
        try:
            with (
                patch.object(daemon_module, "cfg", config),
                patch("jukebox.cfghandler.load_yaml"),
                patch.object(daemon_module.jukebox, "version",
                             return_value="test-version", create=True),
                patch.object(daemon_module, "_acquire_audio_owner", return_value=fd),
                patch.object(daemon_module, "_load_legacy_modules",
                             return_value=legacy_modules),
            ):
                instance = JukeBox("existing.yaml", False)
            self.assertFalse(instance._local_profile)
            self.assertEqual("legacy-nvm", instance.nvm)
            self.assertEqual("legacy-git-state", instance.git_state)
            self.assertEqual(fd, instance._legacy_owner_descriptor)
        finally:
            os.close(fd)

    def test_daemon_import_does_not_import_forbidden_legacy_modules(self):
        forbidden = ("jukebox.rpc.server", "jukebox.NvManager", "components.rfid",
                     "components.playermpd", "components.gpio")
        for name in forbidden:
            sys.modules.pop(name, None)
        importlib.reload(importlib.import_module("jukebox.daemon"))
        self.assertFalse(any(name in sys.modules for name in forbidden))

    def test_required_diagnostic_module_failure_is_propagated_after_cleanup(self):
        import jukebox.daemon as daemon_module
        import jukebox.plugs as plugin

        instance = object.__new__(JukeBox)
        instance._local_runtime = Mock()
        instance._local_runtime.start.return_value = {"ready": True, "failure": None}
        instance._local_runtime.finish_shutdown.side_effect = [
            {"phase": "CLOSING", "ready": False, "quiescent": True,
             "driverAlive": False, "ownerLockHeld": True, "failure": None},
            {"phase": "CLOSED", "quiescent": True,
             "driverAlive": False, "ownerLockHeld": False, "failure": None},
        ]
        instance._local_signal_seen = True
        instance._local_shutdown_deadline = None
        instance._local_signal = None
        with (
            patch.object(daemon_module, "cfg", self.Config({
                "modules": {"named": {"publishing": "publishing"}, "others": ["misc"]}})),
            patch.object(plugin, "load_all_named",
                          side_effect=ImportError("required publisher missing")),
        ):
            with self.assertRaisesRegex(ImportError, "required publisher missing"):
                instance._run_local()
        instance._local_runtime.begin_shutdown.assert_called_once_with()
        self.assertEqual(2, instance._local_runtime.finish_shutdown.call_count)
        self.assertFalse(instance._local_runtime.finish_shutdown.call_args_list[0].kwargs["release_owner"])
        self.assertTrue(instance._local_runtime.finish_shutdown.call_args_list[1].kwargs["release_owner"])

    def test_failed_diagnostic_shutdown_joins_returned_threads_and_retains_owner(self):
        import jukebox.plugs as plugin

        daemon = object.__new__(JukeBox)
        daemon._local_profile = True
        daemon._local_signal_seen = True
        daemon._local_shutdown_deadline = time.monotonic() + 2.0
        daemon._local_signal = signal.SIGTERM
        daemon._local_runtime = Mock()
        daemon._local_runtime.start.return_value = {"ready": True, "failure": None}
        daemon._local_runtime.finish_shutdown.return_value = {
            "phase": "CLOSING", "ready": False, "quiescent": True,
            "driverAlive": False, "ownerLockHeld": True, "failure": None,
        }
        released = threading.Event()
        worker = threading.Thread(target=released.wait, daemon=True)
        worker.start()
        threading.Timer(0.05, released.set).start()
        failure = plugin.PluginShutdownError([worker], [("publishing", object(), RuntimeError())])
        with patch.object(plugin, "close_down", side_effect=failure):
            self.assertEqual(1, daemon._run_local())
        self.assertTrue(released.is_set())
        self.assertFalse(worker.is_alive())
        self.assertEqual(1, daemon._local_runtime.finish_shutdown.call_count)
        self.assertFalse(daemon._local_runtime.finish_shutdown.call_args.kwargs["release_owner"])

    @unittest.skipUnless(sys.platform.startswith("linux"), "canonical owner path is Linux-only")
    def test_existing_unsafe_canonical_directory_is_never_repaired(self):
        import jukebox.daemon as daemon_module

        info = SimpleNamespace(st_mode=0o120777, st_uid=os.geteuid())
        with (
            patch.object(daemon_module.os, "mkdir", side_effect=FileExistsError),
            patch.object(daemon_module.os, "lstat", return_value=info),
            patch.object(daemon_module.os, "chmod") as chmod,
        ):
            with self.assertRaisesRegex(RuntimeError, "unsafe"):
                daemon_module._ensure_audio_owner_directory()
        chmod.assert_not_called()


@unittest.skipUnless(sys.platform.startswith("linux"), "flock ownership semantics require Linux")
class DaemonProfileProcessTests(unittest.TestCase):
    def test_legacy_owner_excludes_local_runtime_before_mpd_connect(self):
        import jukebox.daemon as daemon_module
        descriptor = daemon_module._acquire_audio_owner()
        self.addCleanup(os.close, descriptor)
        script = r'''
import json, socket, sys, time
from components.playback_session.runtime import LocalPlaybackRuntime
attempts = []
connect = socket.socket.connect
def observed(sock, address):
    attempts.append(address)
    return connect(sock, address)
socket.socket.connect = observed
runtime = LocalPlaybackRuntime(
    database_path="/tmp/c2.sqlite", library_root="/tmp/c2-audio",
    credential_path="/tmp/c2-secret", mpd_port=1)
state = runtime.start(deadline=time.monotonic() + 2.0)
print(json.dumps({"state": state, "connects": len(attempts)}), flush=True)
'''
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            [str(_SOURCE), env.get("PYTHONPATH", "")])
        child = subprocess.Popen(
            [sys.executable, "-c", script], cwd=str(_STAGE), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        selector = selectors.DefaultSelector()
        try:
            selector.register(child.stdout, selectors.EVENT_READ)
            self.assertTrue(selector.select(4.0), "local contender did not report")
            result = json.loads(child.stdout.readline())
            self.assertEqual({"code": "OWNER_BUSY"}, result["state"]["failure"])
            self.assertEqual(0, result["connects"])
            self.assertEqual(0, child.wait(timeout=2.0), child.stderr.read())
        finally:
            selector.close()
            if child.poll() is None:
                child.kill()
                child.wait(timeout=2.0)


class LocalSignalShutdownTests(unittest.TestCase):
    def make_daemon(self):
        daemon = object.__new__(JukeBox)
        daemon._local_profile = True
        daemon._local_signal_seen = False
        daemon._local_shutdown_deadline = None
        daemon._local_signal = None
        return daemon

    def test_first_signal_only_sets_plain_flag_and_fixed_deadline(self):
        daemon = self.make_daemon()
        with patch("jukebox.daemon.time.monotonic", side_effect=[100.0, 500.0]), \
                patch.object(JukeBox, "_run_local") as run_local:
            daemon.signal_handler(signal.SIGTERM, None)
            deadline = daemon._local_shutdown_deadline
            daemon.signal_handler(signal.SIGTERM, None)
        self.assertTrue(daemon._local_signal_seen)
        self.assertEqual(signal.SIGTERM, daemon._local_signal)
        self.assertEqual(110.0, deadline)
        self.assertEqual(deadline, daemon._local_shutdown_deadline)
        run_local.assert_not_called()

    def test_restricted_shutdown_requires_closed_quiescent_dead_driver(self):
        daemon = self.make_daemon()
        daemon._local_signal_seen = True
        daemon._local_shutdown_deadline = 120.0
        daemon._local_signal = signal.SIGTERM
        runtime = Mock()
        runtime.start.return_value = {"ready": True, "failure": None}
        runtime.finish_shutdown.side_effect = [
            {"phase": "CLOSING", "ready": False, "quiescent": True,
             "driverAlive": False, "ownerLockHeld": True, "failure": None},
            {"phase": "CLOSED", "quiescent": True, "driverAlive": False,
             "ownerLockHeld": False},
        ]
        daemon._local_runtime = runtime
        with patch.object(JukeBox, "_close_and_join_local_modules", return_value=True):
            daemon._run_local()
        runtime.begin_shutdown.assert_called_once_with()
        self.assertEqual(2, runtime.finish_shutdown.call_count)
        self.assertEqual({"deadline": 120.0, "release_owner": False},
                         runtime.finish_shutdown.call_args_list[0].kwargs)
        self.assertEqual({"deadline": 120.0, "release_owner": True},
                         runtime.finish_shutdown.call_args_list[1].kwargs)

        runtime.finish_shutdown.side_effect = None
        runtime.finish_shutdown.return_value = {
            "phase": "CLOSING", "ready": False, "quiescent": True,
            "driverAlive": False, "ownerLockHeld": True, "failure": None,
        }
        with patch.object(JukeBox, "_close_and_join_local_modules", return_value=True):
            self.assertEqual(1, daemon._run_local())

    def test_signal_during_blocked_synchronous_bootstrap_defers_shutdown_to_main_flow(self):
        daemon = self.make_daemon()
        entered, release = threading.Event(), threading.Event()
        runtime = Mock()

        def blocked_start(**_kwargs):
            entered.set()
            self.assertTrue(release.wait(2.0))
            return {"ready": True, "failure": None}

        runtime.start.side_effect = blocked_start
        runtime.finish_shutdown.side_effect = [
            {"phase": "CLOSING", "ready": False, "quiescent": True,
             "driverAlive": False, "ownerLockHeld": True, "failure": None},
            {"phase": "CLOSED", "quiescent": True,
             "driverAlive": False, "ownerLockHeld": False},
        ]
        daemon._local_runtime = runtime
        results = []
        with (
            patch.object(JukeBox, "_load_local_modules"),
            patch.object(JukeBox, "_close_and_join_local_modules", return_value=True),
        ):
            worker = threading.Thread(target=lambda: results.append(daemon._run_local()))
            worker.start()
            self.assertTrue(entered.wait(1.0))
            daemon.signal_handler(signal.SIGTERM, None)
            runtime.begin_shutdown.assert_not_called()
            release.set()
            worker.join(3.0)
        self.assertFalse(worker.is_alive())
        self.assertEqual([0], results)
        runtime.begin_shutdown.assert_called_once_with()
        self.assertEqual(daemon._local_shutdown_deadline,
                         runtime.finish_shutdown.call_args_list[0].kwargs["deadline"])

    def test_signal_during_blocked_driver_drain_keeps_first_deadline(self):
        daemon = self.make_daemon()
        daemon._local_signal_seen = True
        daemon._local_shutdown_deadline = 110.0
        daemon._local_signal = signal.SIGTERM
        entered, release = threading.Event(), threading.Event()
        runtime = Mock()
        runtime.start.return_value = {"ready": True, "failure": None}

        def blocked_finish(*, deadline, release_owner):
            self.assertEqual(110.0, deadline)
            if release_owner:
                return {"phase": "CLOSED", "quiescent": True,
                        "driverAlive": False, "ownerLockHeld": False}
            entered.set()
            self.assertTrue(release.wait(2.0))
            return {"phase": "CLOSING", "ready": False, "quiescent": True,
                    "driverAlive": False, "ownerLockHeld": True, "failure": None}

        runtime.finish_shutdown.side_effect = blocked_finish
        daemon._local_runtime = runtime
        result = []
        with (
            patch.object(JukeBox, "_load_local_modules"),
            patch.object(JukeBox, "_close_and_join_local_modules", return_value=True),
        ):
            worker = threading.Thread(target=lambda: result.append(daemon._run_local()))
            worker.start()
            self.assertTrue(entered.wait(1.0))
            daemon.signal_handler(signal.SIGTERM, None)
            self.assertEqual(110.0, daemon._local_shutdown_deadline)
            release.set()
            worker.join(3.0)
        self.assertFalse(worker.is_alive())
        self.assertEqual([0], result)


class EntrypointProcessTests(unittest.TestCase):
    def test_entrypoint_returns_stub_status_after_invoking_daemon_with_explicit_config(self):
        entrypoint = _SOURCE / "run_jukebox.py"
        script = textwrap.dedent("""
            import runpy
            import sys
            import types
            from types import SimpleNamespace
            import jukebox.daemon
            misc = types.ModuleType("misc")
            loggingext = types.ModuleType("misc.loggingext")
            import logging
            loggingext.configure_default = lambda *args, **kwargs: logging.getLogger("test")
            loggingext.configure_from_file = lambda *args, **kwargs: logging.getLogger("test")
            misc.loggingext = loggingext
            sys.modules["misc"] = misc
            sys.modules["misc.loggingext"] = loggingext
            def make_daemon(*args):
                return SimpleNamespace(run=lambda: (print("RUN_SENTINEL", flush=True), 73)[1])
            jukebox.daemon.get_jukebox_daemon = make_daemon
            sys.argv = [sys.argv[1], "--conf", sys.argv[2], "-v"]
            runpy.run_path(sys.argv[0], run_name="__main__")
        """)
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            [str(_SOURCE), env.get("PYTHONPATH", "")])
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "jukebox.yaml"
            config.write_text("{}\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-c", script, str(entrypoint), str(config)],
                cwd=str(_SOURCE), env=env, capture_output=True, text=True, timeout=5.0)
        self.assertEqual(73, result.returncode, result.stdout + result.stderr)
        self.assertIn("RUN_SENTINEL", result.stdout)


if __name__ == "__main__":
    unittest.main()

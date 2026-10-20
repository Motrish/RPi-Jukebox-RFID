# -*- coding: utf-8 -*-
"""Jukebox daemon with the compatible legacy profile and gated local playback."""

import atexit
from collections.abc import Mapping, Sequence
import logging
import os
import signal
import stat
import sys
import threading
import time
from typing import Optional

import jukebox
import jukebox.cfghandler

logger = logging.getLogger("jb.daemon")
cfg = jukebox.cfghandler.get_handler("jukebox")
_LOCAL_SIGNAL_BUDGET_SECONDS = 10.0
_LOCAL_START_BUDGET_SECONDS = 30.0
_ALLOWED_NAMED_MODULES = {"misc", "publishing"}
_ALLOWED_OTHER_MODULES = {"misc", "publishing"}


@atexit.register
def log_active_threads():
    """Report threads that remain when the process exits."""
    logger.debug("Active Threads = %s", threading.enumerate())


def _local_profile_enabled(config):
    section = config.get("local_playback", default={})
    if not isinstance(section, Mapping):
        raise ValueError("local_playback must be a mapping")
    value = section.get("enabled", False)
    if type(value) is not bool:
        raise ValueError("local_playback.enabled must be a boolean")
    return value


def _validate_local_modules(config):
    """Validate the complete plugin declaration before importing any plugin code."""
    modules = config.get("modules", default={})
    if not isinstance(modules, Mapping):
        raise ValueError("local playback requires modules mapping")
    named = modules.get("named", {})
    others = modules.get("others", [])
    if (not isinstance(named, Mapping)
            or not isinstance(others, Sequence)
            or isinstance(others, (str, bytes, bytearray))):
        raise ValueError("local playback requires modules.named mapping and modules.others sequence")
    for alias, source in named.items():
        if type(alias) is not str or alias not in _ALLOWED_NAMED_MODULES:
            raise ValueError("local playback contains a forbidden module alias")
        if type(source) is not str or source not in _ALLOWED_NAMED_MODULES:
            raise ValueError("local playback contains a forbidden module source")
        if alias != source:
            raise ValueError("local playback module alias must match its source package")
    for source in others:
        if type(source) is not str or source not in _ALLOWED_OTHER_MODULES:
            raise ValueError("local playback contains a forbidden unnamed module source")


def _ensure_audio_owner_directory():
    """Create the single canonical owner directory only when it is absent."""
    if not (os.name == "posix" and sys.platform.startswith("linux")):
        raise RuntimeError("audio owner is supported only on Linux")
    path = "/tmp/phoniebox-playback-%s" % os.geteuid()
    created = False
    try:
        os.mkdir(path, 0o700)
        created = True
    except FileExistsError:
        pass
    if created:
        os.chmod(path, 0o700, follow_symlinks=False)
    info = os.lstat(path)
    if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)
            or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700):
        raise RuntimeError("audio owner directory is unsafe")
    return path


def _acquire_audio_owner():
    _ensure_audio_owner_directory()
    from components.playback_session.runtime import _acquire_audio_owner_descriptor
    return _acquire_audio_owner_descriptor()


def _load_legacy_modules():
    # Keep these imports out of module initialization: the restricted profile must
    # reject configuration before legacy hardware and RPC packages are imported.
    import jukebox.NvManager
    import jukebox.plugs
    import jukebox.publishing
    import jukebox.rpc.server
    import jukebox.utils
    from misc import flatten
    return jukebox.NvManager, jukebox.plugs, jukebox.publishing, jukebox.rpc.server, jukebox.utils, flatten


class JukeBox:
    def __init__(self, configuration_file: str, write_artifacts: bool):
        self._start_time = time.time()
        self._git_state = None
        self._signal_cnt = 0
        self.rpc_server = None
        self._local_runtime = None
        self._legacy_owner_descriptor = None
        self._local_signal_seen = False
        self._local_shutdown_deadline = None
        self._local_signal = None
        self.write_artifacts = write_artifacts

        jukebox.cfghandler.load_yaml(cfg, configuration_file)
        self._local_profile = _local_profile_enabled(cfg)
        if self._local_profile:
            _validate_local_modules(cfg)
            self._local_runtime = self._make_local_runtime(cfg)
            _ensure_audio_owner_directory()
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
            logger.info("Starting Jukebox Daemon in restricted local playback profile")
            return

        self._legacy_owner_descriptor = _acquire_audio_owner()
        try:
            (self._nv_module, self._plugin, self._publishing, self._rpc_module,
             self._utils, self._flatten) = _load_legacy_modules()
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
            logger.info("Starting Jukebox Daemon (Version %s)", jukebox.version())
            self._git_state = self._utils.get_git_state()
            logger.info("Git state: %s", self._git_state)
            self.nvm = self._nv_module.nv_manager()
            logger.info("Welcome to " + cfg.getn("system", "box_name",
                                                default="Jukebox Version 3"))
            logger.info("Time of start: %s", time.ctime(self._start_time))
        except BaseException:
            os.close(self._legacy_owner_descriptor)
            self._legacy_owner_descriptor = None
            raise

    @staticmethod
    def _make_local_runtime(config):
        from components.playback_session.runtime import LocalPlaybackRuntime

        section = config.getn("local_playback", default={})
        required = ("database_path", "library_root", "credential_path")
        values = {}
        for key in required:
            value = section.get(key) if isinstance(section, Mapping) else None
            if type(value) is not str or not value.startswith("/") or "\x00" in value:
                raise ValueError("local_playback configuration is incomplete or invalid")
            values[key] = value
        return LocalPlaybackRuntime(**values)

    @property
    def start_time(self):
        return self._start_time

    @property
    def git_state(self):
        return self._git_state

    def signal_handler(self, esignal, frame):
        if self._local_profile:
            if not self._local_signal_seen:
                self._local_signal_seen = True
                self._local_signal = esignal
                self._local_shutdown_deadline = time.monotonic() + _LOCAL_SIGNAL_BUDGET_SECONDS
            return
        self._signal_cnt += 1
        timeout = 5.0
        time_start = time.time_ns()
        msg = f"Received signal '{signal.Signals(esignal).name}'. Count = {self._signal_cnt}"
        print(msg)
        logger.debug(msg)
        if self._signal_cnt == 1:
            t = threading.Thread(target=self.exit_gracefully, args=[esignal, timeout],
                                 daemon=True, name="ShutdownThread")
            t.start()
            t.join(timeout)
            if t.is_alive():
                msg = f"Shutdown handler timed out after {timeout} s"
                print(f"Shutdown incomplete. {msg}. Terminating now forcefully!")
                print(f"Active Threads = {threading.enumerate()}")
                logger.error(msg)
                logger.error("Active Threads = %s", threading.enumerate())
                sys.exit(1)
            logger.info("Shutdown time: %.3f ms", (time.time_ns() - time_start) / 1_000_000.0)
            sys.exit(0)
        elif self._signal_cnt == 2:
            print("Waiting for closing down procedure to complete. Pressing Ctrl-C again will close Jukebox down immediately.")
        if self._signal_cnt == 3:
            sys.exit(1)

    def exit_gracefully(self, esignal, timeout):
        cfg_local = cfg
        plugin = self._plugin
        if self.rpc_server is not None:
            self.rpc_server.terminate()
        plugin.call_ignore_errors("player", "ctrl", "stop")
        thread_list = list(filter(lambda x: x is not None,
                                  self._flatten(plugin.close_down(signal_id=esignal))))
        self.nvm.save_all()
        cfg_local.save(only_if_changed=True)
        for thread in thread_list:
            thread.join()
        logger.info("All done. Hear you soon!")

    def _run_local(self):
        state = self._local_runtime.start(deadline=time.monotonic() + _LOCAL_START_BUDGET_SECONDS)
        if not state["ready"]:
            logger.error("Local playback runtime did not become ready: %s", state["failure"])
            return 1
        try:
            self._load_local_modules()
        except BaseException:
            deadline = self._local_shutdown_deadline_or_new()
            try:
                if self._prepare_local_runtime(deadline):
                    if self._close_and_join_local_modules(deadline):
                        self._release_prepared_runtime(deadline)
            except BaseException:
                logger.exception("Cleanup after restricted module initialization failed")
            raise
        while not self._local_signal_seen:
            time.sleep(0.05)
        deadline = self._local_shutdown_deadline_or_new()
        if not self._prepare_local_runtime(deadline):
            return 1
        if not self._close_and_join_local_modules(deadline):
            return 1
        return 0 if self._release_prepared_runtime(deadline) else 1

    def _local_shutdown_deadline_or_new(self):
        if self._local_shutdown_deadline is None:
            self._local_shutdown_deadline = time.monotonic() + _LOCAL_SIGNAL_BUDGET_SECONDS
        return self._local_shutdown_deadline

    def _prepare_local_runtime(self, deadline):
        self._local_runtime.begin_shutdown()
        state = self._local_runtime.finish_shutdown(deadline=deadline, release_owner=False)
        prepared = (state["phase"] == "CLOSING" and not state["ready"]
                    and state["quiescent"] and not state["driverAlive"]
                    and state["ownerLockHeld"] and state["failure"] is None)
        if not prepared:
            logger.error("Local playback runtime did not reach prepared shutdown: %s", state)
        return prepared

    def _close_and_join_local_modules(self, deadline):
        import jukebox.plugs as plugin
        shutdown_failed = False
        try:
            threads = self._close_local_modules()
        except plugin.PluginShutdownError as error:
            threads = error.results
            shutdown_failed = True
            logger.error("Restricted diagnostic module shutdown failed: %s", error)
        threads_joined = _join_plugin_threads(threads, deadline)
        if not threads_joined:
            logger.error("Local playback diagnostic modules did not close before deadline")
        return not shutdown_failed and threads_joined

    def _release_prepared_runtime(self, deadline):
        state = self._local_runtime.finish_shutdown(deadline=deadline, release_owner=True)
        clean = (state["phase"] == "CLOSED" and state["quiescent"]
                 and not state["driverAlive"] and not state["ownerLockHeld"])
        if not clean:
            logger.error("Local playback final shutdown incomplete: %s", state)
        return clean

    def _load_local_modules(self):
        import jukebox.plugs as plugin
        plugin.load_all_named(cfg.getn("modules", "named", default={}),
                              prefix="components", ignore_errors=False)
        plugin.load_all_unnamed(cfg.getn("modules", "others", default=[]),
                                prefix="components", ignore_errors=False)
        plugin.load_all_finalize(ignore_errors=False)

    def _close_local_modules(self):
        import jukebox.plugs as plugin
        return plugin.close_down(signal_id=self._local_signal, ignore_errors=False)

    def run(self):
        if self._local_profile:
            return self._run_local()
        return self._run_legacy()

    def _run_legacy(self):
        time_start = time.time_ns()
        try:
            return self._run_legacy_owned(time_start)
        finally:
            if self._legacy_owner_descriptor is not None:
                os.close(self._legacy_owner_descriptor)
                self._legacy_owner_descriptor = None

    def _run_legacy_owned(self, time_start):
        plugin = self._plugin
        publishing = self._publishing
        plugins_named = cfg.getn("modules", "named", default={})
        plugins_other = cfg.getn("modules", "others", default=[])
        plugin.load_all_named(plugins_named, prefix="components", ignore_errors=True)
        plugin.load_all_unnamed(plugins_other, prefix="components", ignore_errors=True)
        plugin.load_all_finalize(ignore_errors=True)
        pack_ok = plugin.call_ignore_errors("misc", "get_all_loaded_packages")
        pack_error = plugin.call_ignore_errors("misc", "get_all_failed_packages")
        logger.info("Loaded plugins: %s", ", ".join(pack_ok))
        if pack_error:
            logger.error("Plugins with errors during load: %s", ", ".join(pack_error))
        publishing.get_publisher().send("core.plugins.loaded", pack_ok)
        publishing.get_publisher().send("core.plugins.error", pack_error)
        publishing.get_publisher().send("core.started_at", time.ctime(self._start_time))
        publishing.get_publisher().send("core.git_state", self._git_state)
        self.rpc_server = self._rpc_module.RpcServer()
        logger.info("Start-up time: %.3f ms", (time.time_ns() - time_start) / 1_000_000.0)
        if self.write_artifacts:
            import os
            artifacts_dir = "../../shared/artifacts/"
            try:
                os.mkdir(artifacts_dir)
            except FileExistsError:
                pass
            with open(os.path.join(artifacts_dir, "rpc_command_reference.txt"), "w") as stream:
                plugin.dump_plugins(stream)
            with open(os.path.join(artifacts_dir, "rpc_command_alias_reference.txt"), "w") as stream:
                self._utils.generate_cmd_alias_reference(stream)
        self.rpc_server.run()


class JukeBoxBuilder:
    def __init__(self):
        self._instance = None

    def __call__(self, *args, **kwargs):
        if not self._instance:
            self._instance = JukeBox(*args, **kwargs)
        return self._instance


_JUKEBOX_BUILDER: Optional[JukeBoxBuilder] = None


def get_jukebox_daemon(*args, **kwargs):
    global _JUKEBOX_BUILDER
    if _JUKEBOX_BUILDER is None:
        _JUKEBOX_BUILDER = JukeBoxBuilder()
    return _JUKEBOX_BUILDER(*args, **kwargs)


def _join_plugin_threads(value, deadline):
    if value is None:
        return True
    if isinstance(value, (list, tuple, set)):
        complete = True
        for item in value:
            if not _join_plugin_threads(item, deadline):
                complete = False
        return complete
    if not isinstance(value, threading.Thread):
        return True
    value.join(max(0.0, deadline - time.monotonic()))
    return not value.is_alive()

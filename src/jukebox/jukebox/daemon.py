# -*- coding: utf-8 -*-
"""Jukebox daemon with the compatible legacy profile and gated local playback."""

import atexit
from collections.abc import Mapping, Sequence
import hmac
import logging
import math
import os
import re
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
_BEARER_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}\Z")


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


def _http_path_value(value, field):
    if type(value) is not str or not value.startswith("/") or "\x00" in value:
        raise ValueError("%s must be an absolute path" % field)
    return value


class _BearerTokenUnavailable(RuntimeError):
    """Raised when the configured bearer token cannot be safely used."""


def _read_bearer_token(path, *, os_module=os):
    """Read one owner-only URL-safe bearer token without following symlinks."""
    path = _http_path_value(path, "bearer token path")
    required_flags = ("O_RDONLY", "O_NOFOLLOW", "O_CLOEXEC")
    if any(not hasattr(os_module, name) for name in required_flags):
        raise _BearerTokenUnavailable("bearer token unavailable: %s" % path)
    flags = os_module.O_RDONLY | os_module.O_NOFOLLOW | os_module.O_CLOEXEC
    flags |= getattr(os_module, "O_NONBLOCK", 0)
    descriptor = None
    try:
        descriptor = os_module.open(path, flags)
        info = os_module.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode)
                or info.st_uid != os_module.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size > 64):
            raise ValueError("unsafe token file")
        raw = os_module.read(descriptor, 65)
        if len(raw) > 64:
            raise ValueError("oversized token")
        if raw.endswith(b"\n"):
            raw = raw[:-1]
        token = raw.decode("ascii")
        if _BEARER_TOKEN_PATTERN.fullmatch(token) is None:
            raise ValueError("malformed token")
        return token
    except Exception as error:
        raise _BearerTokenUnavailable("bearer token unavailable: %s" % path) from error
    finally:
        if descriptor is not None:
            try:
                os_module.close(descriptor)
            except Exception as error:
                raise _BearerTokenUnavailable(
                    "bearer token unavailable: %s" % path) from error


def _local_http_section(config):
    """Return the raw ``local_playback.http`` mapping or None when absent."""
    section = config.getn("local_playback", default={})
    if section is None:
        section = {}
    if not isinstance(section, Mapping):
        raise ValueError("local_playback must be a mapping")
    http = section.get("http", None)
    if http is None:
        return None
    if not isinstance(http, Mapping):
        raise ValueError("local_playback.http must be a mapping")
    return http


def _local_http_requested(config):
    """Return True only for an explicitly enabled HTTP opt-in."""
    http = _local_http_section(config)
    if http is None:
        return False
    enabled = http.get("enabled", False)
    if type(enabled) is not bool:
        raise ValueError("local_playback.http.enabled must be a boolean")
    return enabled


def _parse_local_http_options(config):
    """Return validated HTTP opt-in options; None when not explicitly enabled.

    The read surface is opt-in only: an absent or disabled ``local_playback.http``
    mapping yields None so no token, store, catalog or server effect is triggered.
    Any explicitly requested but invalid option fails visibly instead of silently
    degrading to a disabled state.
    """
    http = _local_http_section(config)
    if http is None or not _local_http_requested(config):
        return None
    section = config.getn("local_playback", default={})
    playlist_database_path = _http_path_value(
        section.get("playlist_database_path"),
        "local_playback.playlist_database_path")
    bearer_token_path = _http_path_value(
        http.get("bearer_token_path"), "local_playback.http.bearer_token_path")
    playlist_write_token_path = http.get("playlist_write_token_path")
    if playlist_write_token_path is not None:
        playlist_write_token_path = _http_path_value(
            playlist_write_token_path,
            "local_playback.http.playlist_write_token_path")
    port = http.get("port")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("local_playback.http.port must be an integer between 1 and 65535")
    origin_host = http.get("origin_host", "127.0.0.1")
    if type(origin_host) is not str or origin_host not in ("127.0.0.1", "localhost"):
        raise ValueError("local_playback.http.origin_host must be a loopback name")
    budget = http.get("command_budget_seconds", 10.0)
    if type(budget) not in (int, float):
        raise ValueError("local_playback.http.command_budget_seconds must be a finite positive number")
    budget = float(budget)
    if not math.isfinite(budget) or budget <= 0.0:
        raise ValueError("local_playback.http.command_budget_seconds must be a finite positive number")
    options = {"playlist_database_path": playlist_database_path,
               "bearer_token_path": bearer_token_path, "port": port,
               "origin_host": origin_host, "command_budget_seconds": budget}
    if playlist_write_token_path is not None:
        options["playlist_write_token_path"] = playlist_write_token_path
    return options


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
        self._local_http_options = None
        self._local_http = None
        self._local_http_catalog = None
        self._http_start_failed = False
        self._legacy_owner_descriptor = None
        self._local_signal_seen = False
        self._local_shutdown_deadline = None
        self._local_signal = None
        self.write_artifacts = write_artifacts

        jukebox.cfghandler.load_yaml(cfg, configuration_file)
        self._local_profile = _local_profile_enabled(cfg)
        if self._local_profile:
            _validate_local_modules(cfg)
            self._local_http_options = _parse_local_http_options(cfg)
            self._local_runtime = self._make_local_runtime(cfg)
            _ensure_audio_owner_directory()
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
            logger.info("Starting Jukebox Daemon in restricted local playback profile")
            return

        if _local_http_requested(cfg):
            # An explicitly requested HTTP opt-in must never be silently
            # ignored by the legacy profile: fail before any legacy import
            # or owner I/O side effect.
            raise ValueError("local_playback.http requires the restricted local playback profile")

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
        http = _parse_local_http_options(config)
        if http is not None:
            # The permanent dispatch admission store is an explicit HTTP
            # opt-in effect; without the opt-in the runtime default applies
            # and no playlist store is created.
            values["playlist_database_path"] = http["playlist_database_path"]
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
        if getattr(self, "_local_http_options", None) is not None:
            try:
                self._start_local_http()
            except Exception:
                self._http_start_failed = True
                logger.exception("Restricted local HTTP listener failed to start")
                self._shutdown_local_http_after_start_failure()
                return 1
        self._wait_for_local_signal()
        deadline = self._local_shutdown_deadline_or_new()
        return self._shutdown_local(deadline)

    def _wait_for_local_signal(self):
        while not self._local_signal_seen:
            if self._local_http_worker_failed():
                break
            time.sleep(0.05)

    def _local_http_worker_failed(self):
        http = getattr(self, "_local_http", None)
        if http is None or getattr(http, "worker_error", None) is None:
            return False
        logger.error("Local playback HTTP listener worker failed; shutting down")
        self._local_signal_seen = True
        self._local_shutdown_deadline_or_new()
        return True

    def _shutdown_local(self, deadline):
        runtime_prepared = False
        http_drained = False
        modules_closed = False
        catalog_closed = False
        try:
            self._local_runtime.begin_shutdown()
            http = getattr(self, "_local_http", None)
            if http is not None:
                http.begin_shutdown()
            runtime_prepared = self._prepare_local_runtime(deadline, begin_shutdown=False)
        except Exception:
            logger.exception("Local playback runtime shutdown failed")
        finally:
            http_drained = self._finish_local_http(deadline)
            try:
                modules_closed = self._close_and_join_local_modules(deadline)
            except Exception:
                logger.exception("Local playback module shutdown failed")
            finally:
                catalog_closed = self._close_local_http_catalog() if http_drained else False
        if not http_drained:
            logger.error("Local playback HTTP listener did not drain before deadline")
        if not runtime_prepared or not http_drained or not modules_closed or not catalog_closed:
            return 1
        return 0 if self._release_prepared_runtime(deadline) else 1

    def _start_local_http(self):
        options = getattr(self, "_local_http_options", None)
        if options is None:
            return
        token = _read_bearer_token(options["bearer_token_path"])
        write_token_path = options.get("playlist_write_token_path")
        write_authorizer = None
        if write_token_path is not None:
            write_token = _read_bearer_token(write_token_path)
            if hmac.compare_digest(token, write_token):
                raise ValueError("read and playlist write tokens must differ")
        from components.library_api.runtime_http import LocalPlaybackHTTP
        from components.library_api.server import make_read_authorizer
        from components.library_catalog.catalog import LibraryCatalog

        authorizer = make_read_authorizer(token)
        if write_token_path is not None:
            write_authorizer = make_read_authorizer(write_token)
        catalog = LibraryCatalog(options["playlist_database_path"],
                                 cfg.getn("local_playback", "library_root"))
        self._local_http_catalog = catalog
        http_options = {}
        if write_authorizer is not None:
            http_options["write_authorizer"] = write_authorizer
        http = LocalPlaybackHTTP(
            self._local_runtime, catalog, authorizer, options["port"],
            options["origin_host"],
            command_budget_seconds=options["command_budget_seconds"],
            **http_options)
        self._local_http = http
        http.start()

    def _finish_local_http(self, deadline):
        http = getattr(self, "_local_http", None)
        if http is None:
            return True
        try:
            return http.finish_shutdown(deadline=deadline) is True
        except Exception:
            logger.exception("Local playback HTTP shutdown failed")
            return False

    def _close_local_http_catalog(self):
        catalog = getattr(self, "_local_http_catalog", None)
        if catalog is None:
            return True
        try:
            catalog.close()
        except Exception:
            logger.exception("Local playback HTTP catalog close failed")
            return False
        self._local_http_catalog = None
        return True

    def _shutdown_local_http_after_start_failure(self):
        deadline = self._local_shutdown_deadline_or_new()
        drained = False
        try:
            self._local_runtime.begin_shutdown()
            http = getattr(self, "_local_http", None)
            if http is not None:
                http.begin_shutdown()
            self._prepare_local_runtime(deadline, begin_shutdown=False)
        except Exception:
            logger.exception("Cleanup after local HTTP startup failure failed")
        finally:
            drained = self._finish_local_http(deadline)
            try:
                self._close_and_join_local_modules(deadline)
            except Exception:
                logger.exception("Cleanup after local module startup failed")
            finally:
                if drained:
                    self._close_local_http_catalog()
        # Do NOT release owner on HTTP start failure - retain ownership
        # Return 1 to indicate failure, owner retained

    def _local_shutdown_deadline_or_new(self):
        if self._local_shutdown_deadline is None:
            self._local_shutdown_deadline = time.monotonic() + _LOCAL_SIGNAL_BUDGET_SECONDS
        return self._local_shutdown_deadline

    def _prepare_local_runtime(self, deadline, *, begin_shutdown=True):
        if begin_shutdown:
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

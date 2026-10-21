"""HTTP opt-in configuration checks for the restricted daemon profile.

Covers the configuration slice only: parsing/defaults of
``local_playback.http``, rejection of the opt-in in the legacy profile
before any side effect, and the ``playlist_database_path`` runtime
keyword. The HTTP lifecycle wiring is intentionally out of scope here.
"""

import math
import os
from pathlib import Path
import stat
import sys
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

_STAGE = Path(__file__).resolve().parents[2]
_SOURCE = _STAGE / "src" / "jukebox"
if str(_SOURCE) not in sys.path:
    sys.path.insert(0, str(_SOURCE))

from jukebox.daemon import (  # noqa: E402
    JukeBox,
    _parse_local_http_options,
    _read_bearer_token,
    _BearerTokenUnavailable,
)


class Config:
    """Minimal config double with the real handler's get/getn semantics."""

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


def _full_http(local_extra=None, http_extra=None):
    local = {
        "enabled": True,
        "database_path": "/srv/jb/library.sqlite",
        "library_root": "/srv/jb/audio",
        "credential_path": "/etc/jb/owner.password",
        "playlist_database_path": "/srv/jb/playlists.sqlite",
    }
    if local_extra:
        local.update(local_extra)
    http = {"enabled": True}
    if http_extra:
        http.update(http_extra)
    local["http"] = http
    return Config({"local_playback": local})


def _valid_http_extra():
    return {
        "bearer_token_path": "/etc/jb/http-bearer.token",
        "port": 8090,
    }


class LocalHttpOptionsParsingTests(unittest.TestCase):
    def test_absent_or_disabled_http_returns_none(self):
        self.assertIsNone(_parse_local_http_options(Config({})))
        self.assertIsNone(_parse_local_http_options(Config(
            {"local_playback": {"enabled": True}})))
        self.assertIsNone(_parse_local_http_options(Config(
            {"local_playback": {"enabled": True, "http": {"enabled": False}}})))
        self.assertIsNone(_parse_local_http_options(Config(
            {"local_playback": {"enabled": True, "http": {}}})))

    def test_invalid_http_container_or_enabled_flag_is_rejected(self):
        configs = (
            Config({"local_playback": "not-a-mapping"}),
            Config({"local_playback": {"http": []}}),
            Config({"local_playback": {"http": {"enabled": "true"}}}),
            Config({"local_playback": {"http": {"enabled": 1}}}),
        )
        for config in configs:
            with self.subTest(config=config.data):
                with self.assertRaises(ValueError):
                    _parse_local_http_options(config)

    def test_explicit_activation_returns_exact_options(self):
        options = _parse_local_http_options(
            _full_http(http_extra=_valid_http_extra()))
        self.assertEqual({
            "playlist_database_path": "/srv/jb/playlists.sqlite",
            "bearer_token_path": "/etc/jb/http-bearer.token",
            "port": 8090,
            "origin_host": "127.0.0.1",
            "command_budget_seconds": 10.0,
        }, options)

    def test_origin_host_and_command_budget_defaults(self):
        options = _parse_local_http_options(_full_http(http_extra={
            "bearer_token_path": "/etc/jb/http-bearer.token",
            "port": 1,
        }))
        self.assertEqual("127.0.0.1", options["origin_host"])
        self.assertEqual(10.0, options["command_budget_seconds"])

    def test_explicit_origin_host_and_budget_are_accepted(self):
        options = _parse_local_http_options(_full_http(http_extra=dict(
            _valid_http_extra(), origin_host="localhost",
            command_budget_seconds=2.5)))
        self.assertEqual("localhost", options["origin_host"])
        self.assertEqual(2.5, options["command_budget_seconds"])
        self.assertEqual(3, _parse_local_http_options(_full_http(
            http_extra=dict(_valid_http_extra(),
                            command_budget_seconds=3)))["command_budget_seconds"])

    def test_invalid_paths_ports_hosts_and_budgets_are_rejected(self):
        invalid_local = (
            {"playlist_database_path": "relative/path.sqlite"},
            {"playlist_database_path": "/with\x00nul.sqlite"},
            {"playlist_database_path": None},
        )
        for extra in invalid_local:
            with self.subTest(local_extra=extra):
                with self.assertRaises(ValueError):
                    _parse_local_http_options(
                        _full_http(local_extra=extra,
                                   http_extra=_valid_http_extra()))
        invalid_extras = (
            {"bearer_token_path": "relative/token"},
            {"bearer_token_path": "/with\x00nul"},
            {"bearer_token_path": None},
            {"port": 0},
            {"port": 65536},
            {"port": True},
            {"port": "8090"},
            {"port": None},
            {"origin_host": "0.0.0.0"},
            {"origin_host": ""},
            {"origin_host": None},
            {"origin_host": 7},
            {"command_budget_seconds": 0},
            {"command_budget_seconds": -1},
            {"command_budget_seconds": True},
            {"command_budget_seconds": "10"},
            {"command_budget_seconds": math.inf},
            {"command_budget_seconds": math.nan},
        )
        for extra in invalid_extras:
            with self.subTest(extra=extra):
                with self.assertRaises(ValueError):
                    _parse_local_http_options(
                        _full_http(http_extra=dict(_valid_http_extra(),
                                                   **extra)))

    def test_missing_required_values_are_rejected(self):
        for key in ("playlist_database_path",):
            with self.subTest(missing=key):
                with self.assertRaises(ValueError):
                    _parse_local_http_options(_full_http(
                        local_extra={key: None},
                        http_extra=_valid_http_extra()))
        for key in ("bearer_token_path", "port"):
            with self.subTest(missing=key):
                with self.assertRaises(ValueError):
                    _parse_local_http_options(_full_http(http_extra={
                        "bearer_token_path": "/etc/jb/http-bearer.token",
                    }))

    def test_checked_in_example_without_http_parses_as_disabled(self):
        import jukebox.cfghandler as cfghandler
        config = cfghandler.ConfigHandler("local-profile-http-regression")
        example = _STAGE / "resources" / "default-settings" / "jukebox.local-playback.example.yaml"
        cfghandler.load_yaml(config, str(example))
        self.assertIsNone(_parse_local_http_options(config))


class LegacyProfileRejectsHttpOptInTests(unittest.TestCase):
    def test_legacy_opt_in_fails_before_owner_or_legacy_imports(self):
        import jukebox.daemon as daemon_module

        config = Config({
            "local_playback": {"enabled": False, "http": {"enabled": True}},
        })
        with (
            patch.object(daemon_module, "cfg", config),
            patch("jukebox.cfghandler.load_yaml"),
            patch.object(JukeBox, "_make_local_runtime") as make_runtime,
            patch.object(daemon_module, "_acquire_audio_owner") as acquire_owner,
            patch.object(daemon_module, "_load_legacy_modules") as load_legacy,
        ):
            with self.assertRaisesRegex(ValueError, "restricted local playback profile"):
                JukeBox("unused.yaml", False)
        make_runtime.assert_not_called()
        acquire_owner.assert_not_called()
        load_legacy.assert_not_called()

    def test_legacy_profile_without_opt_in_selects_legacy(self):
        import jukebox.daemon as daemon_module

        fd = os.open(os.devnull, os.O_RDONLY)
        from types import SimpleNamespace
        legacy_modules = (
            SimpleNamespace(nv_manager=lambda: "legacy-nvm"),
            object(), object(), object(),
            SimpleNamespace(get_git_state=lambda: "legacy-git-state"),
            lambda value: value,
        )
        config = Config({})
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
            self.assertIsNone(instance._local_http_options)
        finally:
            os.close(fd)


class RuntimeKwargIntegrationTests(unittest.TestCase):
    def test_local_runtime_without_http_omits_playlist_database_path(self):
        with patch("components.playback_session.runtime.LocalPlaybackRuntime") as runtime:
            JukeBox._make_local_runtime(Config({
                "local_playback": {
                    "database_path": "/srv/jb/library.sqlite",
                    "library_root": "/srv/jb/audio",
                    "credential_path": "/etc/jb/owner.password",
                },
            }))
        runtime.assert_called_once_with(
            database_path="/srv/jb/library.sqlite",
            library_root="/srv/jb/audio",
            credential_path="/etc/jb/owner.password",
        )

    def test_local_runtime_with_http_forwards_playlist_database_path(self):
        with patch("components.playback_session.runtime.LocalPlaybackRuntime") as runtime:
            JukeBox._make_local_runtime(_full_http(http_extra=_valid_http_extra()))
        runtime.assert_called_once_with(
            database_path="/srv/jb/library.sqlite",
            library_root="/srv/jb/audio",
            credential_path="/etc/jb/owner.password",
            playlist_database_path="/srv/jb/playlists.sqlite",
        )

    def test_local_profile_stores_options_and_rejects_invalid_http_before_runtime(self):
        import jukebox.daemon as daemon_module

        invalid = Config({
            "local_playback": {
                "enabled": True,
                "database_path": "/srv/jb/library.sqlite",
                "library_root": "/srv/jb/audio",
                "credential_path": "/etc/jb/owner.password",
                "playlist_database_path": "/srv/jb/playlists.sqlite",
                "http": {"enabled": True, "port": 0,
                         "bearer_token_path": "/etc/jb/http-bearer.token"},
            },
            "modules": {"named": {}, "others": []},
        })
        with (
            patch.object(daemon_module, "cfg", invalid),
            patch("jukebox.cfghandler.load_yaml"),
            patch.object(daemon_module, "_ensure_audio_owner_directory"),
            patch.object(JukeBox, "_make_local_runtime") as make_runtime,
        ):
            with self.assertRaisesRegex(ValueError, "http.port"):
                JukeBox("unused.yaml", False)
        make_runtime.assert_not_called()

    def test_local_profile_constructor_keeps_default_http_disabled(self):
        import jukebox.daemon as daemon_module

        config = Config({
            "local_playback": {
                "enabled": True,
                "database_path": "/srv/jb/library.sqlite",
                "library_root": "/srv/jb/audio",
                "credential_path": "/etc/jb/owner.password",
            },
            "modules": {"named": {}, "others": []},
        })
        with (
            patch.object(daemon_module, "cfg", config),
            patch("jukebox.cfghandler.load_yaml"),
            patch.object(daemon_module, "_ensure_audio_owner_directory"),
        ):
            instance = JukeBox("unused.yaml", False)
        self.assertTrue(instance._local_profile)
        self.assertIsNone(instance._local_http_options)


class _FakeOSModule:
    """Controlled os double: no global patching, every call is recorded."""

    O_RDONLY = 0
    O_NOFOLLOW = 0x200000
    O_CLOEXEC = 0x80000

    def __init__(self, *, raw=b"", mode=0o600, uid=1000, current_uid=1000,
                 file_type=stat.S_IFREG, size=None, open_error=None,
                 read_error=None, fstat_error=None):
        self.raw = raw
        self.mode = mode
        self.uid = uid
        self.current_uid = current_uid
        self.file_type = file_type
        self.size = len(raw) if size is None else size
        self.open_error = open_error
        self.read_error = read_error
        self.fstat_error = fstat_error
        self.calls = []
        self.closed = []

    def open(self, path, flags):
        self.calls.append(("open", path, flags))
        if self.open_error is not None:
            raise self.open_error
        return 17

    def fstat(self, descriptor):
        self.calls.append(("fstat", descriptor))
        if self.fstat_error is not None:
            raise self.fstat_error
        return SimpleNamespace(st_mode=self.file_type | self.mode,
                               st_uid=self.uid, st_size=self.size)

    def read(self, descriptor, count):
        self.calls.append(("read", descriptor, count))
        if self.read_error is not None:
            raise self.read_error
        return self.raw[:count]

    def close(self, descriptor):
        self.calls.append(("close", descriptor))
        self.closed.append(descriptor)

    def geteuid(self):
        return self.current_uid


_TOKEN = "AbC" * 13 + "DeFg"  # 43 URL-safe characters


class BearerTokenReadTests(unittest.TestCase):
    def test_valid_token_with_single_trailing_lf_is_returned(self):
        fake = _FakeOSModule(raw=_TOKEN.encode("ascii") + b"\n")
        self.assertEqual(_TOKEN, _read_bearer_token("/etc/jb/token", os_module=fake))
        open_call = next(call for call in fake.calls if call[0] == "open")
        self.assertTrue(open_call[2] & fake.O_NOFOLLOW)
        self.assertTrue(open_call[2] & fake.O_RDONLY == fake.O_RDONLY)
        read_call = next(call for call in fake.calls if call[0] == "read")
        self.assertLessEqual(read_call[2], 65)
        self.assertEqual([17], fake.closed)

    def test_valid_token_without_newline_is_returned(self):
        fake = _FakeOSModule(raw=_TOKEN.encode("ascii"))
        self.assertEqual(_TOKEN, _read_bearer_token("/etc/jb/token", os_module=fake))

    def test_open_error_reports_unavailable_and_opens_nothing(self):
        fake = _FakeOSModule(open_error=OSError("ELOOP: symlink"))
        with self.assertRaises(_BearerTokenUnavailable):
            _read_bearer_token("/etc/jb/token", os_module=fake)
        self.assertEqual([], fake.closed)

    def test_unsafe_metadata_is_rejected(self):
        cases = (
            {"mode": 0o644},
            {"mode": 0o604},
            {"mode": 0o400},
            {"uid": 1001},
            {"file_type": stat.S_IFDIR},
            {"size": 4096},
        )
        for kwargs in cases:
            with self.subTest(**kwargs):
                fake = _FakeOSModule(raw=_TOKEN.encode("ascii") + b"\n", **kwargs)
                with self.assertRaises(_BearerTokenUnavailable):
                    _read_bearer_token("/etc/jb/token", os_module=fake)
                self.assertEqual([17], fake.closed)

    def test_oversized_read_is_rejected_even_with_understated_size(self):
        fake = _FakeOSModule(raw=b"A" * 200, size=40)
        with self.assertRaises(_BearerTokenUnavailable):
            _read_bearer_token("/etc/jb/token", os_module=fake)
        self.assertEqual([17], fake.closed)

    def test_malformed_content_is_rejected(self):
        cases = (
            _TOKEN[:-1].encode("ascii"),            # 42 characters
            (_TOKEN + "X").encode("ascii"),         # 44 characters
            b"",                                    # empty
            (_TOKEN[:42] + "+").encode("ascii"),    # outside URL-safe alphabet
            (_TOKEN[:42] + "\xe4").encode("latin-1"),  # non-ASCII byte
            _TOKEN.encode("ascii") + b"\r\n",       # CRLF instead of one LF
            _TOKEN[:10].encode("ascii") + b"\n" + _TOKEN[10:].encode("ascii"),
            _TOKEN.encode("ascii") + b"\n\n",       # more than one newline
            _TOKEN.encode("ascii") + b"\x00",
        )
        for raw in cases:
            with self.subTest(raw=raw):
                fake = _FakeOSModule(raw=raw)
                with self.assertRaises(_BearerTokenUnavailable):
                    _read_bearer_token("/etc/jb/token", os_module=fake)
                self.assertEqual([17], fake.closed)

    def test_failures_close_the_descriptor_and_never_log_the_token(self):
        for failure in ("fstat", "read"):
            with self.subTest(failure=failure):
                fake = _FakeOSModule(raw=_TOKEN.encode("ascii") + b"\n")
                if failure == "fstat":
                    fake.fstat_error = OSError("boom")
                else:
                    fake.read_error = OSError("boom")
                with self.assertRaises(_BearerTokenUnavailable) as caught:
                    _read_bearer_token("/etc/jb/token", os_module=fake)
                self.assertEqual([17], fake.closed)
                self.assertNotIn(_TOKEN, str(caught.exception))
                self.assertIn("/etc/jb/token", str(caught.exception))

    def test_relative_path_is_rejected_before_any_file_access(self):
        fake = _FakeOSModule()
        with self.assertRaises(ValueError):
            _read_bearer_token("relative/token", os_module=fake)
        self.assertEqual([], fake.calls)


class LocalHttpLifecycleTests(unittest.TestCase):
    def make_daemon(self, options=None):
        daemon = object.__new__(JukeBox)
        daemon._local_runtime = SimpleNamespace(
            start=lambda **_kwargs: {"ready": True, "failure": None},
            snapshot=lambda: {"ready": True},
            begin_shutdown=lambda: self.events.append("runtime.begin"),
            finish_shutdown=self.finish_runtime,
        )
        daemon._local_http_options = options
        daemon._local_signal_seen = True
        daemon._local_shutdown_deadline = 123.0
        daemon._local_signal = "SIGTERM"
        daemon._local_http = None
        daemon._local_http_catalog = None
        daemon._http_start_failed = False
        return daemon

    def setUp(self):
        self.events = []
        self.finish_states = [
            {"phase": "CLOSING", "ready": False, "quiescent": True,
             "driverAlive": False, "ownerLockHeld": True, "failure": None},
            {"phase": "CLOSED", "quiescent": True, "driverAlive": False,
             "ownerLockHeld": False, "failure": None},
        ]

    def finish_runtime(self, *, deadline, release_owner):
        self.events.append("runtime.finish.%s" % release_owner)
        return self.finish_states.pop(0)

    def test_default_profile_does_not_import_http_modules_or_create_resources(self):
        daemon = self.make_daemon()
        with patch.object(JukeBox, "_load_local_modules"), \
                patch.object(JukeBox, "_close_and_join_local_modules", return_value=True), \
                patch("builtins.__import__", side_effect=AssertionError("unexpected import")) as importer:
            # The disabled path must not call the HTTP setup method.
            with patch.object(JukeBox, "_start_local_http", side_effect=AssertionError("HTTP started"), create=True):
                daemon._local_http_options = None
                self.assertEqual(0, daemon._run_local())
        importer.assert_not_called()

    def test_start_forwards_options_and_shutdown_order(self):
        options = {"bearer_token_path": "/etc/token", "playlist_database_path": "/db/list.sqlite",
                   "library_root": "/media", "port": 8090, "origin_host": "localhost",
                   "command_budget_seconds": 2.5}
        daemon = self.make_daemon(options)
        catalog = SimpleNamespace(close=lambda: self.events.append("catalog.close"))

        class Http:
            def __init__(self, runtime, catalog_arg, authorizer, port, host, *, command_budget_seconds):
                self.events_ref = self_test.events
                self.events_ref.append(("construct", runtime, catalog_arg, port, host,
                                        command_budget_seconds))

            def start(self):
                self.events_ref.append("http.start")

            def begin_shutdown(self):
                self.events_ref.append("http.begin")

            def finish_shutdown(self, *, deadline):
                self.events_ref.append(("http.finish", deadline))
                return True

        self_test = self

        with (
            patch("jukebox.daemon.cfg", Config({"local_playback": {"library_root": "/media"}})),
            patch("jukebox.daemon._read_bearer_token", return_value="T" * 43) as read_token,
            patch("components.library_api.server.make_read_authorizer", return_value="authorizer") as auth,
            patch("components.library_catalog.catalog.LibraryCatalog", return_value=catalog) as make_catalog,
            patch("components.library_api.runtime_http.LocalPlaybackHTTP", Http),
            patch.object(JukeBox, "_load_local_modules"),
            patch.object(
                JukeBox, "_close_and_join_local_modules",
                side_effect=lambda deadline: self.events.append("modules.join") or True),
        ):
            self.assertEqual(0, daemon._run_local())
        read_token.assert_called_once_with("/etc/token")
        auth.assert_called_once_with("T" * 43)
        make_catalog.assert_called_once_with("/db/list.sqlite", "/media")
        self.assertIn("http.begin", self.events)
        self.assertLess(self.events.index("runtime.begin"), self.events.index("http.begin"))
        http_finish = next(
            i for i, item in enumerate(self.events)
            if isinstance(item, tuple) and item[0] == "http.finish")
        self.assertLess(self.events.index("runtime.finish.False"), http_finish)
        self.assertLess(http_finish, self.events.index("modules.join"))
        self.assertLess(self.events.index("modules.join"), self.events.index("catalog.close"))
        self.assertLess(self.events.index("catalog.close"), self.events.index("runtime.finish.True"))

    def test_http_drain_failure_retains_owner_and_catalog(self):
        daemon = self.make_daemon({"bearer_token_path": "/token",
                                   "playlist_database_path": "/db/list.sqlite",
                                   "library_root": "/media", "port": 8090,
                                   "origin_host": "127.0.0.1",
                                   "command_budget_seconds": 10.0})
        catalog = SimpleNamespace(close=lambda: self.events.append("catalog.close"))

        class Http:
            def start(self):
                pass

            def begin_shutdown(self):
                lifecycle.events.append("http.begin")

            def finish_shutdown(self, *, deadline):
                return False
        lifecycle = self
        with (
            patch("jukebox.daemon.cfg", Config({"local_playback": {"library_root": "/media"}})),
            patch("jukebox.daemon._read_bearer_token", return_value="T" * 43),
            patch("components.library_api.server.make_read_authorizer", return_value=lambda _: True),
            patch("components.library_catalog.catalog.LibraryCatalog", return_value=catalog),
            patch("components.library_api.runtime_http.LocalPlaybackHTTP", return_value=Http()),
            patch.object(JukeBox, "_load_local_modules"),
            patch.object(JukeBox, "_close_and_join_local_modules", return_value=True),
        ):
            self.assertEqual(1, daemon._run_local())
        self.assertNotIn("runtime.finish.True", self.events)
        self.assertNotIn("catalog.close", self.events)

    def test_token_failure_is_visible_and_has_no_catalog_or_listener(self):
        daemon = self.make_daemon({"bearer_token_path": "/token"})
        with (
            patch("jukebox.daemon._read_bearer_token", side_effect=RuntimeError("unavailable")),
            patch("components.library_catalog.catalog.LibraryCatalog") as catalog,
            patch("components.library_api.runtime_http.LocalPlaybackHTTP") as helper,
            patch.object(JukeBox, "_load_local_modules"),
            patch.object(JukeBox, "_close_and_join_local_modules", return_value=True),
        ):
            self.assertEqual(1, daemon._run_local())
        catalog.assert_not_called()
        helper.assert_not_called()
        self.assertNotIn("runtime.finish.True", self.events)

    def test_helper_start_failure_drains_partial_helper_and_closes_catalog_but_retains_owner(self):
        daemon = self.make_daemon({"bearer_token_path": "/token",
                                   "playlist_database_path": "/db/list.sqlite",
                                   "library_root": "/media", "port": 8090,
                                   "origin_host": "127.0.0.1",
                                   "command_budget_seconds": 10.0})
        catalog = SimpleNamespace(close=lambda: self.events.append("catalog.close"))

        lifecycle = self

        class Http:
            def __init__(self, runtime, catalog, read_authorizer, port,
                         origin_host="127.0.0.1", *, command_budget_seconds=10.0):
                self.runtime = runtime
                self.catalog = catalog
                self.read_authorizer = read_authorizer
                self.port = port
                self.origin_host = origin_host
                self.command_budget_seconds = command_budget_seconds

            def start(self):
                lifecycle.events.append("http.start")
                raise RuntimeError("bind failed")

            def begin_shutdown(self):
                lifecycle.events.append("http.begin")

            def finish_shutdown(self, *, deadline):
                lifecycle.events.append(("http.finish", deadline))
                return True

        with (
            patch("jukebox.daemon.cfg", Config({"local_playback": {"library_root": "/media"}})),
            patch("jukebox.daemon._read_bearer_token", return_value="T" * 43),
            patch("components.library_api.server.make_read_authorizer", return_value=lambda _: True),
            patch("components.library_catalog.catalog.LibraryCatalog", return_value=catalog),
            patch("components.library_api.runtime_http.LocalPlaybackHTTP", Http),
            patch.object(JukeBox, "_load_local_modules"),
            patch.object(JukeBox, "_close_and_join_local_modules", return_value=True),
        ):
            self.assertEqual(1, daemon._run_local())
        self.assertIn("http.begin", self.events)
        self.assertIn("catalog.close", self.events)
        self.assertNotIn("runtime.finish.True", self.events)

    def test_catalog_close_failure_retains_owner(self):
        daemon = self.make_daemon({"bearer_token_path": "/token",
                                   "playlist_database_path": "/db/list.sqlite",
                                   "library_root": "/media", "port": 8090,
                                   "origin_host": "127.0.0.1",
                                   "command_budget_seconds": 10.0})

        class Catalog:
            def close(self):
                raise OSError("close failed")

        self_test = self

        class Http:
            def __init__(self, runtime, catalog, read_authorizer, port,
                         origin_host="127.0.0.1", *, command_budget_seconds=10.0):
                pass

            def start(self):
                pass

            def begin_shutdown(self):
                self_test.events.append("http.begin")

            def finish_shutdown(self, *, deadline):
                self_test.events.append(("http.finish", deadline))
                return True

        with (
            patch("jukebox.daemon.cfg", Config({"local_playback": {"library_root": "/media"}})),
            patch("jukebox.daemon._read_bearer_token", return_value="T" * 43),
            patch("components.library_api.server.make_read_authorizer", return_value=lambda _: True),
            patch("components.library_catalog.catalog.LibraryCatalog", return_value=Catalog()),
            patch("components.library_api.runtime_http.LocalPlaybackHTTP", Http),
            patch.object(JukeBox, "_load_local_modules"),
            patch.object(JukeBox, "_close_and_join_local_modules", return_value=True),
        ):
            self.assertEqual(1, daemon._run_local())
        self.assertNotIn("runtime.finish.True", self.events)

    def test_worker_oserror_is_visible_and_drain_is_not_successful(self):
        from components.library_api.runtime_http import LocalPlaybackHTTP

        class Server:
            timeout = None

            def handle_request(self):
                raise OSError("listener broke")

            def server_close(self):
                pass

        runtime = SimpleNamespace(snapshot=lambda: {"ready": True})
        helper = LocalPlaybackHTTP(runtime, object(), lambda _credential: True, 0)
        with patch("components.library_api.runtime_http._library_server.make_server",
                   return_value=Server()):
            with self.assertLogs("components.library_api.runtime_http", level="ERROR") as logs:
                helper.start()
                helper._thread.join(1)
        self.assertIsInstance(helper.worker_error, OSError)
        self.assertIn("listener worker failed", "\n".join(logs.output))
        self.assertFalse(helper.finish_shutdown(deadline=time.monotonic() + 1))

    def test_worker_failure_triggers_daemon_cleanup_and_failure_exit(self):
        daemon = self.make_daemon({"enabled": True})
        daemon._local_http = SimpleNamespace(
            worker_error=OSError("listener broke"), begin_shutdown=lambda: None)
        daemon._local_http_catalog = None
        with (
            patch.object(JukeBox, "_load_local_modules"),
            patch.object(JukeBox, "_start_local_http"),
            patch.object(JukeBox, "_close_and_join_local_modules", return_value=True),
            patch.object(JukeBox, "_finish_local_http", return_value=False),
        ):
            self.assertEqual(1, daemon._run_local())
        self.assertIn("runtime.begin", self.events)
        self.assertIn("runtime.finish.False", self.events)
        self.assertNotIn("runtime.finish.True", self.events)


if __name__ == "__main__":
    unittest.main()

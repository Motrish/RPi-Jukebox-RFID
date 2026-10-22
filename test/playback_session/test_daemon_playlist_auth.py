"""Separate read and playlist-write bearer authorization regression tests."""

import sys
from pathlib import Path
from unittest.mock import patch
import unittest

_STAGE = Path(__file__).resolve().parents[2]
_SOURCE = _STAGE / "src" / "jukebox"
if str(_SOURCE) not in sys.path:
    sys.path.insert(0, str(_SOURCE))

from jukebox.daemon import JukeBox, _parse_local_http_options  # noqa: E402


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


def _config(http):
    return Config({"local_playback": {
        "enabled": True,
        "database_path": "/db/library.sqlite",
        "library_root": "/audio",
        "credential_path": "/owner",
        "playlist_database_path": "/db/playlists.sqlite",
        "http": {"enabled": True, "bearer_token_path": "/read-token",
                 "port": 8090, **http},
    }})


def _daemon(options):
    daemon = object.__new__(JukeBox)
    daemon._local_http_options = options
    daemon._local_runtime = object()
    daemon._local_http = None
    daemon._local_http_catalog = None
    return daemon


class PlaylistWriteAuthTests(unittest.TestCase):
    def test_write_path_is_optional_and_absent_config_is_unchanged(self):
        options = _parse_local_http_options(_config({}))
        self.assertNotIn("playlist_write_token_path", options)
        self.assertEqual("/read-token", options["bearer_token_path"])
        self.assertIsNone(_parse_local_http_options(Config({})))
        self.assertIsNone(_parse_local_http_options(Config({
            "local_playback": {"http": {"enabled": False,
                                         "playlist_write_token_path": "relative"}}
        })))

    def test_invalid_write_path_rejected_before_owner_io(self):
        import jukebox.daemon as module

        config = _config({"playlist_write_token_path": "relative/write-token"})
        with (patch.object(module, "cfg", config),
              patch("jukebox.cfghandler.load_yaml"),
              patch.object(module, "_ensure_audio_owner_directory") as owner_io,
              patch.object(JukeBox, "_make_local_runtime") as make_runtime):
            with self.assertRaisesRegex(ValueError, "playlist_write_token_path"):
                JukeBox("unused.yaml", False)
        owner_io.assert_not_called()
        make_runtime.assert_not_called()

    def test_read_and_write_use_distinct_authorizers_and_paths(self):
        options = {"bearer_token_path": "/read", "playlist_write_token_path": "/write",
                   "playlist_database_path": "/db/playlists.sqlite", "port": 8090,
                   "origin_host": "127.0.0.1", "command_budget_seconds": 10.0}
        daemon = _daemon(options)
        catalog = object()
        read_auth = object()
        write_auth = object()
        tokens = {"/read": "R" * 43, "/write": "W" * 43}
        with (patch("jukebox.daemon._read_bearer_token", side_effect=tokens.get) as read_token,
              patch("components.library_api.server.make_read_authorizer",
                    side_effect=[read_auth, write_auth]) as make_auth,
              patch("components.library_catalog.catalog.LibraryCatalog",
                    return_value=catalog),
              patch("components.library_api.runtime_http.LocalPlaybackHTTP") as helper,
              patch("jukebox.daemon.cfg", _config({}))):
            daemon._start_local_http()
        self.assertEqual([unittest.mock.call("/read"), unittest.mock.call("/write")],
                         read_token.call_args_list)
        self.assertEqual([unittest.mock.call("R" * 43), unittest.mock.call("W" * 43)],
                         make_auth.call_args_list)
        helper.assert_called_once()
        args, kwargs = helper.call_args
        self.assertIs(args[2], read_auth)
        self.assertIs(kwargs["write_authorizer"], write_auth)

    def test_equal_tokens_fail_before_catalog_listener_and_keep_owner(self):
        secret = "S" * 43
        daemon = _daemon({"bearer_token_path": "/read", "playlist_write_token_path": "/write",
                          "playlist_database_path": "/db/playlists.sqlite", "port": 8090,
                          "origin_host": "127.0.0.1", "command_budget_seconds": 10.0})
        daemon._owner_lock_fd = 42
        with (patch("jukebox.daemon._read_bearer_token", return_value=secret),
              patch("components.library_catalog.catalog.LibraryCatalog") as catalog,
              patch("components.library_api.runtime_http.LocalPlaybackHTTP") as helper):
            with self.assertRaisesRegex(ValueError, "tokens must differ") as raised:
                daemon._start_local_http()
        self.assertNotIn(secret, str(raised.exception))
        catalog.assert_not_called()
        helper.assert_not_called()
        self.assertEqual(42, daemon._owner_lock_fd)

    def test_absent_write_path_reads_only_read_token_and_omits_helper_kwarg(self):
        daemon = _daemon({"bearer_token_path": "/read", "playlist_database_path": "/db/playlists.sqlite",
                          "port": 8090, "origin_host": "127.0.0.1",
                          "command_budget_seconds": 10.0})
        with (patch("jukebox.daemon._read_bearer_token", return_value="R" * 43) as read_token,
              patch("components.library_api.server.make_read_authorizer", return_value="read-auth"),
              patch("components.library_catalog.catalog.LibraryCatalog"),
              patch("components.library_api.runtime_http.LocalPlaybackHTTP") as helper,
              patch("jukebox.daemon.cfg", _config({}))):
            daemon._start_local_http()
        read_token.assert_called_once_with("/read")
        self.assertNotIn("write_authorizer", helper.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()

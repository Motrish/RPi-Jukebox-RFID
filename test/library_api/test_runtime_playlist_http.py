"""Regression tests for optional runtime playlist capabilities."""

import importlib
import sys
import unittest
from pathlib import Path
from unittest import mock


_STAGE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_STAGE_ROOT / "src" / "jukebox"))
LocalPlaybackHTTP = importlib.import_module(
    "components.library_api.runtime_http"
).LocalPlaybackHTTP
from components.playback_session.execution_gate import GateStateError  # noqa: E402


class _OldRuntime:
    def snapshot(self):
        return {"ready": True}

    def dispatch(self, command, *, deadline):
        return command

    def __getattr__(self, name):
        raise AssertionError("unexpected runtime attribute: " + name)


class _PlaylistRuntime(_OldRuntime):
    def __init__(self):
        self.calls = []

    def playlist_list(self, *, limit, cursor, deadline):
        self.calls.append(("playlist_list", limit, cursor, deadline))
        return []

    def playlist_get(self, ident, *, deadline):
        self.calls.append(("playlist_get", ident, deadline))

    def queue_get(self, ident, *, deadline):
        self.calls.append(("queue_get", ident, deadline))

    def playlist_dispatch(self, command, *, deadline):
        self.calls.append(("playlist_dispatch", command, deadline))


class RuntimePlaylistCapabilityTests(unittest.TestCase):
    def make_helper(self, runtime):
        return LocalPlaybackHTTP(
            runtime, object(), lambda credential: True, 0,
            monotonic=lambda: 5.0, command_budget_seconds=7,
            write_authorizer=lambda credential: credential == "valid",
        )

    def test_old_runtime_has_no_optional_callbacks_or_dynamic_lookup(self):
        helper = self.make_helper(_OldRuntime())
        for name in ("playlist_list", "playlist_get", "queue_get",
                     "playlist_dispatch"):
            self.assertIsNone(helper._runtime_callback(name))

    def test_static_playlist_methods_get_deadlines_and_respect_closing(self):
        runtime = _PlaylistRuntime()
        helper = self.make_helper(runtime)
        callbacks = {
            name: helper._runtime_callback(name)
            for name in ("playlist_list", "playlist_get", "queue_get",
                         "playlist_dispatch")
        }
        callbacks["playlist_list"](limit=4, cursor="next")
        callbacks["playlist_get"]("p1")
        callbacks["queue_get"]("q1")
        callbacks["playlist_dispatch"]({"action": "play"})
        self.assertEqual([call[-1] for call in runtime.calls], [12.0] * 4)
        self.assertTrue(helper._authorize_write("valid"))
        helper.begin_shutdown()
        self.assertFalse(helper._authorize_write("valid"))
        with self.assertRaises(GateStateError):
            callbacks["playlist_list"]()

    def test_dynamic_mock_attributes_are_not_capabilities(self):
        runtime = mock.Mock()
        helper = self.make_helper(runtime)
        self.assertIsNone(helper._runtime_callback("playlist_list"))


if __name__ == "__main__":
    unittest.main()

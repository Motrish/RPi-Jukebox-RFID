"""Strict plugin shutdown behavior for the restricted daemon profile."""

from collections import OrderedDict
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import jukebox.plugs as plugs


class PluginShutdownTests(unittest.TestCase):
    def test_strict_shutdown_runs_every_callback_and_preserves_handles_on_failure(self):
        called = []
        thread_handle = object()

        def successful(**kwargs):
            called.append(("success", kwargs))
            return thread_handle

        def failing(**kwargs):
            called.append(("failure", kwargs))
            raise RuntimeError("diagnostic close failed")

        packages = OrderedDict((
            ("first", SimpleNamespace(atexit=[successful])),
            ("second", SimpleNamespace(atexit=[failing])),
            ("third", SimpleNamespace(atexit=[successful])),
        ))
        with patch.object(plugs, "_PLUGINS", packages):
            with self.assertRaises(plugs.PluginShutdownError) as raised:
                plugs.close_down(ignore_errors=False, signal_id=7)

        self.assertEqual(["success", "failure", "success"], [item[0] for item in called])
        self.assertTrue(all(item[1] == {"signal_id": 7} for item in called))
        self.assertEqual([thread_handle, thread_handle], raised.exception.results)
        self.assertEqual(1, len(raised.exception.failures))
        self.assertEqual("second", raised.exception.failures[0][0])

    def test_legacy_shutdown_still_suppresses_callback_errors_and_returns_results(self):
        thread_handle = object()
        packages = OrderedDict((
            ("first", SimpleNamespace(atexit=[lambda: thread_handle])),
            ("second", SimpleNamespace(atexit=[lambda: (_ for _ in ()).throw(RuntimeError())])),
        ))
        with patch.object(plugs, "_PLUGINS", packages):
            self.assertEqual([thread_handle], plugs.close_down())


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

from jukebox.contracts import ContractValidationError
from components.playback_session.runtime import LocalPlaybackRuntime


class RuntimeArgumentTests(unittest.TestCase):
    def runtime(self, **overrides):
        values = {"database_path": "/tmp/library.sqlite",
                  "library_root": "/srv/audio",
                  "credential_path": "/etc/mpd.secret"}
        values.update(overrides)
        return LocalPlaybackRuntime(**values)

    def test_path_arguments_reject_non_plain_strings(self):
        invalid_values = (True, b"/tmp/path", object())
        for field in ("database_path", "library_root", "credential_path", "lock_directory"):
            for value in invalid_values:
                with self.subTest(field=field, value=repr(value)):
                    with self.assertRaises(ContractValidationError) as raised:
                        self.runtime(**{field: value})
                    self.assertEqual((field, "invalid_path"),
                                     (raised.exception.field, raised.exception.reason))

        for field in ("database_path", "library_root", "credential_path"):
            with self.subTest(field=field, value=None):
                with self.assertRaises(ContractValidationError) as raised:
                    self.runtime(**{field: None})
                self.assertEqual((field, "invalid_path"),
                                 (raised.exception.field, raised.exception.reason))

    def test_lock_directory_accepts_none(self):
        self.runtime(lock_directory=None)

    def test_host_rejects_non_plain_strings(self):
        for host in (True, b"127.0.0.1"):
            with self.subTest(host=host):
                with self.assertRaises(ContractValidationError) as raised:
                    self.runtime(mpd_host=host)
                self.assertEqual(("mpd_host", "invalid_host"),
                                 (raised.exception.field, raised.exception.reason))

    def test_port_requires_exact_int_and_accepts_boundaries(self):
        self.runtime(mpd_port=1)
        self.runtime(mpd_port=65535)
        with self.assertRaises(ContractValidationError) as raised:
            self.runtime(mpd_port=6601.0)
        self.assertEqual(("mpd_port", "invalid_port"),
                         (raised.exception.field, raised.exception.reason))

    def test_callable_clock_is_accepted_without_invocation(self):
        calls = []

        class Clock:
            def __call__(self):
                calls.append("called")

        self.runtime(monotonic=Clock())
        self.assertEqual([], calls)

    def test_valid_constructor_has_no_external_side_effects(self):
        calls = []

        def clock():
            calls.append("clock")
            raise AssertionError("constructor invoked clock")

        with patch("builtins.open") as open_spy, \
                patch("os.open") as os_open_spy, \
                patch("socket.socket") as socket_spy, \
                patch("threading.Thread") as thread_spy, \
                patch("uuid.uuid4") as uuid_spy:
            self.runtime(monotonic=clock)

        self.assertEqual([], calls)
        open_spy.assert_not_called()
        os_open_spy.assert_not_called()
        socket_spy.assert_not_called()
        thread_spy.assert_not_called()
        uuid_spy.assert_not_called()


if __name__ == "__main__":
    unittest.main()

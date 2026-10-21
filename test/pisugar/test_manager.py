import socket
import unittest
from unittest.mock import patch

from components.pisugar.manager import PiSugarStatusReader


if not hasattr(socket, "AF_UNIX"):
    socket.AF_UNIX = object()


MODELS = (
    "PiSugar 2 (4-LEDs)",
    "PiSugar 2 (2-LEDs)",
    "PiSugar 2 Pro",
    "PiSugar 3",
)

ERROR_EXPECTATIONS = {
    "SOCKET_MISSING": ("PiSugar manager socket is missing.", True),
    "SOCKET_PERMISSION_DENIED": ("PiSugar manager socket access is denied.", False),
    "SOCKET_TIMEOUT": ("PiSugar manager request timed out.", True),
    "MALFORMED_RESPONSE": ("PiSugar manager returned an invalid status response.", True),
    "UNSUPPORTED_MODEL": ("PiSugar model is unsupported.", False),
    "MANAGER_UNAVAILABLE": ("PiSugar manager is unavailable.", True),
}


def error_mapping(code):
    message, retryable = ERROR_EXPECTATIONS[code]
    return {
        "code": code,
        "message": message,
        "retryable": retryable,
        "operation": "BATTERY_STATUS",
        "details": {},
    }


class FakeSocket:
    def __init__(self, response, *, chunk_size=None, connect_error=None, clock=None):
        self.response = response
        self.chunk_size = chunk_size
        self.connect_error = connect_error
        self.clock = clock
        self.sent = b""
        self.timeouts = []
        self.closed = False
        self.offset = 0

    def settimeout(self, timeout):
        self.timeouts.append(timeout)

    def connect(self, address):
        if self.connect_error is not None:
            raise self.connect_error

    def sendall(self, data):
        self.sent += data

    def recv(self, size):
        if self.clock is not None:
            self.clock[0] += self.clock[1]
        if isinstance(self.response, BaseException):
            raise self.response
        if self.offset >= len(self.response):
            return b""
        take = min(size, self.chunk_size or size)
        data = self.response[self.offset:self.offset + take]
        self.offset += len(data)
        return data

    def close(self):
        self.closed = True


class FakeSocketFactory:
    def __init__(self, responses, **socket_options):
        self.responses = list(responses)
        self.socket_options = socket_options
        self.sockets = []

    def __call__(self, family, socktype):
        self.assert_socket_args(family, socktype)
        response = self.responses.pop(0)
        fake = FakeSocket(response, **self.socket_options)
        self.sockets.append(fake)
        return fake

    @staticmethod
    def assert_socket_args(family, socktype):
        if family != socket.AF_UNIX or socktype != socket.SOCK_STREAM:
            raise AssertionError("reader must use a local Unix stream socket")


def line(value):
    return value.encode("utf-8") + b"\n"


def responses(model=MODELS[0], percent="50"):
    return [line(f"model: {model}"), line(f"battery: {percent}")]


class PiSugarStatusReaderTests(unittest.TestCase):
    def test_disabled_default_returns_contract_snapshot_without_opening_socket(self):
        with patch("components.pisugar.manager.socket.socket") as socket_factory:
            status = PiSugarStatusReader().read_status()

        self.assertEqual(
            status,
            {
                "contractVersion": 1,
                "enabled": False,
                "detected": None,
                "reachable": False,
                "model": None,
                "percent": None,
                "charging": None,
                "measuredAt": None,
                "capabilities": [],
                "error": None,
            },
        )
        socket_factory.assert_not_called()

    def test_enabled_status_reads_only_model_and_battery_over_separate_uds_connections(self):
        factory = FakeSocketFactory(responses("PiSugar 3", "72.5"))
        with patch("components.pisugar.manager.socket.socket", side_effect=factory):
            status = PiSugarStatusReader(enabled=True).read_status()

        self.assertTrue(status["enabled"])
        self.assertTrue(status["detected"])
        self.assertTrue(status["reachable"])
        self.assertEqual(status["model"], "PiSugar 3")
        self.assertEqual(status["percent"], 72.5)
        self.assertIsNone(status["charging"])
        self.assertEqual(status["capabilities"], [])
        self.assertIsNone(status["error"])
        self.assertRegex(status["measuredAt"], r"^\d{4}-\d\d-\d\dT.*Z$")
        self.assertEqual([sock.sent for sock in factory.sockets], [b"get model\n", b"get battery\n"])
        self.assertTrue(all(sock.closed for sock in factory.sockets))

    def test_all_source_models_are_recognized(self):
        for model in MODELS:
            with self.subTest(model=model):
                factory = FakeSocketFactory(responses(model, "25"))
                with patch("components.pisugar.manager.socket.socket", side_effect=factory):
                    status = PiSugarStatusReader(enabled=True).read_status()
                self.assertEqual(status["model"], model)
                self.assertTrue(status["detected"])
                self.assertTrue(status["reachable"])

    def test_zero_hundred_and_decimal_percent_values_are_preserved(self):
        for percent in ("0", "100", "14.25"):
            with self.subTest(percent=percent):
                factory = FakeSocketFactory(responses(percent=percent))
                with patch("components.pisugar.manager.socket.socket", side_effect=factory):
                    status = PiSugarStatusReader(enabled=True).read_status()
                self.assertEqual(status["percent"], float(percent))

    def test_unknown_model_is_unavailable_and_does_not_query_battery(self):
        factory = FakeSocketFactory(responses("PiSugar 9", "99"))
        with patch("components.pisugar.manager.socket.socket", side_effect=factory):
            status = PiSugarStatusReader(enabled=True).read_status()

        self.assertEqual(status["error"], error_mapping("UNSUPPORTED_MODEL"))
        self.assertIsNone(status["detected"])
        self.assertFalse(status["reachable"])
        self.assertIsNone(status["model"])
        self.assertIsNone(status["percent"])
        self.assertIsNone(status["charging"])
        self.assertIsNone(status["measuredAt"])
        self.assertEqual(status["capabilities"], [])
        self.assertEqual(len(factory.sockets), 1)

    def test_missing_socket_returns_safe_empty_snapshot(self):
        self.assert_error_snapshot(FileNotFoundError(), "SOCKET_MISSING")

    def test_permission_error_returns_safe_empty_snapshot(self):
        self.assert_error_snapshot(PermissionError(), "SOCKET_PERMISSION_DENIED")

    def test_timeout_returns_safe_empty_snapshot(self):
        self.assert_error_snapshot(socket.timeout(), "SOCKET_TIMEOUT")

    def test_other_socket_error_returns_safe_empty_snapshot(self):
        self.assert_error_snapshot(ConnectionRefusedError(), "MANAGER_UNAVAILABLE")

    def test_eof_before_newline_is_malformed(self):
        self.assert_response_error(b"model: PiSugar 2 (4-LEDs)", "MALFORMED_RESPONSE")

    def test_invalid_utf8_is_malformed(self):
        self.assert_response_error(b"model: PiSugar 2 (4-LEDs)\xff\n", "MALFORMED_RESPONSE")

    def test_oversized_response_is_malformed(self):
        self.assert_response_error(b"model: " + b"x" * 600 + b"\n", "MALFORMED_RESPONSE")

    def test_unexpected_prefix_is_malformed(self):
        self.assert_response_error(b"battery: 50\n", "MALFORMED_RESPONSE")

    def test_unsolicited_event_after_response_does_not_invalidate_status(self):
        fake_responses = [
            b"model: PiSugar 2 (4-LEDs)\nevent: button\n",
            line("battery: 50"),
        ]
        factory = FakeSocketFactory(fake_responses)
        with patch("components.pisugar.manager.socket.socket", side_effect=factory):
            status = PiSugarStatusReader(enabled=True).read_status()

        self.assertTrue(status["reachable"])
        self.assertEqual(status["model"], MODELS[0])
        self.assertEqual(status["percent"], 50.0)

    def test_unsolicited_event_before_expected_response_fails_closed(self):
        self.assert_response_error(
            b"event: button\nmodel: PiSugar 2 (4-LEDs)\n",
            "MALFORMED_RESPONSE",
        )

    def test_non_finite_and_out_of_range_percentages_are_malformed(self):
        for percent in ("NaN", "Infinity", "-Infinity", "1_0", "-0.1", "100.1"):
            with self.subTest(percent=percent):
                self.assert_response_error(
                    [line(f"model: {MODELS[0]}"), line(f"battery: {percent}")],
                    "MALFORMED_RESPONSE",
                )

    def test_invalid_constructor_timeouts_are_rejected(self):
        for timeout in (0, -1, True, float("nan"), float("inf"), 1.01, 1000, 10**10000):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    PiSugarStatusReader(enabled=True, timeout_seconds=timeout)

    def test_absolute_deadline_expires_when_response_trickles(self):
        clock = [0.0, 0.4]
        fake = FakeSocket(line("model: PiSugar 2 (4-LEDs)"), chunk_size=1, clock=clock)
        with patch("components.pisugar.manager.socket.socket", return_value=fake), patch(
            "components.pisugar.manager.time.monotonic", side_effect=lambda: clock[0]
        ):
            status = PiSugarStatusReader(enabled=True, timeout_seconds=1.0).read_status()

        self.assertEqual(status["error"], error_mapping("SOCKET_TIMEOUT"))
        self.assertFalse(status["reachable"])
        self.assertIsNone(status["percent"])
        self.assertIsNone(status["measuredAt"])

    def test_complete_response_received_after_deadline_is_rejected(self):
        clock = [0.0, 1.1]
        factory = FakeSocketFactory(
            responses(),
            clock=clock,
        )
        with patch("components.pisugar.manager.socket.socket", side_effect=factory), patch(
            "components.pisugar.manager.time.monotonic", side_effect=lambda: clock[0]
        ):
            status = PiSugarStatusReader(enabled=True, timeout_seconds=1.0).read_status()

        self.assertEqual(status["error"], error_mapping("SOCKET_TIMEOUT"))
        self.assertFalse(status["reachable"])
        self.assertIsNone(status["percent"])
        self.assertEqual(len(factory.sockets), 1)

    def test_failed_second_read_does_not_publish_first_read_as_fresh(self):
        factory = FakeSocketFactory([line(f"model: {MODELS[0]}"), socket.timeout()])
        with patch("components.pisugar.manager.socket.socket", side_effect=factory):
            status = PiSugarStatusReader(enabled=True).read_status()

        self.assertFalse(status["reachable"])
        self.assertIsNone(status["model"])
        self.assertIsNone(status["percent"])
        self.assertIsNone(status["charging"])
        self.assertIsNone(status["measuredAt"])

    def assert_error_snapshot(self, error, code):
        fake = FakeSocket(b"", connect_error=error)
        with patch("components.pisugar.manager.socket.socket", return_value=fake):
            status = PiSugarStatusReader(enabled=True).read_status()
        self.assertEqual(status["error"], error_mapping(code))
        self.assertTrue(status["enabled"])
        self.assertIsNone(status["detected"])
        self.assertFalse(status["reachable"])
        self.assertIsNone(status["model"])
        self.assertIsNone(status["percent"])
        self.assertIsNone(status["charging"])
        self.assertIsNone(status["measuredAt"])
        self.assertEqual(status["capabilities"], [])

    def assert_response_error(self, response, code):
        replies = response if isinstance(response, list) else [response]
        with patch("components.pisugar.manager.socket.socket", side_effect=FakeSocketFactory(replies)):
            status = PiSugarStatusReader(enabled=True).read_status()
        self.assertEqual(status["error"], error_mapping(code))
        self.assertFalse(status["reachable"])
        self.assertIsNone(status["detected"])
        self.assertIsNone(status["model"])
        self.assertIsNone(status["percent"])
        self.assertIsNone(status["charging"])
        self.assertIsNone(status["measuredAt"])


if __name__ == "__main__":
    unittest.main()

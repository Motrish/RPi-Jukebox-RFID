"""Read-only PiSugar Power Manager status over its local Unix socket."""

import math
import re
import socket
import time
from datetime import datetime, timezone


_SOCKET_PATH = "/tmp/pisugar-server.sock"
_MAX_RESPONSE_BYTES = 512
_MIN_TIMEOUT_SECONDS = 0.05
_MAX_TIMEOUT_SECONDS = 1.0
_PERCENT_RE = re.compile(r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$")
_ERROR_DEFINITIONS = {
    "SOCKET_MISSING": ("PiSugar manager socket is missing.", True),
    "SOCKET_PERMISSION_DENIED": ("PiSugar manager socket access is denied.", False),
    "SOCKET_TIMEOUT": ("PiSugar manager request timed out.", True),
    "MALFORMED_RESPONSE": ("PiSugar manager returned an invalid status response.", True),
    "UNSUPPORTED_MODEL": ("PiSugar model is unsupported.", False),
    "MANAGER_UNAVAILABLE": ("PiSugar manager is unavailable.", True),
}
_MODELS = frozenset(
    {
        "PiSugar 2 (4-LEDs)",
        "PiSugar 2 (2-LEDs)",
        "PiSugar 2 Pro",
        "PiSugar 3",
    }
)


class _ReadFailure(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _error_payload(code):
    message, retryable = _ERROR_DEFINITIONS[code]
    return {
        "code": code,
        "message": message,
        "retryable": retryable,
        "operation": "BATTERY_STATUS",
        "details": {},
    }


class PiSugarStatusReader:
    """Read model and battery level without enabling control or background work."""

    def __init__(self, socket_path=_SOCKET_PATH, timeout_seconds=1.0, enabled=False):
        if not isinstance(socket_path, str) or not socket_path or chr(0) in socket_path:
            raise ValueError("socket_path must be a non-empty string without NUL")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or timeout_seconds < _MIN_TIMEOUT_SECONDS
            or timeout_seconds > _MAX_TIMEOUT_SECONDS
            or not math.isfinite(timeout_seconds)
        ):
            raise ValueError(
                "timeout_seconds must be finite and between "
                f"{_MIN_TIMEOUT_SECONDS} and {_MAX_TIMEOUT_SECONDS}"
            )
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be a bool")
        self._socket_path = socket_path
        self._timeout_seconds = float(timeout_seconds)
        self._enabled = enabled

    def read_status(self):
        """Return one BatteryStatus mapping; failed reads never reuse old values."""
        if not self._enabled:
            return self._snapshot(
                enabled=False,
                detected=None,
                reachable=False,
                model=None,
                percent=None,
                charging=None,
                measured_at=None,
                error=None,
            )

        try:
            model = self._read_value("model")
            if model not in _MODELS:
                return self._snapshot(
                    enabled=True,
                    detected=None,
                    reachable=False,
                    model=None,
                    percent=None,
                    charging=None,
                    measured_at=None,
                    error=_error_payload("UNSUPPORTED_MODEL"),
                )
            percent = self._parse_percent(self._read_value("battery"))
        except _ReadFailure as failure:
            return self._snapshot(
                enabled=True,
                detected=None,
                reachable=False,
                model=None,
                percent=None,
                charging=None,
                measured_at=None,
                error=_error_payload(failure.code),
            )

        return self._snapshot(
            enabled=True,
            detected=True,
            reachable=True,
            model=model,
            percent=percent,
            charging=None,
            measured_at=datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            error=None,
        )

    def _read_value(self, command):
        response = self._exchange(f"get {command}")
        prefix = f"{command}: "
        if not response.startswith(prefix):
            raise _ReadFailure("MALFORMED_RESPONSE")
        value = response[len(prefix):]
        if not value or value.strip() != value:
            raise _ReadFailure("MALFORMED_RESPONSE")
        return value

    def _exchange(self, command):
        deadline = time.monotonic() + self._timeout_seconds
        connection = None
        try:
            connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._connect_and_send(connection, command, deadline)
            return self._receive_line(connection, deadline)
        except _ReadFailure:
            raise
        except socket.timeout as exc:
            raise _ReadFailure("SOCKET_TIMEOUT") from exc
        except UnicodeDecodeError as exc:
            raise _ReadFailure("MALFORMED_RESPONSE") from exc
        except OSError as exc:
            raise _ReadFailure(self._socket_error_code(exc)) from exc
        finally:
            if connection is not None:
                try:
                    connection.close()
                except OSError:
                    pass

    def _connect_and_send(self, connection, command, deadline):
        connection.settimeout(self._remaining(deadline))
        connection.connect(self._socket_path)
        connection.settimeout(self._remaining(deadline))
        connection.sendall((command + "\n").encode("ascii"))
        self._remaining(deadline)

    def _receive_line(self, connection, deadline):
        response = bytearray()
        while True:
            connection.settimeout(self._remaining(deadline))
            chunk = connection.recv(_MAX_RESPONSE_BYTES + 1 - len(response))
            self._remaining(deadline)
            if not chunk:
                raise _ReadFailure("MALFORMED_RESPONSE")
            newline = chunk.find(b"\n")
            if newline >= 0:
                response.extend(chunk[:newline])
                if len(response) > _MAX_RESPONSE_BYTES:
                    raise _ReadFailure("MALFORMED_RESPONSE")
                break
            response.extend(chunk)
            if len(response) > _MAX_RESPONSE_BYTES:
                raise _ReadFailure("MALFORMED_RESPONSE")
        if response.endswith(b"\r"):
            response = response[:-1]
        return response.decode("utf-8", errors="strict")

    @staticmethod
    def _socket_error_code(error):
        if isinstance(error, PermissionError) or error.errno in (1, 13):
            return "SOCKET_PERMISSION_DENIED"
        if isinstance(error, FileNotFoundError) or error.errno == 2:
            return "SOCKET_MISSING"
        return "MANAGER_UNAVAILABLE"

    @staticmethod
    def _remaining(deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise _ReadFailure("SOCKET_TIMEOUT")
        return remaining

    @staticmethod
    def _parse_percent(value):
        if not _PERCENT_RE.fullmatch(value):
            raise _ReadFailure("MALFORMED_RESPONSE")
        percent = float(value)
        if not math.isfinite(percent) or not 0 <= percent <= 100:
            raise _ReadFailure("MALFORMED_RESPONSE")
        return percent

    @staticmethod
    def _snapshot(
        *,
        enabled,
        detected,
        reachable,
        model,
        percent,
        charging,
        measured_at,
        error,
    ):
        return {
            "contractVersion": 1,
            "enabled": enabled,
            "detected": detected,
            "reachable": reachable,
            "model": model,
            "percent": percent,
            "charging": charging,
            "measuredAt": measured_at,
            "capabilities": [],
            "error": error,
        }

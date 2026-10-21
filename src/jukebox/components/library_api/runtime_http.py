"""Bounded HTTP lifecycle for the loopback library server.

The helper owns only the loopback listener and its worker thread. The sole
runtime coupling is the public pair ``snapshot()`` and
``dispatch(command, *, deadline)``: no runtime internals, no MPD client, no
service or store instance, and no owner release. The existing library server
keeps its auth, limits, wrapper and status mapping unchanged; this module only
supplies the gated authorizer, the deadline-computing dispatch callback and a
drainable lifecycle for the daemon.
"""

import math
import logging
import threading
import time

from components.library_api import server as _library_server
from components.playback_session.execution_gate import GateStateError


_POLL_SECONDS = 0.05
_READY_MESSAGE = "local playback runtime is not ready"
_START_MESSAGE = "local playback HTTP listener failed to start"
logger = logging.getLogger(__name__)


def _finite(value):
    """Return math.isfinite for values that may overflow the conversion."""
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError, ValueError):
        return False


def _clock_reading(clock):
    """Return one validated finite clock reading or fail closed."""
    try:
        value = clock()
    except Exception:
        raise GateStateError("CLOCK_UNAVAILABLE") from None
    if type(value) not in (int, float) or not _finite(value):
        raise GateStateError("CLOCK_UNAVAILABLE") from None
    return value


def _absolute_deadline(value):
    if type(value) not in (int, float) or not _finite(value) or value <= 0:
        raise ValueError("deadline must be a positive finite number")
    return value


class LocalPlaybackHTTP:
    """Own the loopback HTTP surface of one ready local playback runtime."""

    def __init__(self, runtime, catalog, read_authorizer, port,
                 origin_host="127.0.0.1", *, command_budget_seconds=10.0,
                 monotonic=time.monotonic):
        """Validate every parameter before any resource is bound."""
        if type(command_budget_seconds) not in (int, float):
            raise TypeError("command_budget_seconds must be a number")
        if (not _finite(command_budget_seconds)
                or command_budget_seconds <= 0):
            raise ValueError("command_budget_seconds must be positive")
        if not callable(monotonic):
            raise TypeError("monotonic must be callable")
        if not callable(read_authorizer):
            raise TypeError("read_authorizer must be callable")
        if catalog is None:
            raise TypeError("catalog is required")
        if type(port) is not int or not 0 <= port <= 65535:
            raise ValueError("port must be between 0 and 65535")
        if origin_host not in {"127.0.0.1", "localhost"}:
            raise ValueError("origin_host must be a loopback name")
        self._runtime = runtime
        self._catalog = catalog
        self._read_authorizer = read_authorizer
        self._port = port
        self._origin_host = origin_host
        self._command_budget_seconds = command_budget_seconds
        self._monotonic = monotonic
        self._closing = threading.Event()
        self._server = None
        self._thread = None
        self._worker_error = None

    @property
    def address(self):
        """Return the bound loopback ``(host, port)``, or None before start."""
        server = self._server
        return None if server is None else server.server_address[:2]

    @property
    def worker_active(self):
        """Return True while the non-daemon HTTP worker thread is alive."""
        thread = self._thread
        return thread is not None and thread.is_alive()

    @property
    def worker_error(self):
        """Return the listener worker failure, if it stopped unexpectedly."""
        return self._worker_error

    def start(self):
        """Bind the loopback listener and start the non-daemon HTTP worker."""
        if self._thread is not None or self._closing.is_set():
            raise RuntimeError("local playback HTTP lifecycle already started")
        if not self._runtime_ready():
            raise RuntimeError(_READY_MESSAGE)
        try:
            server = _library_server.make_server(
                catalog=self._catalog,
                read_authorizer=self._authorize,
                port=self._port,
                origin_host=self._origin_host,
                dispatch=self._dispatch,
            )
        except Exception as error:
            raise RuntimeError(
                "{}: {}".format(_START_MESSAGE, type(error).__name__)
            ) from None
        self._server = server
        try:
            thread = threading.Thread(
                target=self._serve,
                name="library-playback-http",
                daemon=False,
            )
            thread.start()
        except BaseException as error:
            self._server = None
            try:
                server.server_close()
            finally:
                raise RuntimeError(
                    "{}: {}".format(_START_MESSAGE, type(error).__name__)
                ) from None
        self._thread = thread

    def begin_shutdown(self):
        """Close admission and signal the worker without waiting for it."""
        self._closing.set()

    def finish_shutdown(self, *, deadline):
        """Drain the worker until the absolute deadline; True once stopped."""
        deadline = _absolute_deadline(deadline)
        self.begin_shutdown()
        thread = self._thread
        if thread is None:
            return True
        thread.join(timeout=self._remaining(deadline))
        if thread.is_alive():
            return False
        self._close_server()
        return self._worker_error is None

    def _runtime_ready(self):
        runtime = self._runtime
        if runtime is None:
            return False
        try:
            snapshot = runtime.snapshot()
        except Exception:
            return False
        return isinstance(snapshot, dict) and snapshot.get("ready") is True

    def _authorize(self, credential):
        if self._closing.is_set():
            return False
        return self._read_authorizer(credential)

    def _dispatch(self, command):
        if self._closing.is_set():
            raise GateStateError("CLOSING")
        deadline = _clock_reading(self._monotonic)
        try:
            deadline = deadline + self._command_budget_seconds
        except (OverflowError, TypeError):
            raise GateStateError("CLOCK_UNAVAILABLE") from None
        if not _finite(deadline):
            raise GateStateError("CLOCK_UNAVAILABLE")
        return self._runtime.dispatch(command, deadline=deadline)

    def _serve(self):
        """Poll the listener so shutdown needs no unbounded server wait."""
        server = self._server
        server.timeout = _POLL_SECONDS
        try:
            while not self._closing.is_set():
                server.handle_request()
        except Exception as error:
            # A broken listener must not spin; expose failure to the daemon.
            self._worker_error = error
            logger.exception("Local playback HTTP listener worker failed")

    def _remaining(self, deadline):
        try:
            remaining = deadline - self._monotonic()
        except Exception:
            return 0.0
        if not _finite(remaining):
            return 0.0
        return float(max(0.0, remaining))

    def _close_server(self):
        server = self._server
        self._server = None
        if server is not None:
            server.server_close()

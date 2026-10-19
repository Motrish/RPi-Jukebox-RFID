"""Shared, deadline-bounded access to the existing MPD client."""

import math
import socket
import threading
import time
import uuid

import mpd

from .adapter import SessionFailure, _normalise_mpd_status


class MpdLock:
    """Serialize legacy MPD calls and retain their connect-on-entry behavior."""

    def __init__(self, client, host, port, shared_lock=None):
        self._lock = shared_lock if shared_lock is not None else threading.RLock()
        self.client = client
        self.host = host
        self.port = port

    def _try_connect(self):
        try:
            self.client.connect(self.host, self.port)
        except mpd.base.ConnectionError:
            pass

    def __enter__(self):
        self._lock.acquire()
        self._try_connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._lock.release()

    def acquire(self, blocking=True, timeout=-1):
        locked = self._lock.acquire(blocking, timeout)
        if locked:
            self._try_connect()
        return locked

    def release(self):
        self._lock.release()

    def locked(self):
        return self._lock.locked()


class TrackedMPDClient(mpd.MPDClient):
    """python-mpd2 client that tracks connection replacement under one RLock."""

    def __init__(self, *args, **kwargs):
        self.shared_lock = threading.RLock()
        self._session_epoch = None
        self._session_poisoned = False
        self._session_transaction_thread = threading.local()
        super().__init__(*args, **kwargs)

    def connect(self, *args, **kwargs):
        with self.shared_lock:
            if self._connected():
                return super().connect(*args, **kwargs)
            try:
                result = super().connect(*args, **kwargs)
            except Exception:
                self._session_epoch = None
                self._session_poisoned = True
                raise
            self._session_epoch = uuid.uuid4().hex
            self._session_poisoned = False
            return result

    def disconnect(self):
        with self.shared_lock:
            self._session_epoch = None
            try:
                result = super().disconnect()
            except Exception:
                self._session_poisoned = True
                raise
            self._session_poisoned = False
            return result

    @property
    def session_epoch(self):
        if not self._connected():
            return None
        return self._session_epoch

    def _connected(self):
        try:
            return self.fileno() >= 0
        except Exception:
            return False


class MpdSession:
    """Expose a narrow command set over one already-connected MPD client."""

    def __init__(self, client, monotonic=time.monotonic):
        lock = getattr(client, "shared_lock", None)
        if lock is None or not callable(monotonic):
            raise ValueError("A tracked MPD client and monotonic clock are required.")
        self.client = client
        self.lock = lock
        self._monotonic = monotonic

    def transaction(self, deadline):
        return _Transaction(self, deadline)


class _Transaction:
    def __init__(self, session, deadline):
        self.session = session
        self.deadline = _validate_deadline(deadline)
        self._captured_epoch = None
        self._owner_thread = None
        self._active = False
        self._socket = None
        self._watchdog = None

    def __enter__(self):
        session = self.session
        client_thread = session.client._session_transaction_thread
        if getattr(client_thread, "active", False):
            raise SessionFailure("UNAVAILABLE")
        remaining = self.deadline - session._monotonic()
        if remaining <= 0:
            raise SessionFailure("TIMEOUT")
        if not session.lock.acquire(timeout=min(remaining, threading.TIMEOUT_MAX)):
            raise SessionFailure("TIMEOUT")
        client_thread.active = True
        try:
            if session._monotonic() >= self.deadline:
                raise SessionFailure("TIMEOUT")
            self._captured_epoch = session.client.session_epoch
            self._owner_thread = threading.get_ident()
            if self._captured_epoch is None or session.client._session_poisoned:
                raise SessionFailure("UNAVAILABLE")
            if session.client.timeout is not None or socket.getdefaulttimeout() is not None:
                raise SessionFailure("UNAVAILABLE")
            self._socket = _duplicate_connected_socket(session.client)
            self._arm_watchdog()
            self._active = True
            return self
        except BaseException:
            self._close_socket()
            client_thread.active = False
            session.lock.release()
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        self._check_active()
        failure = None
        self._disarm_watchdog()
        try:
            if self._expired() or self.session._monotonic() >= self.deadline:
                failure = SessionFailure("TIMEOUT")
                self._invalidate_transport()
            elif self._current_epoch() != self._captured_epoch:
                failure = SessionFailure("UNAVAILABLE")
        finally:
            self._active = False
            self._owner_thread = None
            self._close_socket()
            self.session.client._session_transaction_thread.active = False
            self.session.lock.release()
        if failure is not None and exc_type is None:
            raise failure
        return False

    @property
    def epoch(self):
        return self.session.client.session_epoch

    def status(self):
        return _normalise_mpd_status(self._call("status"))

    def repeat(self, value):
        self._call("repeat", value)

    def random(self, value):
        self._call("random", value)

    def single(self, value):
        self._call("single", value)

    def consume(self, value):
        self._call("consume", value)

    def clear(self):
        self._call("clear")

    def addid(self, reference):
        result = self._call("addid", reference)
        if not isinstance(result, str) or not result.isascii() or not result.isdigit():
            self._invalidate_transport()
            raise SessionFailure("UNAVAILABLE")
        return result

    def playid(self, songid):
        self._call("playid", songid)

    def pause(self, value):
        self._call("pause", value)

    def seekid(self, songid, seconds):
        self._call("seekid", songid, seconds)

    def stop(self):
        self._call("stop")

    def _call(self, name, *args):
        self._check_active()
        self._check_deadline()
        if self._current_epoch() != self._captured_epoch:
            self._invalidate_transport()
            raise SessionFailure("UNAVAILABLE")
        try:
            result = getattr(self.session.client, name)(*args)
        except mpd.base.CommandError:
            self._check_after_call()
            raise SessionFailure("COMMAND_REJECTED") from None
        except Exception:
            expired = self._expired() or self.session._monotonic() >= self.deadline
            self._invalidate_transport()
            raise SessionFailure("TIMEOUT" if expired else "UNAVAILABLE") from None
        self._check_after_call()
        return result

    def _check_active(self):
        if not self._active or threading.get_ident() != self._owner_thread:
            raise SessionFailure("UNAVAILABLE")

    def _check_deadline(self):
        if self._expired() or self.session._monotonic() >= self.deadline:
            self._invalidate_transport()
            raise SessionFailure("TIMEOUT")

    def _check_after_call(self):
        if self._expired() or self.session._monotonic() >= self.deadline:
            self._invalidate_transport()
            raise SessionFailure("TIMEOUT")
        if self._current_epoch() != self._captured_epoch:
            self._invalidate_transport()
            raise SessionFailure("UNAVAILABLE")

    def _current_epoch(self):
        epoch = self.session.client.session_epoch
        if epoch is None:
            self.session.client._session_poisoned = True
        return epoch

    def _arm_watchdog(self):
        self._watchdog = _Watchdog(self._socket, self.deadline, self.session._monotonic)
        self._watchdog.start()

    def _expired(self):
        return self._watchdog is not None and self._watchdog.expired

    def _disarm_watchdog(self):
        if self._watchdog is not None:
            self._watchdog.disarm()

    def _invalidate_transport(self):
        self._shutdown_owned_socket()
        client = self.session.client
        if client._session_epoch != self._captured_epoch:
            return
        client._session_epoch = None
        client._session_poisoned = True
        try:
            client.disconnect()
        except Exception:
            client._session_poisoned = True

    def _shutdown_owned_socket(self):
        if self._socket is not None:
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def _close_socket(self):
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None


class _Watchdog:
    def __init__(self, sock, deadline, monotonic):
        self._socket = sock
        self._deadline = deadline
        self._monotonic = monotonic
        self._wake = threading.Event()
        self._state_lock = threading.Lock()
        self._state = "active"
        self._thread = threading.Thread(target=self._run, name="mpd-session-deadline", daemon=True)

    @property
    def expired(self):
        with self._state_lock:
            return self._state == "expired"

    def start(self):
        self._thread.start()

    def disarm(self):
        with self._state_lock:
            if self._state == "active":
                self._state = "disarmed"
            self._wake.set()

    def _run(self):
        while True:
            remaining = self._deadline - self._monotonic()
            if remaining <= 0:
                break
            self._wake.wait(min(remaining, threading.TIMEOUT_MAX))
            if self._wake.is_set():
                return
        with self._state_lock:
            if self._state != "active":
                return
            if self._monotonic() < self._deadline:
                return
            self._state = "expired"
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def _validate_deadline(deadline):
    if isinstance(deadline, bool) or not isinstance(deadline, (int, float)):
        raise ValueError("Deadline must be finite monotonic seconds.")
    try:
        finite = math.isfinite(deadline)
    except (OverflowError, TypeError):
        finite = False
    if not finite:
        raise ValueError("Deadline must be finite monotonic seconds.")
    return float(deadline)


def _duplicate_connected_socket(client):
    try:
        descriptor = client.fileno()
        if descriptor < 0:
            raise OSError("MPD client is disconnected")
        borrowed = socket.socket(fileno=descriptor)
        try:
            duplicate = borrowed.dup()
        finally:
            borrowed.detach()
        return duplicate
    except Exception:
        raise SessionFailure("UNAVAILABLE") from None

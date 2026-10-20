"""Inactive-by-default exclusive owner for one local playback runtime."""

import math
import os
import stat
import sys
import threading
import time
import uuid

from jukebox.contracts import ContractValidationError, validate_identifier, validate_media_ref

from components.local_provider.adapter import LocalProvider, SessionFailure
from components.local_provider.mpd_session import MpdSession, TrackedMPDClient
from components.playback_session.local_playback_service import LocalPlaybackService
from components.playback_session.execution_gate import GateStateError
from components.library_catalog.catalog import CatalogError, LibraryCatalog


_FAILURE_CODES = {"UNSUPPORTED_PLATFORM", "OWNER_BUSY", "OWNER_PATH_UNSAFE",
                  "CREDENTIAL_UNAVAILABLE", "CATALOG_UNAVAILABLE", "BOOTSTRAP_FAILED",
                  "DRIVER_FAILED", "STOP_UNCONFIRMED", "SHUTDOWN_INCOMPLETE"}
_CAPABILITIES = {"canPause": False, "canResume": False, "canSeek": False,
                 "canConfirmStop": True, "canIdentifyNaturalEnd": False}


class LocalPlaybackRuntime:
    """Own process exclusion, bootstrap reconciliation, service and driver."""

    def __init__(self, *, database_path, library_root, credential_path,
                 mpd_host="127.0.0.1", mpd_port=6601, monotonic=time.monotonic,
                 lock_directory=None):
        self.database_path = _path(database_path, "database_path")
        self.library_root = _path(library_root, "library_root")
        self.credential_path = _path(credential_path, "credential_path")
        self.lock_directory = None if lock_directory is None else _path(lock_directory, "lock_directory")
        if type(mpd_host) is not str or mpd_host != "127.0.0.1":
            raise ContractValidationError("mpd_host", "invalid_host")
        if type(mpd_port) is not int or not 1 <= mpd_port <= 65535:
            raise ContractValidationError("mpd_port", "invalid_port")
        if not callable(monotonic):
            raise ContractValidationError("monotonic", "invalid_clock")
        self.mpd_host, self.mpd_port, self._clock = mpd_host, mpd_port, monotonic
        self._lock = threading.Lock()
        self._service_control_condition = threading.Condition(self._lock)
        self._service_control_active = False
        self._phase = "NEW"
        self._ready = False
        self._boot_id = None
        self._failure = None
        self._owner_fd = None
        self._catalog = self._client = self._session = self._provider = self._service = None
        self._timer = None
        self._bootstrap_active = False
        self._bootstrap_effect = False
        self._driving = False
        self._closing_requested = False
        self._finish_active = False
        self._service_shutdown_started = False
        self._cleanup_driver_enabled = False
        self._stop_request_generation = 0
        self._resources_closed = False
        self._client_closed = False
        self._catalog_closed = False
        self._shutdown_prepared = False
        self._shutdown_io_closed = False

    def snapshot(self):
        with self._lock:
            values = (self._phase, self._ready, self._boot_id, self._owner_fd is not None,
                      self._bootstrap_active, self._timer, self._bootstrap_effect,
                      self._driving, None if self._failure is None else dict(self._failure),
                      self._service, self._resources_closed)
        timer_alive = values[5] is not None and values[5].is_alive()
        service = None if values[9] is None else values[9].snapshot()
        return {"phase": values[0], "ready": values[1], "bootId": values[2],
                "ownerLockHeld": values[3], "bootstrapActive": values[4], "driverAlive": timer_alive,
                "quiescent": (not values[4] and not values[6] and not values[7]
                              and (service is None or service["quiescent"])
                              and not (values[0] == "CLOSING" and values[8]
                                       == {"code": "SHUTDOWN_INCOMPLETE"})
                              and (values[0] != "CLOSED"
                                   or (not timer_alive and not values[3] and values[10]))),
                "service": service, "failure": values[8]}

    def start(self, *, deadline):
        _validate_deadline(deadline)
        if float(deadline) <= self._read_clock():
            raise GateStateError("DEADLINE_EXPIRED")
        with self._lock:
            if self._phase == "READY":
                already_ready = True
            elif self._phase == "STARTING" or self._bootstrap_active:
                raise GateStateError("BUSY")
            elif self._phase != "NEW":
                raise GateStateError("CLOSED" if self._closing_requested else "NOT_READY")
            else:
                already_ready = False
                self._phase = "STARTING"
                self._bootstrap_active = True
        if already_ready:
            return self.snapshot()
        return self._start_new(deadline)

    def _start_new(self, deadline):
        code = None
        try:
            if not (os.name == "posix" and sys.platform.startswith("linux")):
                code = "UNSUPPORTED_PLATFORM"
                return self._fail_bootstrap(code)
            self._bootstrap_core(deadline)
            self._bootstrap_effect = False
            self._boot_id = uuid.uuid4().hex
            self._provider = LocalProvider(session=self._session, resolver=self._catalog.resolve,
                                           monotonic=self._clock, capabilities=_CAPABILITIES)
            self._service = LocalPlaybackService(provider=self._provider, boot_id=self._boot_id,
                                                 monotonic=self._clock)
            code = "DRIVER_FAILED"
            from jukebox.multitimer import GenericEndlessTimerClass
            self._timer = GenericEndlessTimerClass(name=None, wait_seconds_per_iteration=0.25,
                                                   function=self._tick)
            self._timer.start()
            with self._lock:
                if self._closing_requested:
                    self._phase = "CLOSING"
                    self._ready = False
                    close_raced = True
                else:
                    self._phase = "READY"
                    self._ready = True
                    close_raced = False
                self._bootstrap_active = False
            if close_raced:
                self._timer.cancel()
            return self.snapshot()
        except _OwnerBusy:
            code = "OWNER_BUSY"
        except _OwnerUnsafe:
            code = "OWNER_PATH_UNSAFE"
        except _StopUnconfirmed:
            code = "STOP_UNCONFIRMED"
        except _CredentialUnavailable:
            code = "CREDENTIAL_UNAVAILABLE"
        except CatalogError as error:
            code = "UNSUPPORTED_PLATFORM" if error.safe.code == "UNSUPPORTED_PLATFORM" else "CATALOG_UNAVAILABLE"
        except Exception:
            if code is None:
                code = "BOOTSTRAP_FAILED"
        return self._fail_bootstrap(code or "BOOTSTRAP_FAILED")

    def _bootstrap_core(self, deadline):
        self._acquire_owner_lock()
        self._catalog = LibraryCatalog(self.database_path, self.library_root)
        self._client = TrackedMPDClient()
        connect_timeout = float(deadline) - self._read_clock()
        if connect_timeout <= 0:
            raise RuntimeError("startup deadline expired")
        self._client.timeout = min(5.0, connect_timeout)
        self._client.idletimeout = None
        self._client.connect(self.mpd_host, self.mpd_port)
        secret = _read_credential(self.credential_path)
        self._session = MpdSession(self._client, monotonic=self._clock)
        self._client.timeout = None
        try:
            with self._session.transaction(deadline) as transaction:
                epoch = transaction.epoch
                transaction.password(secret)
                status = transaction.status()
                if status["state"] in {"play", "pause"}:
                    self._bootstrap_effect = True
                    transaction.stop()
                final_status = transaction.status()
                if (transaction.epoch != epoch or final_status["state"] != "stop"
                        or final_status["hasError"]):
                    raise _StopUnconfirmed()
        except SessionFailure:
            if self._bootstrap_effect:
                raise _StopUnconfirmed() from None
            raise

    def request_start(self, entry_id, media_ref):
        _validate_start_request(entry_id, media_ref)
        with self._lock:
            if self._phase != "READY" or not self._ready:
                raise GateStateError("CLOSED" if self._closing_requested else "NOT_READY")
            service = self._service
        intent_id = service.request_start(entry_id, media_ref)
        self._trigger()
        return intent_id

    def request_stop(self):
        with self._lock:
            service = self._service
            if service is None:
                raise GateStateError("NOT_READY")
            if self._shutdown_io_closed or self._shutdown_prepared:
                raise GateStateError("CLOSED")
            if self._phase == "CLOSED":
                raise GateStateError("CLOSED")
            self._stop_request_generation += 1
            self._cleanup_driver_enabled = True
        self._claim_service_control()
        try:
            result = service.request_stop()
        finally:
            self._release_service_control()
        self._trigger()
        return result

    def begin_shutdown(self):
        with self._lock:
            if self._phase in {"CLOSING", "CLOSED"}:
                service = None
                already_closing = True
            else:
                already_closing = False
                self._closing_requested = True
                self._ready = False
                self._phase = "CLOSING"
                service = self._service
        if already_closing:
            return self.snapshot()
        if service is not None:
            self._begin_service_shutdown(service)
        return self.snapshot()

    def finish_shutdown(self, *, deadline, release_owner=True):
        _validate_deadline(deadline)
        if type(release_owner) is not bool:
            raise ContractValidationError("release_owner", "invalid_boolean")
        with self._lock:
            if self._finish_active:
                raise GateStateError("BUSY")
            if self._phase == "CLOSED":
                already_closed = True
            else:
                already_closed = False
                self._finish_active = True
        if already_closed:
            return self.snapshot()
        try:
            if self._shutdown_prepared:
                if not release_owner:
                    return self.snapshot()
                if float(deadline) <= self._read_clock():
                    return self._shutdown_failure()
                if not self._release_owner_lock():
                    return self._shutdown_failure()
                with self._lock:
                    self._resources_closed = True
                    self._phase, self._ready = "CLOSED", False
                    self._failure = None
                return self.snapshot()
            self.begin_shutdown()
            if float(deadline) <= self._read_clock():
                return self._shutdown_failure()
            return self._finish_until(deadline, release_owner=release_owner)
        finally:
            with self._lock:
                self._finish_active = False

    def _finish_until(self, deadline, *, release_owner=True):
        if not self._wait_for_calls(deadline):
            return self._shutdown_failure()
        if not self._finish_service(deadline):
            return self._shutdown_failure()
        if not self._stop_timer(deadline):
            return self._shutdown_failure()
        if self._bootstrap_effect:
            return self._shutdown_failure("STOP_UNCONFIRMED")
        with self._lock:
            self._shutdown_io_closed = True
        if not self._close_resources(release_owner=release_owner):
            return self._shutdown_failure()
        if not release_owner:
            with self._lock:
                self._shutdown_prepared = True
                self._phase, self._ready = "CLOSING", False
                self._failure = None
            return self.snapshot()
        with self._lock:
            self._resources_closed = True
            self._phase, self._ready = "CLOSED", False
            self._failure = None
        return self.snapshot()

    def _wait_for_calls(self, deadline):
        while True:
            with self._lock:
                active = self._bootstrap_active or self._driving
            now = self._read_clock()
            if not active:
                return now < float(deadline)
            if now >= float(deadline):
                return False
            threading.Event().wait(min(0.01, float(deadline) - now))

    def _finish_service(self, deadline):
        service = self._service
        if service is None:
            return True
        self._begin_service_shutdown(service)
        while True:
            state = service.snapshot()
            if state["quiescent"]:
                with self._lock:
                    self._cleanup_driver_enabled = False
                return True
            if (state["lastFailure"] is not None
                    and state["lastFailure"]["operation"] == "STOP"):
                with self._lock:
                    retry_authorized = self._cleanup_driver_enabled
                if not retry_authorized:
                    return False
            now = self._read_clock()
            if now >= float(deadline):
                return False
            driven = self._drive_once(min(float(deadline), now + 1.0))
            if not driven:
                threading.Event().wait(min(0.005, max(0.0, float(deadline) - self._read_clock())))

    def _begin_service_shutdown(self, service, *, preserve_stop_request_generation=None):
        if not self._claim_service_control(
                preserve_stop_request_generation=preserve_stop_request_generation,
                shutdown=True):
            return False
        try:
            service.begin_shutdown()
        finally:
            self._release_service_control()
        return True

    def _claim_service_control(self, *, preserve_stop_request_generation=None, shutdown=False):
        with self._service_control_condition:
            while self._service_control_active:
                self._service_control_condition.wait()
            if (preserve_stop_request_generation is not None
                    and self._stop_request_generation != preserve_stop_request_generation):
                return False
            if shutdown and self._service_shutdown_started:
                return False
            if shutdown:
                self._service_shutdown_started = True
            self._service_control_active = True
            return True

    def _release_service_control(self):
        with self._service_control_condition:
            self._service_control_active = False
            self._service_control_condition.notify_all()

    def _stop_timer(self, deadline):
        if self._timer is None:
            return True
        self._timer.cancel()
        thread = getattr(self._timer, "timer_thread", None)
        if thread is None:
            return True
        thread.join(max(0.0, float(deadline) - self._read_clock()))
        return not thread.is_alive()

    def _tick(self):
        with self._lock:
            is_ready = self._phase == "READY" and self._ready
            is_cleanup = self._phase == "UNAVAILABLE" and self._cleanup_driver_enabled
            if not (is_ready or is_cleanup):
                return
        try:
            self._drive_once(self._read_clock() + 1.0)
        except BaseException:
            with self._lock:
                self._ready = False
                self._phase = "UNAVAILABLE"
                self._failure = {"code": "DRIVER_FAILED"}
                self._cleanup_driver_enabled = False
                service = self._service
            if service is not None:
                self._begin_service_shutdown(service)

    def _drive_once(self, deadline):
        with self._lock:
            if self._driving or self._service is None:
                return False
            self._driving = True
            service = self._service
            stop_request_generation = self._stop_request_generation
        callback_failed = False
        try:
            service.run_once(deadline=deadline)
        except BaseException:
            callback_failed = True
        finally:
            with self._lock:
                self._driving = False
        state = service.snapshot()
        if callback_failed:
            self._latch_service_failure(service, state.get("lastFailure") or {
                "operation": "DRIVER", "code": "DRIVER_FAILED"},
                stop_request_generation=stop_request_generation)
            return True
        failure = state["lastFailure"]
        pending = state["pending"]
        superseded_start = (
            failure is not None
            and failure.get("operation") == "START"
            and failure.get("code") in {"STALE_EXECUTION", "START_REJECTED"}
            and pending is not None
            and pending.get("operation") == "START"
            and (failure.get("code") == "STALE_EXECUTION"
                 or (state["gate"]["owner"] is None
                     and not state["gate"]["cleanupRequired"]))
        )
        if failure is not None and not superseded_start:
            self._latch_service_failure(
                service, failure, stop_request_generation=stop_request_generation)
            return True
        if state["quiescent"]:
            with self._lock:
                self._cleanup_driver_enabled = False
        with self._lock:
            can_continue = (self._phase == "READY" and self._ready
                            or self._phase == "UNAVAILABLE" and self._cleanup_driver_enabled)
        if state["pending"] is not None and can_continue and self._timer is not None:
            self._trigger()
        return True

    def _latch_service_failure(self, service, failure, *, stop_request_generation=None):
        code = ("STOP_UNCONFIRMED" if failure.get("operation") == "STOP"
                and failure.get("code") == "STOP_UNCONFIRMED" else "DRIVER_FAILED")
        with self._lock:
            retry_published = (stop_request_generation is not None
                               and self._stop_request_generation != stop_request_generation)
            self._ready = False
            if self._phase != "CLOSING":
                self._phase = "UNAVAILABLE"
            self._failure = {"code": code}
            self._cleanup_driver_enabled = bool(retry_published)
        if not retry_published:
            self._begin_service_shutdown(
                service, preserve_stop_request_generation=stop_request_generation)

    def _trigger(self):
        timer = self._timer
        if timer is not None and timer.is_alive():
            timer.trigger()

    def _acquire_owner_lock(self):
        descriptor = _acquire_audio_owner_descriptor(lock_directory=self.lock_directory)
        with self._lock:
            if self._owner_fd is not None:
                os.close(descriptor)
                raise _OwnerUnsafe()
            self._owner_fd = descriptor

    def _fail_bootstrap(self, code):
        with self._lock:
            self._ready = False
            self._phase = "CLOSING" if self._closing_requested else "UNAVAILABLE"
            self._failure = {"code": code}
        cleaned = True
        resources_were_safe_to_close = not self._bootstrap_effect
        if resources_were_safe_to_close:
            cleaned = self._close_resources()
        with self._lock:
            if not cleaned:
                self._failure = {"code": "SHUTDOWN_INCOMPLETE"}
            elif resources_were_safe_to_close:
                self._resources_closed = True
            self._bootstrap_active = False
        return self.snapshot()

    def _close_resources(self, *, release_owner=True):
        with self._lock:
            if self._resources_closed:
                return True
            client_closed, catalog_closed = self._client_closed, self._catalog_closed
        for resource, method, flag in ((self._client, "disconnect", "client"),
                                       (self._catalog, "close", "catalog")):
            if (flag == "client" and client_closed) or (flag == "catalog" and catalog_closed):
                continue
            if resource is not None:
                try:
                    getattr(resource, method)()
                except Exception:
                    return False
                with self._lock:
                    if flag == "client":
                        self._client_closed = True
                        client_closed = True
                    else:
                        self._catalog_closed = True
                        catalog_closed = True
            elif flag == "client":
                with self._lock:
                    self._client_closed = True
                client_closed = True
            else:
                with self._lock:
                    self._catalog_closed = True
                catalog_closed = True
        if not release_owner:
            return True
        return self._release_owner_lock()

    def _release_owner_lock(self):
        with self._lock:
            owner_fd = self._owner_fd
        if owner_fd is not None:
            try:
                os.close(owner_fd)
            except OSError:
                return False
            with self._lock:
                if self._owner_fd == owner_fd:
                    self._owner_fd = None
        return True

    def _shutdown_failure(self, code="SHUTDOWN_INCOMPLETE"):
        with self._lock:
            self._ready = False
            self._phase = "CLOSING"
            self._failure = {"code": code}
        return self.snapshot()

    def _read_clock(self):
        try:
            value = self._clock()
        except Exception:
            raise GateStateError("CLOCK_UNAVAILABLE") from None
        try:
            finite = type(value) in (int, float) and math.isfinite(float(value))
        except (OverflowError, TypeError, ValueError):
            finite = False
        if not finite:
            raise GateStateError("CLOCK_UNAVAILABLE")
        return float(value)


class _OwnerBusy(Exception):
    pass


class _OwnerUnsafe(Exception):
    pass


class _StopUnconfirmed(Exception):
    pass


class _CredentialUnavailable(Exception):
    pass


def _acquire_audio_owner_descriptor(*, lock_directory=None):
    """Return the exclusively locked descriptor for the shared audio owner."""
    uid = os.geteuid()
    directory = lock_directory or "/tmp/phoniebox-playback-%s" % uid
    directory_fd = None
    descriptor = None
    try:
        directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        info = os.fstat(directory_fd)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != uid or stat.S_IMODE(info.st_mode) != 0o700:
            raise OSError("unsafe owner directory")
        flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW
        descriptor = os.open("audio-owner.lock", flags, 0o600, dir_fd=directory_fd)
        os.close(directory_fd)
        directory_fd = None
        file_info = os.fstat(descriptor)
        if (not stat.S_ISREG(file_info.st_mode) or file_info.st_uid != uid
                or stat.S_IMODE(file_info.st_mode) != 0o600):
            raise OSError("unsafe owner file")
        try:
            import fcntl
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise _OwnerBusy()
        return descriptor
    except _OwnerBusy:
        if descriptor is not None:
            os.close(descriptor)
        raise
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        raise _OwnerUnsafe() from None
    finally:
        if directory_fd is not None:
            os.close(directory_fd)


def _path(value, field):
    if type(value) is not str or "\x00" in value or not value.startswith("/"):
        raise ContractValidationError(field, "invalid_path")
    parts = value[1:].split("/")
    if value == "/" or value.endswith("/") or any(item in {"", ".", ".."} for item in parts):
        raise ContractValidationError(field, "invalid_path")
    return value


def _validate_start_request(entry_id, media_ref):
    if type(entry_id) is not str:
        raise ContractValidationError("entryId", "invalid_identifier")
    if type(media_ref) is not dict:
        raise ContractValidationError("mediaRef", "invalid_fields")
    media_snapshot = media_ref.copy()
    if (any(type(key) is not str for key in media_snapshot)
            or any(type(value) is not str for value in media_snapshot.values())):
        raise ContractValidationError("mediaRef", "invalid_fields")
    validate_identifier(entry_id, "entryId")
    ref = validate_media_ref(media_snapshot)
    if ref["kind"] != "LOCAL":
        raise ContractValidationError("mediaRef.kind", "unsupported_source_kind")


def _validate_deadline(value):
    if type(value) not in (int, float):
        raise ContractValidationError("deadline", "invalid_deadline")
    try:
        if not math.isfinite(float(value)):
            raise ValueError
    except (OverflowError, ValueError, TypeError):
        raise ContractValidationError("deadline", "invalid_deadline") from None


def _read_credential(path):
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            info = os.fstat(descriptor)
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > 4096):
                raise ValueError
            raw = os.read(descriptor, 4097)
        finally:
            os.close(descriptor)
        if len(raw) > 4096 or b"\r" in raw or b"\x00" in raw:
            raise ValueError
        value = raw.decode("utf-8")
        if value.endswith("\n"):
            value = value[:-1]
        if not value or "\n" in value:
            raise ValueError
        return value
    except Exception:
        raise _CredentialUnavailable() from None

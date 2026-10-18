"""One-iteration, lease-protected orchestration for trusted setup handlers."""

from __future__ import annotations

import copy
import os
from pathlib import Path
import re
import sqlite3
import stat
from urllib.parse import quote

try:
    import fcntl
except ImportError:  # Windows can validate construction but cannot run workers.
    fcntl = None

from installation.websetup.jobs import JobError, JobStore


_STEPS = ("CHECK_SYSTEM", "CONFIGURE_AUDIO", "VERIFY_INSTALLATION")
_OBSERVATIONS = ("APPLIED", "NOT_APPLIED", "UNKNOWN")
_ERROR_CODES = ("INVALID_REQUEST", "WORKER_BUSY", "WORKER_UNAVAILABLE")
_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,64}\Z", re.ASCII)


class WorkerError(Exception):
    """Public worker error carrying only a stable, redacted code."""

    def __init__(self, code):
        self.code = code if code in _ERROR_CODES else "WORKER_UNAVAILABLE"
        super().__init__(self.code)

    def __str__(self):
        return self.code

    def __repr__(self):
        return "WorkerError({!r})".format(self.code)


def _raise(code):
    raise WorkerError(code) from None


def _file_identity(path):
    try:
        metadata = os.lstat(str(path))
    except Exception:
        _raise("WORKER_UNAVAILABLE")
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        _raise("WORKER_UNAVAILABLE")
    return metadata.st_dev, metadata.st_ino


def _database_identity(database_path):
    if isinstance(database_path, bool) or not isinstance(database_path, (str, Path)):
        _raise("INVALID_REQUEST")
    try:
        if isinstance(database_path, str):
            if not database_path or database_path == ":memory:":
                _raise("INVALID_REQUEST")
            requested = Path(database_path)
        else:
            requested = database_path
        if not str(requested) or str(requested) == ":memory:":
            _raise("INVALID_REQUEST")
        parent = requested.parent.resolve(strict=True)
        canonical = parent / requested.name
        if canonical.is_symlink():
            _raise("WORKER_UNAVAILABLE")
        identity = _file_identity(canonical)
        if not os.access(str(canonical), os.R_OK | os.W_OK):
            _raise("WORKER_UNAVAILABLE")
        return canonical, identity
    except WorkerError:
        raise
    except Exception:
        raise WorkerError("WORKER_UNAVAILABLE") from None


def _validated_handlers(handlers):
    if type(handlers) is not dict or set(handlers) != set(_STEPS):
        _raise("INVALID_REQUEST")
    safe_handlers = {}
    for step in _STEPS:
        try:
            handler = handlers[step]
            is_callable = (callable(getattr(handler, "apply", None))
                           and callable(getattr(handler, "observe", None)))
        except Exception:
            raise WorkerError("INVALID_REQUEST") from None
        if not is_callable:
            _raise("INVALID_REQUEST")
        safe_handlers[step] = handler
    return safe_handlers


def _validate_desired_config(config):
    if (type(config) is not dict
            or set(config) != {"audioOutput", "rfidEnabled", "pisugarEnabled"}
            or type(config.get("audioOutput")) is not str
            or config.get("audioOutput") not in ("SYSTEM_DEFAULT", "HIFIBERRY_MINIAMP")
            or type(config.get("rfidEnabled")) is not bool
            or type(config.get("pisugarEnabled")) is not bool):
        _raise("WORKER_UNAVAILABLE")


def _validate_active_step_state(snapshot):
    status = snapshot["status"]
    applied = snapshot["appliedSteps"]
    if len(applied) > len(_STEPS):
        _raise("WORKER_UNAVAILABLE")
    for index, item in enumerate(applied):
        if (type(item) is not dict or set(item) != {"stepId", "diagnostic"}
                or item["stepId"] != _STEPS[index]
                or item["diagnostic"] != "CONFIRMED"):
            _raise("WORKER_UNAVAILABLE")
    if status == "QUEUED":
        if (snapshot["stepId"] is not None or len(applied) >= len(_STEPS)
                or snapshot["nextAction"] is not None or snapshot["error"] is not None):
            _raise("WORKER_UNAVAILABLE")
        return
    if (len(applied) >= len(_STEPS)
            or snapshot["stepId"] != _STEPS[len(applied)]):
        _raise("WORKER_UNAVAILABLE")
    if status == "RUNNING":
        if snapshot["nextAction"] is not None or snapshot["error"] is not None:
            _raise("WORKER_UNAVAILABLE")
    elif (snapshot["nextAction"] != {"kind": "INSPECT_SYSTEM"}
          or snapshot["error"] is not None):
        _raise("WORKER_UNAVAILABLE")


class Worker:
    """Runs at most one persisted setup step under an OS process lease."""

    def __init__(self, database_path, handlers):
        canonical, identity = _database_identity(database_path)
        safe_handlers = _validated_handlers(handlers)
        self._database_path = canonical
        self._database_identity = identity
        self._lease_path = Path(str(canonical) + ".worker.lock")
        self._handlers = safe_handlers

    def _check_database_identity(self):
        if _file_identity(self._database_path) != self._database_identity:
            _raise("WORKER_UNAVAILABLE")

    def _check_lease_identity(self, descriptor):
        try:
            metadata = os.fstat(descriptor)
            path_metadata = os.lstat(str(self._lease_path))
        except Exception:
            _raise("WORKER_UNAVAILABLE")
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                or not stat.S_ISREG(path_metadata.st_mode) or path_metadata.st_nlink != 1
                or (metadata.st_dev, metadata.st_ino) != (path_metadata.st_dev, path_metadata.st_ino)):
            _raise("WORKER_UNAVAILABLE")

    def _check_identity(self, descriptor):
        self._check_database_identity()
        self._check_lease_identity(descriptor)

    def _check_existing_journal(self):
        """Reject absent or unrelated SQLite files before JobStore can initialize them."""
        self._check_database_identity()
        connection = None
        try:
            uri = "file:{}?mode=ro".format(quote(str(self._database_path), safe="/:"))
            connection = sqlite3.connect(uri, uri=True, timeout=5.0)
            names = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'")}
            if not {"journal_meta", "jobs"}.issubset(names):
                _raise("WORKER_UNAVAILABLE")
        except WorkerError:
            raise
        except Exception:
            raise WorkerError("WORKER_UNAVAILABLE") from None
        finally:
            if connection is not None:
                try:
                    connection.close()
                except sqlite3.Error:
                    pass
        self._check_database_identity()

    @staticmethod
    def _validate_active_snapshot(snapshot):
        expected_fields = {
            "contractVersion", "jobId", "commandId", "status", "stepId",
            "desiredConfigSummary", "appliedSteps", "revision", "createdAt",
            "updatedAt", "nextAction", "error",
        }
        try:
            if type(snapshot) is not dict or set(snapshot) != expected_fields:
                _raise("WORKER_UNAVAILABLE")
            if snapshot["contractVersion"] != "websetup.job.v1":
                _raise("WORKER_UNAVAILABLE")
            if (_TOKEN.fullmatch(snapshot["jobId"]) is None
                    or _TOKEN.fullmatch(snapshot["commandId"]) is None):
                _raise("WORKER_UNAVAILABLE")
            if (type(snapshot["createdAt"]) is not str
                    or not snapshot["createdAt"].endswith("Z")
                    or type(snapshot["updatedAt"]) is not str
                    or not snapshot["updatedAt"].endswith("Z")):
                _raise("WORKER_UNAVAILABLE")
            status = snapshot["status"]
            applied = snapshot["appliedSteps"]
            if status not in ("QUEUED", "RUNNING", "WAITING_USER") or type(applied) is not list:
                _raise("WORKER_UNAVAILABLE")
            if type(snapshot["revision"]) is not int or snapshot["revision"] < 0:
                _raise("WORKER_UNAVAILABLE")
            _validate_desired_config(snapshot["desiredConfigSummary"])
            _validate_active_step_state(snapshot)
        except WorkerError:
            raise
        except Exception:
            raise WorkerError("WORKER_UNAVAILABLE") from None

    def _check_private_parent(self):
        try:
            parent_stat = os.stat(str(self._database_path.parent))
        except Exception:
            raise WorkerError("WORKER_UNAVAILABLE") from None
        if (parent_stat.st_uid != os.geteuid()
                or stat.S_IMODE(parent_stat.st_mode) & 0o022):
            _raise("WORKER_UNAVAILABLE")

    def _open_lease(self):
        flags = os.O_CREAT | os.O_RDWR
        flags |= getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(str(self._lease_path), flags, 0o600)
        except Exception:
            raise WorkerError("WORKER_UNAVAILABLE") from None
        try:
            metadata = os.fstat(descriptor)
            if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                    or metadata.st_uid != os.geteuid()
                    or stat.S_IMODE(metadata.st_mode) & 0o077):
                _raise("WORKER_UNAVAILABLE")
            self._check_lease_identity(descriptor)
            return descriptor
        except Exception:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise WorkerError("WORKER_UNAVAILABLE") from None
        except BaseException:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise

    @staticmethod
    def _take_lock(descriptor):
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError) as error:
            if isinstance(error, BlockingIOError) or getattr(error, "errno", None) in (11, 13):
                _raise("WORKER_BUSY")
            _raise("WORKER_UNAVAILABLE")

    def _acquire(self):
        if os.name != "posix" or fcntl is None or not callable(getattr(fcntl, "flock", None)):
            _raise("WORKER_UNAVAILABLE")
        self._check_private_parent()
        descriptor = self._open_lease()
        try:
            self._take_lock(descriptor)
            self._check_lease_identity(descriptor)
            return descriptor
        except BaseException:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise

    @staticmethod
    def _step_for(snapshot):
        if snapshot["status"] == "WAITING_USER":
            return snapshot["stepId"]
        index = len(snapshot["appliedSteps"])
        if index >= len(_STEPS):
            _raise("WORKER_UNAVAILABLE")
        return _STEPS[index]

    def _observe(self, handler, config):
        try:
            result = handler.observe(copy.deepcopy(config))
        except Exception:
            return "UNKNOWN"
        return result if type(result) is str and result in _OBSERVATIONS else "UNKNOWN"

    def _open_active(self, descriptor):
        self._check_identity(descriptor)
        self._check_existing_journal()
        self._check_identity(descriptor)
        store = JobStore(self._database_path)
        snapshot = store.active()
        if snapshot is not None:
            self._validate_active_snapshot(snapshot)
        if snapshot is not None and snapshot["status"] == "RUNNING":
            self._check_identity(descriptor)
            store.reconcile_interrupted()
            self._check_identity(descriptor)
            snapshot = store.active()
            if snapshot is not None:
                self._validate_active_snapshot(snapshot)
        return store, snapshot

    def _run_waiting(self, store, snapshot, descriptor):
        step = self._step_for(snapshot)
        config = snapshot["desiredConfigSummary"]
        self._check_identity(descriptor)
        observation = self._observe(self._handlers[step], config)
        self._check_identity(descriptor)
        if observation == "APPLIED":
            return store.confirm_step(snapshot["jobId"], snapshot["revision"], step)
        if observation == "NOT_APPLIED":
            return store.fail_step(snapshot["jobId"], snapshot["revision"], step,
                                   "OBSERVATION_FAILED")
        return snapshot

    def _run_queued(self, store, snapshot, descriptor):
        step = self._step_for(snapshot)
        config = snapshot["desiredConfigSummary"]
        self._check_identity(descriptor)
        running = store.begin_step(snapshot["jobId"], snapshot["revision"], step)
        self._check_identity(descriptor)
        try:
            self._handlers[step].apply(copy.deepcopy(config))
        except Exception:
            pass
        self._check_identity(descriptor)
        observation = self._observe(self._handlers[step], config)
        self._check_identity(descriptor)
        if observation == "APPLIED":
            return store.confirm_step(running["jobId"], running["revision"], step)
        if observation == "NOT_APPLIED":
            return store.fail_step(running["jobId"], running["revision"], step,
                                   "STEP_FAILED")
        return store.wait_for_inspection(running["jobId"], running["revision"], step)

    def run_once(self):
        descriptor = self._acquire()
        try:
            store, snapshot = self._open_active(descriptor)
            if snapshot is None:
                return None
            if snapshot["status"] == "WAITING_USER":
                return self._run_waiting(store, snapshot, descriptor)
            return self._run_queued(store, snapshot, descriptor)
        except JobError as error:
            raise error from None
        finally:
            try:
                os.close(descriptor)
            except OSError:
                pass

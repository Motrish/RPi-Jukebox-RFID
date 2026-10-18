"""Durable, transport-free journal for bounded setup jobs."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import re
import sqlite3
from typing import Dict, Iterator, List, Optional
import uuid


_CONTRACT_VERSION = "websetup.job.v1"
_SCHEMA_VERSION = "1"
_COMMAND_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z", re.ASCII)
_JOB_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z", re.ASCII)
_STEPS = ("CHECK_SYSTEM", "CONFIGURE_AUDIO", "VERIFY_INSTALLATION")
_ACTIVE = ("QUEUED", "RUNNING", "WAITING_USER")
_ERROR_CODES = ("STEP_FAILED", "OBSERVATION_FAILED")
_JOB_ERROR_CODES = (
    "INVALID_REQUEST", "JOB_NOT_FOUND", "REVISION_CONFLICT", "INVALID_TRANSITION",
    "COMMAND_ID_REUSED", "JOB_CONFLICT", "STORE_UNAVAILABLE",
)
_MAX_REVISION = (1 << 63) - 1
_SNAPSHOT_FIELDS = (
    "contractVersion", "jobId", "commandId", "status", "stepId",
    "desiredConfigSummary", "appliedSteps", "revision", "createdAt",
    "updatedAt", "nextAction", "error",
)
_JOB_COLUMNS = (
    "job_id", "command_id", "config_json", "status", "step_id",
    "applied_steps_json", "revision", "created_at", "updated_at",
    "next_action_json", "error_json",
)
_SCHEMA_OBJECTS = {
    ("table", "journal_meta"): (
        "CREATE TABLE journal_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    ),
    ("table", "jobs"): (
        "CREATE TABLE jobs (job_id TEXT PRIMARY KEY, command_id TEXT NOT NULL UNIQUE, "
        "config_json TEXT NOT NULL, status TEXT NOT NULL, step_id TEXT, "
        "applied_steps_json TEXT NOT NULL, revision INTEGER NOT NULL, "
        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
        "next_action_json TEXT, error_json TEXT)"
    ),
    ("index", "one_active_job"): (
        "CREATE UNIQUE INDEX one_active_job ON jobs ((1)) "
        "WHERE status IN ('QUEUED', 'RUNNING', 'WAITING_USER')"
    ),
}


class JobError(Exception):
    """Public journal error carrying only a stable, redacted error code."""

    def __init__(self, code: str):
        self.code = code if code in _JOB_ERROR_CODES else "STORE_UNAVAILABLE"
        super().__init__(self.code)

    def __str__(self) -> str:
        return self.code

    def __repr__(self) -> str:
        return "JobError({!r})".format(self.code)


def _raise(code: str) -> None:
    raise JobError(code)


def _validate_command_id(command_id: object) -> str:
    if not isinstance(command_id, str) or _COMMAND_ID.fullmatch(command_id) is None:
        _raise("INVALID_REQUEST")
    return command_id


def _validate_job_id(job_id: object) -> str:
    if not isinstance(job_id, str) or _JOB_ID.fullmatch(job_id) is None:
        _raise("INVALID_REQUEST")
    return job_id


def _validate_config(config: object) -> Dict[str, object]:
    fields = {"audioOutput", "rfidEnabled", "pisugarEnabled"}
    if type(config) is not dict or set(config) != fields:
        _raise("INVALID_REQUEST")
    if (type(config["audioOutput"]) is not str
            or config["audioOutput"] not in ("SYSTEM_DEFAULT", "HIFIBERRY_MINIAMP")):
        _raise("INVALID_REQUEST")
    if type(config["rfidEnabled"]) is not bool or type(config["pisugarEnabled"]) is not bool:
        _raise("INVALID_REQUEST")
    return {
        "audioOutput": config["audioOutput"],
        "rfidEnabled": config["rfidEnabled"],
        "pisugarEnabled": config["pisugarEnabled"],
    }


def _validate_revision(revision: object) -> int:
    if type(revision) is not int or revision < 0:
        _raise("INVALID_REQUEST")
    return revision


def _validate_step_type(step_id: object) -> str:
    if type(step_id) is not str or not step_id or len(step_id) > 64:
        _raise("INVALID_REQUEST")
    if step_id not in _STEPS:
        _raise("INVALID_REQUEST")
    return step_id


def _validate_error_code(error_code: object) -> str:
    if type(error_code) is not str or error_code not in _ERROR_CODES:
        _raise("INVALID_REQUEST")
    return error_code


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class JobStore:
    """SQLite-backed journal; every method owns and closes its connection."""

    def __init__(self, path):
        try:
            self._path = str(path)
            if not self._path:
                _raise("STORE_UNAVAILABLE")
            self._initialize()
        except JobError:
            raise
        except Exception:
            _raise("STORE_UNAVAILABLE")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=5.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _transaction(self, write: bool = False) -> Iterator[sqlite3.Connection]:
        connection = None
        try:
            connection = self._connect()
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            connection.commit()
        except JobError:
            if connection is not None:
                try:
                    connection.rollback()
                except sqlite3.Error:
                    pass
            raise
        except Exception:
            if connection is not None:
                try:
                    connection.rollback()
                except sqlite3.Error:
                    pass
            _raise("STORE_UNAVAILABLE")
        finally:
            if connection is not None:
                try:
                    connection.close()
                except sqlite3.Error:
                    pass

    def _initialize(self) -> None:
        with self._transaction(write=True) as connection:
            tables = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")}
            if not tables:
                connection.execute(_SCHEMA_OBJECTS[("table", "journal_meta")])
                connection.execute(_SCHEMA_OBJECTS[("table", "jobs")])
                connection.execute(_SCHEMA_OBJECTS[("index", "one_active_job")])
                connection.execute(
                    "INSERT INTO journal_meta (key, value) VALUES ('schema_version', ?) ",
                    (_SCHEMA_VERSION,),
                )
                return
            if tables != {"journal_meta", "jobs"}:
                _raise("STORE_UNAVAILABLE")
            schema = {
                (row[0], row[1]): row[2]
                for row in connection.execute(
                    "SELECT type, name, sql FROM sqlite_master "
                    "WHERE name NOT LIKE 'sqlite_%' AND sql IS NOT NULL"
                )
            }
            if schema != _SCHEMA_OBJECTS:
                _raise("STORE_UNAVAILABLE")
            meta_columns = tuple(row[1] for row in connection.execute("PRAGMA table_info(journal_meta)"))
            job_columns = tuple(row[1] for row in connection.execute("PRAGMA table_info(jobs)"))
            if meta_columns != ("key", "value") or job_columns != _JOB_COLUMNS:
                _raise("STORE_UNAVAILABLE")
            meta = connection.execute(
                "SELECT value FROM journal_meta WHERE key = 'schema_version'"
            ).fetchone()
            index = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = 'one_active_job'"
            ).fetchone()
            if meta is None or meta[0] != _SCHEMA_VERSION or index is None:
                _raise("STORE_UNAVAILABLE")

    @staticmethod
    def _snapshot(row: sqlite3.Row) -> Dict[str, object]:
        try:
            result = {
                "contractVersion": _CONTRACT_VERSION,
                "jobId": row["job_id"],
                "commandId": row["command_id"],
                "status": row["status"],
                "stepId": row["step_id"],
                "desiredConfigSummary": json.loads(row["config_json"]),
                "appliedSteps": json.loads(row["applied_steps_json"]),
                "revision": row["revision"],
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
                "nextAction": json.loads(row["next_action_json"])
                if row["next_action_json"] is not None else None,
                "error": json.loads(row["error_json"]) if row["error_json"] is not None else None,
            }
            if tuple(result) != _SNAPSHOT_FIELDS:
                _raise("STORE_UNAVAILABLE")
            return json.loads(_json(result))
        except JobError:
            raise
        except Exception:
            _raise("STORE_UNAVAILABLE")

    @staticmethod
    def _fetch(connection: sqlite3.Connection, job_id: str) -> sqlite3.Row:
        row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            _raise("JOB_NOT_FOUND")
        return row

    @staticmethod
    def _check_revision(row: sqlite3.Row, expected_revision: int) -> None:
        if row["revision"] != expected_revision:
            _raise("REVISION_CONFLICT")

    def submit(self, command_id, desired_config) -> Dict[str, object]:
        command_id = _validate_command_id(command_id)
        config = _validate_config(desired_config)
        config_json = _json(config)
        with self._transaction(write=True) as connection:
            existing = connection.execute(
                "SELECT * FROM jobs WHERE command_id = ?", (command_id,)
            ).fetchone()
            if existing is not None:
                if existing["config_json"] != config_json:
                    _raise("COMMAND_ID_REUSED")
                return self._snapshot(existing)
            active = connection.execute(
                "SELECT 1 FROM jobs WHERE status IN ('QUEUED', 'RUNNING', 'WAITING_USER') LIMIT 1"
            ).fetchone()
            if active is not None:
                _raise("JOB_CONFLICT")
            now = _timestamp()
            job_id = uuid.uuid4().hex
            connection.execute(
                "INSERT INTO jobs (job_id, command_id, config_json, status, step_id, "
                "applied_steps_json, revision, created_at, updated_at, next_action_json, error_json) "
                "VALUES (?, ?, ?, 'QUEUED', NULL, '[]', 0, ?, ?, NULL, NULL)",
                (job_id, command_id, config_json, now, now),
            )
            row = self._fetch(connection, job_id)
            return self._snapshot(row)

    def get(self, job_id) -> Dict[str, object]:
        job_id = _validate_job_id(job_id)
        with self._transaction() as connection:
            return self._snapshot(self._fetch(connection, job_id))

    def active(self) -> Optional[Dict[str, object]]:
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE status IN ('QUEUED', 'RUNNING', 'WAITING_USER') LIMIT 1"
            ).fetchone()
            return self._snapshot(row) if row is not None else None

    def _transition(self, job_id, expected_revision, step_id, operation, error_code=None):
        job_id = _validate_job_id(job_id)
        revision = _validate_revision(expected_revision)
        step_id = _validate_step_type(step_id)
        if operation == "fail":
            error_code = _validate_error_code(error_code)
        with self._transaction(write=True) as connection:
            row = self._fetch(connection, job_id)
            self._check_revision(row, revision)
            if row["revision"] >= _MAX_REVISION:
                _raise("STORE_UNAVAILABLE")
            status = row["status"]
            if operation == "begin":
                try:
                    applied = json.loads(row["applied_steps_json"])
                except Exception:
                    _raise("STORE_UNAVAILABLE")
                next_index = len(applied)
                if status != "QUEUED" or next_index >= len(_STEPS) or step_id != _STEPS[next_index]:
                    _raise("INVALID_TRANSITION")
                values = ("RUNNING", step_id, row["applied_steps_json"], None, None)
            elif operation == "confirm":
                if status not in ("RUNNING", "WAITING_USER") or row["step_id"] != step_id:
                    _raise("INVALID_TRANSITION")
                try:
                    applied = json.loads(row["applied_steps_json"])
                except Exception:
                    _raise("STORE_UNAVAILABLE")
                applied.append({"stepId": step_id, "diagnostic": "CONFIRMED"})
                final = len(applied) == len(_STEPS)
                values = (
                    "SUCCEEDED" if final else "QUEUED", None, _json(applied), None, None,
                )
            else:
                if status not in ("RUNNING", "WAITING_USER") or row["step_id"] != step_id:
                    _raise("INVALID_TRANSITION")
                values = ("FAILED", step_id, row["applied_steps_json"], None, _json({"code": error_code}))
            now = _timestamp()
            connection.execute(
                "UPDATE jobs SET status = ?, step_id = ?, applied_steps_json = ?, "
                "revision = revision + 1, updated_at = ?, next_action_json = ?, error_json = ? "
                "WHERE job_id = ?",
                (values[0], values[1], values[2], now, values[3], values[4], job_id),
            )
            return self._snapshot(self._fetch(connection, job_id))

    def begin_step(self, job_id, expected_revision, step_id) -> Dict[str, object]:
        return self._transition(job_id, expected_revision, step_id, "begin")

    def confirm_step(self, job_id, expected_revision, step_id) -> Dict[str, object]:
        return self._transition(job_id, expected_revision, step_id, "confirm")

    def fail_step(self, job_id, expected_revision, step_id, error_code) -> Dict[str, object]:
        return self._transition(job_id, expected_revision, step_id, "fail", error_code)

    def reconcile_interrupted(self) -> List[Dict[str, object]]:
        changed = []
        with self._transaction(write=True) as connection:
            rows = connection.execute(
                "SELECT * FROM jobs WHERE status = 'RUNNING' ORDER BY created_at, job_id"
            ).fetchall()
            if any(row["revision"] >= _MAX_REVISION for row in rows):
                _raise("STORE_UNAVAILABLE")
            for row in rows:
                connection.execute(
                    "UPDATE jobs SET status = 'WAITING_USER', next_action_json = ?, "
                    "revision = revision + 1, updated_at = ? WHERE job_id = ? AND status = 'RUNNING'",
                    (_json({"kind": "INSPECT_SYSTEM"}), _timestamp(), row["job_id"]),
                )
                changed.append(self._snapshot(self._fetch(connection, row["job_id"])))
        return changed

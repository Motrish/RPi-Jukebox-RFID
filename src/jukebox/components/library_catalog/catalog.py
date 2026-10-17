"""Small SQLite catalog for explicitly registered files under one root."""

import errno
import os
import sqlite3
import stat
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import NamedTuple
from urllib.parse import quote

from jukebox.contracts import ContractValidationError, validate_identifier


_SCHEMA_VERSION = 1
_BUSY_TIMEOUT_SECONDS = 0.250
_ERROR_MESSAGES = {
    "UNSUPPORTED_PLATFORM": "Linux filesystem support is unavailable.",
    "ROOT_CHANGED": "The library root no longer matches the catalog.",
    "MEDIA_UNAVAILABLE": "The requested media file is unavailable.",
    "FILESYSTEM_UNAVAILABLE": "The library filesystem could not be checked.",
    "STORE_BUSY": "The library catalog is busy; retry the operation.",
    "STORE_UNAVAILABLE": "The library catalog is unavailable.",
}


class _SafeError(NamedTuple):
    code: str
    message: str


class CatalogError(Exception):
    """Catalog failure with a stable message that contains no paths."""

    def __init__(self, code: str) -> None:
        message = _ERROR_MESSAGES.get(
            code, _ERROR_MESSAGES["STORE_UNAVAILABLE"]
        )
        self.safe = _SafeError(code, message)
        super().__init__(message)


class LibraryCatalog:
    """Persist file identities and resolve them within one pinned root."""

    def __init__(
        self, database_path: os.PathLike, library_root: os.PathLike
    ) -> None:
        self._closed = False
        self._check_platform()
        self._library_root = self._validate_root_path(library_root)
        self._database_path = self._validate_database_path(database_path)
        self._check_database_outside_root()
        root_fd = self._open_root()
        try:
            self._initialize_store(root_fd)
        finally:
            self._close_descriptor(root_fd)

    @staticmethod
    def _check_platform() -> None:
        required = ("O_PATH", "O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC")
        supported = (
            sys.platform.startswith("linux")
            and hasattr(os, "supports_dir_fd")
            and os.open in os.supports_dir_fd
            and all(hasattr(os, name) for name in required)
        )
        if not supported:
            raise CatalogError("UNSUPPORTED_PLATFORM")

    @staticmethod
    def _validate_root_path(value: os.PathLike) -> str:
        try:
            path = os.fspath(value)
        except TypeError:
            raise ContractValidationError(
                "library_root", "invalid_path"
            )
        if not isinstance(path, str) or not path.startswith("/"):
            raise ContractValidationError("library_root", "invalid_path")
        components = path[1:].split("/") if path != "/" else []
        if any(part in ("", ".", "..") for part in components):
            raise ContractValidationError("library_root", "invalid_path")
        try:
            path.encode("utf-8")
        except UnicodeEncodeError:
            raise ContractValidationError("library_root", "invalid_path")
        return path

    @staticmethod
    def _validate_database_path(value: os.PathLike) -> str:
        try:
            path = os.fspath(value)
        except TypeError:
            raise ContractValidationError(
                "database_path", "invalid_path"
            )
        if not isinstance(path, str) or not os.path.isabs(path):
            raise ContractValidationError("database_path", "invalid_path")
        if not Path(path).parent.is_dir():
            raise CatalogError("STORE_UNAVAILABLE")
        return path

    def _check_database_outside_root(self) -> None:
        real_database = os.path.realpath(self._database_path)
        try:
            common = os.path.commonpath((self._library_root, real_database))
        except ValueError:
            common = ""
        if common == self._library_root:
            raise CatalogError("STORE_UNAVAILABLE")

    def _open_root(self) -> int:
        flags = os.O_PATH | os.O_DIRECTORY | os.O_CLOEXEC
        try:
            descriptor = os.open("/", flags)
        except OSError:
            raise CatalogError("FILESYSTEM_UNAVAILABLE")
        try:
            for component in self._library_root[1:].split("/"):
                if not component:
                    continue
                child = os.open(
                    component,
                    flags | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
                previous = descriptor
                descriptor = child
                self._close_descriptor(previous)
            return descriptor
        except OSError as error:
            try:
                self._close_descriptor(descriptor)
            except OSError:
                pass
            self._raise_root_error(error)

    @staticmethod
    def _raise_root_error(error: OSError) -> None:
        if error.errno in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP):
            raise CatalogError("ROOT_CHANGED")
        raise CatalogError("FILESYSTEM_UNAVAILABLE")

    @staticmethod
    def _fingerprint_from_stat(info: os.stat_result) -> tuple:
        return (
            info.st_dev,
            info.st_ino,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
        )

    @staticmethod
    def _stored_fingerprint(row: sqlite3.Row) -> tuple:
        return tuple(
            int(row[name])
            for name in ("device", "inode", "size", "mtime_ns", "ctime_ns")
        )

    @staticmethod
    def _store_fingerprint(fingerprint: tuple) -> tuple:
        return tuple(str(value) for value in fingerprint)

    @staticmethod
    def _root_fingerprint(descriptor: int) -> tuple:
        try:
            info = os.fstat(descriptor)
        except OSError:
            raise CatalogError("FILESYSTEM_UNAVAILABLE") from None
        return info.st_dev, info.st_ino

    @staticmethod
    def _close_descriptor(descriptor: int) -> None:
        try:
            os.close(descriptor)
        except OSError:
            pass

    def _initialize_store(self, root_fd: int) -> None:
        connection = None
        try:
            connection = self._connect(create=True)
            connection.execute("BEGIN IMMEDIATE")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            tables = self._table_names(connection)
            if version == 0 and not tables:
                self._create_schema(connection, root_fd)
            else:
                self._verify_schema(connection)
                self._verify_root_binding(connection, root_fd)
            connection.commit()
        except sqlite3.Error as error:
            self._rollback(connection)
            raise self._sqlite_error(error)
        except Exception:
            self._rollback(connection)
            raise
        finally:
            self._close_connection(connection)

    @staticmethod
    def _table_names(connection: sqlite3.Connection) -> set:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        return {row[0] for row in rows}

    def _create_schema(
        self, connection: sqlite3.Connection, root_fd: int
    ) -> None:
        connection.execute(
            "CREATE TABLE catalog_meta ("
            "singleton INTEGER PRIMARY KEY CHECK (singleton = 1), "
            "root_path TEXT NOT NULL, root_device TEXT NOT NULL, "
            "root_inode TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE media ("
            "library_id TEXT PRIMARY KEY, relative_path TEXT NOT NULL, "
            "display_name TEXT NOT NULL, device TEXT NOT NULL, "
            "inode TEXT NOT NULL, "
            "size TEXT NOT NULL, mtime_ns TEXT NOT NULL, "
            "ctime_ns TEXT NOT NULL, "
            "tombstoned INTEGER NOT NULL CHECK (tombstoned IN (0, 1)))"
        )
        connection.execute(
            "CREATE UNIQUE INDEX media_active_path ON media(relative_path) "
            "WHERE tombstoned = 0"
        )
        root_device, root_inode = self._root_fingerprint(root_fd)
        connection.execute(
            "INSERT INTO catalog_meta "
            "(singleton, root_path, root_device, root_inode) "
            "VALUES (1, ?, ?, ?)",
            (self._library_root, str(root_device), str(root_inode)),
        )
        connection.execute("PRAGMA user_version = 1")

    def _verify_schema(self, connection: sqlite3.Connection) -> None:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version != _SCHEMA_VERSION:
            raise CatalogError("STORE_UNAVAILABLE")
        if self._table_names(connection) != {"catalog_meta", "media"}:
            raise CatalogError("STORE_UNAVAILABLE")
        expected_columns = {
            "catalog_meta": (
                "singleton", "root_path", "root_device", "root_inode"
            ),
            "media": (
                "library_id", "relative_path", "display_name", "device",
                "inode", "size", "mtime_ns", "ctime_ns", "tombstoned",
            ),
        }
        for table, expected in expected_columns.items():
            actual = connection.execute(
                "PRAGMA table_info({})".format(table)
            ).fetchall()
            if tuple(row["name"] for row in actual) != expected:
                raise CatalogError("STORE_UNAVAILABLE")
        indexes = connection.execute("PRAGMA index_list(media)").fetchall()
        active_index = any(
            row["name"] == "media_active_path"
            and row["unique"] == 1
            and row["partial"] == 1
            for row in indexes
        )
        if not active_index:
            raise CatalogError("STORE_UNAVAILABLE")

    def _verify_root_binding(
        self, connection: sqlite3.Connection, root_fd: int
    ) -> None:
        row = connection.execute(
            "SELECT root_path, root_device, root_inode "
            "FROM catalog_meta WHERE singleton = 1"
        ).fetchone()
        if row is None:
            raise CatalogError("STORE_UNAVAILABLE")
        root_device, root_inode = self._root_fingerprint(root_fd)
        binding = (row[0], int(row[1]), int(row[2]))
        if binding != (self._library_root, root_device, root_inode):
            raise CatalogError("ROOT_CHANGED")

    def _connect(self, create: bool = False) -> sqlite3.Connection:
        if create:
            connection = sqlite3.connect(
                self._database_path,
                timeout=_BUSY_TIMEOUT_SECONDS,
                isolation_level=None,
            )
        else:
            uri_path = quote(self._database_path, safe="/")
            uri = "file:{}?mode=rw".format(uri_path)
            connection = sqlite3.connect(
                uri,
                uri=True,
                timeout=_BUSY_TIMEOUT_SECONDS,
                isolation_level=None,
            )
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _operation(self):
        self._ensure_open()
        root_fd = self._open_root()
        connection = None
        try:
            connection = self._connect()
            connection.execute("BEGIN IMMEDIATE")
            self._verify_schema(connection)
            self._verify_root_binding(connection, root_fd)
            yield root_fd, connection
            connection.commit()
        except sqlite3.Error as error:
            self._rollback(connection)
            raise self._sqlite_error(error)
        except Exception:
            self._rollback(connection)
            raise
        finally:
            self._close_connection(connection)
            self._close_descriptor(root_fd)

    def _ensure_open(self) -> None:
        if self._closed:
            raise CatalogError("STORE_UNAVAILABLE")

    @staticmethod
    def _rollback(connection: sqlite3.Connection) -> None:
        if connection is not None and connection.in_transaction:
            try:
                connection.rollback()
            except sqlite3.Error:
                pass

    @staticmethod
    def _close_connection(connection: sqlite3.Connection) -> None:
        if connection is not None:
            try:
                connection.close()
            except sqlite3.Error:
                pass

    @staticmethod
    def _sqlite_error(error: sqlite3.Error) -> CatalogError:
        if isinstance(error, sqlite3.OperationalError):
            if "locked" in str(error).lower() or "busy" in str(error).lower():
                return CatalogError("STORE_BUSY")
        return CatalogError("STORE_UNAVAILABLE")

    @staticmethod
    def _validate_relative_path(relative_path: str) -> str:
        if not isinstance(relative_path, str) or not relative_path:
            raise ContractValidationError("relative_path", "invalid_path")
        try:
            encoded = relative_path.encode("utf-8")
        except UnicodeEncodeError:
            raise ContractValidationError("relative_path", "invalid_path")
        if len(encoded) > 4095 or relative_path.startswith("/"):
            raise ContractValidationError("relative_path", "invalid_path")
        forbidden = relative_path.endswith("/") or "\\" in relative_path
        forbidden = forbidden or ":" in relative_path
        if forbidden:
            raise ContractValidationError("relative_path", "invalid_path")
        controls = (
            ord(char) < 32 or ord(char) == 127 for char in relative_path
        )
        if any(controls):
            raise ContractValidationError("relative_path", "invalid_path")
        parts = relative_path.split("/")
        if any(part in ("", ".", "..") for part in parts):
            raise ContractValidationError("relative_path", "invalid_path")
        if any(len(part.encode("utf-8")) > 255 for part in parts):
            raise ContractValidationError("relative_path", "invalid_path")
        return relative_path

    def _probe_path(self, root_fd: int, relative_path: str):
        components = relative_path.split("/")
        parent_fd = root_fd
        owned_fd = None
        directory_flags = (
            os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        )
        try:
            for component in components[:-1]:
                child_fd = os.open(
                    component,
                    directory_flags,
                    dir_fd=parent_fd,
                )
                previous_fd = owned_fd
                owned_fd = child_fd
                parent_fd = child_fd
                if previous_fd is not None:
                    self._close_descriptor(previous_fd)
            file_fd = os.open(
                components[-1],
                os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=parent_fd,
            )
            try:
                info = os.fstat(file_fd)
            finally:
                self._close_descriptor(file_fd)
            if not stat.S_ISREG(info.st_mode):
                return None
            return self._fingerprint_from_stat(info)
        except OSError as error:
            if error.errno in (errno.ENOENT, errno.ENOTDIR, errno.ELOOP):
                return None
            raise
        finally:
            if owned_fd is not None:
                self._close_descriptor(owned_fd)

    def _availability(
        self,
        row: sqlite3.Row,
        root_fd: int,
        connection: sqlite3.Connection,
        strict: bool = False,
    ) -> str:
        if row["tombstoned"]:
            return "MISSING"
        try:
            current = self._probe_path(root_fd, row["relative_path"])
        except OSError:
            if strict:
                raise CatalogError("FILESYSTEM_UNAVAILABLE")
            return "UNKNOWN"
        if current is None or current != self._stored_fingerprint(row):
            connection.execute(
                "UPDATE media SET tombstoned = 1 WHERE library_id = ?",
                (row["library_id"],),
            )
            return "MISSING"
        return "AVAILABLE"

    @staticmethod
    def _public_record(row: sqlite3.Row, availability: str) -> dict:
        return {
            "libraryId": row["library_id"],
            "displayName": row["display_name"],
            "availability": availability,
        }

    def register_file(self, relative_path: str) -> dict:
        self._ensure_open()
        relative_path = self._validate_relative_path(relative_path)
        with self._operation() as (root_fd, connection):
            try:
                fingerprint = self._probe_path(root_fd, relative_path)
            except OSError:
                raise CatalogError("FILESYSTEM_UNAVAILABLE")
            if fingerprint is None:
                raise CatalogError("MEDIA_UNAVAILABLE")
            active = connection.execute(
                "SELECT * FROM media WHERE relative_path = ? "
                "AND tombstoned = 0",
                (relative_path,),
            ).fetchone()
            if active is not None:
                if fingerprint == self._stored_fingerprint(active):
                    return self._public_record(active, "AVAILABLE")
                connection.execute(
                    "UPDATE media SET tombstoned = 1 WHERE library_id = ?",
                    (active["library_id"],),
                )
            library_id = "lib_" + uuid.uuid4().hex
            values = self._store_fingerprint(fingerprint)
            try:
                connection.execute(
                    "INSERT INTO media "
                    "(library_id, relative_path, display_name, device, inode, "
                    "size, mtime_ns, ctime_ns, tombstoned) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)",
                    (
                        library_id,
                        relative_path,
                        relative_path.rsplit("/", 1)[-1],
                        *values,
                    ),
                )
            except sqlite3.IntegrityError:
                raise CatalogError("STORE_UNAVAILABLE")
            row = connection.execute(
                "SELECT * FROM media WHERE library_id = ?", (library_id,)
            ).fetchone()
            return self._public_record(row, "AVAILABLE")

    def get_media(self, library_id: str):
        self._ensure_open()
        library_id = validate_identifier(library_id, "library_id")
        with self._operation() as (root_fd, connection):
            row = connection.execute(
                "SELECT * FROM media WHERE library_id = ?", (library_id,)
            ).fetchone()
            if row is None:
                return None
            availability = self._availability(row, root_fd, connection)
            return self._public_record(row, availability)

    def list_media(self, limit: int = 50, cursor: str = None) -> dict:
        self._ensure_open()
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ContractValidationError("limit", "invalid_limit")
        if cursor is not None:
            cursor = validate_identifier(cursor, "cursor")
        with self._operation() as (root_fd, connection):
            if cursor is None:
                rows = connection.execute(
                    "SELECT * FROM media ORDER BY library_id COLLATE BINARY "
                    "LIMIT ?",
                    (limit + 1,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM media WHERE library_id > ? "
                    "ORDER BY library_id COLLATE BINARY LIMIT ?",
                    (cursor, limit + 1),
                ).fetchall()
            has_more = len(rows) > limit
            selected = rows[:limit]
            items = [
                self._public_record(
                    row,
                    self._availability(row, root_fd, connection),
                )
                for row in selected
            ]
            next_cursor = None
            if has_more and items:
                next_cursor = items[-1]["libraryId"]
            return {"items": items, "nextCursor": next_cursor}

    def resolve(self, library_id: str):
        self._ensure_open()
        library_id = validate_identifier(library_id, "library_id")
        with self._operation() as (root_fd, connection):
            row = connection.execute(
                "SELECT * FROM media WHERE library_id = ?", (library_id,)
            ).fetchone()
            if row is None:
                return None
            availability = self._availability(
                row, root_fd, connection, strict=True
            )
            if availability != "AVAILABLE":
                return None
            return {
                "libraryId": library_id,
                "mpdReference": row["relative_path"],
            }

    def close(self) -> None:
        self._closed = True

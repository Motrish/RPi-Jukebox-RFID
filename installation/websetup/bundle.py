"""Private, bounded intake of a verified R01a web bundle."""

from __future__ import annotations

from contextlib import contextmanager
import gzip
import os
from pathlib import Path
import re
import shutil
import stat
import tarfile
import tempfile
from typing import BinaryIO, Iterator, Optional

from tools.web_bundle import BundleError, MAX_ARCHIVE_BYTES, MAX_FILES, MAX_MANIFEST_BYTES
from tools.web_bundle import MAX_TOTAL_INPUT_BYTES as _PRODUCER_MAX_TOTAL_INPUT_BYTES
from tools.web_bundle import verify_bundle


MAX_TOTAL_INPUT_BYTES = _PRODUCER_MAX_TOTAL_INPUT_BYTES
MAX_TAR_STREAM_BYTES = 288 * 1024 * 1024
_READ_CHUNK_BYTES = 64 * 1024
_TAR_BLOCK_BYTES = 512
_MAX_PATH_BYTES = 4096
_MAX_PAX_BYTES = 16 * 1024
_MAX_PAX_HEADERS = MAX_FILES
_PAX_LENGTH = re.compile(rb"[1-9][0-9]*\Z")


class _TarReader:
    """Read gzip output in bounded chunks and account for every expanded byte."""

    def __init__(self, stream: BinaryIO) -> None:
        self.stream = stream
        self.count = 0

    def read(self, size: int) -> bytes:
        if size <= 0:
            return b""
        size = min(size, _READ_CHUNK_BYTES)
        remaining = MAX_TAR_STREAM_BYTES - self.count
        if remaining <= 0:
            extra = self.stream.read(1)
            if extra:
                raise BundleError("expanded archive exceeds the size limit")
            return b""
        data = self.stream.read(min(size, remaining))
        self.count += len(data)
        if self.count > MAX_TAR_STREAM_BYTES:
            raise BundleError("expanded archive exceeds the size limit")
        return data

    def exact(self, size: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < size:
            data = self.read(size - len(chunks))
            if not data:
                raise BundleError("archive is truncated")
            chunks.extend(data)
        return bytes(chunks)

    def discard_zeros(self, size: int) -> None:
        while size:
            data = self.exact(min(size, _READ_CHUNK_BYTES))
            if any(data):
                raise BundleError("archive contains invalid padding")
            size -= len(data)

    def payload_to(self, output: BinaryIO, size: int, aggregate: int) -> int:
        remaining = size
        while remaining:
            data = self.exact(min(remaining, _READ_CHUNK_BYTES))
            output.write(data)
            remaining -= len(data)
            aggregate += len(data)
            if aggregate > MAX_TOTAL_INPUT_BYTES:
                raise BundleError("bundle contents exceed the size limit")
        return aggregate


def _safe_path(value: str) -> tuple[str, ...]:
    try:
        encoded = value.encode("utf-8", "strict")
    except (UnicodeError, AttributeError):
        raise BundleError("archive contains an invalid path") from None
    if not encoded or len(encoded) > _MAX_PATH_BYTES:
        raise BundleError("archive contains an invalid path")
    if value.startswith("/") or "\\" in value or ":" in value:
        raise BundleError("archive contains an unsafe path")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise BundleError("archive contains an unsafe path")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise BundleError("archive contains an unsafe path")
    return tuple(parts)


def _parse_pax_path(data: bytes) -> str:
    position = 0
    path: Optional[str] = None
    while position < len(data):
        separator = data.find(b" ", position)
        if separator < 0:
            raise BundleError("archive contains malformed PAX metadata")
        length_text = data[position:separator]
        if not _PAX_LENGTH.fullmatch(length_text):
            raise BundleError("archive contains malformed PAX metadata")
        length = int(length_text)
        end = position + length
        if end > len(data) or end <= separator + 1 or data[end - 1:end] != b"\n":
            raise BundleError("archive contains malformed PAX metadata")
        record = data[separator + 1:end - 1]
        equals = record.find(b"=")
        if equals <= 0:
            raise BundleError("archive contains malformed PAX metadata")
        try:
            key = record[:equals].decode("ascii", "strict")
            value = record[equals + 1:].decode("utf-8", "strict")
        except UnicodeError:
            raise BundleError("archive contains malformed PAX metadata") from None
        if key != "path" or path is not None:
            raise BundleError("archive contains unsupported PAX metadata")
        path = value
        position = end
    if path is None:
        raise BundleError("archive contains empty PAX metadata")
    return path


def _copy_contents(input_stream: BinaryIO, destination: Path, expected_size: int,
                   limit: int) -> None:
    output_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    output_flags |= getattr(os, "O_BINARY", 0)
    output_fd = os.open(str(destination), output_flags, 0o600)
    copied = 0
    try:
        with os.fdopen(output_fd, "wb") as output_stream:
            while True:
                chunk = input_stream.read(_READ_CHUNK_BYTES)
                if not chunk:
                    break
                copied += len(chunk)
                if copied > limit:
                    raise BundleError("bundle input exceeds the size limit")
                output_stream.write(chunk)
        if copied != expected_size:
            raise BundleError("bundle input changed during intake")
    except BaseException:
        try:
            os.close(output_fd)
        except OSError:
            pass
        raise


def _copy_opened_input(source_path: Path, destination: Path, limit: int,
                       before: os.stat_result) -> None:
    try:
        flags = os.O_RDONLY
        flags |= getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NONBLOCK", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(str(source_path), flags)
        try:
            opened = os.fstat(descriptor)
            if (not stat.S_ISREG(opened.st_mode) or opened.st_dev != before.st_dev
                    or opened.st_ino != before.st_ino or opened.st_size > limit):
                raise BundleError("bundle input changed during intake")
            with os.fdopen(descriptor, "rb", closefd=False) as input_stream:
                _copy_contents(input_stream, destination, opened.st_size, limit)
        finally:
            os.close(descriptor)
    except BundleError:
        raise
    except (OSError, TypeError, ValueError):
        raise BundleError("bundle input could not be read safely") from None


def _copy_input(source: os.PathLike[str] | str, destination: Path, limit: int) -> None:
    try:
        source_path = Path(source)
        before = source_path.lstat()
    except (OSError, TypeError, ValueError):
        raise BundleError("bundle input could not be read safely") from None
    if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
        raise BundleError("bundle input is not a bounded regular file")
    _copy_opened_input(source_path, destination, limit, before)


def _is_case_insensitive(directory: Path) -> bool:
    name = ".r01b-case-probe"
    lower = directory / name.lower()
    upper = directory / name.upper()
    try:
        descriptor = os.open(str(lower), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        return upper.exists()
    except OSError:
        raise BundleError("private staging directory is unavailable") from None
    finally:
        try:
            lower.unlink()
        except FileNotFoundError:
            pass


def _make_output_path(root: Path, parts: tuple[str, ...], directories: set[str],
                      files: set[str], folded: set[str], insensitive: bool) -> Path:
    normalized = "/".join(parts)
    key = normalized.casefold() if insensitive else normalized
    if key in files or key in directories or (insensitive and key in folded):
        raise BundleError("archive contains colliding paths")
    for index in range(1, len(parts)):
        parent_name = "/".join(parts[:index])
        parent_key = parent_name.casefold() if insensitive else parent_name
        if parent_key in files:
            raise BundleError("archive contains colliding paths")
        directories.add(parent_key)
    if any(name.startswith(normalized + "/") for name in files):
        raise BundleError("archive contains colliding paths")
    files.add(key)
    if insensitive:
        folded.add(key)
    target = root.joinpath(*parts)
    current = root
    for part in parts[:-1]:
        current = current / part
        try:
            current.mkdir(mode=0o700)
        except FileExistsError:
            if not current.is_dir() or current.is_symlink():
                raise BundleError("archive contains colliding paths") from None
    return target


def _read_tar_end(reader: _TarReader, has_pending_path: bool) -> None:
    if has_pending_path:
        raise BundleError("archive has an incomplete PAX entry")
    if reader.exact(_TAR_BLOCK_BYTES) != b"\0" * _TAR_BLOCK_BYTES:
        raise BundleError("archive has an invalid end marker")
    while True:
        tail = reader.read(_READ_CHUNK_BYTES)
        if not tail:
            return
        if any(tail):
            raise BundleError("archive has data after its end marker")


def _read_tar_info(block: bytes) -> tarfile.TarInfo:
    try:
        return tarfile.TarInfo.frombuf(block, "utf-8", "strict")
    except (tarfile.TarError, ValueError, UnicodeError, IndexError):
        raise BundleError("archive contains an invalid tar header") from None


def _read_pax_path(reader: _TarReader, info: tarfile.TarInfo) -> str:
    if info.size < 1 or info.size > _MAX_PAX_BYTES:
        raise BundleError("archive PAX metadata exceeds the size limit")
    data = reader.exact(info.size)
    reader.discard_zeros((-info.size) % _TAR_BLOCK_BYTES)
    return _parse_pax_path(data)


def _tar_members(reader: _TarReader) -> Iterator[tuple[tarfile.TarInfo, str]]:
    pending_path: Optional[str] = None
    pax_count = 0
    while True:
        block = reader.exact(_TAR_BLOCK_BYTES)
        if block == b"\0" * _TAR_BLOCK_BYTES:
            _read_tar_end(reader, pending_path is not None)
            return
        info = _read_tar_info(block)
        if info.type == tarfile.XHDTYPE:
            pax_count += 1
            if pending_path is not None or pax_count > _MAX_PAX_HEADERS:
                raise BundleError("archive contains too many PAX headers")
            pending_path = _read_pax_path(reader, info)
            continue
        if info.type != tarfile.REGTYPE:
            raise BundleError("archive contains an unsupported member type")
        name = pending_path if pending_path is not None else info.name
        pending_path = None
        yield info, name


def _extract(archive_path: Path, webroot: Path, expected_count: int) -> None:
    count = 0
    aggregate = 0
    files: set[str] = set()
    directories: set[str] = set()
    insensitive = _is_case_insensitive(webroot)
    try:
        with archive_path.open("rb") as raw, gzip.GzipFile(fileobj=raw, mode="rb") as compressed:
            reader = _TarReader(compressed)
            for info, name in _tar_members(reader):
                parts = _safe_path(name)
                if info.size < 0 or info.size > MAX_TOTAL_INPUT_BYTES - aggregate:
                    raise BundleError("bundle contents exceed the size limit")
                count += 1
                if count > MAX_FILES:
                    raise BundleError("bundle contains too many files")
                target = _make_output_path(webroot, parts, directories, files, set(), insensitive)
                descriptor = os.open(
                    str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL
                    | getattr(os, "O_BINARY", 0), 0o644,
                )
                try:
                    with os.fdopen(descriptor, "wb") as output:
                        aggregate = reader.payload_to(output, info.size, aggregate)
                except BaseException:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass
                    raise
                reader.discard_zeros((-info.size) % _TAR_BLOCK_BYTES)
            if count != expected_count or "index.html" not in files:
                raise BundleError("archive file count or root index is invalid")
    except BundleError:
        raise
    except (OSError, EOFError, gzip.BadGzipFile, tarfile.TarError, ValueError, OverflowError):
        raise BundleError("archive could not be safely unpacked") from None


@contextmanager
def staged_bundle(archive_path: os.PathLike[str] | str,
                  manifest_path: os.PathLike[str] | str,
                  expected_repository: str,
                  expected_commit: str,
                  staging_parent: os.PathLike[str] | str) -> Iterator[Path]:
    """Copy, verify, and privately extract an already-downloaded bundle."""
    private_root: Optional[Path] = None
    try:
        parent = Path(staging_parent)
        parent_stat = parent.lstat()
        if not stat.S_ISDIR(parent_stat.st_mode):
            raise BundleError("staging parent is not a real directory")
        parent = parent.resolve(strict=True)
        private_root = Path(tempfile.mkdtemp(prefix=".web-bundle-", dir=str(parent)))
        if os.name == "posix":
            os.chmod(private_root, 0o700)
        archive_copy = private_root / "archive.tar.gz"
        manifest_copy = private_root / "manifest.json"
        _copy_input(archive_path, archive_copy, MAX_ARCHIVE_BYTES)
        _copy_input(manifest_path, manifest_copy, MAX_MANIFEST_BYTES)
        manifest = verify_bundle(
            archive_copy, manifest_copy, expected_repository, expected_commit
        )
        file_count = manifest["fileCount"]
        webroot = private_root / "webroot"
        webroot.mkdir(mode=0o700)
        _extract(archive_copy, webroot, file_count)
        yield webroot
    except BundleError:
        raise
    except (OSError, TypeError, ValueError, KeyError, OverflowError):
        raise BundleError("bundle could not be staged safely") from None
    finally:
        if private_root is not None:
            shutil.rmtree(private_root, ignore_errors=True)

"""Create and verify deterministic, commit-bound web build bundles."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tarfile
import tempfile
import unicodedata
from typing import BinaryIO, Dict, List, Optional, Sequence, Tuple


MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_INPUT_BYTES = 256 * 1024 * 1024
MAX_FILES = 4096
MAX_MANIFEST_BYTES = 16 * 1024
HASH_CHUNK_BYTES = 1024 * 1024

ARCHIVE_NAME = "webapp-build.tar.gz"
MANIFEST_NAME = "manifest.json"
MANIFEST_FIELDS = frozenset(
    {
        "formatVersion",
        "kind",
        "repository",
        "backendCommit",
        "archiveName",
        "archiveSha256",
        "archiveSizeBytes",
        "fileCount",
    }
)
OWNER_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")
REPOSITORY_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,100}\Z")
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


class BundleError(Exception):
    """A safe, actionable bundle validation error without file contents."""


class _BoundedWriter:
    def __init__(self, stream: BinaryIO, limit: int) -> None:
        self._stream = stream
        self._limit = limit
        self.count = 0

    def write(self, data: bytes) -> int:
        if self.count + len(data) > self._limit:
            raise BundleError("compressed archive exceeds the size limit")
        written = self._stream.write(data)
        if written != len(data):
            raise BundleError("archive could not be written completely")
        self.count += written
        return written

    def flush(self) -> None:
        self._stream.flush()

    def tell(self) -> int:
        return self.count


class _BoundedReader:
    def __init__(self, stream: BinaryIO, expected_size: int) -> None:
        self._stream = stream
        self._expected_size = expected_size
        self.count = 0

    def read(self, size: int = -1) -> bytes:
        remaining = self._expected_size - self.count
        if remaining <= 0:
            return b""
        if size < 0 or size > remaining:
            size = remaining
        data = self._stream.read(size)
        if not data:
            raise BundleError("build file changed while packaging")
        self.count += len(data)
        if self.count > self._expected_size:
            raise BundleError("build file changed while packaging")
        return data


def _validate_repository(value: object) -> str:
    if not isinstance(value, str) or value.count("/") != 1:
        raise BundleError("repository must be a GitHub owner/repository name")
    owner, repository = value.split("/", 1)
    if (
        not OWNER_PATTERN.fullmatch(owner)
        or not REPOSITORY_PATTERN.fullmatch(repository)
        or repository in {".", ".."}
    ):
        raise BundleError("repository must be a GitHub owner/repository name")
    return value


def _validate_commit(value: object) -> str:
    if not isinstance(value, str) or not COMMIT_PATTERN.fullmatch(value):
        raise BundleError("commit must be 40 lowercase hexadecimal characters")
    return value


def _validate_relative_component(name: str) -> None:
    if (
        not name
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or any(unicodedata.category(char) == "Cc" for char in name)
    ):
        raise BundleError("build contains an invalid relative filename")
    try:
        name.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise BundleError("build contains a filename that is not valid UTF-8") from exc


def _inspect_entry(directory: Path, prefix: str, entry: os.DirEntry) -> Tuple[str, Path, Optional[int]]:
    _validate_relative_component(entry.name)
    relative = f"{prefix}/{entry.name}" if prefix else entry.name
    path = directory / entry.name
    try:
        if entry.is_symlink():
            raise BundleError("build contains a symbolic link")
        if entry.is_dir(follow_symlinks=False):
            return relative, path, None
        entry_stat = entry.stat(follow_symlinks=False)
    except OSError as exc:
        raise BundleError("build entry could not be inspected") from exc

    if not stat.S_ISREG(entry_stat.st_mode):
        raise BundleError("build contains a non-regular file")
    return relative, path, entry_stat.st_size


def _collect_build_files(build_path: str) -> Tuple[Path, List[Tuple[str, Path, int]]]:
    requested_root = Path(build_path)
    try:
        root_stat = os.lstat(requested_root)
    except OSError as exc:
        raise BundleError("build directory is unavailable") from exc
    if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
        raise BundleError("build path must be a real directory")
    root = requested_root.resolve(strict=True)

    files: List[Tuple[str, Path, int]] = []
    total_size = 0
    pending: List[Tuple[Path, str]] = [(root, "")]
    while pending:
        directory, prefix = pending.pop()
        try:
            with os.scandir(directory) as scan:
                entries = sorted(scan, key=lambda entry: entry.name)
        except OSError as exc:
            raise BundleError("build directory could not be read") from exc

        for entry in entries:
            relative, path, size = _inspect_entry(directory, prefix, entry)
            if size is None:
                pending.append((path, relative))
                continue
            if len(files) >= MAX_FILES:
                raise BundleError("build contains too many files")
            if size < 0 or total_size + size > MAX_TOTAL_INPUT_BYTES:
                raise BundleError("build files exceed the total input size limit")
            total_size += size
            files.append((relative, path, size))

    files.sort(key=lambda item: item[0])
    if not files or not any(name == "index.html" for name, _, _ in files):
        raise BundleError("build must contain a regular root index.html")
    return root, files


def _resolved_output_path(build_root: Path, requested: Path) -> Path:
    if requested.is_symlink():
        raise BundleError("output directory must not be a symbolic link")
    resolved = requested.resolve(strict=False)
    try:
        resolved.relative_to(build_root)
    except ValueError:
        pass
    else:
        raise BundleError("output directory must be outside the build directory")
    return resolved


def _ensure_output_directory(requested: Path) -> Tuple[Path, bool]:
    created = False
    if requested.exists():
        if not requested.is_dir():
            raise BundleError("output path must be a directory")
        output = requested.resolve(strict=True)
    else:
        if not requested.parent.is_dir():
            raise BundleError("output parent directory must already exist")
        try:
            requested.mkdir()
        except FileExistsError:
            if not requested.is_dir():
                raise BundleError("output path must be a directory")
        except OSError as exc:
            raise BundleError("output directory could not be created") from exc
        else:
            created = True
        output = requested.resolve(strict=True)
    return output, created


def _check_output_names(output: Path) -> None:
    for name in (ARCHIVE_NAME, MANIFEST_NAME):
        if os.path.lexists(output / name):
            raise BundleError("an output file already exists")


def _output_directory(build_root: Path, output_path: str) -> Tuple[Path, bool]:
    requested = Path(output_path)
    _resolved_output_path(build_root, requested)
    output, created = _ensure_output_directory(requested)
    try:
        _check_output_names(output)
    except BundleError:
        if created:
            try:
                output.rmdir()
            except OSError:
                pass
        raise
    return output, created


def _open_regular_file(path: Path, expected_size: int) -> Tuple[int, os.stat_result]:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: Optional[int] = None
    try:
        descriptor = os.open(path, flags)
        current_stat = os.fstat(descriptor)
    except OSError as exc:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        raise BundleError("build file could not be opened") from exc
    if not stat.S_ISREG(current_stat.st_mode) or current_stat.st_size != expected_size:
        os.close(descriptor)
        raise BundleError("build file changed while packaging")
    return descriptor, current_stat


def _write_archive(path: Path, files: Sequence[Tuple[str, Path, int]]) -> Tuple[Path, int]:
    descriptor, temp_name = tempfile.mkstemp(prefix=".web-bundle-", suffix=".tmp", dir=str(path))
    temp_path = Path(temp_name)
    try:
        os.chmod(temp_path, 0o644)
        with os.fdopen(descriptor, "wb") as raw_archive:
            bounded = _BoundedWriter(raw_archive, MAX_ARCHIVE_BYTES)
            with gzip.GzipFile(
                fileobj=bounded,
                mode="wb",
                filename="",
                mtime=0,
                compresslevel=9,
            ) as compressed:
                with tarfile.open(
                    fileobj=compressed,
                    mode="w|",
                    format=tarfile.PAX_FORMAT,
                ) as archive:
                    for relative, source_path, size in files:
                        source_fd, _ = _open_regular_file(source_path, size)
                        with os.fdopen(source_fd, "rb") as source:
                            reader = _BoundedReader(source, size)
                            member = tarfile.TarInfo(relative)
                            member.size = size
                            member.mode = 0o644
                            member.uid = 0
                            member.gid = 0
                            member.uname = ""
                            member.gname = ""
                            member.mtime = 0
                            member.type = tarfile.REGTYPE
                            member.pax_headers = {}
                            archive.addfile(member, reader)
                            if reader.count != size:
                                raise BundleError("build file changed while packaging")
            raw_archive.flush()
            return temp_path, bounded.count
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            temp_path.unlink()
        except OSError:
            pass
        raise


def _hash_file(path: Path, limit: int) -> Tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(HASH_CHUNK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise BundleError("compressed archive exceeds the size limit")
                digest.update(chunk)
    except OSError as exc:
        raise BundleError("archive could not be read") from exc
    return size, digest.hexdigest()


def _manifest_bytes(manifest: Dict[str, object]) -> bytes:
    try:
        encoded = json.dumps(
            manifest,
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8") + b"\n"
    except (TypeError, ValueError, UnicodeError) as exc:
        raise BundleError("manifest could not be encoded") from exc
    if len(encoded) > MAX_MANIFEST_BYTES:
        raise BundleError("manifest exceeds the size limit")
    return encoded


def _write_temp_bytes(output: Path, content: bytes) -> Path:
    descriptor, temp_name = tempfile.mkstemp(prefix=".web-bundle-", suffix=".tmp", dir=str(output))
    temp_path = Path(temp_name)
    try:
        os.chmod(temp_path, 0o644)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            temp_path.unlink()
        except OSError:
            pass
        raise
    return temp_path


def _create_bundle(
    build_path: str,
    output_path: str,
    repository: str,
    commit: str,
) -> Dict[str, object]:
    repository = _validate_repository(repository)
    commit = _validate_commit(commit)
    root, files = _collect_build_files(build_path)
    output, created_output = _output_directory(root, output_path)
    archive_temp: Optional[Path] = None
    manifest_temp: Optional[Path] = None
    created_finals: List[Path] = []
    published = False
    try:
        archive_temp, archive_size = _write_archive(output, files)
        measured_size, archive_digest = _hash_file(archive_temp, MAX_ARCHIVE_BYTES)
        if measured_size != archive_size or measured_size <= 0:
            raise BundleError("archive size changed while packaging")

        manifest: Dict[str, object] = {
            "formatVersion": 1,
            "kind": "phoniebox-webapp",
            "repository": repository,
            "backendCommit": commit,
            "archiveName": ARCHIVE_NAME,
            "archiveSha256": archive_digest,
            "archiveSizeBytes": archive_size,
            "fileCount": len(files),
        }
        manifest_temp = _write_temp_bytes(output, _manifest_bytes(manifest))
        archive_final = output / ARCHIVE_NAME
        manifest_final = output / MANIFEST_NAME
        try:
            os.link(archive_temp, archive_final)
        except FileExistsError as exc:
            raise BundleError("an output file already exists") from exc
        created_finals.append(archive_final)
        try:
            os.link(manifest_temp, manifest_final)
        except FileExistsError as exc:
            raise BundleError("an output file already exists") from exc
        created_finals.append(manifest_final)
        published = True
        return manifest
    except BundleError:
        raise
    except (OSError, tarfile.TarError, EOFError, ValueError, OverflowError) as exc:
        raise BundleError("bundle could not be created") from exc
    finally:
        for temporary in (manifest_temp, archive_temp):
            if temporary is not None:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass
                except OSError:
                    pass
        if not published:
            for final_path in reversed(created_finals):
                try:
                    final_path.unlink()
                except FileNotFoundError:
                    pass
                except OSError:
                    pass
            if created_output:
                try:
                    output.rmdir()
                except OSError:
                    pass


def _reject_json_constant(value: str) -> None:
    raise BundleError("manifest contains a non-finite JSON number")


def _unique_object(pairs: Sequence[Tuple[str, object]]) -> Dict[str, object]:
    result: Dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise BundleError("manifest contains a duplicate field")
        result[key] = value
    return result


def _read_manifest(path: str) -> Dict[str, object]:
    try:
        with open(path, "rb") as stream:
            raw = stream.read(MAX_MANIFEST_BYTES + 1)
    except OSError as exc:
        raise BundleError("manifest could not be read") from exc
    if len(raw) > MAX_MANIFEST_BYTES:
        raise BundleError("manifest exceeds the size limit")
    try:
        text = raw.decode("utf-8", errors="strict")
        manifest = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except BundleError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise BundleError("manifest is not valid UTF-8 JSON") from exc
    if not isinstance(manifest, dict):
        raise BundleError("manifest must be a JSON object")
    return manifest


def _validate_manifest(manifest: Dict[str, object]) -> None:
    if set(manifest) != MANIFEST_FIELDS:
        raise BundleError("manifest fields do not match format version 1")
    if type(manifest["formatVersion"]) is not int or manifest["formatVersion"] != 1:
        raise BundleError("manifest format version is unsupported")
    if manifest["kind"] != "phoniebox-webapp":
        raise BundleError("manifest kind is unsupported")
    _validate_repository(manifest["repository"])
    _validate_commit(manifest["backendCommit"])
    if manifest["archiveName"] != ARCHIVE_NAME:
        raise BundleError("manifest archive name is unsupported")
    archive_digest = manifest["archiveSha256"]
    if not isinstance(archive_digest, str) or not SHA256_PATTERN.fullmatch(archive_digest):
        raise BundleError("manifest archive digest is invalid")
    archive_size = manifest["archiveSizeBytes"]
    if (
        type(archive_size) is not int
        or archive_size <= 0
        or archive_size > MAX_ARCHIVE_BYTES
    ):
        raise BundleError("manifest archive size is invalid")
    file_count = manifest["fileCount"]
    if type(file_count) is not int or file_count <= 0 or file_count > MAX_FILES:
        raise BundleError("manifest file count is invalid")


def _hash_archive(path: str) -> Tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    try:
        with open(path, "rb") as stream:
            while True:
                chunk = stream.read(HASH_CHUNK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_ARCHIVE_BYTES:
                    raise BundleError("archive exceeds the size limit")
                digest.update(chunk)
    except OSError as exc:
        raise BundleError("archive could not be read") from exc
    return size, digest.hexdigest()


def verify_bundle(
    archive_path: str,
    manifest_path: str,
    expected_repository: str,
    expected_commit: str,
) -> Dict[str, object]:
    """Validate identity and archive bytes without parsing or extracting TAR data."""
    repository = _validate_repository(expected_repository)
    commit = _validate_commit(expected_commit)
    manifest = _read_manifest(manifest_path)
    _validate_manifest(manifest)
    if manifest["repository"] != repository or manifest["backendCommit"] != commit:
        raise BundleError("manifest identity does not match the expected repository and commit")
    actual_size, actual_digest = _hash_archive(archive_path)
    if manifest["archiveSizeBytes"] != actual_size:
        raise BundleError("archive size does not match the manifest")
    if manifest["archiveSha256"] != actual_digest:
        raise BundleError("archive digest does not match the manifest")
    return manifest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Package or verify a Phoniebox web build bundle.")
    commands = parser.add_subparsers(dest="command", required=True)

    package = commands.add_parser("package", help="create a deterministic bundle from a finished build")
    package.add_argument("--build-dir", required=True)
    package.add_argument("--output-dir", required=True)
    package.add_argument("--repository", required=True)
    package.add_argument("--commit", required=True)

    verify = commands.add_parser("verify", help="verify bundle identity and archive bytes offline")
    verify.add_argument("--archive", required=True)
    verify.add_argument("--manifest", required=True)
    verify.add_argument("--repository", required=True)
    verify.add_argument("--commit", required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = _build_parser().parse_args(argv)
    try:
        if arguments.command == "package":
            manifest = _create_bundle(
                arguments.build_dir,
                arguments.output_dir,
                arguments.repository,
                arguments.commit,
            )
            print(
                "created repository={} commit={} sha256={} size={}".format(
                    manifest["repository"],
                    manifest["backendCommit"],
                    manifest["archiveSha256"],
                    manifest["archiveSizeBytes"],
                )
            )
            return 0
        manifest = verify_bundle(
            arguments.archive,
            arguments.manifest,
            arguments.repository,
            arguments.commit,
        )
        print(
            "verified repository={} commit={} sha256={} size={}".format(
                manifest["repository"],
                manifest["backendCommit"],
                manifest["archiveSha256"],
                manifest["archiveSizeBytes"],
            )
        )
        return 0
    except BundleError as exc:
        print("web bundle: {}".format(exc), file=sys.stderr)
        return 2
    except (OSError, tarfile.TarError, gzip.BadGzipFile, EOFError, ValueError, OverflowError):
        print("web bundle: operation failed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

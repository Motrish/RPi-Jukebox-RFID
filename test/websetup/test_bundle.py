"""Behavioral tests for private intake of a verified web bundle."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT))

# Keep this import unconditional: the Linux full checkout must report real RED.
from installation.websetup.bundle import BundleError, staged_bundle  # noqa: E402
from installation.websetup import bundle as intake_bundle  # noqa: E402
from tools import web_bundle  # noqa: E402

REPOSITORY = "example-owner/phoniebox"
COMMIT = "0123456789abcdef0123456789abcdef01234567"


class _OversizedReadGuard(Exception):
    pass


class BundleIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.build = self.root / "build"
        self.build.mkdir()
        (self.build / "index.html").write_bytes(b"<!doctype html><p>ready</p>\n")
        (self.build / "static" / "js").mkdir(parents=True)
        (self.build / "static" / "js" / "app.js").write_bytes(b"window.app = true;\n")
        (self.build / "static" / "empty.dat").write_bytes(b"")
        self.output = self.root / "producer-output"
        self.output.mkdir()
        self.parent = self.root / "private-parent"
        self.parent.mkdir()
        self.archive = self.output / web_bundle.ARCHIVE_NAME
        self.manifest = self.output / web_bundle.MANIFEST_NAME
        self.make_producer_bundle()

    def tearDown(self):
        self.temporary.cleanup()

    def make_producer_bundle(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = web_bundle.main([
                "package", "--build-dir", str(self.build),
                "--output-dir", str(self.output),
                "--repository", REPOSITORY, "--commit", COMMIT,
            ])
        self.assertEqual(result, 0)

    def write_archive(self, members, *, trailing=b"", corrupt_crc=False, file_count=None):
        tar_bytes = io.BytesIO()
        with tarfile.open(fileobj=tar_bytes, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for info, payload in members:
                if isinstance(info, str):
                    item = tarfile.TarInfo(info)
                    item.size = len(payload)
                else:
                    item = info
                    if item.isreg():
                        item.size = len(payload)
                archive.addfile(item, io.BytesIO(payload) if item.isreg() else None)
        compressed = gzip.compress(tar_bytes.getvalue() + trailing, mtime=0)
        if corrupt_crc:
            damaged = bytearray(compressed)
            damaged[-8] ^= 1
            compressed = bytes(damaged)
        self.archive.write_bytes(compressed)
        if file_count is None:
            file_count = sum(
                1 for info, _ in members
                if isinstance(info, str) or info.isreg()
            )
        self.write_manifest(file_count)

    def write_raw_tar(self, data, file_count=1):
        self.archive.write_bytes(gzip.compress(data, mtime=0))
        self.write_manifest(file_count)

    def tar_header(self, name, size, kind=tarfile.REGTYPE):
        item = tarfile.TarInfo(name)
        item.type = kind
        item.size = size
        return item.tobuf(format=tarfile.PAX_FORMAT)

    def pax_record(self, key, value):
        body = "{}={}\n".format(key, value).encode("utf-8")
        length = len(body) + 2
        while True:
            record = str(length).encode("ascii") + b" " + body
            if len(record) == length:
                return record
            length = len(record)

    def padded(self, payload):
        return payload + (b"\0" * (-len(payload) % 512))

    def raw_pax_member(self, record_bytes, member_name="static/pax.js", payload=b"pax\n"):
        pax_header = self.tar_header("PaxHeaders/member", len(record_bytes), tarfile.XHDTYPE)
        member_header = self.tar_header(member_name, len(payload))
        return (
            pax_header + self.padded(record_bytes)
            + member_header + self.padded(payload)
        )

    def write_manifest(self, file_count=2):
        data = {
            "formatVersion": 1,
            "kind": "phoniebox-webapp",
            "repository": REPOSITORY,
            "backendCommit": COMMIT,
            "archiveName": web_bundle.ARCHIVE_NAME,
            "archiveSha256": hashlib.sha256(self.archive.read_bytes()).hexdigest(),
            "archiveSizeBytes": self.archive.stat().st_size,
            "fileCount": file_count,
        }
        self.manifest.write_text(json.dumps(data), encoding="utf-8")

    def valid_members(self):
        return [("index.html", b"index\n"), ("static/js/app.js", b"app\n")]

    def run_staged(self, **overrides):
        arguments = {
            "archive_path": self.archive,
            "manifest_path": self.manifest,
            "expected_repository": REPOSITORY,
            "expected_commit": COMMIT,
            "staging_parent": self.parent,
        }
        arguments.update(overrides)
        return staged_bundle(**arguments)

    def assert_rejected_and_clean(self, **overrides):
        before = set(self.parent.iterdir())
        with self.assertRaises(BundleError):
            with self.run_staged(**overrides):
                self.fail("invalid bundle was yielded")
        self.assertEqual(set(self.parent.iterdir()), before)

    def assert_declared_size_rejected_before_payload_read(self, payload_start):
        observations = []
        parent_before = set(self.parent.iterdir())
        original_read = gzip.GzipFile.read

        def guarded_read(stream, size=-1):
            position = stream.tell()
            if size < 0 or size > 64 * 1024:
                observations.append(("blocked", position, size, 0))
                raise _OversizedReadGuard("blocked unsafe decompressor read")
            data = original_read(stream, size)
            observations.append(("read", position, size, len(data)))
            return data

        caught = None
        with mock.patch.object(gzip.GzipFile, "read", guarded_read):
            try:
                with self.run_staged():
                    self.fail("oversized declaration was yielded")
            except (BundleError, _OversizedReadGuard) as error:
                caught = error

        self.assertIsNotNone(caught)
        self.assertTrue(observations)
        self.assertFalse(any(kind == "blocked" for kind, _, _, _ in observations))
        self.assertTrue(any(
            kind == "read" and position + returned == payload_start
            for kind, position, _, returned in observations
        ))
        self.assertFalse(any(
            kind == "read" and returned > 0 and position + returned > payload_start
            for kind, position, _, returned in observations
        ))
        self.assertEqual(set(self.parent.iterdir()), parent_before)

    def test_real_producer_bundle_is_staged_byte_exact_and_removed_on_success(self):
        archive_before = self.archive.read_bytes()
        manifest_before = self.manifest.read_bytes()
        unrelated = self.parent / "keep.txt"
        unrelated.write_bytes(b"keep")
        if os.name == "posix":
            unrelated.chmod(0o600)
        unrelated_mode = stat.S_IMODE(unrelated.stat().st_mode)
        with self.run_staged() as webroot:
            self.assertTrue(webroot.is_dir())
            self.assertEqual((webroot / "index.html").read_bytes(), (self.build / "index.html").read_bytes())
            self.assertEqual((webroot / "static/js/app.js").read_bytes(), (self.build / "static/js/app.js").read_bytes())
            self.assertEqual((webroot / "static/empty.dat").read_bytes(), b"")
            self.assertEqual(self.archive.read_bytes(), archive_before)
            self.assertEqual(self.manifest.read_bytes(), manifest_before)
            self.assertEqual(unrelated.read_bytes(), b"keep")
            try:
                relative_webroot = webroot.resolve().relative_to(self.parent.resolve())
            except ValueError:
                self.fail("validated webroot escaped the caller's staging parent")
            self.assertTrue(relative_webroot.parts)
            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(webroot.stat().st_mode), 0o700)
                ancestor = webroot.parent
                while ancestor != self.parent:
                    self.assertEqual(stat.S_IMODE(ancestor.stat().st_mode), 0o700)
                    ancestor = ancestor.parent
                for path in webroot.rglob("*"):
                    if path.is_dir():
                        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
                    if path.is_file():
                        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)
                self.assertEqual(stat.S_IMODE(unrelated.stat().st_mode), unrelated_mode)
        self.assertEqual(list(self.parent.iterdir()), [unrelated])
        self.assertEqual(unrelated.read_bytes(), b"keep")
        self.assertEqual(stat.S_IMODE(unrelated.stat().st_mode), unrelated_mode)

    def test_source_replacement_after_verification_does_not_change_staged_bytes(self):
        original_archive = self.archive.read_bytes()
        poison = io.BytesIO()
        with tarfile.open(fileobj=poison, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for name, payload in (
                ("index.html", b"replaced after verification"),
                ("static/js/app.js", b"poison"),
            ):
                item = tarfile.TarInfo(name)
                item.size = len(payload)
                archive.addfile(item, io.BytesIO(payload))
        poisoned_archive = gzip.compress(poison.getvalue(), mtime=0)
        original_verify = web_bundle.verify_bundle
        verified_inputs = []

        def verify_then_replace(archive_path, manifest_path, expected_repository, expected_commit):
            archived_copy = Path(archive_path).resolve()
            manifest_copy = Path(manifest_path).resolve()
            archive_relative = archived_copy.relative_to(self.parent.resolve())
            manifest_relative = manifest_copy.relative_to(self.parent.resolve())
            verified_inputs.append((
                archived_copy,
                manifest_copy,
                archive_relative.parts[0],
                manifest_relative.parts[0],
            ))
            verified = original_verify(
                archive_path, manifest_path, expected_repository, expected_commit
            )
            self.archive.write_bytes(poisoned_archive)
            return verified

        try:
            with ExitStack() as stack:
                stack.enter_context(
                    mock.patch.object(web_bundle, "verify_bundle", side_effect=verify_then_replace)
                )
                if getattr(intake_bundle, "verify_bundle", None) is original_verify:
                    stack.enter_context(
                        mock.patch.object(
                            intake_bundle, "verify_bundle", side_effect=verify_then_replace
                        )
                    )
                with self.run_staged() as webroot:
                    self.assertEqual(
                        (webroot / "index.html").read_bytes(),
                        (self.build / "index.html").read_bytes(),
                    )
                    self.assertEqual(
                        (webroot / "static/js/app.js").read_bytes(),
                        (self.build / "static/js/app.js").read_bytes(),
                    )
                    self.assertEqual(len(verified_inputs), 1)
                    archive_copy, manifest_copy, archive_root, manifest_root = verified_inputs[0]
                    self.assertNotEqual(archive_copy, self.archive.resolve())
                    self.assertNotEqual(manifest_copy, self.manifest.resolve())
                    self.assertEqual(archive_root, manifest_root)
                    private_root = self.parent / archive_root
                    self.assertTrue(private_root.is_dir())
                    if os.name == "posix":
                        self.assertEqual(stat.S_IMODE(private_root.stat().st_mode), 0o700)
        finally:
            self.archive.write_bytes(original_archive)

    def test_consumer_exception_is_preserved_and_private_tree_is_removed(self):
        failure = RuntimeError("consumer sentinel")
        with self.assertRaisesRegex(RuntimeError, "consumer sentinel") as raised:
            with self.run_staged():
                raise failure
        self.assertIs(raised.exception, failure)
        self.assertEqual(list(self.parent.iterdir()), [])

    def test_wrong_independent_identity_is_rejected(self):
        self.assertIs(BundleError, web_bundle.BundleError)
        self.assert_rejected_and_clean(expected_repository="other-owner/phoniebox")
        self.assert_rejected_and_clean(expected_commit="f" * 40)

    def test_same_length_archive_tampering_is_rejected(self):
        original = self.archive.read_bytes()
        changed = bytearray(original)
        changed[len(changed) // 2] ^= 1
        self.archive.write_bytes(changed)
        self.assertEqual(len(changed), len(original))
        self.assert_rejected_and_clean()

    def test_manifest_and_archive_symlinks_are_rejected(self):
        for name in ("archive", "manifest"):
            with self.subTest(name=name):
                source = self.archive if name == "archive" else self.manifest
                link = self.root / (name + "-link")
                try:
                    link.symlink_to(source)
                except (OSError, NotImplementedError):
                    self.skipTest("symlink creation is unavailable")
                key = "archive_path" if name == "archive" else "manifest_path"
                self.assert_rejected_and_clean(**{key: link})

    def test_existing_parent_is_required_and_preserved(self):
        sentinel = self.parent / "sentinel"
        sentinel.write_bytes(b"untouched")
        absent_parent = self.root / "absent"
        self.assert_rejected_and_clean(staging_parent=absent_parent)
        self.assertFalse(absent_parent.exists())
        self.assertEqual(sentinel.read_bytes(), b"untouched")

    def test_staging_parent_symlink_is_rejected_without_touching_its_target(self):
        target = self.root / "real-parent"
        target.mkdir()
        sentinel = target / "keep"
        sentinel.write_bytes(b"untouched")
        link = self.root / "parent-link"
        before = set(target.iterdir())
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation is unavailable")
        self.assert_rejected_and_clean(staging_parent=link)
        self.assertEqual(set(target.iterdir()), before)
        self.assertEqual(sentinel.read_bytes(), b"untouched")

    def test_nested_utf8_and_long_pax_names_are_preserved(self):
        relative = Path("static") / ("é" * 80) / "client.js"
        source_file = self.build / relative
        source_file.parent.mkdir(parents=True)
        source_file.write_bytes(b"producer-utf8-long")
        output = self.root / "long-producer-output"
        output.mkdir()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = web_bundle.main([
                "package", "--build-dir", str(self.build),
                "--output-dir", str(output),
                "--repository", REPOSITORY, "--commit", COMMIT,
            ])
        self.assertEqual(result, 0)
        with staged_bundle(
            archive_path=output / web_bundle.ARCHIVE_NAME,
            manifest_path=output / web_bundle.MANIFEST_NAME,
            expected_repository=REPOSITORY,
            expected_commit=COMMIT,
            staging_parent=self.parent,
        ) as webroot:
            self.assertEqual((webroot / relative).read_bytes(), b"producer-utf8-long")

    def test_parent_absolute_windows_and_control_paths_are_rejected(self):
        absolute_target = self.root / "absolute-escape"
        drive_target = str(self.root / "drive-escape").replace("\\", "/")
        drive_target_path = Path(drive_target)
        bad_names = (
            "../escape", "a/../../escape", str(absolute_target), drive_target,
            "a\\b", "bad\nname", "", ".", "./child", "a/./b", "a/../b",
            "name:stream", "x" * 4097,
        )
        if os.name != "nt":
            bad_names += ("//server/share",)
        installation_before = {
            path.relative_to(self.build): path.read_bytes()
            for path in self.build.rglob("*") if path.is_file()
        }
        for name in bad_names:
            with self.subTest(name=repr(name)):
                self.write_archive([("index.html", b"ok"), (name, b"bad")])
                self.assert_rejected_and_clean()
                self.assertFalse((self.root / "escape").exists())
                self.assertFalse((self.parent / "escape").exists())
                self.assertFalse(absolute_target.exists())
                self.assertFalse(drive_target_path.exists())
                self.assertEqual(
                    installation_before,
                    {path.relative_to(self.build): path.read_bytes()
                     for path in self.build.rglob("*") if path.is_file()},
                )

    def test_pax_path_is_validated_after_expansion(self):
        item = tarfile.TarInfo("placeholder")
        item.pax_headers = {"path": "../escaped.js"}
        self.write_archive([("index.html", b"ok"), (item, b"bad")])
        self.assert_rejected_and_clean()
        self.assertFalse((self.root / "escaped.js").exists())

    def test_pax_names_that_resolve_to_the_same_path_are_rejected(self):
        index = self.tar_header("index.html", 2) + self.padded(b"ok")
        first = self.raw_pax_member(self.pax_record("path", "static/same.js"), payload=b"first")
        second = self.raw_pax_member(self.pax_record("path", "static/same.js"), payload=b"second")
        self.write_raw_tar(index + first + second + (b"\0" * 1024), file_count=3)
        self.assert_rejected_and_clean()

    def test_valid_and_invalid_pax_records_have_parser_controls(self):
        index = self.tar_header("index.html", 2) + self.padded(b"ok")
        valid_path = "static/valid-é.js"
        valid_record = self.pax_record("path", valid_path)
        valid_tar = index + self.raw_pax_member(valid_record) + (b"\0" * 1024)
        self.write_raw_tar(valid_tar, file_count=2)
        with self.run_staged() as webroot:
            self.assertEqual((webroot / valid_path).read_bytes(), b"pax\n")

        duplicate_paths = self.pax_record("path", "static/first.js") + self.pax_record("path", "static/second.js")
        malformed_length = b"999 path=static/bad.js\n"
        invalid_utf8 = b"9 path=\xff\n"
        parent_path = self.pax_record("path", "static/../escaped.js")
        for record in (duplicate_paths, malformed_length, invalid_utf8, parent_path):
            with self.subTest(record=record[:40]):
                self.write_raw_tar(
                    index + self.raw_pax_member(record) + (b"\0" * 1024),
                    file_count=2,
                )
                self.assert_rejected_and_clean()

    def test_unmatched_pax_extension_and_unpermitted_pax_fields_are_rejected(self):
        index = self.tar_header("index.html", 2) + self.padded(b"ok")
        path = self.pax_record("path", "static/following.js")
        pax = self.tar_header("PaxHeaders/member", len(path), tarfile.XHDTYPE) + self.padded(path)
        self.write_raw_tar(index + pax + (b"\0" * 1024), file_count=1)
        self.assert_rejected_and_clean()

        first = self.pax_record("path", "static/first.js")
        second = self.pax_record("size", "4")
        combined = self.tar_header("PaxHeaders/member", len(first + second), tarfile.XHDTYPE)
        following = self.tar_header("static/first.js", 4) + self.padded(b"data")
        self.write_raw_tar(
            index + combined + self.padded(first + second) + following + (b"\0" * 1024),
            file_count=2,
        )
        self.assert_rejected_and_clean()

    def test_links_special_files_and_sparse_entries_are_rejected(self):
        entries = []
        for kind in (
            tarfile.DIRTYPE, tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE,
            tarfile.CHRTYPE, tarfile.BLKTYPE, tarfile.CONTTYPE,
            getattr(tarfile, "GNUTYPE_SPARSE", b"S"),
        ):
            item = tarfile.TarInfo("unsafe")
            item.type = kind
            item.linkname = "index.html"
            entries.append((kind, item))
        for kind, item in entries:
            with self.subTest(kind=kind):
                self.write_archive([("index.html", b"ok"), (item, b"")], file_count=1)
                self.assert_rejected_and_clean()

    def test_valid_gnu_longname_and_longlink_extensions_are_rejected(self):
        long_name = "static/" + ("n" * 150) + ".js"
        index_payload = b"ok"
        index = self.tar_header("index.html", len(index_payload)) + self.padded(index_payload)
        extension_name = long_name.encode("utf-8") + b"\0"
        longname = (
            self.tar_header("././@LongLink", len(extension_name), tarfile.GNUTYPE_LONGNAME)
            + self.padded(extension_name)
        )
        regular = self.tar_header("short.js", 2) + self.padded(b"ok")
        self.write_raw_tar(index + longname + regular + (b"\0" * 1024), file_count=2)
        self.assert_rejected_and_clean()

        target = b"index.html\0"
        longlink = (
            self.tar_header("././@LongLink", len(target), tarfile.GNUTYPE_LONGLINK)
            + self.padded(target)
        )
        link = self.tar_header("shortcut", 0, tarfile.LNKTYPE)
        self.write_raw_tar(index + longlink + link + (b"\0" * 1024), file_count=1)
        self.assert_rejected_and_clean()

    def test_valid_global_pax_extension_is_rejected(self):
        index = self.tar_header("index.html", 2) + self.padded(b"ok")
        comment = self.pax_record("comment", "valid global metadata")
        global_header = self.tar_header("GlobalHead", len(comment), tarfile.XGLTYPE)
        self.write_raw_tar(index + global_header + self.padded(comment) + (b"\0" * 1024), file_count=1)
        self.assert_rejected_and_clean()

    def test_duplicate_effective_names_and_file_directory_collisions_are_rejected(self):
        cases = (
            [("index.html", b"one"), ("index.html", b"two")],
            [("index.html", b"ok"), ("a", b"file"), ("a/b.js", b"child")],
            [("index.html", b"ok"), ("a/b.js", b"child"), ("a", b"file")],
        )
        for members in cases:
            with self.subTest(names=[name if isinstance(name, str) else name.name for name, _ in members]):
                self.write_archive(members)
                self.assert_rejected_and_clean()

        probe = self.root / "CaseProbe"
        probe.write_bytes(b"probe")
        insensitive = (self.root / "caseprobe").exists()
        probe.unlink()
        self.write_archive([("index.html", b"ok"), ("Case.js", b"one"), ("case.js", b"two")])
        if insensitive:
            self.assert_rejected_and_clean()
        else:
            with self.run_staged() as webroot:
                self.assertEqual((webroot / "Case.js").read_bytes(), b"one")
                self.assertEqual((webroot / "case.js").read_bytes(), b"two")

    def test_regular_root_index_and_manifest_file_count_are_required(self):
        self.write_archive([("nested/index.html", b"missing root")])
        self.assert_rejected_and_clean()
        self.write_archive(self.valid_members())
        self.write_manifest(file_count=1)
        self.assert_rejected_and_clean()

    def test_compressed_archive_limit_is_enforced_by_the_shared_verifier(self):
        with mock.patch.object(web_bundle, "MAX_ARCHIVE_BYTES", self.archive.stat().st_size - 1):
            self.assert_rejected_and_clean()

    def test_private_copy_enforces_archive_limit_before_shared_verification(self):
        archive_size = self.archive.stat().st_size
        with mock.patch.object(intake_bundle, "MAX_ARCHIVE_BYTES", archive_size - 1):
            self.assert_rejected_and_clean()
        with mock.patch.object(intake_bundle, "MAX_ARCHIVE_BYTES", archive_size):
            with self.run_staged() as webroot:
                self.assertEqual((webroot / "index.html").read_bytes(), (self.build / "index.html").read_bytes())

    def test_actual_member_count_cannot_exceed_the_r01a_limit(self):
        members = [("index.html", b"")]
        members.extend(("asset-{}.js".format(index), b"") for index in range(web_bundle.MAX_FILES))
        self.write_archive(members)
        self.write_manifest(file_count=web_bundle.MAX_FILES)
        self.assert_rejected_and_clean()

    def test_complete_member_aggregate_limit_has_reject_and_accept_controls(self):
        members = [("index.html", b"index"), ("static/data.bin", b"x" * 32)]
        self.write_archive(members)
        with mock.patch.object(intake_bundle, "MAX_TOTAL_INPUT_BYTES", 36):
            self.assert_rejected_and_clean()
        with mock.patch.object(intake_bundle, "MAX_TOTAL_INPUT_BYTES", 37):
            with self.run_staged() as webroot:
                self.assertEqual((webroot / "index.html").read_bytes(), b"index")
                self.assertEqual((webroot / "static/data.bin").read_bytes(), b"x" * 32)

    def test_declared_file_size_is_rejected_before_member_data_is_present(self):
        index = self.tar_header("index.html", 2)
        index_payload = b"ok" + (b"\0" * 510)
        oversized = self.tar_header("large.bin", web_bundle.MAX_TOTAL_INPUT_BYTES + 1)
        self.write_raw_tar(index + index_payload + oversized + (b"\0" * 1024), file_count=2)
        self.assert_declared_size_rejected_before_payload_read(1536)

    def test_oversized_declared_pax_payload_is_rejected_before_reading_it(self):
        index = self.tar_header("index.html", 2)
        index_payload = b"ok" + (b"\0" * 510)
        oversized_pax = self.tar_header("PaxHeaders/member", 1 << 30, tarfile.XHDTYPE)
        self.write_raw_tar(index + index_payload + oversized_pax + (b"\0" * 1024), file_count=1)
        self.assert_declared_size_rejected_before_payload_read(1536)

    def test_complete_pax_and_padding_expansion_obeys_stream_limit_with_control(self):
        index_payload = b"index\n"
        index_header = self.tar_header("index.html", len(index_payload))
        index_member = index_header + self.padded(index_payload)
        pax_member = self.raw_pax_member(self.pax_record("path", "static/é" + ("x" * 120) + ".js"))
        pax_tar = index_member + pax_member + (b"\0" * 1024)
        self.write_raw_tar(pax_tar, file_count=2)
        with mock.patch.object(intake_bundle, "MAX_TAR_STREAM_BYTES", len(pax_tar) - 1):
            self.assert_rejected_and_clean()
        with mock.patch.object(intake_bundle, "MAX_TAR_STREAM_BYTES", len(pax_tar)):
            with self.run_staged() as webroot:
                self.assertEqual((webroot / "index.html").read_bytes(), index_payload)
                self.assertEqual((webroot / ("static/é" + ("x" * 120) + ".js")).read_bytes(), b"pax\n")

    def test_zero_padding_expansion_obeys_stream_limit_with_control(self):
        self.write_archive(self.valid_members(), trailing=b"\0" * 4096)
        raw_size = len(gzip.decompress(self.archive.read_bytes()))
        with mock.patch.object(intake_bundle, "MAX_TAR_STREAM_BYTES", raw_size - 1):
            self.assert_rejected_and_clean()
        with mock.patch.object(intake_bundle, "MAX_TAR_STREAM_BYTES", raw_size):
            with self.run_staged() as webroot:
                self.assertEqual((webroot / "index.html").read_bytes(), b"index\n")

    def test_truncated_member_header_end_and_bad_gzip_crc_are_rejected(self):
        self.write_archive(self.valid_members())
        self.archive.write_bytes(self.archive.read_bytes()[:-5])
        self.write_manifest()
        self.assert_rejected_and_clean()

    def test_short_member_payload_bad_header_checksum_and_missing_end_block_are_rejected(self):
        short_member = self.tar_header("index.html", 4) + b"ab"
        self.write_raw_tar(short_member, file_count=1)
        self.assert_rejected_and_clean()

        bad_header = bytearray(self.tar_header("index.html", 2))
        bad_header[0] ^= 1
        self.write_raw_tar(bytes(bad_header) + self.padded(b"ok") + (b"\0" * 1024), file_count=1)
        self.assert_rejected_and_clean()

        valid_header = self.tar_header("index.html", 2)
        one_end_block = valid_header + self.padded(b"ok") + (b"\0" * 512)
        self.write_raw_tar(one_end_block, file_count=1)
        self.assert_rejected_and_clean()

        self.write_archive(self.valid_members(), corrupt_crc=True)
        self.assert_rejected_and_clean()

        self.write_archive(self.valid_members())
        raw = gzip.decompress(self.archive.read_bytes())
        self.archive.write_bytes(gzip.compress(raw[:100], mtime=0))
        self.write_manifest()
        self.assert_rejected_and_clean()

    def test_nonzero_bytes_after_tar_end_are_rejected(self):
        self.write_archive(self.valid_members(), trailing=b"hidden tar data")
        self.assert_rejected_and_clean()

    def test_malformed_or_disallowed_pax_metadata_is_rejected(self):
        for fields in ({"size": "999999999"}, {"linkpath": "outside"}, {"GNU.sparse.map": "0,1"}):
            item = tarfile.TarInfo("member")
            item.pax_headers = fields
            with self.subTest(fields=fields):
                self.write_archive([("index.html", b"ok"), (item, b"bad")])
                self.assert_rejected_and_clean()

    def test_invalid_manifest_digest_never_yields_a_tree(self):
        data = json.loads(self.manifest.read_text(encoding="utf-8"))
        data["archiveSha256"] = "0" * 64
        self.manifest.write_text(json.dumps(data), encoding="utf-8")
        self.assert_rejected_and_clean()

    def test_safe_errors_do_not_include_local_paths_or_file_contents(self):
        secret = "PRIVATE-MANIFEST-CONTENT-9af1"
        self.manifest.write_text('{"secret":"' + secret, encoding="utf-8")
        with self.assertRaises(BundleError) as raised:
            with self.run_staged():
                self.fail("malformed manifest was yielded")
        self.assertNotIn(str(self.root), str(raised.exception))
        self.assertNotIn(str(self.archive), str(raised.exception))
        self.assertNotIn(str(self.manifest), str(raised.exception))
        self.assertNotIn(secret, str(raised.exception))
        self.assertEqual(list(self.parent.iterdir()), [])

    def test_private_parent_sentinel_is_never_removed_on_failure(self):
        sentinel = self.parent / "owned-by-caller"
        sentinel.mkdir()
        (sentinel / "data").write_bytes(b"keep")
        self.write_archive([("../escape", b"bad")])
        self.assert_rejected_and_clean()
        self.assertEqual((sentinel / "data").read_bytes(), b"keep")

    @unittest.skipUnless(os.name == "posix" and hasattr(os, "mkfifo"), "FIFO input is POSIX-only")
    def test_fifo_input_fails_promptly_in_a_bounded_subprocess(self):
        for input_name in ("archive", "manifest"):
            with self.subTest(input_name=input_name):
                fifo = self.root / (input_name + ".fifo")
                os.mkfifo(fifo)
                archive = fifo if input_name == "archive" else self.archive
                manifest = fifo if input_name == "manifest" else self.manifest
                code = (
                    "from pathlib import Path\n"
                    "from installation.websetup.bundle import BundleError, staged_bundle\n"
                    "try:\n"
                    f"    with staged_bundle(Path({str(archive)!r}), Path({str(manifest)!r}), "
                    f"{REPOSITORY!r}, {COMMIT!r}, Path({str(self.parent)!r})): pass\n"
                    "except BundleError:\n"
                    "    raise SystemExit(0)\n"
                    "raise SystemExit(1)\n"
                )
                result = subprocess.run(
                    [sys.executable, "-c", code], cwd=REPOSITORY_ROOT,
                    capture_output=True, timeout=5, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
                self.assertEqual(list(self.parent.iterdir()), [])


if __name__ == "__main__":
    unittest.main()

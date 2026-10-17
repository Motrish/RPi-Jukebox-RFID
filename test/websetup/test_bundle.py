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
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT))

# Keep this import unconditional: the Linux full checkout must report real RED.
from installation.websetup.bundle import BundleError, staged_bundle  # noqa: E402
from installation.websetup import bundle as intake_bundle  # noqa: E402
from tools import web_bundle  # noqa: E402

REPOSITORY = "example-owner/phoniebox"
COMMIT = "0123456789abcdef0123456789abcdef01234567"


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

    def write_archive(self, members, *, trailing=b"", corrupt_crc=False):
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
        self.write_manifest(len(members))

    def write_raw_tar(self, data, file_count=1):
        self.archive.write_bytes(gzip.compress(data, mtime=0))
        self.write_manifest(file_count)

    def tar_header(self, name, size, kind=tarfile.REGTYPE):
        item = tarfile.TarInfo(name)
        item.type = kind
        item.size = size
        return item.tobuf(format=tarfile.PAX_FORMAT)

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

    def test_real_producer_bundle_is_staged_byte_exact_and_removed_on_success(self):
        archive_before = self.archive.read_bytes()
        manifest_before = self.manifest.read_bytes()
        unrelated = self.parent / "keep.txt"
        unrelated.write_bytes(b"keep")
        with self.run_staged() as webroot:
            self.assertTrue(webroot.is_dir())
            self.assertEqual((webroot / "index.html").read_bytes(), (self.build / "index.html").read_bytes())
            self.assertEqual((webroot / "static/js/app.js").read_bytes(), (self.build / "static/js/app.js").read_bytes())
            self.assertEqual((webroot / "static/empty.dat").read_bytes(), b"")
            self.assertEqual(self.archive.read_bytes(), archive_before)
            self.assertEqual(self.manifest.read_bytes(), manifest_before)
            self.assertEqual(unrelated.read_bytes(), b"keep")
            self.assertEqual(webroot.parent.parent, self.parent)
            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(webroot.parent.stat().st_mode), 0o700)
                for path in webroot.rglob("*"):
                    if path.is_dir():
                        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
                    if path.is_file():
                        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)
        self.assertEqual(list(self.parent.iterdir()), [unrelated])

    def test_consumer_exception_is_preserved_and_private_tree_is_removed(self):
        failure = RuntimeError("consumer sentinel")
        with self.assertRaisesRegex(RuntimeError, "consumer sentinel"):
            with self.run_staged():
                raise failure
        self.assertEqual(list(self.parent.iterdir()), [])

    def test_wrong_independent_identity_is_rejected(self):
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
        self.assert_rejected_and_clean(staging_parent=self.root / "absent")
        self.assertEqual(sentinel.read_bytes(), b"untouched")

    def test_staging_parent_symlink_is_rejected_without_touching_its_target(self):
        target = self.root / "real-parent"
        target.mkdir()
        sentinel = target / "keep"
        sentinel.write_bytes(b"untouched")
        link = self.root / "parent-link"
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation is unavailable")
        self.assert_rejected_and_clean(staging_parent=link)
        self.assertEqual(sentinel.read_bytes(), b"untouched")

    def test_nested_utf8_and_long_pax_names_are_preserved(self):
        long_path = "static/" + ("é" * 90) + "/script.js"
        members = [("index.html", b"ok"), (long_path, b"utf8-long")]
        self.write_archive(members)
        with self.run_staged() as webroot:
            self.assertEqual((webroot / long_path).read_bytes(), b"utf8-long")

    def test_parent_absolute_windows_and_control_paths_are_rejected(self):
        bad_names = ("../escape", "/absolute", "C:/drive", "//server/share", "a\\b", "bad\nname")
        for name in bad_names:
            with self.subTest(name=repr(name)):
                self.write_archive([("index.html", b"ok"), (name, b"bad")])
                self.assert_rejected_and_clean()
                self.assertFalse((self.root / "escape").exists())

    def test_pax_path_is_validated_after_expansion(self):
        item = tarfile.TarInfo("placeholder")
        item.pax_headers = {"path": "../escaped.js"}
        self.write_archive([("index.html", b"ok"), (item, b"bad")])
        self.assert_rejected_and_clean()
        self.assertFalse((self.root / "escaped.js").exists())

    def test_links_special_files_and_sparse_entries_are_rejected(self):
        entries = []
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE, tarfile.BLKTYPE, tarfile.CONTTYPE):
            item = tarfile.TarInfo("unsafe")
            item.type = kind
            item.linkname = "index.html"
            entries.append((kind, item))
        for kind, item in entries:
            with self.subTest(kind=kind):
                self.write_archive([("index.html", b"ok"), (item, b"")])
                self.assert_rejected_and_clean()

    def test_duplicate_effective_names_and_file_directory_collisions_are_rejected(self):
        cases = (
            [("index.html", b"one"), ("index.html", b"two")],
            [("index.html", b"ok"), ("a", b"file"), ("a/b.js", b"child")],
            [("index.html", b"ok"), ("a/b.js", b"child"), ("a", b"file")],
            [("index.html", b"ok"), ("Case.js", b"one"), ("case.js", b"two")],
        )
        for members in cases:
            with self.subTest(names=[name if isinstance(name, str) else name.name for name, _ in members]):
                self.write_archive(members)
                self.assert_rejected_and_clean()

    def test_regular_root_index_and_manifest_file_count_are_required(self):
        self.write_archive([("nested/index.html", b"missing root")])
        self.assert_rejected_and_clean()
        self.write_archive(self.valid_members())
        self.write_manifest(file_count=1)
        self.assert_rejected_and_clean()

    def test_compressed_archive_limit_is_enforced_by_the_shared_verifier(self):
        with mock.patch.object(web_bundle, "MAX_ARCHIVE_BYTES", self.archive.stat().st_size - 1):
            self.assert_rejected_and_clean()

    def test_actual_member_count_cannot_exceed_the_r01a_limit(self):
        members = [("index.html", b"")]
        members.extend(("asset-{}.js".format(index), b"") for index in range(web_bundle.MAX_FILES))
        self.write_archive(members)
        self.write_manifest(file_count=web_bundle.MAX_FILES)
        self.assert_rejected_and_clean()

    def test_declared_file_size_is_rejected_before_member_data_is_present(self):
        index = self.tar_header("index.html", 2)
        index_payload = b"ok" + (b"\0" * 510)
        oversized = self.tar_header("large.bin", web_bundle.MAX_TOTAL_INPUT_BYTES + 1)
        self.write_raw_tar(index + index_payload + oversized + (b"\0" * 1024), file_count=2)
        self.assert_rejected_and_clean()

    def test_oversized_declared_pax_payload_is_rejected_before_reading_it(self):
        index = self.tar_header("index.html", 2)
        index_payload = b"ok" + (b"\0" * 510)
        oversized_pax = self.tar_header("PaxHeaders/member", 1 << 30, tarfile.XHDTYPE)
        self.write_raw_tar(index + index_payload + oversized_pax + (b"\0" * 1024), file_count=1)
        self.assert_rejected_and_clean()

    def test_small_stream_limit_fixture_rejects_header_and_padding_expansion(self):
        index = self.tar_header("index.html", 2)
        index_payload = b"ok" + (b"\0" * 510)
        ordinary_tar = index + index_payload + (b"\0" * 1024)
        self.write_raw_tar(ordinary_tar + (b"\0" * 4096), file_count=1)
        with mock.patch.object(intake_bundle, "MAX_TAR_STREAM_BYTES", len(ordinary_tar)):
            self.assert_rejected_and_clean()

    def test_truncated_member_header_end_and_bad_gzip_crc_are_rejected(self):
        self.write_archive(self.valid_members())
        self.archive.write_bytes(self.archive.read_bytes()[:-5])
        self.write_manifest()
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
        self.archive.unlink()
        with self.assertRaises(BundleError) as raised:
            with self.run_staged():
                self.fail("missing archive was yielded")
        self.assertNotIn(str(self.root), str(raised.exception))
        self.assertNotIn(str(self.archive), str(raised.exception))
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
        fifo = self.root / "archive.fifo"
        os.mkfifo(fifo)
        code = (
            "from pathlib import Path\n"
            "from installation.websetup.bundle import BundleError, staged_bundle\n"
            "try:\n"
            f"    with staged_bundle(Path({str(fifo)!r}), Path({str(self.manifest)!r}), "
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

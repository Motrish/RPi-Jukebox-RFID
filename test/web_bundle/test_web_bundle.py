"""Behavioral tests for the offline web bundle producer and verifier."""

from __future__ import annotations

import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = REPOSITORY_ROOT / "tools" / "web_bundle.py"
REPOSITORY = "example-owner/phoniebox"
COMMIT = "0123456789abcdef0123456789abcdef01234567"


class WebBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(REPOSITORY_ROOT))
        cls.bundle = importlib.import_module("tools.web_bundle")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.build = self.root / "build"
        self.build.mkdir()
        (self.build / "index.html").write_bytes(b"<!doctype html><script src='/static/js/app.js'></script>")
        (self.build / "static" / "js").mkdir(parents=True)
        (self.build / "static" / "js" / "app.js").write_bytes(b"window.app = true;\n")
        (self.build / "static" / "css").mkdir(parents=True)
        (self.build / "static" / "css" / "app.css").write_bytes(b"body { color: #123; }\n")
        (self.build / "asset-manifest.json").write_bytes(b'{"files":{"main.js":"/static/js/app.js"}}\n')
        self.output = self.root / "output"

    def tearDown(self):
        self.temporary.cleanup()

    def run_cli(self, *arguments):
        return subprocess.run(
            [sys.executable, str(TOOL_PATH), *map(str, arguments)],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

    def package(self, output=None, repository=REPOSITORY, commit=COMMIT):
        destination = output or self.output
        return self.run_cli(
            "package",
            "--build-dir", self.build,
            "--output-dir", destination,
            "--repository", repository,
            "--commit", commit,
        )

    def verify(self, archive, manifest, repository=REPOSITORY, commit=COMMIT):
        return self.run_cli(
            "verify",
            "--archive", archive,
            "--manifest", manifest,
            "--repository", repository,
            "--commit", commit,
        )

    def run_main(self, *arguments):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return self.bundle.main(list(map(str, arguments)))

    def assert_no_output_pair(self, output):
        self.assertFalse(
            (Path(output) / "webapp-build.tar.gz").exists()
            and (Path(output) / "manifest.json").exists()
        )

    def test_package_is_deterministic_and_contains_exact_build_bytes(self):
        first = self.package(self.root / "first")
        self.assertEqual(first.returncode, 0, first.stderr)
        before = (self.root / "first" / "webapp-build.tar.gz").read_bytes()
        manifest_before = (self.root / "first" / "manifest.json").read_bytes()

        for item in self.build.rglob("*"):
            if item.is_file():
                os.utime(item, (1_800_000_000, 1_800_000_000))

        second = self.package(self.root / "second")
        self.assertEqual(second.returncode, 0, second.stderr)
        after = (self.root / "second" / "webapp-build.tar.gz").read_bytes()
        manifest_after = (self.root / "second" / "manifest.json").read_bytes()
        self.assertEqual(before, after)
        self.assertEqual(manifest_before, manifest_after)
        self.assertEqual(struct.unpack("<I", before[4:8])[0], 0)

        expected = {
            "index.html": (self.build / "index.html").read_bytes(),
            "static/js/app.js": (self.build / "static/js/app.js").read_bytes(),
            "static/css/app.css": (self.build / "static/css/app.css").read_bytes(),
            "asset-manifest.json": (self.build / "asset-manifest.json").read_bytes(),
        }
        with tarfile.open(fileobj=io.BytesIO(before), mode="r:gz") as archive:
            members = archive.getmembers()
            self.assertEqual([member.name for member in members], sorted(expected))
            for member in members:
                self.assertTrue(member.isfile())
                self.assertEqual(member.mode & 0o777, 0o644)
                self.assertEqual(member.mtime, 0)
                self.assertEqual(member.uid, 0)
                self.assertEqual(member.gid, 0)
                self.assertEqual(member.uname, "")
                self.assertEqual(member.gname, "")
                with archive.extractfile(member) as stream:
                    self.assertEqual(stream.read(), expected[member.name])

    def test_manifest_values_match_inputs_and_a_second_identity_verifies(self):
        result = self.package()
        self.assertEqual(result.returncode, 0, result.stderr)
        archive = self.output / "webapp-build.tar.gz"
        manifest_path = self.output / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(
            set(manifest),
            {
                "formatVersion", "kind", "repository", "backendCommit",
                "archiveName", "archiveSha256", "archiveSizeBytes", "fileCount",
            },
        )
        self.assertEqual(manifest["formatVersion"], 1)
        self.assertEqual(manifest["kind"], "phoniebox-webapp")
        self.assertEqual(manifest["repository"], REPOSITORY)
        self.assertEqual(manifest["backendCommit"], COMMIT)
        self.assertEqual(manifest["archiveName"], "webapp-build.tar.gz")
        self.assertEqual(manifest["archiveSha256"], hashlib.sha256(archive.read_bytes()).hexdigest())
        self.assertEqual(manifest["archiveSizeBytes"], archive.stat().st_size)
        self.assertEqual(manifest["fileCount"], 4)
        self.assertIs(type(manifest["formatVersion"]), int)
        self.assertIs(type(manifest["archiveSizeBytes"]), int)
        self.assertIs(type(manifest["fileCount"]), int)
        verified = self.verify(archive, manifest_path)
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertIn(REPOSITORY, verified.stdout)
        self.assertIn(COMMIT, verified.stdout)

        second_repository = "another-owner/phoniebox"
        second_commit = "abcdef0123456789abcdef0123456789abcdef01"
        second_output = self.root / "second-identity"
        second = self.package(second_output, second_repository, second_commit)
        self.assertEqual(second.returncode, 0, second.stderr)
        second_manifest = json.loads(
            (second_output / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(second_manifest["repository"], second_repository)
        self.assertEqual(second_manifest["backendCommit"], second_commit)
        checked = self.verify(
            second_output / "webapp-build.tar.gz",
            second_output / "manifest.json",
            second_repository,
            second_commit,
        )
        self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_verifier_rejects_wrong_expected_repository_or_commit(self):
        self.assertEqual(self.package().returncode, 0)
        archive = self.output / "webapp-build.tar.gz"
        manifest = self.output / "manifest.json"
        self.assertNotEqual(self.verify(archive, manifest, "other-owner/phoniebox").returncode, 0)
        self.assertNotEqual(self.verify(archive, manifest, commit="f" * 40).returncode, 0)

    def test_verifier_hashes_same_length_tampering_and_rejects_wrong_digest(self):
        self.assertEqual(self.package().returncode, 0)
        archive = self.output / "webapp-build.tar.gz"
        manifest = self.output / "manifest.json"
        original = archive.read_bytes()

        valid = self.verify(archive, manifest)
        self.assertEqual(valid.returncode, 0, valid.stderr)

        changed = bytearray(original)
        changed[len(changed) // 2] ^= 1
        archive.write_bytes(changed)
        self.assertEqual(archive.stat().st_size, len(original))
        self.assertNotEqual(self.verify(archive, manifest).returncode, 0)

        archive.write_bytes(original)
        altered_digest = json.loads(manifest.read_text(encoding="utf-8"))
        replacement = "f" * 64
        if replacement == altered_digest["archiveSha256"]:
            replacement = "e" * 64
        altered_digest["archiveSha256"] = replacement
        wrong_digest_path = self.root / "wrong-digest.json"
        wrong_digest_path.write_text(json.dumps(altered_digest), encoding="utf-8")
        self.assertNotEqual(self.verify(archive, wrong_digest_path).returncode, 0)

    def test_verifier_rejects_truncation_and_size_mismatch(self):
        self.assertEqual(self.package().returncode, 0)
        archive = self.output / "webapp-build.tar.gz"
        manifest = self.output / "manifest.json"
        original = archive.read_bytes()
        archive.write_bytes(original[:-7])
        self.assertNotEqual(self.verify(archive, manifest).returncode, 0)

        data = json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))
        data["archiveSizeBytes"] += 1
        (self.root / "wrong-size.json").write_text(json.dumps(data), encoding="utf-8")
        archive.write_bytes(original)
        self.assertNotEqual(self.verify(archive, self.root / "wrong-size.json").returncode, 0)

    def test_verifier_rejects_missing_fields_invalid_types_and_duplicate_keys(self):
        self.assertEqual(self.package().returncode, 0)
        archive = self.output / "webapp-build.tar.gz"
        manifest = json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))
        valid = self.verify(archive, self.output / "manifest.json")
        self.assertEqual(valid.returncode, 0, valid.stderr)
        invalid_documents = []
        for key in manifest:
            changed = dict(manifest)
            del changed[key]
            invalid_documents.append(json.dumps(changed))
        for key, value in (
            ("formatVersion", 2),
            ("formatVersion", 0),
            ("formatVersion", True),
            ("formatVersion", 1.5),
            ("formatVersion", "1"),
            ("kind", "other"),
            ("repository", "owner/repo/extra"),
            ("backendCommit", "A" * 40),
            ("archiveName", "../webapp-build.tar.gz"),
            ("archiveSha256", "A" * 64),
            ("archiveSizeBytes", True),
            ("archiveSizeBytes", 0),
            ("archiveSizeBytes", 1.5),
            ("archiveSizeBytes", "1"),
            ("fileCount", True),
            ("fileCount", 0),
            ("fileCount", 1.5),
            ("fileCount", "4"),
            ("fileCount", 4097),
        ):
            changed = dict(manifest)
            changed[key] = value
            invalid_documents.append(json.dumps(changed))
        changed = dict(manifest)
        changed["extra"] = "rejected"
        invalid_documents.append(json.dumps(changed))
        invalid_documents.extend(
            [
                json.dumps(manifest).replace('"formatVersion": 1', '"formatVersion": NaN'),
                json.dumps(manifest).replace('"formatVersion": 1', '"formatVersion": Infinity'),
                json.dumps(manifest)[:-1] + ', "formatVersion": 1}',
            ]
        )
        for index, document in enumerate(invalid_documents):
            candidate = self.root / f"manifest-{index}.json"
            candidate.write_text(document, encoding="utf-8")
            with self.subTest(document=index):
                self.assertNotEqual(self.verify(archive, candidate).returncode, 0)

        malformed_utf8 = self.root / "malformed-utf8.json"
        malformed_utf8.write_bytes(b"\xff\xfe")
        self.assertNotEqual(self.verify(archive, malformed_utf8).returncode, 0)

    def test_verifier_enforces_archive_and_manifest_byte_limits(self):
        self.assertEqual(self.package().returncode, 0)
        archive = self.output / "webapp-build.tar.gz"
        manifest = self.output / "manifest.json"
        self.assertEqual(self.verify(archive, manifest).returncode, 0)
        with mock.patch.object(self.bundle, "MAX_ARCHIVE_BYTES", archive.stat().st_size - 1):
            self.assertNotEqual(
                self.run_main(
                    "verify", "--archive", archive, "--manifest", manifest,
                    "--repository", REPOSITORY, "--commit", COMMIT,
                ),
                0,
            )
        with mock.patch.object(self.bundle, "MAX_MANIFEST_BYTES", manifest.stat().st_size - 1):
            self.assertNotEqual(
                self.run_main(
                    "verify", "--archive", archive, "--manifest", manifest,
                    "--repository", REPOSITORY, "--commit", COMMIT,
                ),
                0,
            )

    def test_producer_rejects_missing_index(self):
        (self.build / "index.html").unlink()
        result = self.package()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.output.exists())

    @unittest.skipUnless(os.name == "posix", "POSIX-only invalid filename fixtures")
    def test_producer_rejects_backslash_and_control_character_names(self):
        invalid_name = self.build / "bad\\name.js"
        invalid_name.write_bytes(b"bad")
        self.assertNotEqual(self.package(self.root / "name-output").returncode, 0)
        self.assert_no_output_pair(self.root / "name-output")
        invalid_name.unlink()

        control_name = self.build / "bad\nname.js"
        control_name.write_bytes(b"bad")
        self.assertNotEqual(self.package(self.root / "control-output").returncode, 0)
        self.assert_no_output_pair(self.root / "control-output")

    def test_producer_rejects_file_and_external_directory_symlinks(self):
        file_link = self.build / "linked.js"
        try:
            file_link.symlink_to(self.build / "index.html")
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation is unavailable on this host")
        file_output = self.root / "file-link-output"
        result = self.package(file_output)
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_output_pair(file_output)
        file_link.unlink()

        external = self.root / "outside"
        external.mkdir()
        (external / "secret.js").write_bytes(b"outside")
        directory_link = self.build / "linked-directory"
        directory_link.symlink_to(external, target_is_directory=True)
        output = self.root / "directory-link-output"
        result = self.package(output)
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_output_pair(output)
        directory_link.unlink()

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO creation is unavailable on this host")
    def test_producer_rejects_fifo_promptly(self):
        fifo = self.build / "pipe.js"
        os.mkfifo(fifo)
        fifo_output = self.root / "fifo-output"
        result = self.package(fifo_output)
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_output_pair(fifo_output)

    def test_producer_rejects_existing_outputs_and_output_inside_build_root(self):
        self.output.mkdir()
        (self.output / "manifest.json").write_bytes(b"keep")
        result = self.package()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.output / "manifest.json").read_bytes(), b"keep")
        nested = self.package(self.build / "nested-output")
        self.assertNotEqual(nested.returncode, 0)
        self.assert_no_output_pair(self.build / "nested-output")

    def test_producer_rejects_malformed_identity_and_preserves_each_existing_output(self):
        for repository, commit in (("owner/repo/extra", COMMIT), (REPOSITORY, "bad")):
            output = self.root / f"bad-identity-{len(commit)}"
            result = self.package(output, repository, commit)
            self.assertNotEqual(result.returncode, 0)
            self.assert_no_output_pair(output)

        for existing_name in ("webapp-build.tar.gz", "manifest.json"):
            output = self.root / f"existing-{existing_name.replace('.', '-')}"
            output.mkdir()
            sentinel = output / existing_name
            sentinel.write_bytes(b"keep this exact output")
            unrelated = output / "unrelated-sentinel.txt"
            unrelated.write_bytes(b"also keep")
            result = self.package(output)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(sentinel.read_bytes(), b"keep this exact output")
            self.assertEqual(unrelated.read_bytes(), b"also keep")
            self.assert_no_output_pair(output)

    def test_producer_enforces_file_and_size_limits_with_small_fixtures(self):
        with mock.patch.object(self.bundle, "MAX_FILES", 2):
            too_many = self.run_main(
                "package", "--build-dir", self.build, "--output-dir", self.root / "count-limit",
                "--repository", REPOSITORY, "--commit", COMMIT,
            )
        self.assertNotEqual(too_many, 0)

        with mock.patch.object(self.bundle, "MAX_TOTAL_INPUT_BYTES", 4):
            too_large = self.run_main(
                "package", "--build-dir", self.build, "--output-dir", self.root / "size-limit",
                "--repository", REPOSITORY, "--commit", COMMIT,
            )
        self.assertNotEqual(too_large, 0)

        with mock.patch.object(self.bundle, "MAX_ARCHIVE_BYTES", 1):
            archive_too_large = self.run_main(
                "package", "--build-dir", self.build, "--output-dir", self.root / "archive-limit",
                "--repository", REPOSITORY, "--commit", COMMIT,
            )
        self.assertNotEqual(archive_too_large, 0)

        with mock.patch.object(self.bundle, "MAX_MANIFEST_BYTES", 1):
            manifest_too_large = self.run_main(
                "package", "--build-dir", self.build, "--output-dir", self.root / "manifest-limit",
                "--repository", REPOSITORY, "--commit", COMMIT,
            )
        self.assertNotEqual(manifest_too_large, 0)

    def test_cli_reports_success_and_safe_failure_with_nonzero_status(self):
        successful = self.package()
        self.assertEqual(successful.returncode, 0, successful.stderr)
        self.assertNotIn("<!doctype html>", successful.stdout + successful.stderr)
        failed = self.run_cli(
            "verify", "--archive", self.output / "missing.tar.gz",
            "--manifest", self.output / "missing.json",
            "--repository", REPOSITORY, "--commit", COMMIT,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertNotIn(str(self.root), failed.stdout + failed.stderr)


if __name__ == "__main__":
    unittest.main()

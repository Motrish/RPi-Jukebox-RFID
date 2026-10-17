"""Behavioral tests for the offline web bundle producer and verifier."""

from __future__ import annotations

import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
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
        )

    def package(self, output=None):
        destination = output or self.output
        return self.run_cli(
            "package",
            "--build-dir", self.build,
            "--output-dir", destination,
            "--repository", REPOSITORY,
            "--commit", COMMIT,
        )

    def verify(self, archive, manifest, repository=REPOSITORY, commit=COMMIT):
        return self.run_cli(
            "verify",
            "--archive", archive,
            "--manifest", manifest,
            "--repository", repository,
            "--commit", commit,
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
                with archive.extractfile(member) as stream:
                    self.assertEqual(stream.read(), expected[member.name])

    def test_package_manifest_and_offline_verification_match_identity_and_digest(self):
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
        self.assertEqual(manifest["archiveSha256"], hashlib.sha256(archive.read_bytes()).hexdigest())
        verified = self.verify(archive, manifest_path)
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertIn(REPOSITORY, verified.stdout)
        self.assertIn(COMMIT, verified.stdout)

    def test_verifier_rejects_wrong_expected_repository_or_commit(self):
        self.assertEqual(self.package().returncode, 0)
        archive = self.output / "webapp-build.tar.gz"
        manifest = self.output / "manifest.json"
        self.assertNotEqual(self.verify(archive, manifest, "other-owner/phoniebox").returncode, 0)
        self.assertNotEqual(self.verify(archive, manifest, commit="f" * 40).returncode, 0)

    def test_verifier_rejects_archive_tampering_truncation_and_size_mismatch(self):
        self.assertEqual(self.package().returncode, 0)
        archive = self.output / "webapp-build.tar.gz"
        manifest = self.output / "manifest.json"
        original = archive.read_bytes()
        archive.write_bytes(original[:-7])
        self.assertNotEqual(self.verify(archive, manifest).returncode, 0)
        archive.write_bytes(original + b"tampered")
        self.assertNotEqual(self.verify(archive, manifest).returncode, 0)

        data = json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))
        data["archiveSizeBytes"] += 1
        (self.root / "wrong-size.json").write_text(json.dumps(data), encoding="utf-8")
        archive.write_bytes(original)
        self.assertNotEqual(self.verify(archive, self.root / "wrong-size.json").returncode, 0)

    def test_verifier_rejects_invalid_schema_identity_types_and_duplicate_keys(self):
        self.assertEqual(self.package().returncode, 0)
        archive = self.output / "webapp-build.tar.gz"
        manifest = json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))
        invalid_documents = []
        for key, value in (
            ("formatVersion", 2),
            ("kind", "other"),
            ("repository", "owner/repo/extra"),
            ("backendCommit", "A" * 40),
            ("archiveName", "../webapp-build.tar.gz"),
            ("archiveSha256", "A" * 64),
            ("archiveSizeBytes", True),
            ("fileCount", 0),
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
                json.dumps(manifest)[:-1] + ', "formatVersion": 1}',
            ]
        )
        for index, document in enumerate(invalid_documents):
            candidate = self.root / f"manifest-{index}.json"
            candidate.write_text(document, encoding="utf-8")
            with self.subTest(document=index):
                self.assertNotEqual(self.verify(archive, candidate).returncode, 0)

    def test_producer_rejects_missing_index_symlink_and_invalid_relative_names(self):
        (self.build / "index.html").unlink()
        result = self.package()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.output.exists())

        (self.build / "index.html").write_bytes(b"index")
        link = self.build / "linked.js"
        try:
            link.symlink_to(self.build / "index.html")
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation is unavailable on this host")
        self.assertNotEqual(self.package(self.root / "symlink-output").returncode, 0)
        link.unlink()

        invalid_name = self.build / "bad\\name.js"
        invalid_name.write_bytes(b"bad")
        self.assertNotEqual(self.package(self.root / "name-output").returncode, 0)

    def test_producer_rejects_existing_outputs_and_output_inside_build_root(self):
        self.output.mkdir()
        (self.output / "manifest.json").write_bytes(b"keep")
        result = self.package()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.output / "manifest.json").read_bytes(), b"keep")
        self.assertNotEqual(self.package(self.build / "nested-output").returncode, 0)

    def test_producer_enforces_file_and_size_limits_with_small_fixtures(self):
        with mock.patch.object(self.bundle, "MAX_FILES", 2):
            too_many = self.bundle.main(
                ["package", "--build-dir", str(self.build), "--output-dir", str(self.root / "count-limit"),
                 "--repository", REPOSITORY, "--commit", COMMIT]
            )
        self.assertNotEqual(too_many, 0)

        with mock.patch.object(self.bundle, "MAX_TOTAL_INPUT_BYTES", 4):
            too_large = self.bundle.main(
                ["package", "--build-dir", str(self.build), "--output-dir", str(self.root / "size-limit"),
                 "--repository", REPOSITORY, "--commit", COMMIT]
            )
        self.assertNotEqual(too_large, 0)

        with mock.patch.object(self.bundle, "MAX_ARCHIVE_BYTES", 1):
            archive_too_large = self.bundle.main(
                ["package", "--build-dir", str(self.build), "--output-dir", str(self.root / "archive-limit"),
                 "--repository", REPOSITORY, "--commit", COMMIT]
            )
        self.assertNotEqual(archive_too_large, 0)

        with mock.patch.object(self.bundle, "MAX_MANIFEST_BYTES", 1):
            manifest_too_large = self.bundle.main(
                ["package", "--build-dir", str(self.build), "--output-dir", str(self.root / "manifest-limit"),
                 "--repository", REPOSITORY, "--commit", COMMIT]
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

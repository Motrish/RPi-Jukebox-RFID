"""Portable behavioral tests for the persisted P01b library catalog."""

import os
from pathlib import Path
import sys
import sqlite3
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

_STAGE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_STAGE_ROOT / "src" / "jukebox"))

# E402: isolated stage source root must be added before project imports.
from jukebox.contracts import ContractValidationError  # noqa: E402
from components import library_catalog  # noqa: E402

CatalogError = library_catalog.CatalogError
LibraryCatalog = library_catalog.LibraryCatalog


@unittest.skipUnless(
    sys.platform.startswith("linux"),
    "catalog filesystem semantics require the Linux descriptor backend",
)
class LibraryCatalogTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name) / "music"
        self.root.mkdir()
        self.db = Path(self._temp.name) / "catalog.sqlite3"
        self.catalog = LibraryCatalog(
            database_path=self.db,
            library_root=self.root,
        )
        self.addCleanup(self.catalog.close)

    def write(self, relative_path, content=b"audio"):
        path = self.root.joinpath(*relative_path.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def register(self, relative_path="album/track.flac", content=b"audio"):
        self.write(relative_path, content)
        return self.catalog.register_file(relative_path)

    def test_register_get_list_resolve_return_closed_values(self):
        registered = self.register()
        self.assertEqual(
            set(registered), {"libraryId", "displayName", "availability"}
        )
        self.assertRegex(registered["libraryId"], r"\Alib_[0-9a-f]{32}\Z")
        self.assertEqual(registered["displayName"], "track.flac")
        self.assertEqual(registered["availability"], "AVAILABLE")
        self.assertEqual(
            self.catalog.get_media(registered["libraryId"]), registered
        )
        page = self.catalog.list_media()
        self.assertEqual(set(page), {"items", "nextCursor"})
        self.assertEqual(page["items"], [registered])
        self.assertIsNone(page["nextCursor"])
        self.assertEqual(
            self.catalog.list_media(limit=200)["items"], [registered]
        )
        resolved = self.catalog.resolve(registered["libraryId"])
        library_id = registered["libraryId"]
        self.assertEqual(resolved, {
            "libraryId": registered["libraryId"],
            "mpdReference": "album/track.flac",
        })
        self.assertNotIsInstance(resolved, (tuple, list))
        registered["displayName"] = "changed"
        page["items"][0]["availability"] = "MISSING"
        resolved["mpdReference"] = "changed"
        self.assertEqual(
            self.catalog.get_media(library_id)["displayName"], "track.flac"
        )
        self.assertEqual(
            self.catalog.list_media()["items"][0]["availability"], "AVAILABLE"
        )
        self.assertEqual(
            self.catalog.resolve(library_id)["mpdReference"],
            "album/track.flac",
        )

    def test_same_active_fingerprint_survives_reopen(self):
        first = self.register("same/name.mp3")
        self.catalog.close()
        reopened = LibraryCatalog(
            database_path=self.db,
            library_root=self.root,
        )
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.register_file("same/name.mp3"), first)
        self.assertEqual(reopened.get_media(first["libraryId"]), first)

    def test_aliases_and_renames_get_distinct_ids(self):
        original_path = self.write("one/song.ogg")
        (self.root / "two").mkdir()
        os.link(original_path, self.root / "two" / "song.ogg")
        first = self.catalog.register_file("one/song.ogg")
        alias = self.catalog.register_file("two/song.ogg")
        self.assertNotEqual(first["libraryId"], alias["libraryId"])

        original_path.rename(self.root / "one" / "moved.ogg")
        self.assertEqual(
            self.catalog.get_media(first["libraryId"])["availability"],
            "MISSING",
        )
        moved = self.catalog.register_file("one/moved.ogg")
        self.assertNotEqual(first["libraryId"], moved["libraryId"])

    def test_replacement_tombstones_old_id_and_registers_new_id(self):
        first = self.register("replace.wav", b"old")
        path = self.root / "replace.wav"
        replacement = self.root / "replacement.tmp"
        replacement.write_bytes(b"new-content")
        os.replace(replacement, path)

        self.assertEqual(
            self.catalog.get_media(first["libraryId"])["availability"],
            "MISSING",
        )
        second = self.catalog.register_file("replace.wav")
        self.assertNotEqual(first["libraryId"], second["libraryId"])
        self.assertEqual(
            self.catalog.get_media(first["libraryId"])["availability"],
            "MISSING",
        )
        self.assertIsNone(self.catalog.resolve(first["libraryId"]))

    def test_missing_file_is_a_persistent_tombstone(self):
        item = self.register("gone.mp3")
        (self.root / "gone.mp3").unlink()
        self.assertEqual(
            self.catalog.get_media(item["libraryId"])["availability"],
            "MISSING",
        )
        self.write("gone.mp3", b"back")
        self.assertEqual(
            self.catalog.get_media(item["libraryId"])["availability"],
            "MISSING",
        )
        self.assertIsNone(self.catalog.resolve(item["libraryId"]))
        new_item = self.catalog.register_file("gone.mp3")
        self.assertNotEqual(item["libraryId"], new_item["libraryId"])

    def test_list_is_id_ordered_and_pages_tombstones(self):
        items = [self.register("%02d.mp3" % index) for index in range(5)]
        ordered = sorted(
            items, key=lambda item: item["libraryId"].encode("ascii")
        )
        page1 = self.catalog.list_media(limit=2)
        self.assertEqual(page1["items"], ordered[:2])
        self.assertEqual(page1["nextCursor"], ordered[1]["libraryId"])
        page2 = self.catalog.list_media(limit=2, cursor=page1["nextCursor"])
        page3 = self.catalog.list_media(limit=2, cursor=page2["nextCursor"])
        self.assertEqual(page2["items"] + page3["items"], ordered[2:])
        self.assertIsNone(page3["nextCursor"])

        deleted_id = ordered[2]["libraryId"]
        (self.root / ordered[2]["displayName"]).unlink()
        all_items = self.catalog.list_media(limit=200)["items"]
        deleted = next(
            item for item in all_items if item["libraryId"] == deleted_id
        )
        self.assertEqual(deleted["availability"], "MISSING")

    def test_argument_validation_uses_contract_error(self):
        invalid_paths = [
            "", None, 7, ["x"], b"x", "\ud800", "\x00", "\x01", "\x1f", "\x7f",
            "/absolute.mp3", "trailing/", "a//b", "./a", "../a", "a/../b",
            "a\\b", "a:b", "http://host/a", "bad\nname", "x" * 4096,
            "x" * 256, "é" * 128,
        ]
        for relative_path in invalid_paths:
            with self.subTest(relative_path=repr(relative_path)[:24]):
                with self.assertRaises(ContractValidationError):
                    self.catalog.register_file(relative_path)

        for limit in (True, False, 0, 201, 1.0, "2"):
            with self.subTest(limit=limit):
                with self.assertRaises(ContractValidationError):
                    self.catalog.list_media(limit=limit)
        for cursor in ("", "bad cursor", "/etc/passwd", "x" * 129):
            with self.subTest(cursor=cursor[:24]):
                with self.assertRaises(ContractValidationError):
                    self.catalog.list_media(cursor=cursor)
        for library_id in ("", "../x", "x x", "x" * 129):
            with self.subTest(library_id=library_id[:24]):
                with self.assertRaises(ContractValidationError):
                    self.catalog.get_media(library_id)

    def test_database_location_and_future_schema_are_rejected(self):
        inside_database = self.root / "catalog.sqlite3"
        with self.assertRaises(CatalogError):
            LibraryCatalog(
                database_path=inside_database,
                library_root=self.root,
            )
        self.assertFalse(inside_database.exists())
        self.assertEqual(list(self.root.iterdir()), [])

        future_database = Path(self._temp.name) / "future.sqlite3"
        connection = sqlite3.connect(str(future_database))
        try:
            connection.execute("PRAGMA user_version = 9999")
            connection.commit()
        finally:
            connection.close()
        original_bytes = future_database.read_bytes()
        with self.assertRaises(CatalogError):
            LibraryCatalog(
                database_path=future_database,
                library_root=self.root,
            )
        self.assertEqual(future_database.read_bytes(), original_bytes)

    def test_unknown_valid_id_returns_none(self):
        self.assertIsNone(self.catalog.get_media("lib_" + "0" * 32))
        self.assertIsNone(self.catalog.resolve("lib_" + "0" * 32))

    def test_root_binding_rejects_a_different_root(self):
        self.register()
        other_root = Path(self._temp.name) / "other"
        other_root.mkdir()
        other = None
        try:
            with self.assertRaises(CatalogError) as caught:
                other = LibraryCatalog(
                    database_path=self.db,
                    library_root=other_root,
                )
                other.list_media()
            self.assertEqual(caught.exception.safe.code, "ROOT_CHANGED")
            self.assertNotIn(
                str(other_root), caught.exception.safe.message
            )
        finally:
            if other is not None:
                other.close()

    def test_close_is_idempotent_and_closed_operations_fail_safely(self):
        self.catalog.close()
        self.catalog.close()
        with self.assertRaises(CatalogError) as caught:
            self.catalog.list_media()
        self.assertEqual(caught.exception.safe.code, "STORE_UNAVAILABLE")

    def test_parallel_registration_of_same_path_has_one_identity(self):
        self.write("parallel.mp3")

        def attempt(_index):
            try:
                return self.catalog.register_file("parallel.mp3"), None
            except CatalogError as error:
                return None, error.safe.code

        with ThreadPoolExecutor(max_workers=4) as pool:
            outcomes = list(pool.map(attempt, range(4)))
        for _result, error_code in outcomes:
            self.assertIn(error_code, (None, "STORE_BUSY"))
        final_result = self.catalog.register_file("parallel.mp3")
        for result, _error_code in outcomes:
            if result is not None:
                self.assertEqual(
                    result["libraryId"], final_result["libraryId"]
                )
        rows = self.catalog.list_media()["items"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["libraryId"], final_result["libraryId"])

    def test_database_busy_is_reported_without_a_partial_registration(self):
        self.write("busy.mp3")

        blocker = sqlite3.connect(
            str(self.db), timeout=0, isolation_level=None
        )
        try:
            blocker.execute("BEGIN EXCLUSIVE")
            with self.assertRaises(CatalogError) as caught:
                self.catalog.register_file("busy.mp3")
            self.assertEqual(caught.exception.safe.code, "STORE_BUSY")
        finally:
            blocker.rollback()
            blocker.close()
        self.assertEqual(self.catalog.list_media()["items"], [])

    def test_filesystem_uncertainty_is_not_a_tombstone(self):
        item = self.register("uncertain.mp3")
        # Patch only the probe to make permission behavior deterministic.
        with mock.patch.object(
            self.catalog,
            "_probe_path",
            side_effect=PermissionError("private/path"),
        ):
            result = self.catalog.get_media(item["libraryId"])
            self.assertEqual(result["availability"], "UNKNOWN")
            with self.assertRaises(CatalogError) as caught:
                self.catalog.resolve(item["libraryId"])
        self.assertEqual(caught.exception.safe.code, "FILESYSTEM_UNAVAILABLE")
        self.assertNotIn("private/path", caught.exception.safe.message)
        self.assertEqual(
            self.catalog.get_media(item["libraryId"])["availability"],
            "AVAILABLE",
        )


class PortablePreflightTests(unittest.TestCase):
    def test_import_has_no_filesystem_effect(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(_STAGE_ROOT / "src" / "jukebox")
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-c",
                    "import components.library_catalog",
                ],
                cwd=directory,
                env=environment,
                timeout=5,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_non_linux_fails_before_creating_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "music"
            root.mkdir()
            database = Path(directory) / "catalog.sqlite3"
            with mock.patch.object(sys, "platform", "win32"):
                with self.assertRaises(CatalogError) as caught:
                    LibraryCatalog(database_path=database, library_root=root)
            self.assertEqual(
                caught.exception.safe.code,
                "UNSUPPORTED_PLATFORM",
            )
            self.assertFalse(database.exists())


if __name__ == "__main__":
    unittest.main()

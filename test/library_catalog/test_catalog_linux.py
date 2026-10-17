"""Linux descriptor-boundary tests for the P01b library catalog."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

_STAGE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_STAGE_ROOT / "src" / "jukebox"))

# E402: isolated stage source root must be added before project imports.
from components import library_catalog  # noqa: E402

CatalogError = library_catalog.CatalogError
LibraryCatalog = library_catalog.LibraryCatalog


@unittest.skipUnless(
    sys.platform.startswith("linux"),
    "requires Linux O_PATH and dir_fd semantics",
)
class LinuxLibraryCatalogTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.base = Path(self._temp.name)
        self.root = self.base / "music"
        self.root.mkdir()
        self.db = self.base / "catalog.sqlite3"
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

    def test_regular_file_resolves_and_directory_is_rejected(self):
        self.write("nested/track.flac")
        item = self.catalog.register_file("nested/track.flac")
        self.assertEqual(
            self.catalog.resolve(item["libraryId"])["mpdReference"],
            "nested/track.flac",
        )
        with self.assertRaises(CatalogError) as caught:
            self.catalog.register_file("nested")
        self.assertEqual(caught.exception.safe.code, "MEDIA_UNAVAILABLE")

    def test_final_and_parent_symlinks_are_rejected(self):
        outside = self.base / "outside.mp3"
        outside.write_bytes(b"outside")
        (self.root / "final.mp3").symlink_to(outside)
        (self.base / "outside-dir").mkdir()
        (self.base / "outside-dir" / "track.mp3").write_bytes(b"outside")
        (self.root / "intermediate").symlink_to(
            self.base / "outside-dir", target_is_directory=True
        )
        for relative_path in ("final.mp3", "intermediate/track.mp3"):
            with self.subTest(relative_path=relative_path):
                with self.assertRaises(CatalogError) as caught:
                    self.catalog.register_file(relative_path)
                self.assertEqual(
                    caught.exception.safe.code, "MEDIA_UNAVAILABLE"
                )

    def test_fifo_is_opened_without_blocking_and_rejected(self):
        os.mkfifo(self.root / "pipe")
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(_STAGE_ROOT / "src" / "jukebox")
        environment["P01_ROOT"] = str(self.root)
        environment["P01_DATABASE"] = str(self.base / "fifo-catalog.sqlite3")
        child = (
            "import os\n"
            "import components.library_catalog as catalog_module\n"
            "CatalogError = catalog_module.CatalogError\n"
            "LibraryCatalog = catalog_module.LibraryCatalog\n"
            "catalog = LibraryCatalog(\n"
            "    database_path=os.environ['P01_DATABASE'],\n"
            "    library_root=os.environ['P01_ROOT'],\n"
            ")\n"
            "try:\n"
            "    catalog.register_file('pipe')\n"
            "except CatalogError as error:\n"
            "    assert error.safe.code == 'MEDIA_UNAVAILABLE'\n"
            "else:\n"
            "    raise AssertionError('FIFO was accepted')\n"
            "finally:\n"
            "    catalog.close()\n"
        )
        subprocess.run(
            [sys.executable, "-B", "-c", child],
            cwd=self.base,
            env=environment,
            timeout=5,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def test_replacement_touch_and_chmod_invalidate_old_ids(self):
        path = self.write("change.mp3", b"a")
        first = self.catalog.register_file("change.mp3")
        replacement = self.root / "replacement.tmp"
        replacement.write_bytes(b"replacement")
        os.replace(replacement, path)
        self.assertEqual(
            self.catalog.get_media(first["libraryId"])["availability"],
            "MISSING",
        )
        second = self.catalog.register_file("change.mp3")
        self.assertNotEqual(first["libraryId"], second["libraryId"])

        third_path = self.write("metadata.mp3")
        third = self.catalog.register_file("metadata.mp3")
        stat = third_path.stat()
        os.utime(
            third_path,
            ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000),
        )
        self.assertEqual(
            self.catalog.get_media(third["libraryId"])["availability"],
            "MISSING",
        )

        fourth_path = self.write("mode.mp3")
        fourth = self.catalog.register_file("mode.mp3")
        fourth_path.chmod(0o600)
        self.assertEqual(
            self.catalog.get_media(fourth["libraryId"])["availability"],
            "MISSING",
        )

    def test_root_replacement_or_rebinding_is_rejected(self):
        self.write("rooted.mp3")
        item = self.catalog.register_file("rooted.mp3")
        saved_root = self.base / "saved-music"
        self.root.rename(saved_root)
        self.root.mkdir()
        self.write("rooted.mp3", b"substitute")
        with self.assertRaises(CatalogError) as caught:
            self.catalog.get_media(item["libraryId"])
        self.assertEqual(caught.exception.safe.code, "ROOT_CHANGED")


if __name__ == "__main__":
    unittest.main()

"""Side-effect boundaries for runtime dispatch bootstrap (playlist DB)."""

import os
import sys
import time
import unittest
import uuid
from unittest import mock

from components.playback_session.runtime import LocalPlaybackRuntime, _OwnerBusy


def _db_path():
    # Lexically valid POSIX path (leading "/"), unique, never created on disk.
    return "/tmp/c5b-{}-nested/dir/playlists.db".format(uuid.uuid4().hex)


class _ModuleOS:
    """In-module os proxy: POSIX-looking name, everything else the real os."""

    name = "posix"

    def __getattr__(self, item):
        return getattr(os, item)


class _ModuleSys:
    """In-module sys proxy: linux platform, everything else the real sys."""

    platform = "linux"

    def __getattr__(self, item):
        return getattr(sys, item)


class DispatchBootstrapSideEffectTests(unittest.TestCase):
    def _runtime(self, db_path):
        return LocalPlaybackRuntime(
            database_path="/tmp/library.sqlite",
            library_root="/srv/audio",
            credential_path="/etc/mpd.secret",
            playlist_database_path=db_path,
        )

    def test_constructor_does_not_create_playlist_database(self):
        db_path = _db_path()
        self.assertFalse(os.path.exists(db_path))
        runtime = self._runtime(db_path)
        self.assertEqual(runtime.playlist_database_path, db_path)
        self.assertIsNone(runtime._durable_dispatch)
        self.assertFalse(os.path.exists(db_path))

    def test_owner_failure_does_not_initialize_playlist_database(self):
        db_path = _db_path()
        runtime = self._runtime(db_path)

        def failing_bootstrap(_deadline):
            raise _OwnerBusy()

        runtime._bootstrap_core = failing_bootstrap
        with mock.patch("components.playlists.store.PlaylistStore") as store, \
                mock.patch("components.playback_session.runtime.os", _ModuleOS()), \
                mock.patch("components.playback_session.runtime.sys", _ModuleSys()):
            state = runtime.start(deadline=time.monotonic() + 2.0)
        store.assert_not_called()
        self.assertEqual(state["failure"]["code"], "OWNER_BUSY")
        self.assertFalse(state["ready"])
        self.assertIsNone(runtime._durable_dispatch)
        self.assertFalse(os.path.exists(db_path))


if __name__ == "__main__":
    unittest.main()

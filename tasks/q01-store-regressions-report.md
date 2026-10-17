# Q01 Store Regression Tests

This handoff adds only `test/playlists/test_store_regressions.py` in the exclusive Q01 stage at `G:\Entwicklung\phoniebox-staging\q01-store`. The P03b product stage remained read-only; no runtime files or remote Git references were changed here. The stage contains test artifacts, not a full repository checkout.

The migration regression builds the historical P03a2 three-table SQLite schema from pinned commit `9c859a2e91f90e25d84f4e32ffe9ab369f0d5202` using inline DDL, inserts a synthetic playlist, entry, and persisted canonical command result, and confirms that queue tables are absent before opening the current `PlaylistStore`. It then checks playlist readback and idempotent command replay, verifies additive queue-table creation, and exercises queue creation, playlist loading, append, and readback.

The WAL regression creates a queue through the public store API and installs a SQLite trace callback on the `QUEUE_GET` connection. At the exact entry-select statement, the callback performs a real `QUEUE_APPEND` through `PlaylistStore.execute`. The in-progress read must return the pre-append revision and entries; the next read must return the committed revision and both entries. This makes the interleaving deterministic and avoids timing-based concurrency tests.

Validation results:

- Targeted Q01 tests, from `G:\Entwicklung\phoniebox-staging\q01-store`:
  ` $env:PYTHONPATH='G:\Entwicklung\phoniebox-staging\p03b\src\jukebox'; python -B -m unittest discover -s test/playlists -p test_store_regressions.py -v ` — **2 tests passed, exit 0**.
- Existing P03b playlist suite, from read-only `G:\Entwicklung\phoniebox-staging\p03b`:
  ` $env:PYTHONPATH='G:\Entwicklung\phoniebox-staging\p03b\src\jukebox'; python -B -m unittest discover -s test/playlists -p 'test_*.py' -v ` — **36 tests passed, exit 0**.
- Targeted flake8, from Q01 stage, using `G:\Entwicklung\phoniebox-tools\python` on `PYTHONPATH`:
  `python -m flake8 --max-line-length=127 --max-complexity=12 --ignore=E126,E127,E128,W503,F824 --per-file-ignores=__init__.py:F401 test/playlists/test_store_regressions.py` — **exit 0**.

An initial targeted run failed during temporary-directory cleanup because fixture SQLite connections were not explicitly closed on Windows. The test fixture was corrected to use `contextlib.closing`; the final targeted run passed. No failure against product behavior was observed. No GitHub commit, branch update, upload, or CI run was performed by this test-authoring step; publication and CI observation remain with Root.

Publication readback (read-only verification):

- Root published commit `7cabbafa7b6440f57a9d265a63f052e2a08d6edf` on `future3/test-store-regressions`, parent `b2be3f39f54d8f492966a407c3b7293d1311e1fa`, tree `7addf447bc51354995110b78df485778de611a1f`.
- GitHub compare from the stated parent reports exactly one commit ahead, zero behind, and one added path: `test/playlists/test_store_regressions.py` (190 additions, 0 deletions). Remote file readback returned blob `030f993e1c35aec199ec33c91f0e8c6c1ad29a25`. That matches the staged file's Git blob SHA after removing the local UTF-8 BOM; the code content is otherwise identical.
- At verification time, GitHub combined commit status contained no checks and the commit-associated PR workflow run query returned no runs. Therefore CI has not been observed as started or completed in this readback; Root owns subsequent CI observation.

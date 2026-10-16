# P03b – SQLite-Queue und Playlistübergänge

Stand: 16.10.2026. Stage `G:/Entwicklung/phoniebox-staging/p03b`, Basis `9c859a2e91f90e25d84f4e32ffe9ab369f0d5202` (P03a2). Die zwei für den Publish freigegebenen Dateien sind `src/jukebox/components/playlists/store.py` und `test/playlists/test_queue_store.py`. Die kopierte P03a2-Datei `test/playlists/test_store.py` und `src/jukebox/components/playlists/__init__.py` blieben byteidentisch zu P03a2. Root bestätigt vor Publish 36 Storetests, 22 Contracttests und Lint Exit 0. Root-SHA, Tree, Readback und CI folgen nach Veröffentlichung.

## Umfang

Der bestehende PlaylistStore und sein `command_log` bleiben die einzige Store-/Idempotenzinstanz. Das Schema ergänzt idempotent `queues` und `queue_entries` mit `CREATE TABLE IF NOT EXISTS`; bestehende Playlist-/Ledgertabellen und -daten bleiben erhalten. Queue-Source-Playlistfelder haben absichtlich keinen Playlist-Fremdschlüssel, sodass Löschung einer Playlist die Queueherkunft als Historie nicht entfernt.

Implementiert sind die neun CONTRACT-1-Schreibaktionen `QUEUE_CREATE`, `QUEUE_LOAD_PLAYLIST`, `QUEUE_APPEND`, `QUEUE_REMOVE`, `QUEUE_MOVE`, `QUEUE_SET_MODES`, `QUEUE_SET_CURRENT`, `QUEUE_SAVE_NEW_PLAYLIST` und `QUEUE_SAVE_PLAYLIST`, außerdem atomarer `get_queue`. Alle Änderungen und vollständigen Ergebnisse laufen durch die bestehende `BEGIN IMMEDIATE`-Transaktion und das vorhandene Command-Ledger. LOAD/SAVE prüfen beide beteiligten Revisionen vor der Mutation und sammeln beide Konflikte; Laden/Entfernen der ausgewählten Entry-ID wird abgelehnt; Queueverschieben erhält die Auswahl. LOAD und beide SAVE-Varianten erzeugen neue Entry-IDs, speichern Herkunft nur beim Laden und erhöhen jeweils nur die betroffene Revision. Queue-Herkunft überlebt Playlistlöschung.

## RED-Nachweis

Tatsächlicher früher RED-Aufruf gegen den unveränderten P03a2-Store, mit den damals vorhandenen 12 neuen Queuefällen:

```powershell
$env:PYTHONPATH='G:\Entwicklung\phoniebox-staging\p03b\src\jukebox;G:\Entwicklung\phoniebox-staging\p03b\src\jukebox\jukebox'
python -m unittest discover -s test\playlists -p test_queue_store.py -v
exit $LASTEXITCODE
```

Exitcode 1; `Ran 12 tests`, `FAILED (errors=12)`. Die Queuebefehle scheiterten erwartungsgemäß mit `NotImplementedError` („This store slice supports playlist write actions only.“); Queueaktionen und `get_queue` waren zu diesem Zeitpunkt noch nicht implementiert.

## Zwischenfehler und Korrekturen

Ein späterer Lauf der ersten Implementierung mit 15 Queuefällen hatte einen Fehler und einen Folgefehler im Test-Teardown. Der MAX-Playlistrevision-Test erwartete `REVISION_EXHAUSTED`, aber übergab absichtlich noch die alte Queue-Revision; korrekt war `REVISION_CONFLICT`. Die Fixture wurde so geändert, dass sie die aktuelle MAX-Queue-Revision übergibt und danach die Zielplaylist-Max-Revision prüft. Der Fehler im Teardown entstand, weil ein `with sqlite3.connect(...)` den SQLite-Handle unter Windows nicht schließt; der Test verwendet jetzt `try/finally` mit explizitem `close()`.

Bei der ersten vollständigen Kombination aus Store- und Contracttests liefen die damaligen 35 Storetests erfolgreich, danach schlug `test_v1` mit `FileNotFoundError` fehl: Die unveränderte `test/contracts/fixtures/v1.json` war noch nicht in den isolierten Stage kopiert. Ich kopierte die A02-Fixture unverändert nur als lokale Testabhängigkeit nach P03b; kein Contractcode wurde verändert. Der anschließende Contracttestlauf war erfolgreich.

## Finale Prüfungen

Exakter finaler kombinierter Aufruf:

```powershell
$env:PYTHONPATH='G:\Entwicklung\phoniebox-staging\p03b\src\jukebox;G:\Entwicklung\phoniebox-staging\a02\src\jukebox'
python -m unittest discover -s test\playlists -p 'test_*.py' -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m unittest discover -s test\contracts -p test_v1.py -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$env:PYTHONPATH='G:\Entwicklung\phoniebox-tools\python'
python -m flake8 --max-line-length=127 --max-complexity=12 --ignore=E126,E127,E128,W503,F824 --per-file-ignores=__init__.py:F401 src test
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m py_compile src\jukebox\components\playlists\store.py test\playlists\test_queue_store.py
```

Exitcode 0. Storetests: 36/36 bestanden, darunter 20 unveränderte P03a2-Regressionen und 16 neue Queuefälle. Contracttests: 22/22 bestanden. Flake8: keine Befunde. `py_compile`: erfolgreich. Root hat diese Ergebnisse unabhängig frisch bestätigt.

Die Queuefälle prüfen Create/Append/Remove/Move/Modi/Auswahl, No-op-Revisionen, Duplicate-IDs und lückenlose Ordnung, ausgewählte Eintragsguards, LOAD-Reset/Copies, SAVE-Copies mit unabhängigen Revisionen, vollständige Doppelkonflikte, Idempotenz-Replay und parallele gleiche `commandId`, Rollback für LOAD/SAVE-New/SAVE-Replace, Revision-Maximum, additive Schemainitialisierung und Wiederöffnung der Datenbank.

P03b enthält keine Runtime-, Player-, Transport-, Plugin-, Hardware- oder zusätzlichen Dependencyänderungen. Kein Branch, Commit oder Blob wurde von diesem Stage aus erzeugt.

## Remote-Publish und CI

P03b-Implementierung und lokaler Stage-Nachweis wurden eingefroren, bevor Root die zwei freigegebenen Dateien atomar publizierte. Remote-Compare, Readback und CI-Status folgen unmittelbar unten. Lokale Stagingtests ersetzen den integrierten Checkout/CI-Nachweis nicht.

Remote-Publish und Readback (Rootmeldung anschließend unabhängig per Connector geprüft): Root veröffentlichte Commit `1b6f1a86725b60310f74ca0c69ee0a5c380c6559`, Tree `e268b0d3e280ae875a4a8eeea683598b05fb7e46`, auf `future3/feature-queue-store`, Parent `9c859a2e91f90e25d84f4e32ffe9ab369f0d5202`. Compare `9c859a2...` → `1b6f1a8...`: `ahead_by=1`, `behind_by=0`, genau die zwei freigegebenen Pfade (`store.py` +376/−4; neues `test_queue_store.py` +442/−0). Committext: `feat: persist independent queues and atomic playlist transfers`.

Readback aus dem Commit-Tree: `src/jukebox/components/playlists/store.py` Blob `6465ade05f159296b428230bcf7674015f960d5b` (41 526 Bytes), `test/playlists/test_queue_store.py` Blob `2ff2d887007819fc4daaffe46fdf1170a9163aba` (23 983 Bytes). Beide Blobs wurden abgerufen und textuell mit dem eingefrorenen Stage verglichen; nach CRLF/LF-Normalisierung war jeder Text identisch. Der Compare enthält keine weiteren Dateien.

Vorhandener Push-Run `38962176404` (`.github/workflows/pythonpackage_future3.yml`) hat passenden Head-SHA und Branch. Beim ersten frischen Jobs-Readback liefen Python 3.9–3.12 in der Abhängigkeitsinstallation; Python 3.13 war queued. Die Gesamt-CI ist offen und wird nur lesend in Abständen von mindestens fünf Minuten geprüft; es wurden keine Jobs ausgelöst oder wiederholt.

Reviewgrenze: `test_playlist_data_and_command_ledger_survive_additive_queue_schema` erstellt bereits mit P03b-Schema und prüft anschließend Wiederöffnung derselben Datenbank. Der Fall belegt weder Upgrade einer vorhandenen reinen P03a2-Datenbank noch die Migration bei vorher bestehenden Playlist-/Ledgerdaten. Ein gezielter Q01-Alt-Schema-Upgradefall ist offen. Ebenso ist für `get_queue` noch kein WAL-Interleaving-Regressionsfall nachgewiesen, der einen konkurrierenden Writer zwischen Header- und Entry-SELECT über `PlaylistStore.execute` ausführt und die atomare Snapshotrevision prüft. Diese zwei Nachweise sind offen; eine erfolgreiche Migration oder WAL-Interleavingprüfung wird nicht behauptet. Die Tabellenänderung selbst ist additiv als `CREATE TABLE IF NOT EXISTS` im Storecode sichtbar.

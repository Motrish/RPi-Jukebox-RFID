# P03a2 – Playliständerungen und Übersicht

Stand: 16.10.2026. P03a2 wurde von Root auf `future3/feature-playlist-edits` veröffentlicht. Der Commit `9c859a2e91f90e25d84f4e32ffe9ab369f0d5202` hat Tree `ff6a3c7b0199d0c320ebc8d58e41c3c55ea55ca2` und basiert direkt auf `52fa7be23e2cccaff00cb21e60d3902cb0feb851`. Compare `52fa7be...` → `9c859a2...` bestätigt `ahead_by=1`, `behind_by=0`, genau zwei geänderte Dateien: `store.py` (+165/−6) und `test_store.py` (+184/−0).

## Remote-Readback

Der Commit-Readback bestätigt die Commit-SHA, den Tree und den Committext `feat: edit delete reorder and paginate saved playlists`. Der rekursive Tree enthält für `src/jukebox/components/playlists/store.py` Blob `11aa92b67a54a22e6c03f094edbc67e300e6c3d9` (22 370 Bytes) und für `test/playlists/test_store.py` Blob `57f1ac4c0731c6d2b87103893a03cd2410ac159c` (22 634 Bytes). Beide Remote-Blobs wurden erneut gelesen und mit dem eingefrorenen Stage unter `G:/Entwicklung/phoniebox-staging/p03a2/` verglichen; nach Vereinheitlichung der Zeilenenden und Entfernung eines möglichen UTF-8-BOM stimmte der Text für beide Dateien überein. Die unveränderte `__init__.py` ist kein Teil dieses Commits.

## Umfang

P03a2 ergänzt den vorhandenen `PlaylistStore` um `PLAYLIST_RENAME`, `PLAYLIST_REMOVE`, `PLAYLIST_MOVE`, `PLAYLIST_DELETE` und `list_playlists`. Die Aktionen verwenden dieselbe SQLite-Datenbank, dieselbe Command-Idempotenz und dieselbe Schreibtransaktion wie P03a1. Rename/Move-No-ops behalten die Revision; Remove löscht genau eine Entry-ID und normalisiert die Positionen; Move akzeptiert den finalen Index; Delete speichert einen wiederholbaren Beleg mit der letzten geprüften Revision. Die Übersicht liefert genau `contractVersion`, `playlists` und `nextCursor`, sortiert nach `playlistId`, mit validiertem Cursor und echtem Integerlimit 1–200.

## Tests und Befehle

Die Fortsetzung berichtete eine RED-Phase, in der die noch nicht implementierten Handler und die fehlende Listenmethode erwartet scheiterten. Der ursprüngliche Terminalaufruf und seine Ausgabe sind nicht mehr verfügbar; deshalb wird hier kein exakter RED-Befehl oder Exitcode als Rohnachweis behauptet.

Reproduzierbarer fokussierter Lauf im eingefrorenen Stage:

```powershell
$env:PYTHONPATH='G:\Entwicklung\phoniebox-staging\p03a2\src\jukebox;G:\Entwicklung\phoniebox-staging\a02\src\jukebox'
python -m unittest discover -s test\playlists -p test_store.py -v
```

Exitcode: 0; 20/20 Tests bestanden. Die 7 P03a2-spezifischen Tests decken Rename/No-op, Entfernen genau eines doppelten Vorkommnisses, Move in beide Richtungen und No-op/Rangefehler, Delete-Beleg und Cascade, Revisionserschöpfung sowie paginierte LIST-Form und Argumentgrenzen ab. Die P03a1-Regressionen bleiben im selben Store-Testmodul enthalten.

Zusätzliche erfolgreiche Prüfungen:

```powershell
$env:PYTHONPATH='G:\Entwicklung\phoniebox-tools\python'
python -m flake8 --max-line-length=127 --max-complexity=12 --ignore=E126,E127,E128,W503,F824 --per-file-ignores=__init__.py:F401 src test
python -m py_compile src\jukebox\components\playlists\store.py test\playlists\test_store.py
```

Exitcode 0 für beide Prüfungen; flake8 fand keine Befunde. Es wurden keine Dateien aus P03a1 geändert und keine Commits oder Branches aus dem Stage erstellt.

## Integrierte CI

Der vorhandene Push-Run `38961153409` für `.github/workflows/pythonpackage_future3.yml` wurde beim Commit ausgelöst; Head-SHA und Branch stimmen. Beim ersten Jobs-Readback liefen Python 3.9–3.12 in der Abhängigkeitsinstallation, Python 3.13 war queued. Das ist nur ein Zwischenstand, kein CI-Erfolg. Es wurden keine Jobs manuell gestartet oder erneut ausgeführt.

## P03b – Vorbereitung, noch kein Implementierungsauftrag

P03b erweitert ausschließlich dieselbe `PlaylistStore`-Instanz und dasselbe `command_log`; es entsteht weder eine zweite Storeklasse mit separater Ledger-/Transaktionsgrenze noch ein Runtime-/MPD-/Pluginanschluss. Vor Codebeginn müssen A02-Review und Root-Freigabe den konkreten Branch/SHA sowie die Schreibdateien benennen. Erwartete Schreibpfade: bestehende `src/jukebox/components/playlists/store.py`; Tests vorzugsweise getrennt in `test/playlists/test_queue_store.py`, damit `test_store.py` eingefroren bleibt. `components/playlists/__init__.py` nur anfassen, falls die freigegebene API explizit Exporte verlangt.

Vorgeschlagene Testgruppen gemäß CONTRACT 1:

- `QUEUE_CREATE`: leere und nichtleere Queue, Revision 0, eigene `entryId`s, `sourceEntryId=null`, beide Herkunftsfelder null, `currentEntryId=null`, Modi `OFF`; Duplikatmedien bleiben getrennte Vorkommnisse, Grenzwert 10 000.
- `QUEUE_GET` / `COMMAND_GET`: vollständiger atomarer Queue-Snapshot, fehlende ID, getrennte Playlist-/Queue-Revision und ein gemeinsames gespeichertes CommandResult.
- `QUEUE_APPEND`, `QUEUE_REMOVE`, `QUEUE_MOVE`: Eintragsreihenfolge und lückenlose Positionen, ID-Erhalt, Duplikate, No-op/Revision, Konflikt-/NOT_FOUND-/Limitfehler; ausgewählte Entry-ID darf nicht entfernt werden (`ACTIVE_ENTRY_REQUIRES_CONTROLLER`), Move muss `currentEntryId` erhalten.
- `QUEUE_SET_MODES` / `QUEUE_SET_CURRENT`: gültige Enumwerte und Null-/Entry-ID-Grenzen, Materialitätsregel für Revision und Wiederholung desselben `commandId`; keine Behauptung tatsächlicher Shuffle- oder Wiedergabewirkung.
- `QUEUE_LOAD_PLAYLIST`: neue Queue-Entry-IDs mit `sourceEntryId` aus der Playlist, exakte Playlistordnung/-revision als Herkunft, Modi zurück auf `OFF`, keine Mutation der Playlist. Prüfe atomar Queue- und Playlistrevision; bei Konflikten beide gefundenen Konflikte exakt melden und keinerlei Teilmutation.
- `QUEUE_SAVE_NEW_PLAYLIST` / `QUEUE_SAVE_PLAYLIST`: Queueordnung als unabhängige Playlistkopie mit neuen IDs, keine Mutation der Queue; beim Update Playlistrevision +1 und unveränderter Name. Konflikte beider Objekte gesammelt prüfen; bei jeder Ablehnung bleiben beide Objekte und Ledger atomar konsistent.
- Gemeinsame Idempotenz-/Parallel-/Rollbackfälle über Queueaktion und beide Cross-Object-Übergänge: gleiche commandId parallel genau einmal; gleicher Schlüssel mit anderem Payload ohne Seiteneffekt; nach gespeicherter Ablehnung Replay derselben Ablehnung; Fehler zwischen Mutation und Resultatpersistierung rollt alle geänderten Queue-/Playlistzeilen und den Ledgerclaim zurück; verlorene Antwort mit derselben commandId liefert dieselben generierten IDs.

Alle P03b-Tests sollten temporäre SQLite-Datenbanken und synthetische Medienreferenzen verwenden. Ein echter konkurrierender Schreibablauf muss die konfliktbehafteten Snapshotrevisionen innerhalb derselben `BEGIN IMMEDIATE`-Transaktion prüfen; Tests dürfen keine zweite Implementierung der SQL-Logik nachstellen. Hardware, Audio, Netz, neue Dependencies, RPC und Pluginregistrierung bleiben außerhalb dieses Vertragslices.

CI-Update: Ein frischer GET auf `actions/runs/38961153409/jobs?per_page=100` zeigt Python 3.9, 3.10, 3.11 und 3.12 erfolgreich abgeschlossen; Python 3.13 führt gerade `pytest with coverage` aus. Der Run ist noch nicht abgeschlossen; ein Gesamterfolg wird daher nicht behauptet.

CI-Abschluss: Ein weiterer frischer Jobs-Readback bestätigt, dass auch Python 3.13 und der `finish`-Job erfolgreich abgeschlossen sind. Damit sind alle Jobs in Run `38961153409` erfolgreich; es wurde kein erneuter Lauf gestartet.

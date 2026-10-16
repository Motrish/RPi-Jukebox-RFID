# A02a – Python-Verträge für Playlist und Queue

Status: lokal implementiert und gezielt geprüft; Root veröffentlicht die vier freigegebenen Dateien auf `future3/feature-contracts`. A02a bleibt bis zur Remote-Rücklesung und vollständigen V3-CI unverified. A02b (JavaScript-Konformität) und der sichere Transportanschluss sind nicht Teil dieses Slices.

## Umfang

Implementiert wurden transportfreie Python-stdlib-Validatoren für `MediaRef`, Playlist-/Queue-Einträge und Snapshots, die 15 freigegebenen Schreibkommandos, deren `CommandResult`-Arme, versionlose `Error`-Objekte sowie `validate_identifier`. Validatoren nehmen JSON-kompatible Mapping-/Listenwerte an und liefern tiefe `dict`-/`list`-Kopien. `ContractValidationError.error` enthält einen stabilen versionlosen Fehlerrahmen. Die Fixtures verwenden ausschließlich synthetische IDs und Medien.

Es wurden ausschließlich diese vier Produktbranchdateien erstellt:

- `src/jukebox/jukebox/contracts/__init__.py`
- `src/jukebox/jukebox/contracts/v1.py`
- `test/contracts/test_v1.py`
- `test/contracts/fixtures/v1.json`

Der Importpfad folgt der V3-Struktur: Root-`conftest.py` setzt `src/jukebox` auf `sys.path`; das Pythonpaket liegt darunter in `src/jukebox/jukebox`. Es wurden keine Runtime-, RPC-, Web-, Registry-, Abhängigkeits- oder CI-Dateien geändert.

## Red/Green-Nachweis

- Erster Testlauf vor dem Modul: erwartetes Rot, Exit 1 durch `ModuleNotFoundError: jukebox.contracts.v1`.
- Nach dem Schreiben der zusätzlichen Command-/Resulttests und vor deren Implementierung: erwartetes Rot, Exit 1 durch `ImportError: cannot import name 'validate_command'`.
- Für die späteren unabhängigen Reviewkorrekturen wurden Tests im selben Patchzyklus ergänzt; sie wurden nicht in einem separaten Vorher-Lauf rot ausgeführt. Das ist hier ausdrücklich kein TDD-Red-Nachweis.

## Lokale Prüfungen

- `python -m unittest discover -s test/contracts -p 'test_*.py' -v` — Exit 0, 22 Tests.
- `$env:PYTHONPATH='G:\Entwicklung\phoniebox-tools\python'; python -m flake8 --max-line-length=127 --max-complexity=12 --ignore=E126,E127,E128,W503,F824 --per-file-ignores=__init__.py:F401 src test` — Exit 0.

Die gezielten Tests laufen aus dem isolierten Artefaktordner `G:\Entwicklung\phoniebox-staging\a02` mit dem Baseline-Importpfad. Das ist kein vollständiger V3-Checkout und kein integrierter Actions-Nachweis.

## Ausgangsbasis und offene Nachweise

- Commitbasis: `58826fcf880f521292c56c43b682fa67cfdc2418`.
- Basis-Tree: `14c8a895c4c5e6903315096a75c6b918228b6fa1` (Tree-SHA, verschieden von der Commit-SHA).
- Produktcommit: `9f5f400e453ff8e07a64b2f597717b24321d5fcd` auf `future3/feature-contracts`; Commit-Tree `7d23b9e2b15582735d4eb8796d726d10142dcd78`, Parent exakt die Commitbasis.
- GitHub-Compare: ein Commit vorwärts, keiner rückwärts; genau die vier freigegebenen Dateien neu hinzugefügt.
- Remote-Readback: alle vier Blobinhalte auf der Produktcommit-SHA stimmen nach Zeilenend-Normalisierung exakt mit dem Luna-Stagingstand überein.
- Python-Workflow Run `38959948228`: Jobs 3.9, 3.10, 3.11 und 3.12 bestanden; 3.13 steht bei letzter Abfrage noch `queued`. Gesamtworkflow daher noch offen.
- Hardware-, Browser-, Installer- und Playbackabnahmen: durch A02a nicht belegt.

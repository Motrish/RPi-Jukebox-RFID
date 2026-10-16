# P03a1 – SQLite-Playliststore (Teilslice)

Stand: 16.10.2026. P03a1 wurde auf Branch `future3/feature-playlist-store` in zwei Commits veröffentlicht: `26cf8a08486880998bbffac8e136025f274513dc` (Tree `809d135e28e4873a039afb2d45f0c7b24ced2ea9`, Parent A02 `9f5f400e453ff8e07a64b2f597717b24321d5fcd`) und Follow-up `52fa7be23e2cccaff00cb21e60d3902cb0feb851` (Tree `1166dc41e79c7e3617fde54e283710709a4d14c5`, Parent `26cf8a08486880998bbffac8e136025f274513dc`). Zusammen ändern sie ausschließlich die drei nachfolgend genannten Dateien. Diese Notiz markiert weder P03a noch P03 als insgesamt fertig.

## Umfang und Dateien

Der Store unterstützt ausschließlich `PLAYLIST_CREATE`, `PLAYLIST_GET`, `PLAYLIST_APPEND` und `COMMAND_GET`. Er speichert Snapshots und Command-Ergebnisse transportfrei mit SQLite. `BEGIN IMMEDIATE` umfasst Idempotenzclaim, Mutationsprüfung, Änderung und vollständiges Resultat; Getter verwenden validierte Contract-IDs. Playlist-Header und Einträge werden in einer expliziten Lesetransaktion aus demselben SQLite-Snapshot gelesen.

Die drei freigegebenen Dateien liegen in `G:/Entwicklung/phoniebox-staging/p03a/`:

- `src/jukebox/components/playlists/store.py`
- `src/jukebox/components/playlists/__init__.py`
- `test/playlists/test_store.py`

Beim Erst-Publish wurde Readback für alle drei Dateien bytegenau anhand ihrer Git-Blob-SHA gegen damaliges Staging geprüft (Staging-UTF-8-BOM beim Blobvergleich entfernt): `store.py` `bcbe322bbbcd70bf5c72db79a70e6dd9984aa3fa`, `__init__.py` `4de7ab192e389d328a07b99085d71723d384a3eb`, `test_store.py` `a70b5f25f4768a07076addc40c03a20c70488039`. Der Folgecommit ersetzt die Testdatei mit den nachfolgenden Root-Review-Regressionstests; ihr finaler Blob ist `eab84fe96a95170d3a3b12f8ca9bf1597ba97bf4` und stimmt bytegenau mit Staging überein. Compare A02→finale P03a1-Branch meldet `ahead_by=2`, `behind_by=0`; die gesamte Änderung besteht aus genau diesen drei Dateipfaden. Der Folgecommit ändert ausschließlich `test/playlists/test_store.py` (+63/−2).

Kein Runtime-/Plugin-/Transport-/MPD- oder Hardwareanschluss. Keine A02-Datei verändert.

## Nachweise

Die Store-Tests decken CREATE/GET/APPEND mit Reihenfolge und doppelten Medien bei getrennten Entry-IDs, Revisionsfortschritt und No-op-Regeln, gleiche commandId mit identischem und abweichendem Payload, konkurrierende gleiche commandId, gespeicherte/replaybare Revisionsablehnung, fehlende Getterobjekte, ungültige Getter-IDs, unvollständigen Command-Logeintrag, Rollback nach ausgeführter Mutation vor Resultatspeicherung sowie erneutes Abrufen nach verlorener Antwort ab.

Der Snapshot-Regressionsfall verwendet eine echte WAL-Datenbank und führt zwischen den beiden SELECTs über `PlaylistStore.execute` einen konkurrierenden APPEND aus. Der beobachtete GET bleibt vollständig auf der alten Revision; ein anschließender GET sieht den neuen Stand.

RED-Nachweis: Der erste fokussierte Testlauf scheiterte erwartungsgemäß mit `ModuleNotFoundError` für das noch nicht implementierte Storemodul. Nach Implementierung und nach den drei Root-Review-Korrekturen wurden die Tests erneut ausgeführt.

Erfolgreiche Prüfungen:

- A02-Contracttests: `python -m unittest discover -s G:\Entwicklung\phoniebox-staging\a02\test\contracts -p test_v1.py -v` — 22/22 bestanden.
- P03a1-Storetests: `python -m unittest discover -s test\playlists -p test_store.py -v` mit lokalem `PYTHONPATH` auf die beiden isolierten Staging-`src/jukebox`-Pfade — 13/13 bestanden.
- `python -m py_compile src\jukebox\components\playlists\store.py test\playlists\test_store.py` — bestanden.
- Flake8 mit dem bereitgestellten Tools-PYTHONPATH und Root-Parametern (`--max-line-length=127 --max-complexity=12 --ignore=E126,E127,E128,W503,F824 --per-file-ignores=__init__.py:F401 src test`) — keine Befunde.

Die Tests enthalten keine Annahmen über einen benachbarten A02-Ordner und verändern keine Repository-Importpfade. Im integrierten Repo werden die Baseline-`conftest.py`-Pfade verwendet; der lokale `PYTHONPATH` ist nur für das Staging-Smoke-Testing gesetzt.

## Integrierte CI

Die vorhandene `.github/workflows/pythonpackage_future3.yml` wurde beim Push ausgelöst (Run `38960045632`, Event `push`, Branch und Head stimmen mit obigem Commit überein). Beim ersten Readback war der Run `queued`; später liefen die Python-Matrixjobs `build (3.10)` und `build (3.11)`, während `3.9`, `3.12` und `3.13` noch queued waren. Der ursprüngliche Push-Run `38960045632` auf dem inzwischen überholten Erstcommit wird nicht weiter beobachtet. Auf dem finalen Head `52fa7be23e2cccaff00cb21e60d3902cb0feb851` laufen die vorhandenen Push- und Pull-Request-Runs `38960469965` und `38960476066` desselben Workflows; beim jüngsten Readback waren beide queued und ihre Matrixjobs Python 3.9–3.13 ebenfalls queued. Keine Jobs wurden manuell gestartet oder erneut ausgeführt.

## Grenzen und nächster Schritt

Dies ist P03a1, kein Abschluss von P03a. Die übrigen Playlist-Schreibaktionen, Playlist-Übersicht sowie Queue- und Controlleroperationen fehlen absichtlich. Die Regressionen sind lokale Stagingtests; ein vollständiger integrierter Checkout-/CI-Lauf auf dem von Root erzeugten Integrationscommit steht noch aus. Root hat beide geprüften Commits auf dem genannten Branch veröffentlicht.

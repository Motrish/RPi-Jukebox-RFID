# P03a1 – unabhängiges finales Review

Final geprüfter Commit: `52fa7be23e2cccaff00cb21e60d3902cb0feb851`, Tree `1166dc41e79c7e3617fde54e283710709a4d14c5`, Elterncommit `26cf8a08486880998bbffac8e136025f274513dc`, auf A02a `9f5f400e453ff8e07a64b2f597717b24321d5fcd` gestapelt. Stand: 16.10.2026. Reviewer unabhängig vom Luna-Codeautor; ausschließlich Prosa.

## Urteil

Für den begrenzten P03a1-Slice am finalen SHA kein freigabesperrender Befund. Der frühere Rollbacknachweis wurde im Folgecommit sinnvoll korrigiert; STORE_BUSY mit sicherer Wiederholung und zwei unterschiedliche konkurrierende APPEND-Kommandos auf derselben Revision sind zusätzlich abgedeckt. Dies ist die fachliche Code-/Testfreigabe dieses SHAs, keine vorweggenommene vollständige Actions-/Runtime-/Hardwareabnahme.

In der gelesenen Create-/Appendimplementierung wurde darüber hinaus kein konkreter freigabesperrender Produktfehler festgestellt. Der Scope umfasst nur PLAYLIST_CREATE, PLAYLIST_APPEND, PLAYLIST_GET und COMMAND_GET; übrige Playlistaktionen und Queuefunktionen werden nicht als implementiert oder abgenommen betrachtet.

## Geschlossener Befund und Nachprüfung

Im Elternstand `26cf8a0`, `test/playlists/test_store.py`, Test ab Zeile 197: Nach simulierter Unterbrechung in `_write_command_result` prüft der Test korrekt das Fehlen der commandId. Seine Playlistprüfung fragt jedoch die nie erzeugte ID `any_generated_id` ab (Zeile 207). Dieser Assert würde auch dann bestehen, wenn die tatsächlich eingefügte Playlist und ihre Einträge verwaist im Store verblieben. Er beweist somit keine vollständige Rücknahme der Mutation.

Nachweis jetzt vorhanden: Der Luna-Test erfasst die tatsächlich erzeugte playlistId, unterbricht nach der realen Erstellung innerhalb der Transaktion, bestätigt das Fehlen dieser Playlist und der commandId und prüft alle drei betroffenen Tabellen playlists, playlist_entries und command_log auf vollständige Leerheit. Der BUSY-Test hält eine echte SQLite-Schreibsperre, erwartet STORE_BUSY und bestätigt, dass commandId noch nicht beansprucht ist; nach Freigabe wird dieselbe commandId einmal angewendet und anschließend identisch wiedergegeben. Zwei unterschiedliche APPENDs mit erwarteter Revision 0 liefern genau APPLIED und REJECTED/REVISION_CONFLICT, einen Eintrag, Revision 1 und beide korrekten Ledgerresultate. Reviewer hat keine Ersatztests oder Patches geschrieben.

## Readback und Identität

Der ursprüngliche GitHub-Compare gegen A02a meldet drei neue Dateien. Der Folgecompare 26cf8a0...52fa7be meldet genau einen Commit und ausschließlich eine Änderung an test/playlists/test_store.py; Produktquelle und Paketinitialisierung sind bytegleich zum zuvor gelesenen Stand. Der neue Test wurde am finalen SHA gelesen; die bereits am Eltern-SHA gelesenen Produktblobs sind laut vollständigem Folgecompare unverändert. Nach Entfernung ausschließlich des lokalen UTF-8-BOM stimmen die berechneten Git-Blob-SHA-1-Werte mit dem Remoteinhalt überein; übrige Bytes einschließlich Zeilenenden sind gleich.

| Datei | Git-Blob-SHA |
| --- | --- |
| src/jukebox/components/playlists/__init__.py | 4de7ab192e389d328a07b99085d71723d384a3eb |
| src/jukebox/components/playlists/store.py | bcbe322bbbcd70bf5c72db79a70e6dd9984aa3fa |
| test/playlists/test_store.py | eab84fe96a95170d3a3b12f8ca9bf1597ba97bf4 |

Dies ist kein behaupteter lokaler Vollcheckout. Der im Modulteiltest verwendete A02a-Quellinhalt ist separat am A02a-SHA abgeglichen; siehe [A02a-Review](a02-review.md).

## Gelesene Implementierung

- `execute` validiert zuerst CONTRACT1, begrenzt den Slice auf CREATE/APPEND und verwendet eine kanonische JSONdarstellung für den Inhaltsvergleich. SQLwerte sind parametrisiert.
- `BEGIN IMMEDIATE` umfasst Commandbeanspruchung, Mutation, Ergebnisvalidierung/-speicherung und Commit auf derselben Verbindung. Eindeutiger command_id-Primärschlüssel plus SQLite-Schreibserialisierung verhindert eine zweite Wirkung desselben Wunsches.
- Wiederholung gleicher commandId/Inhalt liefert das ursprüngliche gespeicherte Resultat; abweichender Inhalt liefert COMMAND_ID_REUSED und überschreibt den ursprünglichen Beleg nicht. Fachliche Ablehnungen werden innerhalb derselben Transaktion gespeichert.
- APPEND prüft Existenz und erwartete Revision vor Änderung, hält Medien-Duplikate mit eigenen Eintrags-IDs auseinander, erhält Reihenfolge und erhöht die Revision genau einmal. Leerer Append ist wirkungslos. Listen-/Revisionsgrenzen werden vor Inserts geprüft.
- `get_playlist` validiert den Identifier vor SQLite und liest Metadaten/Einträge unter einem gemeinsamen BEGIN-Readtransaction. Der vorhandene gezielte WAL-Interleavingtest bestätigt alten konsistenten Snapshot und danach neuen konsistenten Stand.
- `get_command` validiert den Identifier; fehlende Zeile bedeutet COMMAND_NOT_FOUND, vorhandene Zeile ohne Ergebnis STORE_UNAVAILABLE. Decoder validiert gespeicherte Resultate und leitet keine beschädigten Resultate als Erfolg weiter.
- SQLite-Busy/Locked wird mit begrenzter Wartezeit als STORE_BUSY/retryable true behandelt, übrige Datenbankfehler als sichere STORE_UNAVAILABLE-Diagnose. Fehlerpfade rollen die laufende Transaktion zurück. Die zuvor fehlenden zielgenauen Gegenbeispiele sind im Folgecommit enthalten und erfolgreich nachgeprüft.
- Kein RPC-/Plugin-/Player-/Hardwareanschluss und keine privilegierte Wirkung. Die neue Komponente registriert sich nicht automatisch als öffentlich aufrufbares Plugin.

## Prüfungen und Grenze

Selbst ausgeführt: `python -B -m unittest discover -s test/playlists -p test_store.py -v`, Arbeitsordner `G:/Entwicklung/phoniebox-staging/p03a`, mit PYTHONPATH auf dessen `src/jukebox` sowie den getrennten A02a-Artefaktordner. Ergebnis am finalen Testblob: 13 Tests, Exit 0. Der unveränderte Elternstand war zuvor mit 11 Tests erfolgreich geprüft worden. Die Identität der verwendeten Module wurde oben abgeglichen. Dies ist ausdrücklich ein lokaler Modulteilnachweis; keine integrierte CI-/Geräteabnahme.

Root meldete Lint Exit 0 für beide Module vor dem reinen Testfolgecommit. Die Produktquelle blieb seither unverändert; ein eigener zusätzlicher Lintlauf des Reviewers wird nicht behauptet. Vollständiger Actions-Checkout und Pythonmatrix laufen gesondert; deren Erfolg wird hier nicht vorweggenommen. Bestehende Phoniebox und Musikdaten wurden nicht angesprochen, Produktdateien/Tests wurden durch den Reviewer nicht geändert.

Quellen: [ursprünglicher Compare](https://github.com/Motrish/RPi-Jukebox-RFID/compare/9f5f400e453ff8e07a64b2f597717b24321d5fcd...26cf8a08486880998bbffac8e136025f274513dc), [geprüfter Folgecompare](https://github.com/Motrish/RPi-Jukebox-RFID/compare/26cf8a08486880998bbffac8e136025f274513dc...52fa7be23e2cccaff00cb21e60d3902cb0feb851), [CONTRACT1](a01-contracts.md).

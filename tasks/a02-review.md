# A02a – unabhängiges Review

Geprüfter Commit: `9f5f400e453ff8e07a64b2f597717b24321d5fcd`, Tree `7d23b9e2b15582735d4eb8796d726d10142dcd78`, gegen Basis `58826fcf880f521292c56c43b682fa67cfdc2418`. Stand: 16.10.2026. Reviewer unabhängig vom Luna-Codeautor; ausschließlich Prosa, keine Code-/Teständerung.

## Urteil

Für den begrenzten transportfreien A02a-Slice kein freigabesperrender Befund. Die zuvor gemeldeten Status-/LIMIT_EXCEEDED-Fehler sind korrigiert und durch Regressionen abgedeckt. Versionklassifikation folgt dem Root-Ruling: falsche Typen VALIDATION_ERROR, andere echte Ganzzahl UNSUPPORTED_VERSION. Öffentliche Identifierprüfung verwendet dieselbe begrenzte ASCII-Tokenregel wie Medien-/Objekt-IDs und ist im Paketexport verfügbar.

Das ist eine fachliche Codefreigabe des genannten SHAs, keine Behauptung eines vollständigen integrierten CI-/Runtime-/Hardware-/HTTPSnachweises. A02b/Transportanschluss und Gesamt-A01/A02 bleiben offen.

## Umfang und Readback

GitHub-Compare meldet genau einen Commit und ausschließlich vier hinzugefügte Dateien; keine bestehende Registry, kein Router, keine Abhängigkeit, kein Workflow und kein Playerpfad wurde verändert. Alle vier Dateien wurden am exakten Commit über den Connector gelesen und gegen die Stagingdateien kryptografisch abgeglichen.

| Datei | Git-Blob-SHA am geprüften Commit |
| --- | --- |
| src/jukebox/jukebox/contracts/__init__.py | 6baaed595c6404fce81ab8748b525d94a9281cb5 |
| src/jukebox/jukebox/contracts/v1.py | 2c050deaa8863ae1450be83b891cf565566f56d8 |
| test/contracts/test_v1.py | f62233aceb571944fb7d824063bc3c2504a724c5 |
| test/contracts/fixtures/v1.json | be573867052586a36cb4d9d64b3cad724dc8a48b |

Die lokalen Stagingdateien besitzen jeweils ein UTF-8-BOM. Nach ausschließlich dessen Entfernung ergeben die lokal berechneten Git-Blob-SHA-1-Werte exakt die obigen Remote-SHAs. Die übrigen Bytes einschließlich Zeilenenden stimmen überein. Es wird deshalb keine rohe Bytegleichheit einschließlich BOM behauptet; nachgewiesen ist der mechanisch veröffentlichte Quellinhalt ohne BOM. Es wurde dabei keine Datei geändert oder ein Ersatzcheckout aufgebaut.

## Geprüfte Eigenschaften

- LOCAL/SPOTIFY sind geschlossene Varianten; freie Pfade und beliebige Spotify-URLs werden nicht als MediaRef akzeptiert. IDs sind begrenzte ASCII-Token, Spotifytrack-URIs genau 22 Buchstaben/Ziffern nach dem Präfix.
- Versionen, Revisionen und Positionen prüfen echte Ganzzahlen ohne Boolean-/Floatkoerzierung. Snapshotfelder sind geschlossen; Entry/Error sind unversioniert, Snapshot/Command/Result tragen Version 1.
- Doppelte Medien bleiben bei verschiedenen entryIds erlaubt; doppelte entryIds und inkonsistente Positionen werden abgewiesen. Queueherkunftsfelder sind gepaart und currentEntryId muss existieren oder null sein.
- Alle 15 Schreibkommandos besitzen die festgelegten Felder. APPLIED-/REJECTED-Arme und ihre playlist-/queue-/Löschresultate sind geschlossen. Codeabhängige Error.details und retryable werden validiert.
- Unhashbare status-Werte erreichen nun den stabilen ContractValidationError. Überlange Listen erzeugen LIMIT_EXCEEDED mit field/limit; der erzeugte Fehler besteht wiederum validate_error.
- stdlib-only, keine Pluginregistrierung, keine Audio-/Netz-/SQL-/Privilegienwirkung. Die neue Identifierfunktion ist eine Wiederverwendung der existierenden Tokenprüfung.

## Prüfungen und Grenzen

Selbst ausgeführt im Artefaktordner `G:/Entwicklung/phoniebox-staging/a02`: `python -B -m unittest discover -s test/contracts -p test_v1.py -v`. Ergebnis: 22 Tests, Exit 0. Dazu gehören die neuen Regressionen für falsche Versiontypen, unhashbare Statuswerte, LIMIT-Fehlerrückvalidierung und öffentliche Identifiergrenze. Dieser Lauf ist aufgrund des obigen Blobabgleichs dem geprüften Quellinhalt zugeordnet, bleibt aber ausdrücklich ein lokaler Modulteilnachweis.

Root meldet beide Module frisch lintfrei; Luna meldet ebenfalls Lint Exit 0. Der Reviewer hat keinen weiteren Lintlauf behauptet und keine neuen Testsnippets geschrieben. Vollständiger Checkout und integrierte vorhandene Prüfungen müssen auf Actions am Integrations-SHA nachgewiesen werden.

Nicht blockierender, bereits mit Root abgegrenzter Punkt für P03b: CONTRACT1 fordert keine ausdrückliche Querprüfung zwischen sourcePlaylistId null und einzelnen sourceEntryIds. Der Validator akzeptiert diese Kombination; V1-Storeaktionen sollen trotzdem nur konsistente Herkunft erzeugen. Daraus wurde kein zusätzliches A02a-Kriterium gemacht.

Quellen: [exakter Compare](https://github.com/Motrish/RPi-Jukebox-RFID/compare/58826fcf880f521292c56c43b682fa67cfdc2418...9f5f400e453ff8e07a64b2f597717b24321d5fcd), [Contract](a01-contracts.md).

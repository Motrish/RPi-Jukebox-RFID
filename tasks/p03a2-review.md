# P03a2 – unabhängiges Review

Geprüfter Commit: `9c859a2e91f90e25d84f4e32ffe9ab369f0d5202`, Tree `ff6a3c7b0199d0c320ebc8d58e41c3c55ea55ca2`, gegen `52fa7be23e2cccaff00cb21e60d3902cb0feb851`. Stand: 16.10.2026. Reviewer unabhängig vom Luna-Codeautor; ausschließlich Prosa, keine Produkt-/Teständerung.

## Urteil

Kein freigabesperrender Befund für den transportfreien P03a2-Slice. RENAME, REMOVE, MOVE, DELETE und die seitenweise Playlistübersicht passen zur freigegebenen CONTRACT1-Semantik einschließlich Rootpräzisierung für LIST. Die bestehenden CREATE-/APPEND-/Ledger-/Readtransaction-Eigenschaften bleiben in diesem Diff erhalten.

Dies ist die fachliche Freigabe des genannten Commits. Sie ersetzt keinen vollständigen CI-/Integrations-/Runtime-/Hardwaretest. Queue und Playback wurden nicht implementiert oder abgenommen; die spätere Speicherung einer Queuekopie darf beim Playlistlöschen keine Cascade auf ihre Arbeitskopie erhalten.

## Umfang, Remoteinhalt und lokaler Abgleich

GitHub-Compare meldet genau einen Commit mit ausschließlich zwei geänderten Dateien. Beide Remoteinhalte wurden am exakten SHA gelesen. Nach Entfernung ausschließlich des lokalen UTF-8-BOM ergeben die berechneten Git-Blob-SHA-1-Werte dieselben Remoteobjekte; alle übrigen Bytes einschließlich Zeilenenden stimmen überein.

| Datei | Git-Blob-SHA |
| --- | --- |
| src/jukebox/components/playlists/store.py | 11aa92b67a54a22e6c03f094edbc67e300e6c3d9 |
| test/playlists/test_store.py | 57f1ac4c0731c6d2b87103893a03cd2410ac159c |

Keine Registry-, Router-, Abhängigkeits-, Workflow- oder Hardwaredatei ist Teil des Diffs. Ein lokaler Vollcheckout wird nicht behauptet.

## Geprüfte Eigenschaften

- Sämtliche sechs Playlist-Schreibaktionen durchlaufen denselben validierten Kommandorahmen, dieselbe BEGIN-IMMEDIATE-Transaktion und das vorhandene Idempotenzregister. Gleiches commandId/Inhalt liefert den gespeicherten ursprünglichen Beleg; Inhaltsabweichung mutiert nichts. Alle neuen Handler laufen innerhalb dieser bestehenden Grenze.
- Vor RENAME/REMOVE/MOVE/DELETE prüft `_playlist_before_edit` Existenz und erwartete Revision. Ein wirkungsloser Wunsch überspringt diese Konkurrenzprüfung nicht. RENAME erhöht nur bei tatsächlich geändertem Namen die Revision.
- REMOVE prüft die konkrete Eintrags-ID innerhalb der bezeichneten Playlist. Erst danach wird genau diese global eindeutige entryId entfernt. Gleiche Medien und Titel bleiben als andere Vorkommnisse bestehen; die restlichen IDs ändern sich nicht. Die verbleibenden Positionen werden lückenlos neu vergeben.
- MOVE entfernt zunächst die betreffende ID aus der gelesenen Ordnung und setzt sie am endgültigen Zielindex ein. Beide Richtungen, unveränderte Position und zu großer Index besitzen nachvollziehbare Semantik. Negative/Boolean-/Floatpositionen werden bereits vom unveränderten Contractvalidator abgewiesen.
- Die Reindexierung verschiebt alle alten Positionen zuerst um 10001. Zulässige alte Positionen liegen bei maximal 10000 Einträgen in 0 bis 9999; der temporäre Bereich ist vollständig disjunkt. Die anschließende Vergabe 0 bis N-1 kollidiert deshalb nicht mit UNIQUE(playlist_id, position). Alle Zwischenschritte bleiben in derselben Transaktion und verletzen CHECK(position >= 0) nicht.
- Materielle RENAME-/REMOVE-/MOVE-Änderungen bei maximaler Revision werden mit REVISION_EXHAUSTED vor der Mutation abgewiesen. No-op-Rename und No-op-Move bleiben ohne neue Revision zulässig. DELETE erfindet keine neue Revision und liefert den letzten geprüften Wert als deletedRevision; deshalb ist DELETE auch an der Maximalrevision zulässig.
- DELETE entfernt Playlist und eigene Einträge über die aktivierte Foreign-Key-Cascade. Commandbelege bleiben erhalten. Wiederholung derselben Lösch-commandId liefert den ursprünglichen Beleg; ein neuer Löschwunsch gegen das fehlende Objekt wird dauerhaft als NOT_FOUND abgelehnt.
- LIST validiert limit als echte Ganzzahl 1 bis 200 und cursor nach der gemeinsamen Tokenregel vor dem ersten SQLitezugriff. Keysetabfrage sortiert nach playlistId und liest limit plus 1. nextCursor ist genau dann die letzte ausgelieferte ID, wenn eine weitere Zeile existiert; sonst null. Bei unverändertem Bestand wird keine leere Folgeseite fälschlich angekündigt; zwischen Seiten dürfen konkurrierende Änderungen auftreten.
- LIST besitzt exakt contractVersion, playlists und nextCursor; jede Zeile nur playlistId, name und revision. Ein einzelnes SELECT/fetchall liest die Seite konsistent. Unterschiedliche Seiten sind vertraglich keine gemeinsame dauerhafte Momentaufnahme. SQLwerte sind parametrisiert; der Cursor wird nicht als Pfad interpretiert.

## Tests und Beweisgrenzen

Selbst ausgeführt in `G:/Entwicklung/phoniebox-staging/p03a2`: `python -B -m unittest discover -s test/playlists -p test_store.py -v`, mit PYTHONPATH auf dessen `src/jukebox` und die abgeglichenen A02a-Artefakte. Ergebnis: 20 Tests, Exit 0. Dies ist ein lokaler Modulteilnachweis zu den oben kryptografisch zugeordneten Quellinhalten.

Die neuen Fälle prüfen materielles und wirkungsloses Rename, Entfernen eines konkreten doppelten Mediumvorkommnisses, MOVE in beide Richtungen unter UNIQUE sowie No-op und Zielgrenze, DELETE-Beleg und echte Entry-Cascade, Maximalrevision mit erlaubten No-ops/DELETE, drei geordnete LIST-Seiten sowie unzulässige limit-/cursor-Argumente. Die zuvor geprüften 13 Tests bleiben Bestandteil des erfolgreichen Laufs, insbesondere atomarer Read-Snapshot, korrekter Rollback aller drei Tabellen, gleiche und verschiedene konkurrierende Kommandos, BUSY/Retry und Ledgernullfehler.

Vollständiger GitHub-Actions-Checkout, Pythonmatrix und dortige Lintprüfung werden separat von Root verfolgt; deren Abschluss wurde in diesem Review nicht vorweggenommen. Der Reviewer hat keine zusätzlichen Tests oder Patches geschrieben und keine reale Box angesprochen.

## Nicht blockierender Dokumentationspunkt

Der frühere CONTRACT1-Absatz zur Übersicht nennt noch items, während die später ausdrücklich für P03a2 ergänzte Rootpräzisierung playlists festlegt. Für dieses Review ist die neuere explizite Festlegung maßgeblich. Root wurde auf den älteren widersprüchlichen Ausdruck hingewiesen; der Reviewer hat den freigegebenen Vertrag nicht eigenmächtig geändert.

Quellen: [exakter Compare](https://github.com/Motrish/RPi-Jukebox-RFID/compare/52fa7be23e2cccaff00cb21e60d3902cb0feb851...9c859a2e91f90e25d84f4e32ffe9ab369f0d5202), [CONTRACT1](a01-contracts.md), [vorheriges Store-Review](p03a1-review.md).

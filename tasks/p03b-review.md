# P03b – unabhängiges Review

Geprüfter Commit: `1b6f1a86725b60310f74ca0c69ee0a5c380c6559`, Tree `e268b0d3e280ae875a4a8eeea683598b05fb7e46`, gegen `9c859a2e91f90e25d84f4e32ffe9ab369f0d5202`. Stand: 16.10.2026. Reviewer unabhängig vom Luna-Codeautor; ausschließlich Prosa, keine Produkt-/Teständerung.

## Urteil

Kein freigabesperrender Befund für den transportfreien P03b-Slice. Die neun Queue-Schreibaktionen und get_queue entsprechen den freigegebenen CONTRACT1-Daten-/Transaktionsregeln. Der bestehende gemeinsame Schreibpfad und das Commandregister werden erweitert; es entsteht kein zweites Idempotenzregister und keine zweite Audiosteuerung.

Dies ist eine fachliche Code-/Testfreigabe des genannten SHAs. Sie ist kein vollständiger integrierter CI-/Runtime-/Hardware-/Migrationsnachweis. Insbesondere QUEUE_SET_CURRENT bleibt eine interne Datenoperation; keine RPCregistrierung oder Controller-/Providerwirkung wurde eingeführt.

## Remoteinhalt und Identität

GitHub-Compare meldet genau einen Commit und ausschließlich zwei Dateien. Beide Inhalte wurden am exakten SHA gelesen und gegen Staging geprüft. Nach Entfernung ausschließlich des lokalen UTF-8-BOM ergeben die berechneten Git-Blob-SHA-1-Werte exakt die Remoteobjekte; übrige Bytes einschließlich Zeilenenden sind identisch.

| Datei | Git-Blob-SHA |
| --- | --- |
| src/jukebox/components/playlists/store.py | 6465ade05f159296b428230bcf7674015f960d5b |
| test/playlists/test_queue_store.py | 2ff2d887007819fc4daaffe46fdf1170a9163aba |

Die sechs weiteren lokal für die Tests verwendeten Dateien wurden ebenfalls gegen ihre bereits geprüften Vorgängerblobs abgeglichen: Paketinitialisierung 4de7ab192e389d328a07b99085d71723d384a3eb, bisherige Storetests 57f1ac4c0731c6d2b87103893a03cd2410ac159c sowie A02a-Paket, Validator, Contracttests und Fixture mit den im A02a-Review verzeichneten SHAs. Der Compare verändert diese Abhängigkeiten nicht. Es wird kein lokaler Vollcheckout behauptet.

## Geprüfte Invarianten

- Alle 15 Playlist-/Queue-Schreibkommandos laufen durch denselben validierten Rahmen und dieselbe BEGIN-IMMEDIATE-Transaktion. Beanspruchung der global eindeutigen commandId, Prüfung, Mutation und Resultatpersistenz bleiben atomar. Inhaltstreue Wiederholung liefert das ursprüngliche Ergebnis mit denselben generierten IDs; anderer Inhalt unter derselben ID mutiert nichts.
- QUEUE_CREATE erzeugt Revision 0, eigene Queueeintrags-IDs, sourceEntryId null, keine Auswahl/Herkunft und Modi OFF. Identische Medien erhalten getrennte Eintragsidentitäten.
- QUEUE_APPEND erhält vorhandene Herkunft, Modi und Auswahl; neue Vorkommnisse tragen sourceEntryId null. Leeres Anhängen ist wirkungslos. Materielle Änderung prüft Listen-/Revisionsgrenze und erhöht nur die Queuerevision.
- QUEUE_REMOVE prüft nach der Queuerevision den Auswahlguard und anschließend die konkrete Eintrags-ID in genau dieser Queue. Der aktuell ausgewählte Eintrag kann nicht durch eine reine Storeoperation entfernt werden. Andere Vorkommnisse bleiben erhalten, Positionen werden lückenlos neu vergeben, die Auswahl-ID bleibt stabil.
- QUEUE_MOVE verschiebt nach dem endgültigen Index und erhält IDs sowie aktive Auswahl. Die temporäre Reindexierung um 10001 ist wie bei Playlists disjunkt vom gültigen Bereich 0 bis 9999 und damit unter UNIQUE(queue_id, position) sicher. No-op-Move erhöht keine Revision.
- QUEUE_SET_MODES ändert ausschließlich Modi und gegebenenfalls einmal die Queuerevision, nicht die Eintragsordnung. QUEUE_SET_CURRENT akzeptiert nur null oder ein Vorkommnis derselben Queue. Eine echte Auswahländerung erhöht die Queuerevision; wiederholter identischer Zustand bleibt wirkungslos. Keine Operation behauptet hörbare Wiedergabe.
- QUEUE_LOAD_PLAYLIST liest beide Objektstände unter derselben Schreibtransaktion und meldet alle festgestellten Revisionskonflikte vor Mutation. Eine Auswahl verhindert Ersetzen. Erfolg kopiert die exakte Playlistordnung mit neuen Queue-IDs und echten sourceEntryIds, setzt Herkunft auf den übernommenen Stand, Auswahl auf null und Modi OFF. Nur die Queuerevision steigt; Playlist bleibt unverändert. Neuer Ladebefehl erzeugt immer eine neue Kopie, gleicher commandId spielt den alten Beleg wieder.
- QUEUE_SAVE_NEW_PLAYLIST prüft die Queuerevision und erzeugt eine neue Playlist mit Revision 0 und frischen Eintrags-IDs. QUEUE_SAVE_PLAYLIST prüft Queue- und Zielplaylistrevision gemeinsam, meldet beide Konflikte und ersetzt Zielzeilen erst danach. Zielname bleibt erhalten; nur die Playlistrevision steigt. Queue, Auswahl, Modi und historische Herkunft bleiben unverändert.
- Additive queues-/queue_entries-Tabellen besitzen eine eigene Queue-Entry-Cascade, aber keine Foreign Keys von sourcePlaylistId/sourceEntryId auf die Herkunftsplaylist. Löschen der gespeicherten Playlist löscht damit weder Queuekopie noch historische Herkunft. CREATE/APPEND/LOAD erzeugen zugleich nur die für ihre Fälle konsistente Herkunft; das früher diskutierte Validatorquerfeldthema führt hier nicht zu widersprüchlichen erzeugten Daten.
- get_queue validiert die ID vor SQLite und liest Header samt Einträgen in einer gemeinsamen BEGIN-Readtransaction. Revisionswert, Auswahl und Eintragsordnung stammen damit aus einer Controllersicht der Datenbank. Rückgabe wird durch den unveränderten Queuevalidator geprüft.
- Maximale Revisionen verhindern materielle Änderungen vor Wirkung; No-ops bleiben möglich. Fehlende Objekte, aktive Auswahl und Revisionskonflikte ergeben strukturierte gespeicherte Ablehnungen. Technische Persistenzfehler rollen Mutation und Commandbeanspruchung gemeinsam zurück; das vorhandene BUSY-/Retryverhalten wird weiterverwendet.

## Selbst ausgeführte Prüfungen

Arbeitsordner `G:/Entwicklung/phoniebox-staging/p03b`, PYTHONPATH auf dessen `src/jukebox`:

- `python -B -m unittest discover -s test/playlists -p 'test_*.py' -v`: 36 Tests, Exit 0.
- `python -B -m unittest discover -s test/contracts -p test_v1.py -v`: 22 Tests, Exit 0.

Das sind lokale Modulteilnachweise für die oben identifizierten Inhalte. Die 16 neuen Queuefälle umfassen erzeugte IDs/Duplikate, persistente Wiederholung/Reopen, Auswahl-/Modus-/Revisionsregeln, aktiven Remove-/Loadguard, beide Konflikte bei LOAD und SAVE, Kopier-/IDtrennung, historische Quelle nach Playlistlöschung, gemeinsame Idempotenz über getrennte Storeobjekte und Rollback bei Load/Save/Save-New. Die bisherigen 20 Playlist-/Ledgerfälle bleiben erfolgreich.

Root meldet zusätzlich Lint Exit 0. Ein eigener erneuter Lintlauf des Reviewers und ein abgeschlossener vollständiger Actionslauf werden hier nicht behauptet. Reale Box, Audio und Musikdaten wurden nicht angesprochen.

## Unabhängige Gegenproben als Prosa für Q01

Folgende Fälle sind sinnvolle nächste unabhängige Nachweise, keine behaupteten durch den Reviewer geschriebenen oder ausgeführten Tests und keine zusätzlich erfundenen Sperrkriterien:

1. Queue-Read unter WAL gezielt zwischen Header- und Entryabfrage mit einem konkurrierenden Append bzw. Auswahlwechsel verschränken. Erwartet: vollständig alter Snapshot, anschließend vollständig neuer Snapshot. Die Implementierung besitzt die korrekte gemeinsame Readtransaction; bisher ist dieser gezielte Interleavingfall nur für get_playlist vorhanden.
2. Eine wirklich mit dem vorigen P03a2-Stand erzeugte Drei-Tabellen-Datenbank samt Playlist-/Commandbelegen mit P03b öffnen. Erwartet: unveränderte alte Inhalte plus funktionierende neue Queuetabellen. Der neue Test mit additive_queue_schema im Namen startet bereits mit dem P03b-Initializer und belegt daher Reopen/Koexistenz, keinen echten Versionsübergang. Die aktuelle SQLänderung ist allerdings rein additiv und ersetzt keine vorhandenen Tabellen.
3. Eine Playlist laden, danach dieselbe gespeicherte Playlist bearbeiten und die geladene Queue anhängen/verschieben; anschließend die Queue zurück in genau diese Playlist speichern. Erwartet: historische sourcePlaylistRevision der Queue bleibt unverändert, Zielrevision steigt getrennt und die Queuekopie folgt keiner gespeicherten Änderung automatisch.
4. Einen erfolgreichen LOAD-/SAVE-Beleg erst nach weiteren Objektänderungen und Reopen wiederholen. Erwartet: dieselben ursprünglichen IDs und Resultate; keine Neuladung des aktuellen Quellstands. Dafür dieselbe commandId auch absichtlich mit einer anderen Aktionsfamilie verwenden: COMMAND_ID_REUSED, keine zweite Wirkung.

Diese Proben ergänzen vorhandene Fälle, ersetzen aber keine spätere Controller-, Event-, Sicherheits- oder Geräteabnahme. Die früheren LIST-/Getter-Prosaunterschiede sind durch Root im Contract bereinigt.

Quellen: [exakter Compare](https://github.com/Motrish/RPi-Jukebox-RFID/compare/9c859a2e91f90e25d84f4e32ffe9ab369f0d5202...1b6f1a86725b60310f74ca0c69ee0a5c380c6559), [CONTRACT1](a01-contracts.md), [A02a-Review](a02-review.md), [P03a2-Review](p03a2-review.md).

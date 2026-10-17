# Q01 Store – unabhängiges Review

Geprüfter Commit `7cabbafa7b6440f57a9d265a63f052e2a08d6edf`, Tree `7addf447bc51354995110b78df485778de611a1f`, gegen `b2be3f39f54d8f492966a407c3b7293d1311e1fa`. Stand: 16.10.2026. Ausschließlich Testreview/Prosa, keine Produktänderung durch Reviewer.

## Urteil

Kein freigabesperrender Befund. Der einzelne neue Test ergänzt die zwei im P03b-Review benannten unabhängigen Nachweise sinnvoll: physische Datenbank im früheren Drei-Tabellen-Schema vor Queueinitialisierung und deterministisches WAL-Interleaving während get_queue. Beide Fälle arbeiten mit realem SQLite und dem tatsächlichen Store, ohne gefälschte Storeantworten.

GitHub-Compare zeigt genau eine neue Datei `test/playlists/test_store_regressions.py`, Blob `030f993e1c35aec199ec33c91f0e8c6c1ad29a25`. Der vollständige Remoteinhalt wurde am exakten SHA gelesen. Der lokale Git-Blobhash stimmt nach Entfernung ausschließlich des UTF-8-BOM exakt überein. Der Compare von P03b `1b6f1a8` zur Q01-Basis `b2be3f3` zeigt ausschließlich die bereits separat geprüfte Installer-CI-Datei; die Storequelle blieb unverändert.

## Aussage der zwei Fälle

Der Schemafall baut anhand der mit P03a2 abgeglichenen DDL tatsächlich nur playlists, playlist_entries und command_log auf, schreibt synthetische Playlist-/Entrydaten sowie einen vollständigen historischen Commandbeleg und schließt die Verbindung. Vor Öffnen des neuen Stores wird ausdrücklich bestätigt, dass queues und queue_entries fehlen. Der aktuelle Initializer ergänzt diese Tabellen; Playlist und alter Commandbeleg bleiben identisch lesbar. Wiederholung des alten Befehls gibt denselben gespeicherten Resultatsnapshot zurück und erzeugt keine zweite Playlist. Anschließend funktionieren Queueanlage, Laden der alten Playlist und Anhängen neuer Einträge.

Das belegt einen synthetischen Übergang des echten früheren SQLite-Schemas. Die frühere Produktversion bzw. ein alter Installer wird dabei nicht ausgeführt; ein V2-/Geräte-/allgemeiner Migrationsnachweis wird daraus nicht abgeleitet. Die synthetischen IDs erfüllen die freigegebene opaque Tokenregel.

Der WAL-Fall setzt SQLite-WALmodus und installiert ausschließlich auf der tatsächlichen QUEUE_GET-Verbindung einen Tracecallback vor der Entryabfrage. Dieser löst über dieselbe öffentliche Store-API, aber eine eigene Schreibverbindung, einen realen APPEND samt Commit aus. Eine Wiederholungssperre verhindert rekursive Auslösung. Schreibfehler werden gesammelt und explizit ausgeschlossen; der Test prüft zusätzlich, dass die Auslösung tatsächlich stattfand und der Writer APPLIED meldet. Der alte Getter liefert trotzdem alte Revision und alte Einträge. Ein späterer Getter liefert erhöhte Revision und beide Einträge. Damit wird die zuvor nur statisch geprüfte atomare Readtransaction gezielt herausgefordert; kein Threadtiming oder Sleep ist nötig.

## Selbst ausgeführte Prüfung

Im Artefaktordner `G:/Entwicklung/phoniebox-staging/q01-store`, mit PYTHONPATH auf die zuvor abgeglichene unveränderte P03b-Quelle:

`python -B -m unittest discover -s test/playlists -p test_store_regressions.py -v`

Ergebnis: zwei Tests, Exit 0. Das bleibt ein lokaler Modulteilnachweis. Die zuvor selbst geprüften 36 Storetests und 22 Contracttests werden nicht als neuer vollständiger CI-Lauf dieses SHAs ausgegeben. Root berichtet zwei frische erfolgreiche Fälle, der Luna-Autor weitere Store-/Lintprüfungen; vollständige Actionsabnahme ist getrennt.

Keine Netzwerk-/Audio-/Hardware-/Produktwirkung wird durch die Fälle eingeführt; temporäre Datenbanken enthalten ausschließlich synthetische Daten. Keine zusätzlichen Tests oder Patches vom Reviewer.

Quellen: [exakter Compare](https://github.com/Motrish/RPi-Jukebox-RFID/compare/b2be3f39f54d8f492966a407c3b7293d1311e1fa...7cabbafa7b6440f57a9d265a63f052e2a08d6edf), [P03b-Review](p03b-review.md).

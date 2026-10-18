# B01a – unabhängiges finales Review

Geprüfter Commit `fb2a7d0d5388b775ffa369c0eeed920509d407d6`, Tree `50fbca0d67e879b43994b4286b9b1bc850199930`, gegen `b2be3f39f54d8f492966a407c3b7293d1311e1fa`. Stand: 16.10.2026. Reviewer unabhängig vom Luna-Codeautor; ausschließlich Prosa, keine Code-/Teständerung.

## Urteil

Kein freigabesperrender Befund für den eng freigegebenen B01a-Slice. Der Reader liest ausschließlich Modell und Prozentwert, ist standardmäßig deaktiviert und liefert bei jedem Fehler einen vollständigen unbekannten Status. Die Rootpräzisierungen zu Deadlineprüfungen nach I/O, erstem LF, Folgeevents und fünfteiliger Fehlerform sind umgesetzt und durch vorhandene Regressionen geprüft.

Dies ist eine fachliche Code-/Mocktestfreigabe des genannten SHAs. Keine Hardware-/Managerinstallations-/UDS-Rechte-/Gesamt-B01-Abnahme. Das von Root benannte Ziel Raspberry Pi Zero W ARMv6, Raspberry Pi OS Lite 32-bit und PiSugar 2 (2-LED) wurde nicht angesprochen oder als funktionierend getestet.

## Umfang und Blobabgleich

GitHub-Compare meldet genau einen Commit mit ausschließlich drei neuen Dateien. Alle drei wurden am exakten SHA gelesen. Nach Entfernung ausschließlich des lokalen UTF-8-BOM ergeben die berechneten Git-Blob-SHA-1-Werte exakt die Remoteobjekte; übrige Bytes einschließlich Zeilenenden sind identisch.

| Datei | Git-Blob-SHA |
| --- | --- |
| src/jukebox/components/pisugar/__init__.py | 170855ec11b92258d4589cd863dd5dc61f6bf415 |
| src/jukebox/components/pisugar/manager.py | f6fd80fecd9a67ad0ceff20e8f79799d827f39c7 |
| test/pisugar/test_manager.py | 551d412c81b92ddddce20aba4a30302f5539ed9a |

Keine Registrierung, zusätzliche Abhängigkeit, GPIO-/I²C-/RTC-/Shutdownaktion, Service-/Workflowänderung oder Hintergrundabfrage ist enthalten. Ein lokaler Vollcheckout wird nicht behauptet.

## Protokollprüfung am offiziellen Quellpin

Zusätzlich tatsächlich gelesen: offizielles PiSugar-Repository am Commit `ea025c2d3d261427206ae1a2e9b8f853c2b3af12`, Dateien pisugar-server/src/stream.rs, pisugar-server/src/cmds.rs und pisugar-core/src/model.rs. Strictstream verwendet LinesCodec, Standardstream ergänzt LF an Antworten; beide führen zusätzlich einen Eventkanal. Response.entire_string erzeugt das erwartete Schlüsselpräfix. Die dortigen get-model-/get-battery-Zweige und alle vier Modellnamen stimmen mit dem Reader überein.

Je Befehl wird eine neue lokale AF_UNIX/SOCK_STREAM-Verbindung geöffnet. Sichtbare Schreibdaten sind ausschließlich `get model` plus LF und `get battery` plus LF. Der Reader stellt kein frei parametrisierbares öffentliches Kommandointerface bereit. Nach der ersten LF-Zeile wird geschlossen; Daten danach werden nicht als Teil der Antwort dekodiert. Ein vorangestelltes Event hat das falsche Präfix und schlägt bewusst geschlossen fehl. Diese Strategie entspricht der aktuellen Rootfreigabe; sie garantiert keine erfolgreiche Messung während eines vorgezogenen Managerereignisses.

## Geprüfte Verhaltenseigenschaften

- Konstruktion erzeugt keine Socketverbindung. enabled=false ist Standard; read_status liefert dann sofort das definierte Deaktivierungsobjekt ohne I/O. enabled und Timeouttypen werden geprüft; Boolean, nicht endliche Werte und Timeout außerhalb 0,05 bis 1,0 Sekunden werden abgewiesen. Auch sehr große Integer erreichen keine unsichere Floatkonvertierung.
- Jeder Befehl erhält eine eigene absolute monotone Deadline. Connect, Senden und alle Empfangsteilstücke verwenden ausschließlich die jeweils verbleibende Zeit; Teilstücke verlängern das Budget nicht. Nach Connect wird vor Send erneut geprüft, nach Send explizit und nach jedem Recv erneut, bevor die Antwort akzeptiert wird. Ein vollständig erst nach Frist zurückkehrender Read gilt deshalb als Timeout. Zwei vollständige Befehle können zusammen bis zu zwei einzelne Befehlsbudgets benötigen; es wird keine gemeinsame Ein-Sekunden-Frist für die gesamte Messreihe behauptet.
- Der Empfang fordert höchstens die verbleibenden Bytes bis 512 plus ein zusätzliches Grenz-/LFbyte an. Die erste Zeile wird vor strikter UTF-8-Dekodierung auf maximal 512 Bytes begrenzt. Ein einzelnes CR vor LF wird entfernt; fehlendes LF, EOF, kaputte Kodierung, Übergröße und falsches/leer-/whitespacebehaftetes Präfix-/Wertformat werden abgewiesen. Ereignisdaten nach LF sind ausdrücklich außerhalb dieser ersten Antwort.
- Die Prozentform erlaubt nur vollständige numerische Syntax und anschließend endliche Werte im Bereich 0 bis 100. Unterstriche, NaN/Infinity und Werte außerhalb des Bereichs werden nicht als Messung angenommen. 0, 100 und Dezimalwerte bleiben erhalten.
- Nur exakt PiSugar 2 (4-LEDs), PiSugar 2 (2-LEDs), PiSugar 2 Pro und PiSugar 3 werden erkannt. Unbekanntes Modell führt vor Batteryabfrage zu UNSUPPORTED_MODEL und vollständigen Nullwerten, nicht zu einer ähnlich benannten Modellannahme.
- Socketfehler werden in feste Kategorien überführt; Berechtigungsfehler und unbekanntes Modell sind nicht retryable, die anderen freigegebenen Kategorien schon. error besitzt genau code, message, retryable, operation und details; operation ist BATTERY_STATUS und details ist leer. Kein Raw-Servertext, Traceback oder konfigurierter Socketpfad wird ausgegeben. Das belegt die A01-Fehlerform mit dem freigegebenen B01-Codesatz, keine Kompatibilitätsbehauptung zum engeren bisherigen Store-Errorvalidator.
- Erfolg setzt detected/reachable true, Modell und Prozent sowie erst nach beiden gültigen Antworten measuredAt in UTC. Scheitert insbesondere der zweite Read, werden auch das vorher gelesene Modell und sämtliche Mess-/Zeitwerte null. Es existiert kein Messwertcache. charging bleibt stets null und capabilities stets leer; Modellnamen schalten keine Energieaktionen frei.
- Jede geöffnete Verbindung wird im finally-Block geschlossen, auch bei Parse-/Timeout-/Socketfehlern. Es gibt keinen TCP-Fallback.

## Selbst ausgeführte Verifikation

Arbeitsordner `G:/Entwicklung/phoniebox-staging/b01`, PYTHONPATH auf dessen src/jukebox:

`python -B -m unittest discover -s test/pisugar -p test_manager.py -v`

Ergebnis: 20 Tests, Exit 0. Vorhandene Fälle belegen insbesondere standardmäßig deaktiviertes Verhalten, nur zwei feste Befehle/frische Verbindungen, vier Modelle, Prozentgrenzen, alle Fehlerkategorien, vollständige Nullwerte bei Teilausfall, falsches Framing/UTF-8/Übergröße, Event vor bzw. nach Antwort und beide absoluten Deadlinefälle mit simuliertem Zeitfortschritt. Root meldet zusätzlich frischen Lint Exit 0; ein eigener weiterer Lintlauf wird nicht behauptet.

Das Socketfixture simuliert auf dem Windows-Testhost gegebenenfalls die fehlende AF_UNIX-Konstante. Die Tests beweisen deshalb Fake-/Parserverhalten, keine Windows-UDS-Unterstützung und keine echte Linuxsocket-Verbindung. Auf dem Ziel bleiben Manager-/Firmwareversion, Socketpfad und Rechte, Strictmodus, reale Responsevarianten, Netzteilwechsel und Ausfälle zu prüfen. Das spätere Fünf-Sekunden-Polling mit begrenztem Backoff ist nicht Teil dieses Readers.

Einige frühere allgemeine Absätze im B01-Vertragsbericht nennen noch fehlende Geräteangaben bzw. jede Zusatzzeile als Fehler; die späteren Rootpräzisierungen und der aktuelle Auftrag bestimmen hier die maßgebliche Ziel-/Firstline-Semantik. Der Reviewer hat den Vertrag nicht eigenmächtig geändert.

Quellen: [exakter Produktcompare](https://github.com/Motrish/RPi-Jukebox-RFID/compare/b2be3f39f54d8f492966a407c3b7293d1311e1fa...fb2a7d0d5388b775ffa369c0eeed920509d407d6), [B01-Vertrag](b01-pisugar-contract.md), [offizieller Streamquellstand](https://github.com/PiSugar/pisugar-power-manager-rs/blob/ea025c2d3d261427206ae1a2e9b8f853c2b3af12/pisugar-server/src/stream.rs), [offizielle Befehle](https://github.com/PiSugar/pisugar-power-manager-rs/blob/ea025c2d3d261427206ae1a2e9b8f853c2b3af12/pisugar-server/src/cmds.rs), [Modellnamen](https://github.com/PiSugar/pisugar-power-manager-rs/blob/ea025c2d3d261427206ae1a2e9b8f853c2b3af12/pisugar-core/src/model.rs).

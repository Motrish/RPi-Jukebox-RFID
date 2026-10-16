# B01 PiSugar-Statusadapter: Recherche und Vertragsvorschlag

Stand: 2026-10-16. Die Recherche wurde für den freigegebenen B01a-Slice aktualisiert. Dieser Slice liest ausschließlich Modell und Prozentwert über die lokale UDS-Verbindung; es gibt keine PiSugar-Aktionen, RTC-Aufrufe, Abschaltungen, Konfigurationen, Schreibkommandos oder Hintergrundabfragen. Geräte- und Modellangaben zur Zielbox fehlen, deshalb bleibt Hardwareverifikation offen.

## Abgleich mit den Projektverträgen

Backlog B01 verlangt das Lesen des lokalen Managers, Modell/Fähigkeiten/Messzeit, Parser-, Timeout- und Berechtigungsfehlerbehandlung sowie anfängliches Fünf-Sekunden-Polling mit begrenztem Fehlerbackoff. Gültige, fehlerhafte und fehlende Antworten müssen unterscheidbar sein; alte Werte dürfen nicht als frisch erscheinen. Der reale Netzteilwechsel gehört zur Hardwareprüfung F04.

A01 BatteryStatus ist die maßgebliche Form: `contractVersion`, `enabled`, `detected`, `reachable`, `model`, `percent`, `charging`, `measuredAt`, `capabilities`, `error`. `detected` ist `true`, `false` oder `null`; `reachable` ist Boolean; `model` ist Text oder `null`; `percent` ist 0–100 oder `null`; `charging` ist Boolean oder `null`; `measuredAt` ist UTC oder `null`. Deaktiviert liefert `enabled=false`, `detected=null`, `reachable=false`, Null-Messwerte, leere `capabilities` und keinen Badge. Ein fehlgeschlagener aktueller Leseversuch liefert `reachable=false`, `percent=null`, `charging=null`; dieser Vorschlag cached keine alten Messwerte. Aktionen in `capabilities` werden nicht von diesem Statusadapter geliefert.

Quellen: [Projekt-Backlog B01](../docs/superpowers/plans/multi-agent/backlog.md#b01--socketstatus-und-fähigkeiten) · [A01 BatteryStatus](a01-contracts.md#batteriestatus-und-setupjob--vorläufige-anschlussverträge).

## Verifizierte PiSugar-Schnittstelle

Die offizielle [PiSugar Power Manager Dokumentation](https://docs.pisugar.com/docs/product-wiki/battery/pisugar-power-manager) nennt den Unix-Domain-Socket `/tmp/pisugar-server.sock`; TCP 8423, WebSocket 8422 und HTTP 8421 sind ebenfalls dokumentiert, werden hier aber nicht benutzt. Die Dokumentation zeigt `nc -U /tmp/pisugar-server.sock` und zeilenbasierte Befehle. Für Status sind belegt:

| Nur-Lese-Befehl | dokumentierte Antwort | Einsatzvorschlag |
| --- | --- | --- |
| `get model` | `model: PiSugar 2` | Modell feststellen; streng gegen bekannte Namen prüfen |
| `get battery` | `battery: [number]` | Prozent; nur endliche Zahl 0–100 akzeptieren |
| `get battery_charging` | `battery_charging: [true|false]` | dokumentiert mit Hinweis, für neue Modelle stattdessen die zwei folgenden Werte zu verwenden |
| `get battery_power_plugged` | `battery_power_plugged: [true|false]` | laut Doku nur neues Modell |
| `get battery_allow_charging` | `battery_allow_charging: [true|false]` | laut Doku nur neues Modell |
| `get battery_led_amount` | `battery_led_amount: [2|4]` | Doku erklärt 2 LEDs als neues PiSugar-2-Modell; kein hinreichender Beleg für universelle Capability-Inferenz |

Die [offizielle Rust-Implementierung](https://github.com/PiSugar/pisugar-power-manager-rs/tree/ea025c2d3d261427206ae1a2e9b8f853c2b3af12) bestätigt die Standard-UDS-Adresse im README und die Antworten im `pisugar-server/src/cmds.rs`: `get <name>` antwortet als `<name>: <Wert>`, Fehler als Text. `pisugar-server/src/stream.rs` verarbeitet Requests zeilenweise und schreibt eine Antwort pro Zeile. Der Server hat zusätzlich einen Eventkanal, der Statusantworten ungefragt in dieselbe Verbindung schreiben kann. Deshalb sollte der Adapter pro Befehl eine frische UDS-Verbindung öffnen, genau eine Kommandozeile senden und die erste begrenzte Antwortzeile lesen, statt eine dauerhafte Verbindung oder ein frei wiederverwendbares Kommandointerface anzubieten. Der dokumentierte und implementierte Server hat sowohl Standard-Streammodus als auch optionalen Strict-Modus; an der Zielinstallation ist deren Konfiguration noch nicht bekannt. Das Verhalten mit realer Installation muss F04 prüfen.

Die Rust-Quelle kennt genau die Modellstrings `PiSugar 2 (4-LEDs)`, `PiSugar 2 (2-LEDs)`, `PiSugar 2 Pro`, `PiSugar 3` (`pisugar-core/src/model.rs`). Die Doku beschreibt PiSugar 2 4-LED als altes Modell, 2-LED als neues Modell und weist für PiSugar 3 auf getrennte Modellunterstützung hin. Sie sagt, neue Modelle sollen Ladezustand aus `battery_power_plugged` und `battery_allow_charging` ableiten. Da die tatsächliche Zielbox fehlt und die Begriffe „new model“ in der Doku kein vollständiges Modell-Mapping spezifizieren, bleibt `charging=null`, solange ein künftig freigegebener Modellprofil-Eintrag nicht genau festlegt, welche Antworten erforderlich sind und wie `charging` hergeleitet wird. Unbekannte Modellstrings werden nicht auf ein ähnliches Modell abgebildet. Status-Capabilities bleiben leer; Modellstrings allein schalten keine Fähigkeiten frei.

Es werden ausschließlich die oben genannten `get`-Befehle gesendet. Insbesondere kein `set_*`, `rtc_*`, `safe_shutdown_*`, `force_shutdown`, `help` oder Shell-/Konfigurationskommando. Dass die Serverimplementierung weitere lesende Kommandos kennt, ist keine Freigabe, sie einzubeziehen.

Quellreferenzen: [offizielle Befehlsdokumentation](https://docs.pisugar.com/docs/product-wiki/battery/pisugar-power-manager#commands), [README Socket- und Antwortprotokoll](https://github.com/PiSugar/pisugar-power-manager-rs/blob/ea025c2d3d261427206ae1a2e9b8f853c2b3af12/README.md#unix-domain-socket-websocket-tcp-api), [Server-Streamverarbeitung](https://github.com/PiSugar/pisugar-power-manager-rs/blob/ea025c2d3d261427206ae1a2e9b8f853c2b3af12/pisugar-server/src/stream.rs), [Serverbefehle und Response-Format](https://github.com/PiSugar/pisugar-power-manager-rs/blob/ea025c2d3d261427206ae1a2e9b8f853c2b3af12/pisugar-server/src/cmds.rs), [Modellnamen und LED-Zahl](https://github.com/PiSugar/pisugar-power-manager-rs/blob/ea025c2d3d261427206ae1a2e9b8f853c2b3af12/pisugar-core/src/model.rs).

## API- und Dateivorschlag für die Implementierungsfreigabe

Maximal drei Dateien, alle ausschließlich unter `src/jukebox/components/pisugar/` und Tests unter dem entsprechenden Testbaum:

1. `src/jukebox/components/pisugar/__init__.py` – kleiner Export des Statusadapters.
2. `src/jukebox/components/pisugar/manager.py` – Python-Standardbibliothek (`socket`, `datetime`, `math`, `re`), keine Fremdabhängigkeit und keine Pluginregistrierung.
3. `test/pisugar/test_manager.py` – Tests mit Unix-Socket-Fixture/fake server, kein PiSugar, I²C oder Hardwarezugriff.

Freigegebene API: `PiSugarStatusReader(socket_path="/tmp/pisugar-server.sock", timeout_seconds=1.0, enabled=False).read_status() -> dict`. Der Konstruktor weist Timeoutwerte unter 0,05 Sekunden, über 1,0 Sekunden, nicht endliche Zahlen und boolesche Werte zurück. Das Ergebnis ist ein JSON-kompatibles BatteryStatus-Mapping nach A01. Bei `enabled=False` wird ohne Socketzugriff sofort der definierte deaktivierte Status geliefert. `read_status()` führt pro Aufruf ausschließlich eine feste Liste von `get`-Befehlen aus; keine beliebigen Kommandos von außen, keine eigene Polling-Thread-/Schedulerlogik und kein stale-value-Cache. Der spätere Consumer soll regulär alle 5 Sekunden aufrufen und nach Fehlern mit begrenztem Backoff bis maximal 60 Sekunden arbeiten; der Reader enthält keine Pollingsteuerung.

Jeder einzelne Befehl erhält eine harte Deadline von 1 Sekunde für Connect, Senden und Empfangen; diese wird nicht bei eingehenden Teilstücken zurückgesetzt. Jede Antwortzeile ist auf 512 Bytes begrenzt. Empfang endet beim ersten LF; ein EOF ohne vollständige Antwort, ungültiges UTF-8, zu lange Zeile, unerwartetes Schlüsselpräfix, unerwartete Zeile vor dem Antwortpräfix, kaputte Zahl, NaN/Infinity, Prozent außerhalb 0–100 sowie Socket-/Berechtigungsfehler gelten als fehlgeschlagene aktuelle Messung. Jeder Fehler folgt dem gemeinsamen A01-Errorformat {code, message, retryable, operation, details}, mit operation=`BATTERY_STATUS`, details={} und kategoriefesten messages. SOCKET_MISSING, SOCKET_TIMEOUT, MANAGER_UNAVAILABLE und MALFORMED_RESPONSE sind wiederholbar; SOCKET_PERMISSION_DENIED und UNSUPPORTED_MODEL sind es nicht. Keine rohen Serverfehlermeldungen oder Pfade an API/UI weiterreichen. Eine Teilmessung ist nicht erreichbar und wird nicht als frischer Status publiziert. `measuredAt` wird erst nach erfolgreicher vollständiger, akzeptierter Messreihe auf UTC-Zeit gesetzt.

`detected=true` gilt nur nach vollständiger erfolgreicher Messung mit exakt einem der vier bekannten Modellstrings und gültigem Prozentwert. Unbekannter Modellstring ergibt gemäß B01a `detected=null`, `reachable=false`, `model=null`, alle Messwerte und Zeitstempel null sowie `UNSUPPORTED_MODEL`. Fehlender Socket, Timeout und jeder andere Fehler der aktuellen Messung liefern ebenfalls `detected=null`, `reachable=false`, `model=null`, Null-Messwerte und sichere Fehlercodes. `detected=false` wird in diesem Slice nicht verwendet. Alle Werte sind bei Fehlern null; es gibt keinen Cache. Deaktivierter Reader (`enabled=False`, Standard) macht keinen Socketzugriff, gibt den A01-Deaktivierungssnapshot mit leeren capabilities und `error=null` zurück.

## Vorgeschlagene Fake-Socket-Abdeckung und offene Hardwareprüfung

Die Unit-Tests prüfen alle vier bekannten Modellnamen, Prozent 0/100/Dezimalwerte, unbekanntes Modell, fehlenden Socket, PermissionError, Timeout, EOF/fehlende Antwort, ungültiges UTF-8, falsches Präfix, Event vor bzw. nach der ersten Antwortzeile, Antwortgrenze, kaputte/NaN/Infinity/außerhalb liegende Prozentwerte, Timeout mit tröpfelnder Antwort, fehlgeschlagenen zweiten Read ohne Teilmessung sowie die standardmäßig deaktivierte Variante ohne Verbindungsversuch. Nur die Befehle `get model` und `get battery` dürfen am Fake-Socket sichtbar sein. Assertions müssen zeigen, dass fehlgeschlagene Reads niemals vorherige Messwerte als frisch zurückgeben und dass nur feste `get`-Befehle auf dem Fake-Socket auftauchen. Ladezustandsableitung wird erst getestet, sobald das genaue Modellmapping belegt und freigegeben ist.

Als Zielgerät wurden durch Root ein ursprünglicher Raspberry Pi Zero W (ARMv6), Raspberry Pi OS Lite 32-bit und PiSugar 2 (2-LED) bestätigt. Diese Angaben sind noch kein Live-Hardwaretest. Offen bis F04 bleiben installierte PiSugar-Version/Firmware, tatsächlicher Socketpfad/Dateirechte, Manager-Version und Strict-Modus, reale Response-Varianten/Zeilenenden, Netzteilwechsel unter Last und Verhalten bei laufendem Manager-Neustart. Der Reader setzt `charging=null` und `capabilities=[]` für alle Modelle, bis dafür ein eigener Modellprofil-Scope freigegeben wird. Das 5-Sekunden-Polling und ein maximal 60-Sekunden-Fehlerbackoff gehören zum späteren Consumer, nicht in diesen Reader. Die offizielle Doku und der geprüfte Rust-Quellstand `ea025c2d3d261427206ae1a2e9b8f853c2b3af12` belegen den veröffentlichten Protokollvertrag, aber nicht die Installation auf der Zielbox.





## B01a implementierter Stage-Slice

Root hat B01a eng auf genau drei Dateien freigegeben, Stage-Basis `b2be3f39f54d8f492966a407c3b7293d1311e1fa` und Arbeitsverzeichnis `G:/Entwicklung/phoniebox-staging/b01`. Im Stage liegen `src/jukebox/components/pisugar/manager.py`, `src/jukebox/components/pisugar/__init__.py` und `test/pisugar/test_manager.py`. Es wurde kein Branch und kein Remote-Commit angelegt; Root publiziert nach Übergabe. Der Reader nutzt ausschließlich `AF_UNIX`, eine frische Verbindung je festem Befehl, und sendet nur `get model` sowie `get battery`. `enabled=False` ist Standard und öffnet keinen Socket. `charging` und `capabilities` bleiben immer null bzw. leer. Jeder Befehl hat höchstens eine Sekunde Deadline über Connect/Senden/Empfangen; Parser und Socketfehler ergeben stabile, pfad- und rohtextfreie Fehlercodes. Unbekannte Modellnamen liefern den ausdrücklich freigegebenen UNKNOWN-Snapshot (Modell/Messwerte/Zeitstempel null, `UNSUPPORTED_MODEL`).

Der angeforderte Quellstand wurde am offiziellen PiSugar-Repository als `master` HEAD `ea025c2d3d261427206ae1a2e9b8f853c2b3af12` gelesen; die GitHub-Quelllinks oben sind auf diese SHA gepinnt. Das ist eine Quellbeobachtung, keine Behauptung zur Version auf der Box.

RED-Nachweis: vor Erstellung von `manager.py` lief `python -m unittest discover -s G:/Entwicklung/phoniebox-staging/b01/test/pisugar -v` (mit `PYTHONPATH=G:/Entwicklung/phoniebox-staging/b01/src/jukebox`) mit Exit 1: `ModuleNotFoundError: No module named 'components.pisugar.manager'`. Nach Implementierung scheiterten zunächst Tests auf dem Windows-Host, weil dessen Python kein `socket.AF_UNIX` anbietet; das Test-Fixture simuliert nun diesen Plattformkonstantenwert, während der Produktcode weiter ausschließlich AF_UNIX anfordert und keinen TCP-Fallback hat.

Frische Grünverifikation im Stage:

- `$env:PYTHONPATH='G:\Entwicklung\phoniebox-staging\b01\src\jukebox'; python -m unittest discover -s 'G:\Entwicklung\phoniebox-staging\b01\test\pisugar' -v` — 20 Tests, Exit 0.
- `$env:PYTHONPATH='G:\Entwicklung\phoniebox-tools\python'; python -m flake8 --max-line-length=127 --max-complexity=12 --ignore=E126,E127,E128,W503,F824 --per-file-ignores=__init__.py:F401 src test` — Exit 0. Ein früherer Lintlauf hatte W391/E203/F401 und C901; diese Befunde wurden bereinigt und danach frisch erneut geprüft.
- `python -m py_compile src/jukebox/components/pisugar/manager.py src/jukebox/components/pisugar/__init__.py test/pisugar/test_manager.py` — Exit 0.

Die 20 gezielten Unittests decken die vier Quellmodellnamen, Status mit 0/100/Dezimalwert, disabled-by-default ohne Socket, nur die zwei freigegebenen Befehle, unbekanntes Modell, Socket-/Berechtigungs-/Timeoutfehler, fehlenden Zeilenabschluss, ungültige Kodierung, falsches Präfix, eine unerwartete Zeile vor der Antwort (Fehler) und Eventdaten nach der erwarteten LF-Zeile im selben recv (Erfolg mit anschließendem Socketclose), Antwortgrenze, NaN/Infinity/Underscore-/Rangefehler, tröpfelnde und vollständige aber verspätete Antworten mit absoluter Deadline sowie fehlgeschlagenen zweiten Read ohne Teilmessung ab. Die Tests verwenden Fake-Sockets; sie beweisen weder reale UDS-Rechte noch Verhalten mit PiSugar-Hardware. Der volle Repository-Testlauf und CI bleiben bis zur Veröffentlichung/Integration Root-Aufgabe; F04-Hardwareprüfung bleibt offen.


Veröffentlichungscheckpoint: B01a bei fb2a7d0d5388b775ffa369c0eeed920509d407d6 unabhängig reviewed; Python 3.9–3.13 und finish in 38966180905 erfolgreich. PR 8 als 5057f0b60c4e85f595fd09450be8341f1f377c48 in future3/modern-ui integriert. Die erste gültige LF-Antwort ist maßgeblich; nachfolgende Eventbytes werden ignoriert und die Verbindung geschlossen, vorhergehende falsche Prefixzeilen sind Fehler. Pro Befehl gilt ein eigenes Budget bis einer Sekunde; zwei Reads können zusammen zwei Budgets benötigen. Keine Hardware-/Runtime-/Gesamt-B01-Freigabe.

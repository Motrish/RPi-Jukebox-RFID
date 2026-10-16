# P01a1 – unabhängiges Review

Stand: 16.10.2026. Reviewer Sol; ausschließlich Quellenprüfung, vorhandene Tests und dieser Prosa-Bericht. **Keine Freigabe für den geprüften Commit: ein priorisierter Abschluss-/Reservierungsfehler bleibt offen.** Root hat den Sperrbefund bestätigt und die Korrektur seriell an Luna vorgesehen.

## Prüfgegenstand und Integrität

Geprüft wurde Commit `7ede9cfac2c91f1c889b55d31a938d85e4b560dc`, Tree `af274160533d8d37dbb4605486447d802a06ac14`, gegen Parent `5057f0b60c4e85f595fd09450be8341f1f377c48`. GitHub-Commitmetadaten und veröffentlichter Compare bestätigen genau vier neue Dateien. Der vollständige Vertrag `tasks/p01-local-provider-contract.md`, einschließlich Rootfreigabe und der letzten Präzisierungen zu Guard-/Epochfristen, initialem START, OBSERVE und Resolvercallable, wurde gelesen.

Alle vier veröffentlichten Dateien wurden am unveränderlichen Commit über den GitHub Connector gelesen. Die unten angegebenen Git-Blobhashes stimmen mit Staging nach UTF8-Textdekodierung und CRLF→LF-Normalisierung überein. Diese Aussage betrifft den normalisierten veröffentlichten Inhalt, keine rohe Bytegleichheit der Windowsdateien.

| Datei | Veröffentlichter und normalisiert lokal errechneter Git-Blob |
| --- | --- |
| `src/jukebox/components/local_provider/__init__.py` | 0d685fca09d8611b2a56852b788694262e47c75a |
| src/jukebox/components/local_provider/adapter.py | f5e9416e59dfea75585495b27b1d4c500e21af7d |
| test/local_provider/test_adapter.py | 289fa6dc6ea3b08992ae780a84175031725ea884 |
| test/local_provider/fixtures/v1.json | 283e36532dc8576d9b797a16803af30de7ac068a |

Die beiden lokalen Importkopien `jukebox/contracts/__init__.py` und `v1.py` wurden zusätzlich gegen die Originale desselben Remotecommits gelesen. Nach Zeilenenden- und EOF-Newline-Normalisierung ist ihr Inhalt identisch; Remote-Blobs sind `6baaed595c6404fce81ab8748b525d94a9281cb5` und `2c050deaa8863ae1450be83b891cf565566f56d8`. Sie gehören nicht zu den vier veröffentlichten Änderungen. Der Stageordner ist ein Teilmodul, kein vollständiger Checkout.

Quelle: [Commit](https://github.com/Motrish/RPi-Jukebox-RFID/commit/7ede9cfac2c91f1c889b55d31a938d85e4b560dc), [Adapter](https://github.com/Motrish/RPi-Jukebox-RFID/blob/7ede9cfac2c91f1c889b55d31a938d85e4b560dc/src/jukebox/components/local_provider/adapter.py), [Tests](https://github.com/Motrish/RPi-Jukebox-RFID/blob/7ede9cfac2c91f1c889b55d31a938d85e4b560dc/test/local_provider/test_adapter.py).

## P1 – Kontextabschluss kann Wirkung vergessen oder eine unbestätigte Reservierung freigeben

Betroffen sind insbesondere `adapter.py:164–181`, `329–355` und `469–474`. Erfolgsreceipt und interne Erfolgszustände entstehen noch innerhalb von `with self._session(...)`. Anschließend läuft erst `session.transaction.__exit__`. Eine Exception dieses Abschlusses wird in `_session` als Fehler mit `effect=False` übersetzt. Zu diesem Zeitpunkt ist `_uncertain` bereits auf false gesetzt. Die exklusive Sessionklammer bietet keinen MPD-Rollback; bereits gesendete Optionen, clear/addid/playid/stop bleiben Wirkung.

Konkreter START-Pfad: Vor-/Nachstatus und playid gelingen, danach wirft der Kontextabschluss `SessionFailure("TIMEOUT")`. `_start_resolved` erreicht seinen Fehlerarm und `_restore_unmutated_start` stellt die vorherige Zuordnung wieder her. Beim allerersten START ist damit überhaupt keine identity mehr reserviert, obwohl der neue Titel läuft. Sein expliziter Cleanup-STOP wird mit EXECUTION_CONFLICT abgewiesen. Bei einem neuen START nach zuvor bestätigtem STOP wird entsprechend die alte terminale Zuordnung wiederhergestellt, obwohl die neue identity bereits mutiert hat. Die Rückgabe kann zudem REJECTED statt UNCONFIRMED behaupten.

Konkreter STOP-Pfad: Nach erfolgreichem Stopstatus werden `_uncertain=False` und `_confirmed_stopped=True` gesetzt. Wirft erst danach der Kontextabschluss TIMEOUT/UNAVAILABLE, liefert die Methode UNCONFIRMED/STOP_UNCONFIRMED, behält aber `_confirmed_stopped=True`. Damit darf anschließend eine neue START-identity beginnen, obwohl der letzte Stopauftrag gegenüber dem Aufrufer ausdrücklich unbestätigt blieb. Das widerspricht dem Vertrag, wonach erst CONFIRMED/STOPPED die Reservierung freigibt.

Dies ist ein statisch nachverfolgter Quellbefund; der Reviewer hat keinen eigenen Testcode erzeugt oder zusätzlichen Reproducer ausgeführt. Der vorhandene Fake besitzt keinen fehlschlagenden Kontextabschluss. Erforderliche Regressionen durch den Autor: Exitfehler nach initialem START, Exitfehler beim neuen START nach terminalem STOP sowie Exitfehler nach STOP. Sie müssen gespeicherte Zuordnung, nächste START-Ablehnung und gezielt erlaubten Cleanup-STOP prüfen, nicht nur den Fehlercode. Nach möglichen Schreibwirkungen darf eine Abschlussstörung weder die alte Zuordnung zurückbringen noch die neue Reservierung vergessen; STOP-Freigabe und Erfolg müssen mit dem vollständigen Abschluss konsistent sein.

Eng verwandte Beleggrenze: `_confirmed` prüft Guard, epoch und Frist vor dem Kontextabschluss, der bereits gebaute Beleg wird anschließend unverändert zurückgegeben. Ändert der Abschluss noch epoch oder verbraucht die restliche Frist und kehrt normal zurück, gibt es keine spätere Prüfung. Die Korrektur muss die Verantwortung für den vollständigen Abschluss und seine epoch-/Deadlinegrenzen ausdrücklich behandeln; ein gültiger Vorabbeleg darf nicht unbemerkt über eine veränderte Session hinweg zurückkehren. Das ist kein Auftrag für reale I/O oder einen größeren Gateway, sondern betrifft dieselbe injizierte Kontextform.

## Bereits nachvollziehbare Vertragsteile

Abgesehen von dieser Abschlusslücke sind die drei letzten Rootkorrekturen im Code vorhanden: Fristprüfung nach Guard und nach Epoch-/Methodenzugriff unmittelbar vor dem Protokollcall; initialer START akzeptiert nur play; OBSERVE mit hasError=true wird PROVIDER_STATE_MISMATCH. Der wiederholte aktive START darf dagegen play/pause beobachten und sendet keine Schreibaktion.

START setzt repeat=0, random=0, single=1, consume=0, leert die Queue und verwendet exakt die ASCII-songid aus addid für playid. Ein frischer Nachstatus bestätigt ID, Einzeleintrag, Profil und play. PAUSE/RESUME nutzen explizit pause(1/0), SEEK bleibt songid-gebunden. Fremde laufende songid wird durch STOP nicht gestoppt; alte identity nach neuer Zuordnung wird vor Sessionaufrufen abgewiesen. Beobachtetes stop löst weder natürliches Ende noch automatische Reservierungsfreigabe aus.

Guard wird vor jedem Protokollcall und vor Bestätigung geprüft. Ein gültiger anderer epoch unterbricht den normalen Protokollpfad und entfernt die alten Beobachtungsfelder aus dem Fehlerbeleg. Zeit-/Sessionstörungen nach mutierenden Calls halten im normalen Callfehlerpfad die Reservierung. Receipt-/Errorfelder sind geschlossen aufgebaut, Diagnosen verwenden eigene sichere Texte, retryable bleibt false. Öffentliche Identity-/Deadline-/Positionseingaben werden vor Wirkung validiert; Statusformen und nicht darstellbare Millisekunden führen zu sichtbarem Fehler. Diese Befunde heben den Kontextabschlussfehler nicht auf.

## Ausgeführte Prüfung und Grenzen

Unabhängig ausgeführt im Stageordner, mit PYTHONPATH auf dessen src/jukebox: `python -B -m unittest discover -s test/local_provider -p test_adapter.py -v`. Ergebnis: **15 Tests, Exit 0**. Root meldete V3lint erfolgreich; der Reviewer hat diesen Lintlauf nicht selbst wiederholt. Die bestehenden Tests beweisen die in ihren Fakes simulierten Fälle, enthalten aber keine der oben genannten Exitregressionen.

Keine reale MPD-/Resolver-/RPC-/Registrybindung und keine Hintergrundarbeit wurden eingeführt. Der injizierte Fake beweist keine tatsächlich begrenzte Lock-/Socket-/Resolverwartezeit, keine physische Audiostille, keinen ARMv6-Betrieb und keine Hardwarefähigkeiten. P04-Serialisierung und Generationhoheit, vertrauenswürdiger realer LibraryResolver, tatsächliche Sessionbegrenzung/Reconnectidentität und spätere Zielgeräte-/Integrationsabnahme bleiben offen. Vollständige Remote-CI wird durch Root separat am Checkpoint beurteilt.

Ergebnis: Korrektur des P1-Befunds und exaktes Folgecommitreview erforderlich; bis dahin P01a1 nicht freigeben. Nur dieser Prosa-Bericht wurde geschrieben.

## Abschluss des Folgereviews am Commit 82d9547

Geprüfter Folgecommit: `82d9547f5c4431e77ef9312f1ca5fbc1e5fe54d6`, Tree `e565397f5a125e8c8d13e6db51489912e1d2ecf6`, direkter Parent `7ede9cfac2c91f1c889b55d31a938d85e4b560dc`, PR 9. **Für diesen Folgecommit ist der oben beschriebene P1-Befund behoben; im eng abgegrenzten Folgereview bestehen keine offenen Blocker.** Die vorherige Sperre bezieht sich weiterhin historisch auf 7ede9cf und wird nicht rückwirkend umgeschrieben. Dieses Ergebnis bewertet den transportfreien Adaptervertrag, keine Runtime-/Hardwarefreigabe und keinen Mergeentscheid.

Der aktualisierte vollständige Vertrag sowie `p01-local-provider-report.md` und `p01-stop-gate-report.md` wurden gelesen. Der frühere Übergabeabschnitt mit 21 Tests beschreibt einen Zwischenstand; maßgeblich für diesen Abschluss ist die spätere Stopfreigabekorrektur mit 25 Tests. Der exakte veröffentlichte Fixdiff umfasst nur die folgenden zwei Dateien:

| Datei | Blob am Folgecommit |
| --- | --- |
| src/jukebox/components/local_provider/adapter.py | 04b870718ba6fd8b7151d953341c99118dd4a082 |
| test/local_provider/test_adapter.py | 71564daa8b970616a73dd7a06dcb60103987e63e |

Beide vollständigen Remote-Blobs wurden gelesen und mit dem eingefrorenen Stage verglichen. UTF8-dekodierter Stageinhalt nach CRLF→LF-Normalisierung stimmt jeweils exakt mit dem Remotetext überein; die unabhängig errechneten Git-Blobhashes ergeben die obigen Werte. Commitmetadaten bestätigen Tree und Parent. Die beiden anderen ursprünglichen P01-Dateien und die Contracts gehören nicht zu diesem Fixdiff.

Die Korrektur schließt den ursprünglichen Effektverlust: `_session` führt in Zeile 345 den abschließenden Guard-/epoch-/Deadlinecheck erst nach normaler Rückkehr aus `session.transaction` aus. START, wiederholter aktiver START, PAUSE/RESUME, SEEK, STOP und OBSERVE verlassen erst diese gesamte Klammer, bevor sie CONFIRMED-Belege erzeugen. Erfolgsmarker werden ebenfalls erst danach gesetzt. Ein Exitfehler nach mutierendem START lässt `_uncertain` und die neue identity/songid erhalten; `_restore_unmutated_start` kann die begonnene Ausführung deshalb nicht auf keine oder eine alte terminale Zuordnung zurücksetzen. Ein normaler Exit mit epochwechsel bzw. Fristablauf liefert keinen Erfolg; bei epochwechsel bleiben die alten Beobachtungsfelder invalidiert. Die entsprechenden Regressionen verwenden den tatsächlichen Nach-yield-Abschluss des Fakekontexts.

Die Stopfreigabe wird in Zeile 163 nach gültiger öffentlicher Eingabe, eigener identity und Stopfähigkeit bereits vor Sessioneintritt entzogen. Daher überlebt ein altes terminales CONFIRMED/STOPPED nicht fälschlich den nächsten angenommenen, unbestätigten STOP. Geprüft und durch bestehende Tests abgedeckt sind Entry-TIMEOUT und -UNAVAILABLE, hasError im aktuellen Status, bereits abgelaufene Deadline sowie ein Exitfehler. In allen diesen Fällen bleibt eine neue START-identity gesperrt; ein anschließend erneut vollständig bestätigter STOP gibt START wieder frei. Eine abgelaufene Deadline sendet keinen Session-/Protokollaufruf. Fremde STOP-identity und ungültige öffentliche Deadline erreichen die Freigabeänderung nicht und erhalten die aktuelle Zuordnung. Auch der alte STOP nach tatsächlichem Replacement wird vor Sessionaufrufen abgewiesen.

Unabhängig erneut ausgeführt mit dem vorhandenen Stage und dessen unveränderten Importkopien: `python -B -m unittest discover -s test/local_provider -p test_adapter.py -v`. Ergebnis: **25 Tests, Exit 0**. Dazu zählen explizite ursprüngliche START-/Replacement-/STOP-Exitregressionen, die terminalen Stopwiederholungen und Abschlussfehler für PAUSE, RESUME, SEEK und OBSERVE. Root meldet zusätzlich selbst erfolgreichen gezielten V3lint; dieser Lint wurde im Folgereview nicht erneut ausgeführt. Keine neuen Tests oder Reproducer wurden durch den Reviewer verfasst.

Die Grenzen bleiben unverändert: keine reale Session-/LibraryResolverbindung, keine nachgewiesene Unterbrechbarkeit real blockierenden I/O oder eines realen Kontextabschlusses, keine physische Audiostille oder Hardwareabnahme. Die abschließende epochprüfung setzt die in der Übergabe beschriebene weiterhin lesbare live epochquelle des injizierten Kontexts voraus; eine spätere reale Bindung muss das erfüllen. Lokale Tests sind Teilmodulnachweise; vollständige Remote-CI beurteilt Root separat am Checkpoint. Keine weitere Architektur- oder Implementierungsarbeit ist Bestandteil dieses Folgereviews.

Quelle: [Folgecommit](https://github.com/Motrish/RPi-Jukebox-RFID/commit/82d9547f5c4431e77ef9312f1ca5fbc1e5fe54d6), [exakter Fixdiff](https://github.com/Motrish/RPi-Jukebox-RFID/compare/7ede9cfac2c91f1c889b55d31a938d85e4b560dc...82d9547f5c4431e77ef9312f1ca5fbc1e5fe54d6).

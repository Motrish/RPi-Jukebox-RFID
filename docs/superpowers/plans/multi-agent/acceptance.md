# Test- und Abnahmeplan

Dieser Plan ergänzt den [Hauptplan](../2026-10-16-phoniebox-multi-agent-plan.md). Er trennt simulierte Vertragsnachweise von echten OS-, Browser- und Hardwarebelegen. Eine Mockprüfung belegt ausschließlich Verhalten an der simulierten Schnittstelle. Sie belegt weder echte MPD-/Soloist-Wiedergabe noch PiSugar, systemd, Audioausgabe oder eine frische Pi-Installation.

## Nachweisarten

| Ebene | Belegt | Belegt nicht |
| --- | --- | --- |
| Unit | Queue-Zustände, Reihenfolge, Validierung, Retry-/Backoff-Regeln, Log-Redigierung | Dienste, Hardware oder hörbares Audio |
| API-/Komponentenvertrag | Schemas, Authentifizierung, Konflikte, Events, Workerzustände | Kompatibilität mit installiertem Phoniebox-/MPD-/PiSugar-Stand |
| Browser | Navigation, Viewports, Fokus, Fehlerzustände, Wiederverbindung | Gültiger Spotify-Zugriff, vertrauenswürdiges Zertifikat, Audio |
| OS-Integration | systemd, Rechte/Pfade, Locks, Persistenz und reale Auftragswiederaufnahme | Nicht getestete Pi-Modelle/OS-Versionen |
| Zielhardware | Audio, Soloist, RFID/Tasten, PiSugar, Reboot, Netzunterbrechung, Installation | Kompatibilität mit nicht getesteter Hardware |

Für jeden Nachweis werden Ebene, getesteter Commit/Bundlestand, Ergebnis und offene Grenze vermerkt. Verträge können mit simulierten MPD-, Soloist-, Netzwerk-, Dateisystem- und PiSugar-Diensten entwickelt werden. Die jeweiligen Integrationen brauchen anschließend reale Nachweise.

## Szenarien

| Bereich | Eingabe/Aktion | Erwartetes Ergebnis | Erforderlicher Nachweis |
| --- | --- | --- | --- |
| Playlist-Speicherung | Zwei lokale Titel mit gleichem Namen und unterschiedlichen Bibliotheks-IDs speichern/laden | Titel bleiben unterscheidbar; IDs und Reihenfolge bleiben stabil | Unit + SQLite/API-Vertrag; Pi-Stichprobe |
| Revisionenkonflikt | Zwei Clients laden dieselbe Revision; Client A ändert die Queue, B schreibt anschließend auf alter Revision | B erhält Konflikt und kann neu laden; keine stille Überschreibung | Unit/Vertrag; anschließend zwei Browser |
| Quellenwechsel | Lokal → Spotify → lokal abspielen | Nur ein Anbieter gleichzeitig; nächster Start erst nach bestätigtem Stop | Mock-Zustandsautomat; danach MPD und Soloist am Pi |
| Langsamer Start mit Skip/Stop | Während `PREPARING`/asynchronem Providerstart Skip oder Stop senden; anschließend Providerantwort eintreffen lassen | Vor und nach jeder asynchronen Rückkehr wird die Generation geprüft; veralteter Start erzeugt keinen Ton und wird nötigenfalls gestoppt | Unit mit kontrollierbarem Promise/Fake; danach Pi mit verzögertem Start |
| Stop nicht bestätigt | Provider-Stop verzögern oder Bestätigung auslassen, während nächster Titel/Engine angefordert wird | Nächste Engine startet nicht; Timeout zeigt Fehlerzustand statt paralleler Audioausgabe | Unit/Vertrag; gezielter Stop-Timeout am Pi |
| WebSocket und Prozessende | Für dieselbe Ausführung WebSocket-Ende und Prozess-Exit melden, auch in umgekehrter Reihenfolge | Titelende wird genau einmal verarbeitet; Folgetitel startet nicht doppelt | Unit mit beiden Eventreihenfolgen; anschließend Providerlogs am Pi |
| Veraltetes Ende-Event | Nach Quellenwechsel trifft das Ende-Event der alten Sitzung ein | Queueposition bleibt unverändert; kein zusätzlicher Start | Unit mit Sitzungs-ID; danach Pi-Logs |
| Ende, Stop, Fehler | Natürliches Ende, expliziter Stop und Dienst-/Netzfehler einzeln auslösen | Jeder Fall hat definierte, unterscheidbare Queue-Reaktion; Prozessende gilt nicht automatisch als Titelende | Unit/Vertrag und entsprechende reale Pi-Fälle |
| Browser geschlossen | Gemischte Queue starten, Browser schließen und nächsten Titel abwarten | Wiedergabe läuft weiter; erneutes Öffnen zeigt aktuellen Zustand | Zielhardware, Browser nur Auslöser |
| Controller-Instanzsperre | Zwei Controllerinstanzen mit derselben Datenbank/Player-Ressource starten | Genau eine Instanz erwirbt die Sperre; die zweite übernimmt keine Befehle oder doppelte Events | Unit/OS-Integration mit echten Prozessstarts |
| Boot/Event-Reconnect | Während Booten und WebSocket-Verbindungsabbruch Events senden; anschließend reconnecten | Client lädt zuerst vollständigen Snapshot, wendet danach geordnete Events an; bei Lücke/Reconnect lädt er erneut Snapshot; kein zweiter maßgeblicher Browserzustand | Contract/Browser mit Lücken- und Reconnect-Simulation; anschließend Reboot und Netzabbruch am Pi |
| Shuffle/Repeat | Gemischte Liste mit Shuffle/Repeat mehrfach durchlaufen | Keine durch Event-Rennen erzeugten Duplikate; Reihenfolge entspricht der vereinbarten Regel | Deterministischer Unit-Test; anschließend notierte Pi-Folge |
| Spotify offline | Netz während Spotify-Titel trennen | Eintrag wird als nicht verfügbar markiert; begrenztes Warten oder eingestelltes Überspringen; keine Endlosschleife/Listenänderung | Mock für Timeout; echte Netzunterbrechung am Pi |
| Token/Moduswechsel | Zugriff ablaufen lassen und zwischen Connect und Phoniebox-Modus wechseln | Fehler sichtbar; lokale Musik bedienbar; gemischte Position gemäß Vertrag wiederaufnehmbar | Mock für Ablauf; echte OAuth-/Soloist-Prüfung |
| OAuth-Schutz | Falsches `state`, Callback-Hostabweichung und HTTP-Callback versuchen | Callback wird abgewiesen; Token bleibt serverseitig; sichere Hilfestellung wird gezeigt | Unit/Vertrag/Browser; HTTPS-Vertrauen auf Desktop und Smartphone |
| PiSugar-Zustände | Deaktiviert, Socketfehler, Manager getrennt und gültige Messung prüfen | Deaktiviert/Ausfall/niedriger Ladestand sind verschieden; kein alter Messwert als aktuell, Fehler nie als 0 % | Fake-Socket für Vertrag; echtes Modell und Manager für Hardwarebeleg |
| PiSugar-Unterpfad | Herstelleroberfläche inklusive Assets, WebSocket/Login über `/integrations/pisugar/` aufrufen | Funktionen laufen über Geräteadresse. Eine native Ersatzansicht ersetzt die Hersteller-GUI nur, wenn dokumentierte funktionale Deckung für die geforderten Herstellerfunktionen nachgewiesen ist; ein Status-Badge allein genügt nicht | Echter Browser und konkrete PiSugar-/Webserverversion; Mock reicht nicht |
| Frische Installation | Unterstütztes OS ohne Phoniebox bootstrappen und Setup öffnen | Setup ist vor dem Player erreichbar und funktioniert ohne Audio-/Spotify-Konfiguration | Frische SD und reale OS-/systemd-Installation |
| Abbruch/Wiederaufnahme | Installer nach einem protokollierten Schritt stoppen, Browser schließen, Worker/Box neu starten und fortsetzen | ID/Fortschritt bleiben; erledigte Schritte laufen nicht doppelt; Fehler und Fortsetzungspunkt sind klar | Unit für Auftragsmodell plus OS-Integration und Ziel-Pi-Durchlauf |
| Doppelte Aufträge | Auftrag zweimal starten und zwei Aufträge parallel senden | Lock verhindert parallele Änderungen; zweite Anfrage zeigt bestehenden Auftrag oder klaren Konflikt | Vertrags-/Unit-Test plus echte Worker-Prozesse |
| Netzwechsel | Unerreichbare Netzkonfiguration übernehmen | Neue Adresse ist vorab genannt; Fehlschlag erhält oder stellt alten Zugang wieder her | Isoliertes Testnetz und Testkarte; Mock genügt nicht |
| Eingabe/Logs | Shell-Metazeichen in Gerätename/Pfad eingeben; Logs prüfen | Keine Zusatzbefehle; Secrets und Einmalcodes erscheinen nicht in Logs/Antworten | Unit/Vertrag plus OS-Integration mit Nebenwirkungsprüfung |
| V2-Import | Bestand inventarisieren, Vorschau anzeigen und auf separater Karte importieren | Original bleibt unverändert; Karten/Musik stimmen mit Manifest/Prüfsummen überein; Verluste sind ausgewiesen | Kopie/zweite SD, Prüfsummen und Stichprobe aller Datentypen |
| Update/Rückkehr | Passendes Fork-Bundle installieren und Gesundheitsprüfung gezielt fehlschlagen lassen | Sicherung und Auftrag sind zuordenbar; Fehler stoppt Freigabe; Rückweg berücksichtigt Datenformat und Soloist-Version | OS-Integration auf Testkarte; abgelaufenes Soloist-Binary ist kein Rückweg |
| UI-Bedienung | Start, Playlist und Fehler bei 390/768/1440 px sowie per Tastatur verwenden | Kein notwendiger Horizontal-Scroll; Fokus sichtbar; Player bleibt beim Navigieren erhalten | Browser auf Viewports und Desktop-/Mobilgerät; Designvergleich nach Verfügbarkeit der Referenz |

## Hardwarevoraussetzungen und Zeitprotokoll

Vor Hardwareabnahme sind Raspberry-Pi-Modell/Architektur, tatsächliches Raspberry-Pi-OS-Lite-32-Bit-Abbild samt Release und Prüfsumme, Phoniebox-Release samt vollständiger Commit-ID, Audioausgabe/-Stack, Reader/Tasten/GPIO, PiSugar-Modell/Firmware/Manager und Spotify-Anbieterversion samt ARMv6-ABI zu erfassen. Auf separater SD installieren; die Bestandskarte nicht überschreiben. Soloist nur offiziell beziehen und nicht im Fork verteilen. OAuth-Suche/Import und Soloist-Kopplung sind getrennte Prüfungen. GPIO-/I²C-Konflikte mit Reader oder Audio-HAT gezielt erfassen.

Für jeden der zehn vorgesehenen Quellenwechsel mindestens protokollieren: Gerät/Softwarestände, Richtung (lokal→Spotify oder zurück), Anforderungszeit, bestätigter Stop, Startanforderung, erster hörbarer Ton, Erfolg/Fehler, Überlappung/Aussetzer und Logreferenz. Die Messmethode für „erster hörbarer Ton“ vorher festlegen, etwa Audioaufnahme mit Zeitbezug oder manuelle Beobachtung. Zusätzlich Wechselabbruch, Netzverlust und Neustart getrennt messen. Zeiten als Beobachtungen samt Verteilung und Durchlaufzahl berichten; keine unbelegte Millisekundenschwelle oder Leistungsgarantie ableiten.

Installerprotokoll: Zeit je Schritt, Neustartdauer, Unterbrechungspunkt, Wiederaufnahmezeit und Zustand nach Rückkehr erfassen. Protokolle, Screenshots und Artefakte vor Ablage auf Tokens, Passwörter, Einmalcodes, personenbezogene Bibliotheksdaten und unnötige Geräte-/Netzwerkdetails prüfen. Nur Testkonten und synthetische Daten verwenden, wo möglich. Keine Secrets in Git, Bundle, Logs oder Browserantworten.

## Ticketzuschnitt und Eigentum

Ausführbare Arbeit wird in kleine Luna-Tickets geschnitten: Queue-/SQLite-Vertrag; Revisionenkonflikt; Quellenwechsel; veraltete Events; Worker-Lock/Fortschritt; Wiederaufnahme; PiSugar-Status; PiSugar-Unterpfad; OAuth-Callback/Fehlerzustände; Importmanifest; Installer-Netzrollback; Hardware-Abnahmeprotokoll. Jedes Ticket nennt Eingabe/Aktion, erwartetes Ergebnis, Mockgrenze, reale Voraussetzungen, Nachweisartefakt und offenen Fehlerfall.

Jedes Ticket hat genau einen Codeeigentümer. Koordinator editiert keine gemeinsam genutzten Code- oder Schema-Dateien. Gemeinsame Queue-, API- oder Worker-Schemas erhalten je Änderungsserie einen einzelnen Luna-Eigentümer; übrige Tickets integrieren gegen den vereinbarten Vertrag. Konfliktlösungen, CI, Tests, Konfiguration, Installer und Merge-Konflikt-Fixes sind ebenfalls Luna-Arbeit. Sol-Koordinator/Reviewer darf Produktcode lesen und reviewen, übernimmt aber ausschließlich Planung/Review und liefert keine Patches. Technische Integration und Fixes gehören an den benannten Luna-X-Integrator. Root führt nur mechanische Integrationsschritte an bereits geprüften Änderungen aus und editiert keine gemeinsam genutzten Code-/Schema-Dateien. Astra wird nicht eingesetzt.

**Exklusive Ressourcenregel:** Pro Box, SD-Karte und Spotify-Session gibt es zu jedem Zeitpunkt genau einen benannten Besitzer. Andere Agents führen währenddessen keine Tests, Flash-Vorgänge, Kontoänderungen oder Neustarts auf dieser Ressource aus. Eigentumsübergabe erfolgt erst nach Abschluss, Dokumentation des Zustands und ausdrücklicher Übergabe. Verschiedene Testaufgaben an derselben Box rechtfertigen keine gleichzeitige Nutzung.

## 4-Slot-Wellenbelegung

Die verbindliche Wellenreihenfolge, Rollenverteilung und Review-Slot-Rotation stehen in Abschnitt 6 des [Hauptplans](../2026-10-16-phoniebox-multi-agent-plan.md). Dieser Abnahmeplan übernimmt dessen technische Höchstgrenze von vier aktiven Slots; der aktuelle Ressourcenmodus ist Root plus genau ein Worker mit serieller Reviewübergabe gemäß tasks/resource-policy.md. Sol kann Code lesen und reviewen, aber keine Patches liefern. Ausführbare Änderungen, technische Integration und Fixes erledigt Luna; Root führt nur mechanische Integrationsschritte aus. Pro Box, SD-Karte und Spotify-Session bleibt genau ein exklusiver Besitzer zuständig.

## Freigabekriterium

Releasefreigabe setzt einen nachvollziehbaren Ziel-Commit samt passendem Bundle, frische Installation auf der festgelegten OS-/Pi-Konfiguration, gemischte Wiedergabe per Web/RFID/Tasten bei geschlossenem Browser, exklusive Quellenwechsel, PiSugar-Ausfallunterscheidung, Neustart/Netzverlust/Installer-Wiederaufnahme sowie Import und Rückweg auf separater SD voraus. Fehlende Konten oder Hardware lassen den zugehörigen Beleg offen; ein Mock ersetzt ihn nicht.

Zielgerätepräzisierung: Original Zero W mit ARMv6 und PiSugar 2 (2 LEDs). Soloist hat keinen passenden Download und ist auf diesem Gerät ausgeschlossen. Frühere Soloist-Nennungen dieser Matrix beschreiben die ursprüngliche Anbieterannahme; ihre funktionalen Start-/Stop-/Auth-/Updateprüfungen gelten für den künftig belegten ARMv6-Anbieter. Ein erfolgreicher Bookworm-ARMv7-Container schließt keine Geräteabnahme. Siehe [Hardwareprofil](../../../../tasks/f04-hardware-profile.md).

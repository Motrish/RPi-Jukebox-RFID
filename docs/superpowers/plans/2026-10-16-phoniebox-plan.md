# Phoniebox – Umsetzungsplan

Ursprünglicher Etappenplan; maßgeblich sind inzwischen der Mehragentenplan und das Hardwareprofil: originaler Zero W ARMv6, Raspberry Pi OS Lite 32 Bit und PiSugar 2 (2 LEDs). Soloist-Nennungen dokumentieren die frühere Anbieterannahme und sind keine Freigabe für diese Box.

> Für Umsetzung: executing-plans verwenden und jedes Arbeitspaket prüfen. Bei ausdrücklich gewünschter Delegation alternativ subagent-driven-development.

**Ziel:** Nutzer-Fork mit neuer GUI, gemischten lokalen/Spotify-Playlists, PiSugar und Webinstallation.

**Architektur:** V3-Kern und Webclient erweitern. Gemeinsame Queue besitzt den Wiedergabezustand; lokale Musik und Spotify erhalten Adapter. Eine Geräteadresse bündelt GUI, API, PiSugar und Setup.

**Technik:** Bestehendes React, Python/RPC/Ereignisse, MPD, Soloist als bevorzugter Versuch, gemeinsame PulseAudio-Ausgabe, SQLite für neue Playlists, vorhandener Webserver, systemd.

**Konzept:** [Design und Architektur](../specs/2026-10-16-phoniebox-design.md).

Dies ist der angefragte Konzept-/Etappenplan. Endgültige Codeänderungen und Testimplementierungen folgen nach Hardwareprüfung und Wiedergabenachweis. Noch keine Produktimplementierung begonnen.

## Übergreifende Vorgaben

- Eine geprüfte Bookworm-Konfiguration zuerst, weitere OS-Versionen nach eigenem Installationstest.
- Queue/Wiedergabe im Kern, unabhängig vom Browser.
- Eine Geräteadresse; interne Steuerdienste bleiben lokal.
- Vorhandene Gerätefunktionen wiederverwenden und prüfen.
- Keine Zugangsdaten oder Spotify-Binaries im Fork.
- Separate SD-Karte vor Bestandsimport; keine ungeprüfte Überschreibinstallation.
- Neue Dateien unten sind Vorschläge; genaue Einhängepunkte am gewählten Release prüfen.

## Abhängigkeiten

```text
01 Basis → 02 Wiedergabenachweis → 03 Fork/Build
                                  ├→ 04 Gestaltung
                                  └→ 05 lokaler Player
05 → 06 gemischte Queue → 07 Spotify-Bibliothek
04/05 → 08 PiSugar
03 → 09 Bootstrap → 10 Webkonfiguration
06/07/08/10 → 11 Migration/Update → 12 Abnahme/Release
```

## 01 – Zielgerät und Basis

**Abhängigkeit:** keine. **Bereiche:** neue documentation/fork/support-matrix.md und decisions.md.

- [ ] Pi, OS/Architektur, Bestand, Audio, Reader, GPIO und PiSugar erfassen.
- [ ] Stabilen V3-Release evaluieren, vollständigen Commit und unverzichtbare Bestandsfunktionen dokumentieren.
- [ ] Bei fehlendem unverzichtbarem Feature V2-Alternative vor UI-Arbeiten bewerten.

**Abnahme:** unterstützte Ausgangskonfiguration und vollständige Liste der zu übernehmenden Daten.

**Prüfung:** unveränderte Basis auf zweiter SD-Karte installieren; lokale Musik, Reader und Tasten real testen.

## 02 – Spotify und Quellenwechsel nachweisen

**Abhängigkeit:** 01. **Vorgeschlagene Dateien:** tools/probes/mixed-playback.py und documentation/fork/spotify-feasibility.md.

- [ ] Persönlichen Soloist-Zugang, Architektur, Kopplung und gemeinsame Ausgabe prüfen.
- [ ] Feste Folge lokal → Spotify → lokal ohne Browser spielen; Ende, Stop und Fehler unterscheiden.
- [ ] Pause/Seek/Skip, Lautstärkegrenze, Neustart, Netzausfall und Connect-Modus prüfen; Wechselzeiten messen.

**Abnahme:** wiederholbarer Durchlauf ohne Überlagerung, bestätigte Steuerbarkeit, dokumentierter Anmelde-/Updateweg. Resume/Seek nur im nachgewiesenen Umfang zusagen.

**Prüfung:** zehn Quellenwechsel, Abbruch während Wechsel, Wiederholung nach Neustart. Scheitert Soloist, Mopidy-Spotify nur nach eigenem aktuellem Nachweis evaluieren.

## Kontrollpunkt A

- [ ] Basis, Spotify und Audio passen zum Zielgerät.
- [ ] Grenzen im Konzept ergänzt; kein fertiger Editor auf unbewiesener Wiedergabe.

## 03 – Nutzer-Fork und Build

**Abhängigkeit:** 02. **Bereiche:** Fork/Remotes, .github/workflows/fork-checks.yml, fork-release.yml, documentation/fork/development.md.

- [ ] GitHub-Anmeldung erneuern, echten Fork anlegen oder vorhandenen verwenden.
- [ ] Produktbranch vom gewählten Commit; upstream und Lizenzhinweise erhalten.
- [ ] Bestehende Prüfungen übernehmen, Web-Bundle eindeutig zu Commit/Release bauen.

**Abnahme:** Fork-Verknüpfung sichtbar, sauberer Produktbranch, Build ohne persönliche Daten.

**Prüfung:** frischer Checkout, vorhandene Upstream-Prüfungen und Web-Build. Befehle aus Manifesten des gewählten Commits übernehmen; Bundle-Prüfsumme erfassen.

## 04 – Gestaltung und Navigation

**Abhängigkeit:** 03 und sichtbare Referenzgrafik. **Bereich:** src/webapp; geplante Einheiten AppShell, PlayerBar, QueuePanel, Theme. In kleine UI-Arbeitspakete aufteilen.

- [ ] Referenz analysieren und Design-Tokens festlegen.
- [ ] Startseite, Playlist und Mobilansicht abstimmen; Navigation/Komponenten daraus bauen.
- [ ] Lade-/Leer-/Fehlerzustände, lokale Ressourcen und durchgängigen Player ergänzen.

**Abnahme:** alle Seiten erreichbar, Player bleibt beim Navigieren, Smartphone ohne horizontale Pflichtscrollleiste.

**Prüfung:** Screenshots bei 390/768/1440 Pixel Breite vergleichen; Tastatur, Fokus, lange Titel und Touch-Ziele prüfen. Echte Playerdaten folgen in 05/06.

## 05 – Eigene Musik durchgehend bedienen

**Abhängigkeit:** 03; Oberfläche aus 04 schrittweise anschließen. **Bereiche:** lokaler Player, gemeinsame Schnittstelle, Webanbindung und gezielte Tests.

- [ ] Bestehende Schnittstellen lesen; Status/Fähigkeiten/Ereignisse vereinheitlichen.
- [ ] Bibliothek, Upload und Wiedergabe in neuer Oberfläche bedienen.
- [ ] RFID/GPIO auf denselben Befehlspfad führen; Zustand nach Neuverbindung nachladen.

**Abnahme:** Web/Hardware steuern denselben Zustand; Browser schließen beendet keine Musik.

**Prüfung:** lokale Player-Prüfungen, Upload/Indexierung und Reader-Test; zwei Browser und Verbindungsabbruch/Wiederverbindung.

## 06 – Gemischte Playlists und Queue

**Abhängigkeit:** 02/05. **Einheiten:** components/playlists, components/playback_session, components/spotify_soloist, Web-Playlist/Queue. Vier getrennt prüfbare Teilaufgaben, jeweils gezielte Tests.

- [ ] **06a Speicherung:** Quellen, stabile IDs/Reihenfolge transaktional speichern; doppelte Titel zulassen.
- [ ] **06b Ablauf:** ein Anbieter, bestätigte Wechsel, Sitzungs-IDs gegen alte Ereignisse, Neustartzustand.
- [ ] **06c Bedienung:** anhängen/verschieben/löschen, speichern/laden, Shuffle/Repeat für gesamte Liste.
- [ ] **06d Modi:** Connect-Wechsel/Rückkehr und definierte Reaktion auf Spotify-Ausfall.

**Abnahme:** Beispielplaylist vollständig abspielbar; RFID startet gemischte Liste; parallele Befehle erzeugen weder zweiten Anbieter noch doppelten Fortschritt.

**Prüfung:** Zustandsautomat mit simulierten Enden, Stop, Timeouts, verspäteten Ereignissen. Danach echter Pi-Test mit Tasten, Shuffle, Repeat, Reboot und Netzausfall. Wechselzeiten mit 02 vergleichen.

## Kontrollpunkt B

- [ ] Web, RFID und GPIO bestehen denselben gemischten Durchlauf.
- [ ] Anmeldung, Ausfälle und Moduswechsel verständlich bedienbar.

## 07 – Spotify-Bibliothek

**Abhängigkeit:** 06. **Bereiche:** components/spotify_catalog, OAuth, Spotify-Unterseite, Integrationsvertrag. Zugang und Bibliothek separat liefern.

- [ ] HTTPS-Callback, PKCE, state, serverseitige Tokens und erneutes Login umsetzen.
- [ ] Links validieren, freigegebene Suche/Playlists seitenweise anzeigen.
- [ ] Titel geordnet in Phoniebox-Liste importieren; nicht verfügbare Einträge kennzeichnen.

**Abnahme:** Reihenfolge erhalten, lokale Musik dazwischen einfügbar, keine Zusage lokaler Audioexports nach Spotify.

**Prüfung:** echtes Smartphone/HTTPS und Desktop; Login verweigern, Tokenablauf, API-Limits, mehrseitige Listen. Eingeschränkte Rechte führen zu erklärter Teilfunktion.

## 08 – PiSugar

**Abhängigkeit:** 04/05. **Bereiche:** components/pisugar, Akkuanzeige, Energie-Unterseite, Webserver-Route, Modelltests. Status und Herstelleroberfläche separat liefern.

- [ ] Modell/Fähigkeiten erkennen, aktuelle Werte über lokalen Manager lesen.
- [ ] Akku/Laden anzeigen; deaktiviert, getrennt und niedrigen Ladestand unterscheiden.
- [ ] Herstelleroberfläche unter derselben Adresse integrieren; Energieeinstellungen an Dienst delegieren.

**Abnahme:** kein zusätzlicher Browser-Port, aktuelle Messung und funktionierende Unterseite; deaktiviert keine Anzeige.

**Prüfung:** Netzteilwechsel, Dienststopp, Reboot am realen Modell; Assets/WebSocket/Login unter Unterpfad; Abschalten ohne Browser mit sicherer Testkonfiguration.

## 09 – Bootstrap und Installationsaufträge

**Abhängigkeit:** 03. **Bereiche:** installation/bootstrap-web.sh, installation/websetup, Setup-Ansicht, systemd-Units. Minimalzugang und Worker separat liefern.

- [ ] Webzugang vor Player, Einmalcode und Systemprüfung bereitstellen.
- [ ] Bekannte Schritte als persistente Aufträge mit IDs und Lock ausführen.
- [ ] Redigierte Logs, Wiederaufnahme, Sperren des Initialzugangs ergänzen.

**Abnahme:** frisches unterstütztes OS erreicht Setup; Browser schließen beendet keinen Auftrag; Doppelanfrage startet keine zweite Installation.

**Prüfung:** frische SD-Karte, fehlendes Netz, Speicherknappheit und laufender Auftrag. Shell-Sonderzeichen in Eingaben dürfen keine Zusatzbefehle ausführen.

## 10 – Konfiguration im Browser

**Abhängigkeit:** 09 und jeweils 05–08. **Bereiche:** Wizard, deklarative Konfiguration, bekannte Routinen, Selbsttest. Pro Schritt ein kleines Arbeitspaket.

- [ ] Audio/Testton, Reader/Testscan, Musikpfad/Testwiedergabe einrichten.
- [ ] Optional Spotify/PiSugar; externe Konto- und Zertifikatsschritte verständlich führen.
- [ ] Vorschau, Installation, Neustart/Wiederverbindung und Abschlusstest anbieten.

**Abnahme:** normale Konfiguration nach Bootstrap ohne weiteres SSH; ausgelassenes Plugin verhindert keine lokale Musik.

**Prüfung:** vollständige Smartphone-Installation; Schritte abbrechen/wiederholen; misslungener Netzwechsel erhält oder stellt Zugang wieder her.

## Kontrollpunkt C

- [ ] Neuinstallation aus Fork reproduzierbar.
- [ ] Musik/Plugins laufen nach Neustart; Setup geschlossen.

## 11 – Migration und Updates

**Abhängigkeit:** 06/07/08/10. **Bereiche:** tools/migrate-v2.py, Importvorschau, Sicherungsmanifest, Updateauftrag, Anleitung. Import und Update separat liefern.

- [ ] V2-Daten lesend inventarisieren, sichern, mit Vorschau importieren.
- [ ] Musik/Karten erhalten; nicht übertragbare Ordner-/GPIO-/Audiooptionen ausweisen.
- [ ] Zusammengehörige Releases aktualisieren, vorher Konfiguration/Daten sichern, nachher prüfen; Soloist-Ablaufdatum beachten.

**Abnahme:** Original unverändert, Stichproben aller Zuordnungstypen korrekt, Update erhält Nutzerdaten und geeigneten Rückweg.

**Prüfung:** Import auf zweiter Karte; Dateizahl/Prüfsummen vergleichen. Fehlgeschlagenes Update und Rückkehr einschließlich Datenformat prüfen. Abgelaufenes Soloist-Binary nicht als Rückweg nutzen.

## 12 – Gesamtabnahme und Fork-Release

**Abhängigkeit:** 11. **Bereiche:** CI, Integrationstests, Release, README, Screenshots, Anleitungen.

- [ ] Alle Konzeptkriterien auf Hardware prüfen; Ressourcen/Wechselzeiten dokumentieren.
- [ ] Desktop/Mobil und öffentliche Routen prüfen; Secrets/private Daten ausschließen.
- [ ] Getesteten Release im Nutzer-Fork veröffentlichen und aus frischem Checkout installieren.

**Abnahme:** echter Fork mit Release, passendem Bundle und reproduzierbarer Installation; alle vier Anforderungen nachgewiesen.

**Prüfung:** frisch installieren → Spotify koppeln → gemischte Liste per RFID → Browser schließen → Akku → Neustart → Update/Rückkehr. Erst danach gilt Release als fertig.

## Aufwand und Übergabe

Grobe Schätzung für eine erfahrene Person: Basis/Machbarkeit 2–4 Arbeitstage; GUI/Player 8–14; Spotify-Bibliothek/PiSugar 4–7; Installation/Migration/Abnahme 7–12. Insgesamt etwa 4–8 Arbeitswochen, abhängig von Hardware und wiederverwendbaren Funktionen. Nach 02 neu schätzen; keine gemessene Zusage.

Kritischer Pfad: 01 → 02 → 05 → 06 → 10 → 11 → 12. Gestaltung/PiSugar können nach geklärten Schnittstellen unabhängig vorbereitet werden.

Der aktuelle Auftrag liefert Konzept und Plan. Fork-Erstellung, Produktcode und Boxinstallation sind spätere Umsetzungsschritte. Vor schreibendem GitHub-Zugriff lokale Anmeldung erneuern.

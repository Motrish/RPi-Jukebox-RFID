# Mehragenten-Backlog

Verbindliche Modell-/Schreibregeln: [Hauptplan](../2026-10-16-phoniebox-multi-agent-plan.md). Status ausschließlich in [todo.md](../../../../tasks/todo.md). Aufgaben unten sind geplant, nicht bereits umgesetzt.

## Verwendung

Jedes Paket nennt Owner/Modell, direkte Vorgänger, Schreibbereich, Liefergegenstand und konkreten Nachweis. Pfade für neue Module sind Vorschläge. F03 ermittelt bestehende Einstiegspunkte und die ausführbaren Build-/Testbefehle. Ein Codingbriefing benennt vor Start die konkreten bis zu etwa fünf Dateien und gezielten Befehle aus dieser Baseline; bei größerem Umfang Paket teilen. Keine Zeilennummern oder bestehenden Testkommandos erfinden.

Ein Ticket umfasst die Tests seiner neuen Logik. Q01 ergänzt unabhängige Fehlerfälle, statt alle Tests auf das Ende zu verschieben. Sol-Tickets liefern ausschließlich Prosa/Analyse; jede technische Datei einschließlich Schema, Workflow oder Test stammt von Luna. Gemeinsame Dateien werden durch X mit eindeutigem Schreibbesitz angeschlossen. Ein Anschluss wird im gleichen Ticket als getrennte serielle X-Teilaufgabe protokolliert und geprüft.

## Fundament

### F01 – Git- und Testumgebung verfügbar machen

**Owner:** X / Luna high. **Vorgänger:** keine. **Bereich:** isolierter Checkout und Entwicklungsprotokoll, kein Produktcode.

Erreichbaren Git-Arbeitsplatz, Abhängigkeiten und Worktree-Unterstützung feststellen. Falls aktuelle Sandbox blockiert bleibt, zulässigen Arbeitsplatz mit vollständigem Checkout bereitstellen; kein manuelles Zusammenstückeln von GitHub-Einzeldateien als angeblich vollständige Basis. Connectorrechte durch kleinen Schreibvorgang auf isoliertem Arbeitsbranch prüfen; Workflowrechte separat erfassen.

**Abnahme/Prüfung:** lesender Fetch, eigener Branch, mechanischer Commit/Push und Rücklesen desselben SHA funktionieren; keine Änderung am Defaultbranch. Fehlende Rechte werden konkret benannt. Diese Aktionen erst bei späterer Ausführung, nicht im Planauftrag.

### F02 – Vollständige V3-Basis im Fork

**Owner:** X / Luna high. **Vorgänger:** F01. **Bereich:** neuer V3-Basis-/Produktbranch, Herkunftsprotokoll.

Geprüften Upstream-Release auswählen, vollständige Commit-ID und Objektverfügbarkeit feststellen; Originalhistorie in Nutzer-Fork übernehmen. Bestehenden develop-Branch erhalten. Quelle, Lizenz und Basis-Commit dokumentieren; Tagverfügbarkeit nicht voraussetzen.

**Abnahme/Prüfung:** Forkbranch enthält den gewählten Upstream-Commit unverändert; Checkout, Elternhistorie und erforderliche Dateien überprüfbar. Kein Branch auf bloß vermuteten fremden SHA.

### F03 – Baseline, Schnittstelleninventur und Build

**Owner:** X / Luna high, A liest mit. **Vorgänger:** F02. **Bereich:** Baseline-/Einhängepunktdokumentation; nötige isolierte CI-Anbindung.

Unveränderten V3-Build und vorhandene Prüfungen ausführen. Tatsächliche Python-/React-/RPC-/Servicepfade, Befehle, Abhängigkeiten und Web-Bundle-Prüfsumme erfassen. Alle Wiedergabeschreiber inventarisieren: Web, RFID, GPIO, MPD, RPC, Start-/Shutdownskripte und Timer.

**Abnahme/Prüfung:** Baselinebefehle reproduzierbar; vorbestehende Fehler getrennt; jeder Player-Schreibpfad benannt und einer späteren Umleitung zugeordnet. Größere CI-Änderung als eigenes F03-Unterticket durch Luna.

### F04 – Zielgerät und Testressourcen festhalten

**Owner:** C/A / Sol high, rein beschreibend. **Vorgänger:** keine. **Bereich:** Hardware-/OS-Matrix und Ressourcenregister.

Pi-Modell, Bookworm-Abbild/Architektur, Audio, Reader/Tasten, PiSugar, Bestandsversion und externe Konten erfassen. Zweite SD und kontrolliertes Testnetz einplanen. Fehlende Angaben mit abhängigen Hardwaretickets markieren.

**Abnahme/Prüfung:** konkretes erstes Zielsystem und sicherer Testaufbau benannt; niemand beansprucht kompatible ungetestete Modelle. Ohne Angaben bleibt das Ticket offen, unabhängige Planung läuft weiter.

### F05 – Designreferenz verfügbar machen

**Owner:** A / Sol high, rein beschreibend. **Vorgänger:** keine. **Bereich:** Referenznachweis und visuelle Anforderungen.

Die originale Dribbble-Datei tatsächlich ansehen; bei fehlendem Zugriff eine Nutzerkopie als Voraussetzung erfassen. Farb-, Typografie-, Abstands- und Layoutmerkmale beschreiben, ohne einen technischen Theme-Code zu erzeugen.

**Abnahme/Prüfung:** Quelle sichtbar, Analyse am Bild nachvollziehbar. Ohne Grafik keine Freigabe der visuellen Referenztreue.

## Architektur und gemeinsame Verträge

### A01 – Verbindliche Prosa-Verträge

**Owner:** A / Sol xhigh. **Vorgänger:** F03. **Bereich:** beschreibende Player-/API-/Jobverträge.

Felder und Semantik aus Hauptplan präzisieren: Liste versus laufende Queue, getrennte Revisionen, generation/executionId/Bootidentität, Befehlsannahme versus Ausführung, Fehler, Providerfähigkeiten, aktueller Titel löschen/verschieben, RFID-Unterbrechung, Resume und Connect. HTTPS-/Zertifikatsweg und Installerprivilegien als Architekturentscheidung dokumentieren.

**Abnahme/Prüfung:** für jedes öffentliche Kommando Erfolgs-, Konflikt-, Fehler- und Wiederholungsfall beschrieben. Unabhängiger Sol-Review gleicht alle Produzenten und Verbraucher ab. Keine Implementierung oder maschinenlesbaren Schemas durch Sol.

### A02 – Verträge technisch verankern

**Owner:** X / Luna high. **Vorgänger:** A01. **Bereich:** Schema-/Validierungsdateien, API-Clientgrenze, synthetische gemeinsame Fixtures.

Prosa in die zum vorhandenen Stack passenden maschinenlesbaren Verträge übersetzen. Bestehenden Transport wiederverwenden; Snapshot, Eventfolge und stabile Fehler abbilden. Root-Router/Pluginregistrierung nur im exklusiven X-Schreibfenster ändern.

**Abnahme/Prüfung:** Backend und Frontend verstehen dieselben Fixtures; unbekannte Quelle, ungültige Revision und fehlende Pflichtfelder abgewiesen. Generierte Dateien haben einen klaren Erzeugungsweg.

## Player und Queue

### P01 – Lokalen Anbieter kapseln

**Owner:** P / Luna high. **Vorgänger:** A02. **Bereich:** lokaler Adapter und dessen Tests; bestehende MPD-Anbindung lesen.

Start, Pause, Resume, Seek nach Fähigkeit und bestätigtes Stoppen über den vorhandenen lokalen Player abbilden. Eigenständiges MPD-Autoadvance gegenüber zentralem Fortschritt ausdrücklich regeln.

**Abnahme/Prüfung:** Fake-MPD-Vertrag für jede Aktion; echter lokaler Titel startet/pausiert/stoppt auf Zielgerät. Geräteanteil benötigt F04.

### P02 – Quellenwechsel als Hardwareversuch

**Owner:** P / Luna xhigh. **Vorgänger:** P01, S01, F04. **Bereich:** isolierte Probe und Messprotokoll, keine fertige Queue-GUI.

Lokale Datei → Soloist-Einzeltrack → lokale Datei über gemeinsame Ausgabe ausführen. Stopbestätigung, Titelende, Pause/Seek/Skip und Neustart untersuchen; Latenz hörbar/aufgezeichnet messen.

**Abnahme/Prüfung:** zehn dokumentierte Wechsel, kein gleichzeitiger Anbieter; Prozessende nach Stop und natürliches Ende unterscheidbar. Unerfüllte Fähigkeiten begrenzen Produktvertrag. G1 erfordert diesen realen Nachweis.

### P03 – Playlist- und Queue-Speicherung

**Owner:** P / Luna high. **Vorgänger:** A02. **Bereich:** components/playlists/ und SQLite-Tests.

Stabile Einträge, gleiche Medien mehrfach, getrennte gespeicherte Playlist/laufende Queue und Revisionen transaktional speichern. Konflikt und Wiederholung nach commandId definieren.

**Abnahme/Prüfung:** speichern/laden erhält doppelte Titel und Reihenfolge; parallele Änderung auf alter Revision wird abgewiesen; derselbe Befehl hängt nur einmal an. Rollback unterbrochener Transaktion testen.

### P04 – Serialisierte Wiedergabe und Abbruch

**Owner:** P / Luna xhigh. **Vorgänger:** P01, P03. **Bereich:** components/playback_session/ und fokussierte Zustandsprüfungen.

Ein Controller und eine Enginehoheit; Instanzsperre, Generation vor/nach asynchronem Start, Stop/Skip/natürliches Ende getrennt. Status-/Bootidentität bei Ereignissen; nach Crash Realität abgleichen.

**Abnahme/Prüfung:** Skip während langsamen Starts erzeugt keinen verspäteten Ton; Stop während Wechsel startet keinen Nachfolger; doppelte Endereignisse schalten nur einmal. Timeout eines unbestätigten Stopps bleibt sichtbarer Fehler.

### P05 – Soloist als zweiter Anbieter integrieren

**Owner:** S / Luna xhigh, Anschluss durch P/X seriell. **Vorgänger:** P02, P04, S01. **Bereich:** Soloist-Adapter und dessen Controlleranschluss in getrennten Schreibfenstern.

Geprüften Einzeltrackbetrieb in Providervertrag überführen. Sessionverzeichnis exklusiv besitzen, Exit/WS gemeinsam eindeutig klassifizieren, Abbruch alter Ausführung bestätigen.

**Abnahme/Prüfung:** alte Exit-/WS-Ereignisse ändern neuen Titel nicht; realer Mischdurchlauf ohne Browser; Prozessfehler und Buildablauf sichtbar. G3 noch nicht ohne P06/P07.

### P06 – Playlistaktionen und Offline-Regeln

**Owner:** P / Luna high. **Vorgänger:** P05. **Bereich:** Queueaktionen und deren Tests.

Shuffle/Repeat über ganze Liste; Verhalten beim Verschieben/Löschen des laufenden Titels und bei Offlineeinträgen implementieren. Begrenztes Warten/Pausieren sowie gewählte Skipoption.

**Abnahme/Prüfung:** deterministische Shuffle-/Repeat-Szenarien; laufenden Titel ändern gemäß A01; Internetausfall erzeugt keine Endlosschleife oder Änderung gespeicherter Liste.

### P07 – RFID, GPIO und Timer an gemeinsame Steuerung führen

**Owner:** P / Luna high, zentrale Registrierung X. **Vorgänger:** F03/P04 für P07a; P06 für P07b. **Bereich:** inventarisierte Aufrufer, je Reader-/Tastenpfad ein kleines Unterticket.

P07a nach P04: lokale RFID-/GPIO-/Timerpfade an den zentralen Controller anschließen und lokal testen, vor Gate G2. P07b nach P06: alle Quellen einschließlich Spotify, Resume/Timer und zweitem Kartenscan vollständig prüfen. Alte direkte Steuerung nicht nebenher aktiv lassen. P07 als Ganzes schließt erst nach beiden Teilen.

**Abnahme/Prüfung:** jede Inventurzeile besitzt Nachweis; RFID startet Mischliste, Taste skippt Spotify→lokal, Timer stoppt aktuellen Anbieter. Web/Hardware stimmen überein.

### P08 – Connect-Modus und Wiederherstellung

**Owner:** P/S / Luna xhigh, seriell am Controller. **Vorgänger:** P07. **Bereich:** Moduswechsel und Persistenztests.

Bewusste Connect-Übernahme, Rückkehr und Crash/Reboot behandeln. Gespeicherten Queuezustand mit real laufendem Anbieter versöhnen; keine zweite Soloist-Instanz starten.

**Abnahme/Prüfung:** Moduswechsel erhält Queueposition gemäß Vertrag; Start nach Crash zwischen Speicherung/Audioausgabe erzeugt keine Doppelinstanz. Einschränkungen externer Übernahme im Einzeltrackmodus sichtbar.

## Spotify-Zugang und Bibliothek

### S01 – Soloist-Kopplung und Ausgabebasis

**Owner:** S / Luna high. **Vorgänger:** F03, A02; Gerätetest F04. **Bereich:** isolierte Anbieterprobe/Sessionverwaltung.

Offiziellen Download, persönlichen Key, unterstützte Architektur und Pairing nachweisen. Gemeinsamen Audio-Stack mit lokalem Player testen; Secrets und Sitzungsdaten aus Git heraushalten.

**Abnahme/Prüfung:** Soloist allein spielt auf Pi, Session überlebt Neustart, fehlerhafter Key verständlich; kein Binary im Fork. Ablaufdatum für Updatepfad erfassen.

### S02 – Web-API-OAuth

**Owner:** S / Luna high. **Vorgänger:** A02; tatsächlicher HTTPS-Weg aus A01. **Bereich:** OAuth-/Tokenmodul und Callbacktests.

PKCE/state, serverseitige Tokens, exakt registrierten Callback und erneutes Login implementieren. Von Soloist-Pairing unabhängig halten. Keine HTTP-.local-Lösung behaupten.

**Abnahme/Prüfung:** falsches state/Callback abweisen, Tokens weder Browserantwort noch Log; echtes Desktop-/Smartphone-Login mit vertrauenswürdigem HTTPS nachweisen.

### S03 – Katalog, Linkvalidierung und seitenweiser Import

**Owner:** S / Luna high. **Vorgänger:** S02, P03. **Bereich:** components/spotify_catalog/ und API-Contracttests.

Unterstützte Suche/Playlists laden und Titel als geordnete Snapshotreferenzen importieren. Beschränkte Rechte, Rate-Limits, unbekannte und lokale Spotify-Einträge behandeln.

**Abnahme/Prüfung:** mehrseitiger Import behält Reihenfolge, wiederholter Auftrag dupliziert nicht, nicht verfügbare Einträge ausgewiesen; echtes Konto bestätigt tatsächlich freigegebene Funktionen.

### S04 – Ablauf und erneute Anmeldung

**Owner:** S / Luna high. **Vorgänger:** S01, S02. **Bereich:** Fähigkeiten/Diagnose und Zugangserneuerung.

Ungültige Connect-/Web-API-Sitzung und Soloist-Buildablauf getrennt anzeigen. Rechtzeitiger Updatehinweis, sicherer Key-/Tokenwechsel und erneutes Login.

**Abnahme/Prüfung:** simulierte Ablaufgrenzen und echter Wiederanmeldeablauf; lokale Musik bleibt bedienbar; abgelaufener Build wird nicht als funktionierendes Rückkehrziel angeboten.

## Oberfläche

### U01 – Visuelles Konzept anhand der Vorlage

**Owner:** A / Sol high, nur Beschreibung. **Vorgänger:** F05. **Bereich:** Designbeschreibung und Referenzvergleich.

Startseite, Playlist und Smartphone strukturieren; Farbe/Typografie/Abstände/Zustände beschreiben. Bedienvokabular und gleiche Aktionen für beide Quellen festlegen.

**Abnahme/Prüfung:** sichtbarer Bezug zur tatsächlichen Grafik; sämtliche Navigationspunkte und Fehlerzustände enthalten. Technische Tokens schreibt U02.

### U02 – Shell, Theme und Navigation

**Owner:** U / Luna high. **Vorgänger:** A02, U01. **Bereich:** AppShell/Theme/PlayerBar; Routeranschluss durch X.

Referenzkonzept technisch umsetzen, lokale Ressourcen, responsive Navigation und durchgängige Playerfläche. Vorläufige datengesteuerte Fixtures sind ausdrücklich simuliert.

**Abnahme/Prüfung:** Screenshots 390/768/1440 px, Fokus/Tastatur, lange Titel und Seitenwechsel; kein horizontales Pflichtscrollen.

### U03 – Lokale Bibliothek anzeigen

**Owner:** U / Luna high. **Vorgänger:** U02, P01; echte Playeraktionen zusätzlich P04 und geprüfter serieller X-Anschluss. **Bereich:** features/library/ und Browserprüfung.

Lokale Ordner/Titel anzeigen und suchen; vor P04 sind Fixtures zulässig. Echte Playeraktionen ausschließlich durch den zentralen Controller auslösen, niemals direkt durch den MPD-/Provideradapter. Leere Bibliothek und Dienstfehler führen zu konkreten nächsten Aktionen.

**Abnahme/Prüfung:** zwei Titel mit gleichem Namen unterscheidbar, Start per Bibliotheks-ID; keine freien Dateipfade; echter lokaler Titel über UI bedienbar.

### U04 – Upload und Indexierung

**Owner:** U/X / Luna high. **Vorgänger:** U03. **Bereich:** Uploadansicht; vorhandene Uploadgrenze und Integration separat.

Vorhandene Uploadfunktion wiederverwenden und Indexierungszustand anzeigen. Fehler/Abbruch und ungültige Pfade an der Backendgrenze behandeln.

**Abnahme/Prüfung:** zulässige Datei hochladen→indexieren→abspielen; Pfadgrenzen und Fehlerfall geprüft. Kein neuer umfassender Dateimanager als Nebenprojekt.

### U05 – Liveplayer, Warteschlange und Playlists

**Owner:** U / Luna high. **Vorgänger:** U03, P03, P06. **Bereich:** features/player/ und playlists/, bei mehr als fünf Dateien teilen.

Vor Vergabe verbindlich in U05a Liveplayer/Snapshot/Events/Reconnect und U05b Playlistaktionen/Revisionkonflikte teilen; getrennte Schreibfenster und Nachweise. Server-Snapshot/Events, Reconnect und Revisionkonflikte darstellen. Quellen anzeigen, Liste speichern/laden/ordnen, aktueller Titel eindeutig. Prozessannahme nicht als erfolgreiche Wiedergabe anzeigen.

**Abnahme/Prüfung:** zwei Browser mit konkurrierender Änderung; Reconnect nach Eventlücke; Browser schließen, später richtiger Laufzustand. Echte Mischliste benötigt P07.

### U06 – Spotify-Unterseite

**Owner:** U / Luna high. **Vorgänger:** U02, S03, S04. **Bereich:** features/spotify/.

Links, Suche, verfügbare Listen und Import in gemischte Liste anbieten. Anmeldung, Rechte-/Rate-Limitfehler und getrennte Playback-/API-Verbindung anzeigen.

**Abnahme/Prüfung:** Spotify-Titel zwischen eigene Titel setzen; Konto ohne bestimmte Rechte verständlich eingeschränkt; keine zusätzliche Browser-Portadresse.

### U07 – Energieansicht und Akkuanzeige

**Owner:** U / Luna high. **Vorgänger:** U02, B01, B02. **Bereich:** features/power/ plus Headeranschluss durch X.

Native Akku-/Ladeanzeige und Modellfähigkeiten; Link zur integrierten Herstelleroberfläche. Deaktiviert, nicht erreichbar und veraltete Messung unterscheiden.

**Abnahme/Prüfung:** ohne Plugin kein Badge; Managerausfall zeigt unbekannt statt 0; unterstützte Einstellungen am echten Modell und Smartphone bedienen.

## PiSugar

### B01 – Socketstatus und Fähigkeiten

**Owner:** B / Luna high. **Vorgänger:** A02. **Bereich:** components/pisugar/ und Fake-Sockettests.

Lokalen Manager lesen, Modell/Fähigkeiten/Messzeit liefern; Parser, Timeout und Rechtefehler behandeln. Anfangs fünf Sekunden Abfrage mit begrenztem Fehlerbackoff.

**Abnahme/Prüfung:** gültige/kaputte/fehlende Antwort unterscheiden; kein alter Wert als frisch; reale Netzteiländerung sichtbar. Hardwareanteil benötigt F04.

### B02 – Begrenzte Energieaktionen

**Owner:** B / Luna high. **Vorgänger:** B01. **Bereich:** PiSugar-Aktionsgrenze und Tests.

Nur modellgestützte typisierte Aktionen, Wertebereiche und Rechte. Abschaltstrategie im Dienst belassen; I²C/GPIO-Konflikte dokumentieren.

**Abnahme/Prüfung:** unzulässiges Modell/Parameter abgewiesen, keine freie Shellaktion; kontrollierter Abschalttest ohne Browser auf sicherem Aufbau.

### B03 – Hersteller-GUI unter Geräteadresse

**Owner:** B/X / Luna high, Webserverdateien exklusiv X. **Vorgänger:** F03, A02, F04. **Bereich:** Route/Proxy-/Pfadkonfiguration und echte Browsertests.

PiSugar-GUI unter /integrations/pisugar/ einschließlich Assets, Login und WebSockets integrieren. Falls Pfade nicht unterstützt, gezielte Korrektur oder explizite native Funktionsdeckung; keinen bloßen iframe als bestanden melden.

**Abnahme/Prüfung:** reale Herstelleroberfläche unter gleicher Adresse/HTTPS funktioniert; Authentifizierung wird nicht umgangen. Native Badge alleine schließt dieses Ticket nicht.

## Installation

### I01 – Minimaler Setupzugang

**Owner:** I / Luna high. **Vorgänger:** F03, A02. **Bereich:** installation/bootstrap-web.sh und minimaler Setupdienst.

Setup vor Player starten, OS/Bestand prüfen, Adresse und zeitlich begrenzten Einmalzugang bereitstellen. Kein Build der gesamten UI auf schwacher Box als Pflicht, vorkompiliertes passendes Bundle.

**Abnahme/Prüfung:** frisches Ziel-OS erreicht Setup ohne laufenden Player; abgelaufener/falscher Zugang abgewiesen; vorhandene Installation nicht überschrieben.

### I02 – Persistente Aufträge und privilegierter Worker

**Owner:** I / Luna xhigh. **Vorgänger:** I01. **Bereich:** installation/websetup/Jobs, Worker und systemd-Anschluss durch X.

Bekannte Installationsschritte, Lock, commandId und Fortschritt persistieren. Browser darf keine freien Befehle oder Scriptpfade übergeben. Secretredigierung an Loggrenze.

**Abnahme/Prüfung:** Doppelanfrage startet einmal, zweiter Auftrag Konflikt; Browserende/Workerneustart erhält Status; Shell-Sonderzeichen erzeugen keine Zusatzwirkung.

### I03 – Audio-/RFID-Wizard als erster kompletter Pfad

**Owner:** I/U / Luna high, serielle Backend-/UI-Teilaufgaben. **Vorgänger:** I02, P01, U02. **Bereich:** Audio-/Reader-Konfiguration und Setupansicht.

Vor Vergabe verbindlich in I03a Audio/Testton, I03b Reader/Testscan und I03c Musikpfad/Testdatei/Vorschau/Selbsttest teilen; getrennte Backend-/UI-Teilaufträge, höchstens etwa fünf Schreibdateien je Auftrag. Vorhandene Routinen parametrisieren und wiederholbar machen.

**Abnahme/Prüfung:** frisches OS nach Bootstrap bis lokaler Wiedergabe ohne weiteres SSH; Wiederholung erzeugt keine doppelten Dienst-/Konfigeinträge.

### I04 – Optionale Plugins im Wizard

**Owner:** I/U / Luna high. **Vorgänger:** I03, S04, B02, U06, U07. **Bereich:** Pluginschritte, Key-/Pairing-/API-Führung.

Spotify-Download/Key/Pairing getrennt von API-Login, PiSugar-Modell/Service und Test anzeigen. Plugin überspringen und später einrichten ermöglichen.

**Abnahme/Prüfung:** ausgelassene Plugins verhindern lokale Musik nicht; tatsächliche Anmeldung/PiSugarprüfung nachvollziehbar; keine Secrets in Fortschrittsantworten.

### I05 – Verwaltung, HTTPS und Netzwechsel

**Owner:** I/X / Luna xhigh. **Vorgänger:** I02, A01. **Bereich:** Verwaltungszugang, gewählter Zertifikatsweg und Netzwerkauftrag, getrennte Untertickets.

Initialsetup schließen, spätere Verwaltung authentifizieren, den in A01 entschiedenen HTTPS-Weg technisch führen. Netzänderung mit künftiger Adresse und Rückfall ausführen. Kein eigener öffentlicher Authdienst als zusätzliches Produkt.

**Abnahme/Prüfung:** Desktop/Smartphone vertrauen dem gewählten HTTPS-Weg; unautorisierte Verwaltungsaktionen abgewiesen; falsches Testnetz stellt bisherigen Zugang wieder her. OAuth-Echtprüfung S02 kann erst danach schließen, falls HTTPS durch I05 bereitgestellt wird.

### I06 – Abbruch und Wiederaufnahme

**Owner:** I / Luna xhigh. **Vorgänger:** I03, I04, I05. **Bereich:** Schrittzustände und OS-Integrationstests.

Reboot/Warten auf Nutzer/Fehlschlag sauber unterscheiden; nach Neustart prüfen, welche Wirkung tatsächlich eingetreten ist. Halb angewendete Schritte nicht blind wiederholen.

**Abnahme/Prüfung:** Unterbrechung vor/nach Seiteneffekt, erneuter Workerstart und Browserrückkehr; gleiche Auftrags-ID, nachvollziehbare Diagnose, kein doppelter Seiteneffekt. Mindestens echter Pi-Durchlauf.

## Migration und unabhängige Prüfung

### M01 – Lesende V2-Inventur und Vorschau

**Owner:** M / Luna high. **Vorgänger:** F03, A01. **Bereich:** tools/migrate-v2.*, Vorschau/Manifest und Tests.

Kopie des Bestands erfassen: Musik, Karten, Ordneroptionen, Resume, Audio/GPIO. Übertragbar/nicht übertragbar und Zielmapping anzeigen; keine Originaländerung.

**Abnahme/Prüfung:** synthetische Bestände verschiedener Zuordnungstypen und echte Kopie; Quelle vor/nachher gleiche Prüfsummen, problematische Pfade sichtbar.

### M02 – Import mit Sicherung und Rückweg

**Owner:** M / Luna high. **Vorgänger:** M01, P08, I06. **Bereich:** Importanwendung und Wiederherstellungsnachweis.

Freigegebenes Mapping auf zweiter Karte anwenden, Konflikte und wiederholten Import behandeln. Datenformatversion und Backupmanifest zuordnen.

**Abnahme/Prüfung:** Dateizahl/Prüfsummen und Kartenstichproben stimmen; unterbrochener Import lässt Quelle unverändert; Wiederherstellung getestet.

### Q01 – Unabhängige Regressionen

**Owner:** Q / Luna high, nicht Autor des geprüften Tickets. **Vorgänger:** A02 und jeweils fertiges Implementierungsticket. **Bereich:** separate test/fork/-Dateien und Browserfälle.

Gegenbeispiele aus Abnahmematrix schreiben: Eventrennen, Revisionkonflikte, Statusfrische, OAuth, Workerlocks und Logredigierung. Als rollende Arbeit nach jedem relevanten Ticket, kein letzter Sammeltest.

**Abnahme/Prüfung:** jeweils konkreter Fehlerauslöser und sichtbare Erwartung; Mockgrenze benannt; neue Tests im integrierten Commit ausgeführt. Gemeinsame Fixtures nur über X.

### Q02 – Browser und Referenzabnahme

**Owner:** Q / Luna high, A/R wertet visuell aus. **Vorgänger:** U04–U07, B03, I04, F05. **Bereich:** Browsertests und redigierte Screenshots.

390/768/1440 px, Tastatur, Fokus, lange Inhalte, Wiederverbindung und alle Fehler-/Leerzustände prüfen. Bildvergleich zur tatsächlichen Referenz.

**Abnahme/Prüfung:** Player über Navigation erhalten, Geräteadresse konsistent, keine verdeckten Pflichtaktionen; echte Smartphoneprüfung neben simulierten Viewports.

### Q03 – Exklusive Hardwareabnahme

**Owner:** Q/P/I / Luna high, pro Ressource nacheinander. **Vorgänger:** P08, S03, S04, B03, I06, M02, R01. **Bereich:** Testharness und Geräteprotokoll, redigierte Nachweise.

Frischinstallation→Pairing→gemischte RFID-Liste→Browser schließen→Tasten/Timer→PiSugar→Netzverlust→Neustart→Update/Rückkehr. Firmware/Versionen, zehn Wechsel und Messmethode protokollieren.

**Abnahme/Prüfung:** alle Pflicht-Hardwarefälle nachgewiesen; kein CI-/Mockersatz für fehlendes Gerät/Konto. Ungetestete Matrixeinträge bleiben unfreigegeben.

## Update und Release

### R01 – Updatepfad und passende Artefakte

**Owner:** I/X / Luna high, serielle Integrationsarbeit. **Vorgänger:** I06, P08, S04. **Bereich:** Updateauftrag, CI-/Bundle-Manifest, Gesundheitsprüfung.

Forkquelle, Backend, Web-Bundle und Datenversion zusammenhalten. Vorher sichern, nachher prüfen; Rollback nur mit kompatiblen Daten und noch gültigem Soloist-Build.

**Abnahme/Prüfung:** gezielt falsches Bundle und fehlgeschlagener Healthcheck stoppen Freigabe; Rückweg auf Testkarte funktioniert; Musik/Secrets erhalten, Herstellerbinary nicht im Release.

### R02 – Gesamt-Review und Releasevorbereitung

**Owner:** R / Sol xhigh für Review; X/Q / Luna für nötige technische Korrekturen und Artefakte. **Vorgänger:** Q02, Q03.

Genauen Integrations-Commit gegen alle Nutzeranforderungen prüfen, Restbefunde beheben, zugehöriges Bundle und README/Anleitungen/Screenshots zusammenstellen. Nach Codekorrektur betroffene Nachweise aktualisieren.

**Abnahme/Prüfung:** keine offenen freigabesperrenden Befunde; unveränderlicher geprüfter Commit und Bundle; Installation aus genau dem Nutzer-Fork reproduzierbar. Veröffentlichung erst im Rahmen des später autorisierten Releaseauftrags.

## Start- und Abschlussregeln

A02, P03/P04, U02 und isolierte Adaptertests dürfen nach ihren Basisabhängigkeiten mit synthetischen Verträgen starten. Hardwareabhängige Teile schließen erst mit echtem Nachweis. P05 darf erst nach P02 umgesetzt werden. Vollständiger Wizard I04 erst nach den Pluginverträgen; I01/I02 können früher entstehen.

S03/S04 dürfen gegen den implementierten S02-Vertrag mit synthetischen Antworten beginnen; ihre echten OAuth-/Katalognachweise bleiben bis zum funktionierenden HTTPS-Weg offen. I05 darf dafür unabhängig von I04 vorgezogen werden. S02 und I05 haben keine zirkuläre Codingabhängigkeit: OAuth wird nach A01/A02 gegen Contractfixtures entwickelt; I05 stellt gegebenenfalls das reale HTTPS bereit. S02 bekommt bis zur realen Anmeldung den Status implemented mit offenem Hardware-/Endgerätenachweis, nicht verified.

Q01 ist ein wiederkehrender Auftrag mit einzelnen Kindtickets je Diff; Q02 fasst Browsernachweise zusammen, Q03 besitzt die reale Gesamtabnahme. Diese Rollen erzeugen keine zusätzlichen gleichzeitigen Slots.

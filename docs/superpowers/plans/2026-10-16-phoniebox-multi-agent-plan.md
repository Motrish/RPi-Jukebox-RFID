# Phoniebox – detaillierter Mehragentenplan

Stand: 16.10.2026. Entwicklung durch den Nutzer gestartet; Ausführung beginnt mit F01/F02 und den Startbedingungen dieses Plans.

**Ziel:** Im Fork Motrish/RPi-Jukebox-RFID eine neue GUI, gemischte lokale/Spotify-Playlists, PiSugar-Verwaltung und Webinstallation entwickeln.

**Architektur:** Vorhandenen V3-Kern und React-Client erweitern. Ein zentraler Koordinator besitzt die Wiedergabe; lokale Musik und Spotify erhalten getrennte Adapter. GUI, API, PiSugar und Setup erscheinen unter einer Geräteadresse.

**Technik:** Bestehendes Python/React/RPC, MPD, Soloist als zu prüfender Kandidat, gemeinsame Audioausgabe, SQLite für neue Playlistdaten, vorhandener Webserver und systemd.

**Grundlage:** [Konzept](../specs/2026-10-16-phoniebox-design.md), [bisheriger Etappenplan](2026-10-16-phoniebox-plan.md), [Integrationsrecherche](../../../integration-research.md).

**Ausführung:** Subagent-driven-development und dispatching-parallel-agents unter den folgenden Modell-, Schreib- und Ressourcenregeln. Dieses Dokument ersetzt die Reihenfolge und Agentenzuordnung des alten Plans; die fachlichen Anforderungen bleiben bestehen.

## 1. Dokumente und verbindliche Regeln

- Dieser Hauptplan regelt Modelle, Zuständigkeiten, Schnittstellen und Ausführung.
- [Backlog](multi-agent/backlog.md) beschreibt alle Arbeitspakete mit Abnahme und Prüfnachweis.
- [Übergaben](multi-agent/handoffs.md) enthält direkt verwendbare Agentenbriefings.
- [Abnahmematrix](multi-agent/acceptance.md) beschreibt konkrete Tests und die Aussagegrenzen von Mocks.
- [Aufgabenstatus](../../../tasks/todo.md) ist die einzige operative Statusliste. Status wird nicht parallel in mehreren Checklisten geführt.

Astra wird nicht eingesetzt. Sämtliche Modelle der Sol-Familie erhalten ausschließlich Analyse-, Planungs- und Reviewaufgaben. Produktcode, Testcode, Skripte, CI-Dateien, Dienstkonfiguration, maschinenlesbare Schemas, technische Konfliktauflösung und Korrekturen schreibt ausschließlich GPT-6 Luna. Diese breite Auslegung entspricht dem Wunsch, Sol nicht zum Coden zu verwenden.

Der Koordinator darf Dokumentation führen, vorhandene Prüfungen ausführen, Ergebnisse lesen und freigegebene Änderungen mechanisch zusammenführen. Bei nötigen Codeänderungen oder Merge-Konflikten weist er die Arbeit einem Luna-Agenten zu. Reviewer liefern Befunde und Gegenbeispiele in Prosa, keine Ersatzimplementierungen oder Patches.

## 2. Modellwahl

Die aktuelle OpenAI-Dokumentation ordnet Luna fokussierten, häufigen Aufgaben und GPT-6.1 Sol komplexen koordinierten Arbeiten zu. Die konkrete Rollenzuordnung hier ist eine Projektentscheidung unter den Nutzervorgaben, keine Garantie für eine bestimmte Fehlerquote. [Modellwahl](https://developers.openai.com/api/docs/guides/model-selection), [Luna](https://developers.openai.com/api/docs/models/gpt-6-luna).

| Rolle | Modell / Reasoning | Aufgabe und Grenze |
| --- | --- | --- |
| C – Koordination | gpt-6.1-sol / high | Abhängigkeiten, Briefings, Fortschritt, Entscheidungen; kein Code |
| A – Architektur | gpt-6.1-sol / xhigh | Modulgrenzen, Zustandsregeln, Verträge als Prosa; kein Code |
| R – unabhängiges Review | gpt-6.1-sol / high; xhigh für Playback/Installer/Abschluss | Anforderungen, Nebenläufigkeit, Sicherheit und Gesamtänderung prüfen; kein Code |
| U – Weboberfläche | gpt-6-luna / high | Kleine React-Slices nach abgestimmtem Design; technische Theme-/UI-Dateien |
| P – Player und Queue | gpt-6-luna / xhigh | Zustandsautomat, persistente Listen, Quellenwechsel; pro Ticket eine Invariante |
| S – Spotify | gpt-6-luna / high | Soloist-Anbindung, später Web-API/OAuth; technische Risiken einzeln liefern |
| B – PiSugar | gpt-6-luna / high | Socket-Adapter, Fähigkeiten, Unterpfad-Anbindung |
| I – Installation | gpt-6-luna / xhigh | Bootstrap, begrenzter Worker, Wiederaufnahme, Updates |
| M – Migration | gpt-6-luna / high | Lesender V2-Import, Sicherung, Datenübernahme |
| Q – unabhängige Tests | gpt-6-luna / high | Testcode und Integrationsharness; unabhängig vom Autor des geprüften Tickets |
| X – Integration | gpt-6-luna / high | Gemeinsame Dateien, Konflikte, Integration und technische Korrekturen |

Für vollständig spezifizierte mechanische Aufgaben kann Luna auf medium reduziert werden. high ist der Standard für Implementierung, xhigh für die genannten Nebenläufigkeits-/Berechtigungsfragen. Ältere Sol-Versionen werden nicht zusätzlich verteilt; sie würden die Rollen vervielfachen, ohne die Codingbeschränkung aufzuheben.

Rollen sind keine elf permanent laufenden Agenten. Für jedes überschaubare Ticket wird ein frischer Agent oder ein klar abgegrenzter Folgeturn gestartet. Modell und Reasoning werden explizit gesetzt; kein stilles Vererben und kein automatischer Wechsel auf ein verbotenes Modell. Beim tatsächlichen Start die vom Client angebotenen Modellnamen erneut prüfen. [Subagent-Konfiguration](https://learn.chatgpt.com/docs/agent-configuration/subagents).

## 3. Ausgangslage und Startbedingungen

Bestätigt: Fork existiert, Connector liest Dateien und meldet push/admin. Ein echter Schreibvorgang ist noch nicht getestet. Beim letzten Branchcheck enthält der Fork nur develop; future3 ist nicht vorhanden. Lokales Git scheitert weiterhin am Netzwerkzugriff. Der Connector ersetzt keinen ausführbaren lokalen Checkout und keine isolierte Testumgebung.

Vor Coding erforderlich:

1. Git-fähige Entwicklungsumgebung mit nutzbarem Repository und Abhängigkeiten herstellen, etwa geeigneter lokaler/Cloud-Arbeitsplatz. Kein Umgehen der bestehenden Sandboxregeln.
2. V3-Basis vollständig aus Upstream übernehmen, mit exakter Commit-ID und Historie. Ein fremder SHA ist kein Beleg dafür, dass dessen Objekte im Fork verfügbar sind. Zuerst Objekterreichbarkeit prüfen; ansonsten über eine Git-fähige Umgebung übertragen. develop nicht auf V3 umschreiben.
3. Baseline-Build und existierende Tests auf unverändertem V3-Stand ausführen, Befehle und bekannte Fehler erfassen.
4. Auf einem isolierten Arbeitsbranch einen kleinen nachprüfbaren Schreibvorgang testen. Adminrechte alleine beweisen weder App-Schreibrechte noch Workflow-Schreibrechte.

Hardware und Grafik bleiben offen: Pi-Modell, OS/Architektur, Reader, Tasten, DAC/HAT, PiSugar-Modell und Bestandsinstallation; Spotify-Konto/Key; sichtbare Dribbble-Grafik. Ohne Hardware sind Dokumentation, Verträge und Mocks möglich; Geräteabnahme bleibt offen. Ohne Grafik keine Behauptung einer vorlagengetreuen Gestaltung.

## 4. Schreibzuständigkeiten und Isolation

Jeder Coding-Agent arbeitet in einem eigenen Worktree und Branch auf derselben ausdrücklich benannten Integrations-Commit-ID. Auch bei geteiltem Host verwendet jeder Toolaufruf den absoluten zugewiesenen Arbeitsordner. Der gemeinsame Standardordner ist keine Isolation. Falls getrennte Worktrees nicht verfügbar sind, darf nur ein Agent gleichzeitig Code schreiben.

Geplante Pfade werden in F03 an reale Upstream-Einhängepunkte angepasst. Keine erfundenen vorhandenen Dateien oder Zeilennummern.

| Bereich | Schreibowner |
| --- | --- |
| src/jukebox/components/playback_session/ und playlists/ | P |
| src/jukebox/components/spotify_soloist/ und spotify_catalog/ | S |
| src/jukebox/components/pisugar/ | B |
| src/webapp/src/features/player/, library/, playlists/, spotify/, power/, setup/ | jeweils beauftragtes U-Ticket |
| installation/websetup/ und Bootstrap | I |
| tools/migrate-v2.* und zugehörige Tests | M |
| test/fork/ und Browser-Abnahmetests | Q oder expliziter Ticketautor für dessen eigene Tests |
| Root-Abhängigkeiten, Pluginregistrierung, zentrale Router, zentrale API-Schemas, Webserverkonfiguration, CI | X in gesondertem Integrationsticket |
| Planung, Prosa-Verträge, Status und Entscheidungsprotokoll | C/A; Reviewer kommentieren nur |

Ein Ticket darf seine eigenen Tests in benannten Pfaden ändern. Q schreibt zusätzliche unabhängige Tests in eigenen Dateien; gemeinsame Fixtures werden exklusiv über X geändert. Der gleiche Rollenname erlaubt nicht zwei Agenten gleichzeitig dieselbe Datei zu bearbeiten.

Jedes Ticket benennt erlaubte Schreibpfade und nur lesbare Abhängigkeiten. Bedarf außerhalb des Bereichs an C melden; dieser vergibt ein Folgeticket oder überträgt den Schreibbesitz ausdrücklich. Gemeinsame Einstiegspunkte werden gesammelt durch X integriert. Kein selbstständiges Ändern der API oder des Datenformats durch einen Verbraucher.

Getrennte Worktrees isolieren keine Hardware: die Testbox, Audioausgabe, SD-Karte, Datenbank, Testnetz und Spotify-Sitzung haben jeweils einen exklusiven Besitzer. Ein Ressourcenregister im Status nennt Ressource, Besitzer, Ticket und Freigabezeitpunkt. Keine parallelen Installer-/Playback-/PiSugar-Schreibtests auf derselben Box.

## 5. Verträge vor paralleler Implementierung

A beschreibt Regeln und Datenfelder; X setzt die maschinenlesbaren Schemas samt Konformitätsprüfungen um. Die folgende Tabelle ist die fachliche Vertragsbasis. Die tatsächliche Transportanbindung wird mit den vorhandenen V3-Schnittstellen abgeglichen, kein zweiter widersprüchlicher Player eingeführt.

| Vertrag | Verbindlicher Inhalt |
| --- | --- |
| MediaRef | kind LOCAL oder SPOTIFY; lokale Bibliotheks-ID oder validierter Spotify-URI; keine beliebigen Dateipfade |
| PlaylistEntry | entryId, MediaRef, Titelanzeige, Reihenfolge; identische Titel dürfen mehrfach vorkommen |
| QueueSnapshot | queueId, revision, sourcePlaylistRevision, entries, currentEntryId, repeatMode, shuffleMode; keine stille Änderung durch Import/Neusortieren |
| PlaybackState | STOPPED, PREPARING, PLAYING, PAUSED, SWITCHING, ERROR; aktiver Anbieter, executionId, generation, bootId, eventSequence, Position, Fähigkeiten |
| PlayerCommand | commandId und erwartete Queue-Revision für Listenänderungen; beabsichtigte Aktion, Servervalidierung |
| Provider | Start einer Ausführung; Pause/Resume/Seek soweit unterstützt; Stop mit ausdrücklicher Bestätigung; Ereignisse eindeutig einer Ausführung zuordnen |
| BatteryStatus | enabled, detected, reachable, model, percent oder unbekannt, charging oder unbekannt, measuredAt, capabilities |
| SetupJob | jobId, Status, stepId, gewünschte Konfiguration, angewendete Schritte, redigierte Diagnose, nextAction; Schließen des Browsers beendet den Auftrag nicht |
| Error | stabiler code, verständliche message, retryable, betroffene Operation; keine Geheimnisse |

Regeln:

- Queueänderungen sind transaktional. Veraltete revision erzeugt einen Konflikt, keine stille Überschreibung; bei HTTP 409. Wiederholung derselben commandId führt nicht zum doppelten Anhängen oder Skip. Laufende Aktionen werden als laufend angezeigt.
- Eine Instanzsperre verhindert zwei aktive Controllerprozesse. Playerbefehle werden serialisiert. Sowohl vor einem asynchronen Anbieterstart als auch nach dessen Rückkehr prüfen, ob generation noch aktuell ist. Ein inzwischen gestoppter/übersprungener Start darf keinen Ton mehr erzeugen; ggf. diese alte Instanz wieder stoppen.
- Titelende und Prozessende derselben Ausführung werden einmal verarbeitet. Stop, Skip, Fehler und natürliches Ende bleiben getrennte Ursachen.
- Unbestätigter Stop blockiert den nächsten Anbieter. Bei Timeout sichtbarer Fehler statt Audioüberlagerung. Verbindungsabbruch ist keine Stopbestätigung.
- MPD-Autoadvance und Soloist-Einzeltrackverhalten dürfen nicht zusätzlich zur zentralen Queue weiterschalten. Das gewählte Eigentumsmodell im Vertrag festhalten und real testen.
- Sämtliche direkten RFID-/GPIO-/RPC-/MPD-Steuerpfade inventarisieren und umleiten. Eine neue Oberfläche alleine übernimmt nicht die Playerhoheit.
- Gespeicherte Playlistrevision, laufende Queuerevision und reine Positionsereignisse bleiben getrennt. Browser lädt zunächst einen vollständigen Snapshot mit Bootidentität; geordnete Events danach. Bei Lücken oder Wiederverbindung neuen Snapshot laden. UI-Zustand bleibt kein zweiter maßgeblicher Laufzustand.
- Soloist-Sitzung und Web-API-OAuth separat behandeln. Lokale Wiedergabe bleibt bei API-Ausfall verfügbar. Kein browserabhängiges Abspielen.
- PiSugar-Ausfall ergibt unbekannte Werte und gemeldete Nichterreichbarkeit. Abschalten bleibt im Systemdienst.
- Installation ist wiederholbar und gegen parallele Änderungen gesperrt. Privilegierter Worker akzeptiert nur bekannte typisierte Schritte, kein freies Kommando.

Sol liefert dabei keine ausführbaren Schemas, Tests oder Implementierungen. API-/Datenformatänderungen nach Vertragsfreigabe werden als Entscheidung mit betroffenen Verbrauchern dokumentiert und vor deren Weiterarbeit integriert.

## 6. Wellen und Slotbelegung

Höchstens vier aktive Slots: C plus drei Arbeitsslots. Ein Review ersetzt einen Arbeitsslot. C zählt auch dann mit, wenn es koordiniert. Fertige Worker freigeben oder pausierte Rollen wiederverwenden; keine impliziten weiteren Unteragenten.

| Welle | Arbeitsslot 1 | Arbeitsslot 2 | Arbeitsslot 3 | Ergebnis |
| --- | --- | --- | --- | --- |
| W0 | X: Umgebung/Basis/Build | A: Bestand und Verträge | A/Q: Testvoraussetzungen und Referenzanalyse | G0, startfähige Basis |
| W1 | S: Soloist-Probe | P: lokale Anbindung | U: Design/Shell, sobald Grafik sichtbar | G1, Playback machbar und Verträge stabil |
| W2 | P: Queue-Speicherung/-Ablauf plus P07a lokale Hardwarepfade | U: Bibliothek/grundlegende lokale Playeraktionen | B: PiSugar-Status | G2, lokale Musik durch neue Oberfläche |
| W3 | P/X: gemischte Steuerung und P07b Quellenprüfung | S: OAuth/Katalog | I: Setupzugang/Aufträge | G3, gemischte Wiedergabe |
| W4 | U: Playlist/Spotify/Power-Slices | B/X: PiSugar-Unterpfad | I: Hardware-/Plugin-Konfiguration | G4, integrierte Plugins |
| W5 | I: Wiederaufnahme/Update | M: V2-Import | Q: unabhängige Browser-/Fehlerprüfungen | G5, installierbarer Kandidat |
| W6 | P/Q: Playback-Hardwaretest | U/Q: Browser und Nachweise ohne Boxänderung | I/Q: frische Installation auf separater Ressource, sonst warten | G6, Releaseabnahme |

Innerhalb jeder Welle haben Backlog-Abhängigkeiten Vorrang. Die Tabelle ist kein Auftrag, abhängige Tickets zugleich zu starten. Während ein Review läuft, bestehen z. B. C + Luna-P + Luna-U + Sol-R; ein dritter Coding-Agent kommt erst nach Freigabe eines Slots hinzu. Normalbetrieb: C plus zwei Luna-Coder und ein unabhängiger Sol-Reviewer. Ein dritter Luna-Coder nutzt den Reviewslot nur, solange kein Review ansteht. Große Reviews übergreifend, kleine Reviews direkt nach jedem Ticket.

W0 korrigiert den alten Plan: Fork besteht bereits; V3-Basis und Build werden früh vorbereitet, statt hinter dem Spotify-Versuch zu warten. Hardwareversuch blockiert die vollständige gemischte Implementierung, nicht alle Dokumentations-/UI-/Vertragsarbeit.

## 7. Prüfpunkte

| Gate | Freigabebedingung |
| --- | --- |
| G0 – Arbeitsfähig | erreichbare V3-Objekte, exakter Commit, isolierter Checkout, Baselineprüfungen, geprüfter Branch-Schreibweg |
| G1 – Technik entschieden | echter lokaler→Spotify→lokaler Versuch; Audio/Anmeldung/Steuergrenzen dokumentiert; Verträge freigegeben |
| G2 – Lokaler vertikaler Pfad | neue GUI spielt eigene Musik über P04; P07a bestätigt lokale RFID/Tasten/Web-Konsistenz; Browserende ohne Wiedergabeende |
| G3 – Gemischter Player | persistente Queue, Race-/Timeoutprüfungen, keine doppelte Engine, echter Mischdurchlauf mit Hardware |
| G4 – Plugins integriert | zulässiger Spotify-Import; PiSugar Status und Unterseite unter gleicher Adresse; deaktivierte Plugins funktionieren |
| G5 – Installation/Migration | frische Browserinstallation, Wiederaufnahme, doppelte Aufträge, Bestandsimport/Rückweg auf Kopie nachgewiesen |
| G6 – Release | unabhängiges Gesamt-Review, alle erforderlichen realen Nachweise, getesteter Commit plus Bundle und Installationsquelle passen |

Mock-/Contract-/Browser-/OS-/Hardware-Nachweise getrennt markieren. Bestehende Fehler der unveränderten Basis werden dokumentiert; neue Fehler dürfen nicht als alte Baselinefehler übernommen werden. Fehlende Hardware oder Konten bleiben offene Nachweise.

## 8. Arbeits- und Reviewzyklus

1. C vergibt ein startbereites Ticket aus der Statusliste: Commit, Kontextdateien, Schreibpfade, Vertrag, konkrete Szenarien, Ressourcen und Modell.
2. Implementer liest genau diesen Kontext, nennt notwendige Zusatzdateien und schreibt zunächst einen aussagekräftigen Fehlerfall bei neuer Logik; dann minimal implementieren und gezielt prüfen.
3. Übergabe enthält Commit, tatsächlichen Diff, ausgeführte Befehle/Exitcodes, Nachweisart und Grenzen. Nicht ausgeführt wird ausdrücklich als nicht ausgeführt angegeben.
4. Unabhängiger R prüft denselben unveränderlichen Commit auf Anforderungen und Qualität. Q ergänzt risikobezogene Tests; diese werden ebenfalls durch Luna geschrieben.
5. Bei Befund korrigiert der zuständige Luna-Agent, danach wird der neue Commit erneut geprüft. Implementiert, reviewed und verified bleiben unterschiedliche Zustände; fehlende echte Nachweise sperren verified. Ein Review des vorigen Commits gilt nicht für ungeprüfte Nachbesserungen.
6. X integriert geprüfte Tickets seriell. Bei Konflikt technischen Fix durch Luna erstellen, relevante Prüfungen wiederholen und neuen Integrationsstand reviewen.
7. C vermerkt integriert und geprüft inklusive Commit und Nachweisen. Fertiger Branch alleine ist noch kein integriertes Ergebnis.

Nach zwei erfolglosen Korrekturrunden: Sol analysiert Ursache in Prosa, Ticket kleiner schneiden, frischer Luna-Agent mit xhigh. Weitere Eskalation bedeutet Spezifikation vereinfachen, reproduzierbaren Fall isolieren oder fehlende Voraussetzung beschaffen. Sie bedeutet niemals Astra oder Sol-Coding einzusetzen. Ungeklärte Fehler in Queuehoheit, Datenverlust, Privilegien oder echten Hardwarepflichten sperren das betroffene Gate.

## 9. Nachweise, Kontext und Kosten

Pro Ticket ein kurzes Briefing, kein kompletter Chatverlauf. Start mit Konzeptabschnitt, Ticket, Vertragsversion, Baseline-Commit und direkt betroffenen Dateien. Weitere Dateien nur begründet lesen. Bei Fortsetzung Status/Commit zuerst prüfen, damit erledigte Arbeit nicht neu verteilt wird.

Aufwände messen: Modell, Reasoning, Anzahl Anläufe, Laufzeit, tatsächliche Token/Usage soweit verfügbar, Prüfkosten und Reviewbefunde je Ticket. Keine erfundenen Eurobeträge oder feste Beschleunigungsfaktoren. API-Preise sind keine verlässliche Rechnung für den aktuellen Client-/Planverbrauch.

Luna nach klaren Verträgen parallelisieren; Sol konzentriert auf Architekturentscheidungen, komplexe Reviews und Koordination. Erst nach W1 aus gemessenen Ticketlaufzeiten eine Terminschätzung ableiten. Die frühere Spanne von 4–8 Personenarbeitswochen wird durch drei Worker nicht automatisch zu einem Drittel Kalenderzeit; Hardware, Reviews und Integration bleiben teilweise seriell.

## 10. Sicherheit und Berechtigungsgrenzen

Konkrete bereits autorisierte Arbeiten fortsetzen, keine erneuten Bestätigungsrunden für Routineentscheidungen. Der Nutzer hat die Entwicklung nach diesem Plan autorisiert. Reversible Entwicklungsarbeiten und Arbeit auf isolierten Forkbranches laufen innerhalb dieses Auftrags. Die vorhandene Box und ihre Daten werden erst im festgelegten sicheren Testaufbau verändert; Releaseveröffentlichung bleibt ein eigener Abschluss. Während späterer Umsetzung Eingriffe in vorhandene Musik/SD/Netz separat von einer sicheren Testumgebung behandeln und die im Gespräch erteilte Autorisierung berücksichtigen.

Tokens, Keys, echte Musik und gerätespezifische Secrets weder in Briefings noch Git/Logs/Bundles verteilen. Authentifizierter Backendzugang statt direkter öffentlicher Soloist-/PiSugar-Steuerports. Installer-Logs redigieren. Prüfberichte vor Veröffentlichung bereinigen.

## 11. Erste Ausführungsserie

Zuerst F01–F05: Arbeitsumgebung, V3-Basis, Baseline, Geräteinventur, sichtbare Referenz. Danach A01/A02-Verträge, S01/P01/P02-Machbarkeit sowie U01-Design. Produktimplementierung erst nach den zugehörigen Startbedingungen, ohne auf eine künstliche globale Freigabe aller unabhängigen Teile zu warten.

Alle detaillierten Tickets, Modelle und Szenarien stehen im [Backlog](multi-agent/backlog.md).

# Phoniebox – Aufgabenstatus

Entwicklung am 16.10.2026 durch den Nutzer gestartet. F01/F02 laufen; technische Produktimplementierung wartet auf ausführbare V3-Basis und Baseline.

Verbindlich: [Hauptplan](../docs/superpowers/plans/2026-10-16-phoniebox-multi-agent-plan.md), [Backlog](../docs/superpowers/plans/multi-agent/backlog.md). Diese Datei ist die einzige operative Statusliste.

Statusfolge: planned → ready → in_progress → implemented → reviewed → integrated → verified. implemented bedeutet Code vorhanden, erforderliche reale Nachweise können noch fehlen. reviewed und integrated setzen geprüfte SHAs voraus. verified erfordert alle für das Ticket vorgeschriebenen Nachweisarten. blocked benennt die konkrete fehlende Voraussetzung.

| Ticket | Arbeitspaket | Status | Ergebnis-SHA / Nachweis |
| --- | --- | --- | --- |
| F01 | Git- und Testumgebung verfügbar machen | blocked | API-Schreiben/Zurücklesen bestätigt; lokaler Checkout/Worktrees weiterhin gesperrt |
| F02 | Vollständige V3-Basis im Fork | implemented | feature/foundation = 4fa84fd50750fd4b52984d51aa7c95466cf5b241; Remotehistorie geprüft, lokaler Nachweis offen |
| F03 | Baseline, Schnittstelleninventur und Build | in_progress | V3-Webbuild erfolgreich; Python/Installations-CI läuft; Quellen-Teilbericht vorhanden |
| F04 | Zielgerät und Testressourcen festhalten | blocked | Geräteangaben asynchron angefragt; unabhängige Arbeit läuft |
| F05 | Designreferenz verfügbar machen | blocked | Abruf erneut fehlgeschlagen; tasks/f05-design-report.md |
| A01 | Verbindliche Prosa-Verträge | planned | Noch keine Produktumsetzung |
| A02 | Verträge technisch verankern | planned | Noch keine Produktumsetzung |
| P01 | Lokalen Anbieter kapseln | planned | Noch keine Produktumsetzung |
| P02 | Quellenwechsel als Hardwareversuch | planned | Noch keine Produktumsetzung |
| P03 | Playlist- und Queue-Speicherung | planned | Noch keine Produktumsetzung |
| P04 | Serialisierte Wiedergabe und Abbruch | planned | Noch keine Produktumsetzung |
| P05 | Soloist als zweiter Anbieter integrieren | planned | Noch keine Produktumsetzung |
| P06 | Playlistaktionen und Offline-Regeln | planned | Noch keine Produktumsetzung |
| P07 | RFID, GPIO und Timer an gemeinsame Steuerung führen | planned | Noch keine Produktumsetzung |
| P08 | Connect-Modus und Wiederherstellung | planned | Noch keine Produktumsetzung |
| S01 | Soloist-Kopplung und Ausgabebasis | planned | Noch keine Produktumsetzung |
| S02 | Web-API-OAuth | planned | Noch keine Produktumsetzung |
| S03 | Katalog, Linkvalidierung und seitenweiser Import | planned | Noch keine Produktumsetzung |
| S04 | Ablauf und erneute Anmeldung | planned | Noch keine Produktumsetzung |
| U01 | Visuelles Konzept anhand der Vorlage | planned | Noch keine Produktumsetzung |
| U02 | Shell, Theme und Navigation | planned | Noch keine Produktumsetzung |
| U03 | Lokale Bibliothek anzeigen | planned | Noch keine Produktumsetzung |
| U04 | Upload und Indexierung | planned | Noch keine Produktumsetzung |
| U05 | Liveplayer, Warteschlange und Playlists | planned | Noch keine Produktumsetzung |
| U06 | Spotify-Unterseite | planned | Noch keine Produktumsetzung |
| U07 | Energieansicht und Akkuanzeige | planned | Noch keine Produktumsetzung |
| B01 | Socketstatus und Fähigkeiten | planned | Noch keine Produktumsetzung |
| B02 | Begrenzte Energieaktionen | planned | Noch keine Produktumsetzung |
| B03 | Hersteller-GUI unter Geräteadresse | planned | Noch keine Produktumsetzung |
| I01 | Minimaler Setupzugang | planned | Noch keine Produktumsetzung |
| I02 | Persistente Aufträge und privilegierter Worker | planned | Noch keine Produktumsetzung |
| I03 | Audio-/RFID-Wizard als erster kompletter Pfad | planned | Noch keine Produktumsetzung |
| I04 | Optionale Plugins im Wizard | planned | Noch keine Produktumsetzung |
| I05 | Verwaltung, HTTPS und Netzwechsel | planned | Noch keine Produktumsetzung |
| I06 | Abbruch und Wiederaufnahme | planned | Noch keine Produktumsetzung |
| M01 | Lesende V2-Inventur und Vorschau | planned | Noch keine Produktumsetzung |
| M02 | Import mit Sicherung und Rückweg | planned | Noch keine Produktumsetzung |
| Q01 | Unabhängige Regressionen | planned | Noch keine Produktumsetzung |
| Q02 | Browser und Referenzabnahme | planned | Noch keine Produktumsetzung |
| Q03 | Exklusive Hardwareabnahme | planned | Noch keine Produktumsetzung |
| R01 | Updatepfad und passende Artefakte | planned | Noch keine Produktumsetzung |
| R02 | Gesamt-Review und Releasevorbereitung | planned | Noch keine Produktumsetzung |

## Bekannte Startvoraussetzungen

- Git-CLI-Netzwerkzugriff ist aktuell blockiert; F01 benötigt einen zulässigen ausführbaren Entwicklungsarbeitsplatz.
- Fork enthält nach letztem Check nur develop; V3-Objekte und Basisbranch in F02 bereitstellen.
- Connector-Schreibweg tatsächlich durch Commit/Ref/Datei-Zurücklesen bestätigt; Änderungen von Workflowdateien weiterhin nicht separat geprüft.
- Zielgerät, OS-Abbild, PiSugar-Modell, Audio/Reader und Spotify-Zugang noch nicht erfasst.
- Referenzgrafik bislang nicht abrufbar; F05 offen.

## Ressourcenregister

| Ressource | Besitzer | Ticket | Zustand / Freigabe |
| --- | --- | --- | --- |
| Zielbox und Audioausgabe | Nicht vergeben | Keines | Hardware noch nicht festgelegt |
| Test-SD und V2-Kopie | Nicht vergeben | Keines | Testaufbau noch nicht festgelegt |
| Spotify-Sitzung und Konto | Nicht vergeben | Keines | Zugang noch nicht bereitgestellt |
| Kontrolliertes Testnetz | Nicht vergeben | Keines | Nicht eingerichtet |

## Entscheidungen

- Gesamte Sol-Familie ausschließlich Planung/Review; Luna schreibt alle ausführbaren Projektartefakte.
- Astra vollständig ausgeschlossen, auch bei Eskalation.
- Höchstens vier aktive Agenten inklusive Koordinator; Review ersetzt einen Arbeitsslot.
- Genau ein Codeowner pro Datei/Änderungsserie; genau ein Besitzer pro Hardware-/Kontoresource.
- V3-Basis und unveränderten Build früh herstellen, vor vollständiger gemischter Playerimplementierung.

## Planreviews

- Unabhängige Architekturprüfung durch gpt-6.1-sol: Generation nach asynchronem Start, Controllerinstanzsperre, MPD-Autoadvance und vollständige Aufruferinventur aufgenommen.
- Unabhängige Testplanung durch gpt-6-luna: Mockgrenzen, reale Hardwarepflichten und exklusive Ressourcenvergabe aufgenommen.
- Finaler Konsistenzreview abgeschlossen: 42 Top-Level-Tickets, Modell-/Slot-/Schreibregeln konsistent. Befunde zur frühen lokalen Hardwareanbindung P07a und zum zentralen U03-Steuerpfad korrigiert; I03/U05 vor Vergabe verbindlich geteilt, S02/I05-Nachweisabhängigkeit präzisiert.

## Ausführung am 16.10.2026

- Dokumentationsbranch docs/development-plan und Draft-PR 1 veröffentlicht; neun Dateien unverändert zurückgelesen.
- feature/foundation enthält die unveränderte V3-Releasebasis; develop blieb unverändert.
- future3/ci-baseline bei 58826fcf880f521292c56c43b682fa67cfdc2418 hat exakt den Upstream-V3-Dateibaum; vorhandene CI wurde dadurch ausgelöst.
- V3-Webbuild und V3-Markdown sind erfolgreich; Python-/Installerresultate zum Zeitpunkt dieses Status noch offen.
- Dokumentationsformat korrigiert, um den fehlgeschlagenen Markdowncheck des Plan-PRs zu beheben.
- Beide aktiven Subagenten meldeten das Nutzungslimit, Wiederverfügbarkeit laut Meldung 23:06 Uhr. Coding bleibt Luna zugeordnet; keine Astra-/Sol-Coding-Ersatzroute.

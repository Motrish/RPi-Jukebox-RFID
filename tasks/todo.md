# Phoniebox – Aufgabenstatus

Entwicklung am 16.10.2026 durch den Nutzer gestartet. V3-Basis, Remote-Schreibweg und Web-/Python-Baseline sind bestätigt. Nach dem zurückgesetzten Nutzungslimit laufen A01 und die isolierte CI-Korrektur; transportfreie Module werden mit vollständigem CI-Checkout entwickelt.

Verbindlich: [Hauptplan](../docs/superpowers/plans/2026-10-16-phoniebox-multi-agent-plan.md), [Backlog](../docs/superpowers/plans/multi-agent/backlog.md). Diese Datei ist die einzige operative Statusliste.

Statusfolge: planned → ready → in_progress → implemented → reviewed → integrated → verified. implemented bedeutet Code vorhanden, erforderliche reale Nachweise können noch fehlen. reviewed und integrated setzen geprüfte SHAs voraus. verified erfordert alle für das Ticket vorgeschriebenen Nachweisarten. blocked benennt die konkrete fehlende Voraussetzung.

| Ticket | Arbeitspaket | Status | Ergebnis-SHA / Nachweis |
| --- | --- | --- | --- |
| F01 | Git- und Testumgebung verfügbar machen | blocked | API-Schreiben/Zurücklesen bestätigt; lokaler Checkout/Worktrees weiterhin gesperrt |
| F02 | Vollständige V3-Basis im Fork | implemented | feature/foundation = 4fa84fd50750fd4b52984d51aa7c95466cf5b241; Remotehistorie geprüft, lokaler Nachweis offen |
| F03 | Baseline, Schnittstelleninventur und Build | in_progress | V3-Webbuild/Python erfolgreich; Bullseye-Build fehlgeschlagen, Bookworm läuft; Quellen-Teilbericht vorhanden |
| F04 | Zielgerät und Testressourcen festhalten | blocked | Geräteangaben asynchron angefragt; unabhängige Arbeit läuft |
| F05 | Designreferenz verfügbar machen | blocked | Abruf erneut fehlgeschlagen; tasks/f05-design-report.md |
| A01 | Verbindliche Prosa-Verträge | in_progress | CONTRACT 1 für Daten-/Store-Slice durch Root reviewed; Gesamtanschluss offen |
| A02 | Verträge technisch verankern | in_progress | A02a verified/integrated bei 9f5f400 (PR 3), 22 lokale Tests/Lint und volle Pythonmatrix bestanden; A02b/Anschluss offen |
| P01 | Lokalen Anbieter kapseln | in_progress | Sol präzisiert P01a-Vertrag anhand gepinnter MPD-Anbindung; Code/Hardware offen |
| P02 | Quellenwechsel als Hardwareversuch | planned | Noch keine Produktumsetzung |
| P03 | Playlist- und Queue-Speicherung | verified | Alle 15 Speicheraktionen, 36 Storetests + 22 Contracts, Python 3.9–3.13 und Review bestanden; PR 4/5/6 integriert, transportfreier Slice |
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
| B01 | Socketstatus und Fähigkeiten | in_progress | B01a-Codefreigabe für Modell/Prozent per UDS; opt-in, Deadline/Fehler ohne stale Messwerte; Modellprofile/Hardware offen |
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
| Q01 | Unabhängige Regressionen | in_progress | Zwei zusätzliche Storeproben in PR 7, lokal geprüft; Gesamt-Q01 bleibt offen |
| Q02 | Browser und Referenzabnahme | planned | Noch keine Produktumsetzung |
| Q03 | Exklusive Hardwareabnahme | planned | Noch keine Produktumsetzung |
| R01 | Updatepfad und passende Artefakte | planned | Noch keine Produktumsetzung |
| R02 | Gesamt-Review und Releasevorbereitung | planned | Noch keine Produktumsetzung |

## Bekannte Startvoraussetzungen

- Git-CLI-Netzwerkzugriff ist aktuell blockiert; F01 benötigt einen zulässigen ausführbaren Entwicklungsarbeitsplatz.
- V3-Objekte sind erreichbar; feature/foundation und future3/modern-ui bestehen. develop bleibt unverändert.
- Connector-Schreibweg einschließlich Workflowdatei durch Commit/Ref/Datei-Zurücklesen bestätigt; CI-Korrektur 83b0c01 liegt in Draft-PR 2, Review und Runnerabschluss offen.
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
- V3-Webbuild, Pythonmatrix und V3-Markdown sind erfolgreich; Bullseye-Imagebuild scheitert an Paket-404, Bookworm läuft noch.
- Dokumentationsformat korrigiert, um den fehlgeschlagenen Markdowncheck des Plan-PRs zu beheben.
- Beide aktiven Subagenten meldeten das Nutzungslimit, Die Limitmeldung nennt 11:06 PM als nächsten Versuch; Clientzeit ist maßgeblich. Coding bleibt Luna zugeordnet; keine Astra-/Sol-Coding-Ersatzroute.
- Dokumentations-PR nach Formatkorrektur: Markdownchecks erfolgreich auf 029ba31b4cbb259f9c336855122a384cccd7ac7e.

## Fortsetzung nach Limitreset

- Luna und Sol antworten wieder; die frühere Limitmeldung ist historisch und blockiert die aktuelle Arbeit nicht mehr.
- future3/modern-ui startet exakt bei 58826fcf880f521292c56c43b682fa67cfdc2418 und ist der isolierte V3-Integrationsbranch. develop wird nicht umgeschrieben.
- Draft-PR 2 enthält ausschließlich die von Luna verfasste Entfernung des aktiven Bullseye-Installerjobs. Bookworm bleibt Ziel der neuen Supportmatrix; der ursprüngliche Bullseye-Fehler wird weiterhin dokumentiert.
- Remote-Entwicklung ist für transportfreie Module freigegeben: eigene Artefaktordner, eindeutige Schreibowner und isolierte GitHub-Branches bewahren den vollständigen Basisbaum. GitHub Actions testet einen vollständigen Checkout. Lokal ausgeführte Modulprüfungen sind nur Teilnachweise und werden entsprechend bezeichnet.
- Diese Arbeitsweise ersetzt weder lokale Worktrees noch Geräteprüfungen. F01 und G0 bleiben teilweise offen; Runtimeanbindung, Quellenwechsel, Installerabnahme und vorlagengetreues Design behalten ihre bisherigen Nachweisbedingungen.

### Freigegebene Teilschritte

- CONTRACT 1 ist für A02a fachlich geprüft: versionierte Wurzeln, geschlossene Felder, exklusive Resultatform und konkrete Fehler-/Idempotenzregeln. Gesamte Runtimearchitektur bleibt offen.
- A02a: Luna besitzt vier neue Dateien unter src/jukebox/jukebox/contracts und test/contracts, eigene Branchbasis 58826fc; keine Runtime-/RPC-/CI-/Webänderungen.
- P03a1: Luna bereitet ausschließlich Playlist CREATE/GET/APPEND und COMMAND_GET vor. Weitere Playlistaktionen sind P03a2; Queue und objektübergreifende Übergänge sind P03b. Ein gemeinsames Commandregister wird seriell erweitert.
- CI-Commit 83b0c01 wurde unabhängig durch Sol geprüft: keine sperrenden Diffbefunde. Bookworm-Runnerabschluss bleibt vor Integration erforderlich; die Änderung repariert Bullseye nicht, sondern begrenzt die Zielmatrix.

- A02a-Pfadkorrektur aus der echten conftest-Importauflösung: Contracts gehören ins innere Corepaket src/jukebox/jukebox/contracts; der zuerst vorgeschlagene Nachbarpfad war ungeeignet. Luna korrigiert Stage und Tests vor dem Commit.

### Veröffentlichte Produktteilschritte

- A02a: 9f5f400e453ff8e07a64b2f597717b24321d5fcd, Tree 7d23b9e2b15582735d4eb8796d726d10142dcd78, PR 3 gegen future3/modern-ui. Vier Luna-Dateien mechanisch durch Root veröffentlicht, Compare/Readback bestätigt. Sol-Review ohne sperrenden Befund; Root und Reviewer führten 22 Unitprüfungen erfolgreich aus. Bestehende V3-Lintregeln lokal ohne Befund. Vollständiger Pythonlauf 38959948228 noch nicht insgesamt abgeschlossen.
- P03a1: 26cf8a08486880998bbffac8e136025f274513dc, Tree 809d135e28e4873a039afb2d45f0c7b24ced2ea9, PR 4 auf A02a gestapelt. Drei Luna-Dateien mechanisch durch Root veröffentlicht, Compare/Readback bestätigt. Root führte 11 Storetests erfolgreich aus; lokale Lintprüfung ohne Befund. Unabhängiges Review und Pythonlauf 38960045632 offen.
- Reviewerbefunde wurden durch Luna korrigiert: typisierter Statusfehler, kontraktgerechter Listenlimitfehler, strikte Versiontypen, gemeinsame ID-Prüfung, atomarer Read-Snapshot, vorhandener unvollständiger Ledger als Storefehler und portable Testimporte. Die Reviewkorrekturen haben zusätzliche Regressionen; ein separater RED-Vorherlauf wurde dabei nicht für jeden Fix ausgeführt und wird nicht behauptet.
- Der erste Blobupload eines Agenten hing über acht Minuten. Root beendete den hängenden Aufruf; bis dahin gab es keinen Produktcommit. Veröffentlichungen nutzen danach create_tree mit vollständigem Basisbaum und expected_sha beim Branchupdate.

### P03a2 gestartet

P03a1 ist bei 52fa7be23e2cccaff00cb21e60d3902cb0feb851 unabhängig ohne sperrenden Befund geprüft; die ursprüngliche Rollback-Nachweislücke ist durch aussagekräftige Tests geschlossen. P03a2 erweitert denselben Store durch Luna im separaten Artefaktordner: RENAME, REMOVE, MOVE, DELETE und paginierte Playlistübersicht. Nur Store und eigene Testdatei ändern sich, keine Queue-/Runtime-/Schema-/Transportänderung. Basis bleibt der geprüfte 52fa-Stand; vollständige CI ist weiterhin ein eigener offener Nachweis.

### Geprüfte Integration und Queuefortsetzung

- A02a: vollständiger Pythonlauf 38959948228 mit allen fünf Pythonversionen und finish erfolgreich. Exakter geprüfter SHA per Fast-forward in future3/modern-ui übernommen; PR 3 wird von GitHub als integriert geführt.
- P03a1: vollständiger Pythonlauf 38960469965 einschließlich finish erfolgreich. PR 4 am geprüften Head 52fa7be gemerged; Integrationscommit 149f1ff95126f952e068649774ab676a216c6c3c hat exakt dessen Tree 1166dc41e79c7e3617fde54e283710709a4d14c5.
- P03a2: 9c859a2e91f90e25d84f4e32ffe9ab369f0d5202, Tree ff6a3c7b0199d0c320ebc8d58e41c3c55ea55ca2, unabhängiges Review ohne Sperrbefund, 20 Storetests und volle Pythonmatrix im Lauf 38961153409 erfolgreich. PR 5 gemerged; Integrationscommit feeaf46030cc955353834e141642f3cc90f381a3.
- Der unveränderte Bookworm-Baselinelauf hat alle fünf Installerprüfungen erfolgreich abgeschlossen. Die isolierte Matrixkorrektur in PR 2 wird weiterhin getrennt überprüft.
- P03b ist freigegeben: dieselbe Store-/Idempotenzinstanz wird im eigenen Luna-Artefaktordner um die neun Queueaktionen und atomare Load-/Save-Übergänge ergänzt. Queue-Speicherung ist keine Wiedergabe- oder Gerätefreigabe. Nur store.py und eine neue Queue-Testdatei dürfen geändert werden.

### Speicherabschluss und weitere unabhängige Arbeit

- P03b: Commit 1b6f1a86725b60310f74ca0c69ee0a5c380c6559, Tree e268b0d3e280ae875a4a8eeea683598b05fb7e46, 36 Storetests + 22 Vertragstests lokal erfolgreich. Pythonlauf 38962176404 einschließlich aller fünf Versionen und finish erfolgreich. Unabhängiges Review ohne Sperrbefund; PR 6 als 2bb86457b8921de9ee079a3fc58b37be9f7d038b integriert.
- Matrixkorrektur 83b0c01: Bookworm-Build, fünf Installerprüfungen und cleanup im Lauf 38957569477 erfolgreich. PR 2 nach Review als b2be3f39f54d8f492966a407c3b7293d1311e1fa integriert. Bullseye bleibt dokumentierter alter Fehler, kein repariertes Ziel.
- Q01-Storeproben: 7cabbafa7b6440f57a9d265a63f052e2a08d6edf, Tree 7addf447bc51354995110b78df485778de611a1f, PR 7. Genau ein neuer unabhängig von Storeautor verfasster Luna-Test. Zwei Fälle lokal und im Sol-Review erfolgreich; vollständige CI noch offen. Proben decken synthetisches P03a2-Alt-Schema ohne Queue und Queue-WAL-Interleaving ab; kein V2-Import-/Installerbeleg.
- P01a wird als Prosa auf tatsächlichen PlayerMPD-/MPD-Protokollgrenzen präzisiert. B01 beginnt mit offizieller PiSugar-Socket-/Modellrecherche. Beide erhalten erst nach Vertragsprüfung ihre eng begrenzte Codefreigabe; Registry/Runtime/Audio-/Gerätefreigaben bleiben separat.
- Lokaler npm-Download des optionalen Markdownprüfers wurde vom Betriebssystem mit EACCES abgewiesen; kein Umgehen oder Eskalieren. Dokumentationslint bleibt in vorhandener GitHub-CI. Lokales Flake8 ist innerhalb des Workspace verfügbar.

### PiSugar-Teilslice

B01a erhält drei neue Luna-Dateien (manager.py, Paketexport, Tests). Der Adapter liest ausschließlich get model und get battery über UDS, ohne Pollingthread oder Runtimeanschluss. Standard ist deaktiviert; charging bleibt null und capabilities leer. Erfolgreicher vollständiger Read liefert frische UTC-Messzeit; unbekanntes Modell und jeder aktuelle Fehler liefern keine Messwerte. Pro Kommando gilt eine harte Deadline einschließlich Connect/Send/Receive und eine Antwortgrenze von 512 Bytes. Offizielle PiSugar-Quelle ist auf ea025c2d3d261427206ae1a2e9b8f853c2b3af12 gepinnt. Hardware, Ladeprofil und Energieaktionen sind separate Nachweise.

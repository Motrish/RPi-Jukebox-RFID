# Phoniebox – Aufgabenstatus

Entwicklung am 16.10.2026 durch den Nutzer gestartet. V3-Basis, Remote-Schreibweg und Web-/Python-Baseline sind bestätigt. Nach dem zurückgesetzten Nutzungslimit werden transportfreie Module mit vollständigem CI-Checkout entwickelt. Integriert sind Core-Verträge, Playlist-/Queue-Store, lokaler Adapter/Katalog, PiSugar-Reader, die Reactoberfläche mit echter Bibliotheksansicht und ein optionaler lokaler nginx-Anschluss. Vollständige Wiedergabeintegration, Browserinstaller und Zielgerätetests bleiben offen.

Verbindlich: [Hauptplan](../docs/superpowers/plans/2026-10-16-phoniebox-multi-agent-plan.md), [Backlog](../docs/superpowers/plans/multi-agent/backlog.md). Diese Datei ist die einzige operative Statusliste.

Statusfolge: planned → ready → in_progress → implemented → reviewed → integrated → verified. implemented bedeutet Code vorhanden, erforderliche reale Nachweise können noch fehlen. reviewed und integrated setzen geprüfte SHAs voraus. verified erfordert alle für das Ticket vorgeschriebenen Nachweisarten. blocked benennt die konkrete fehlende Voraussetzung.

| Ticket | Arbeitspaket | Status | Ergebnis-SHA / Nachweis |
| --- | --- | --- | --- |
| F01 | Git- und Testumgebung verfügbar machen | blocked | API-Schreiben/Zurücklesen bestätigt; lokaler Checkout/Worktrees weiterhin gesperrt |
| F02 | Vollständige V3-Basis im Fork | implemented | feature/foundation = 4fa84fd50750fd4b52984d51aa7c95466cf5b241; Remotehistorie geprüft, lokaler Nachweis offen |
| F03 | Baseline, Schnittstelleninventur und Build | in_progress | V3-Webbuild/Python und Bookworm-ARMv7-Installer erfolgreich; alte Bullseye-404 dokumentiert, Matrixkorrektur integriert; ARMv6-Gerätenachweis offen |
| F04 | Zielgerät und Testressourcen festhalten | in_progress | Zero W (ARMv6), Raspberry Pi OS Lite 32 Bit, PiSugar 2 (2 LEDs), Raspbian 13 trixie (13.6) und HiFiBerry MiniAmp bestätigt; aktive Audioanbindung/Test-SD offen |
| F05 | Designreferenz verfügbar machen | verified | Nutzerbild reference/template.webp am 17.10.2026 sichtbar; u01-design-spec.md |
| A01 | Verbindliche Prosa-Verträge | in_progress | CONTRACT 1 für Daten-/Store-Slice durch Root reviewed; Gesamtanschluss offen |
| A02 | Verträge technisch verankern | in_progress | A02a und A02b1 verified/integrated: PR12 als ea87e4a7, 12 Jest-/22 Pythonvertragstests, vollständiger Web-/Chromiumpass und Pythonmatrix; Transport/Gesamtparität offen |
| P01 | Lokalen Anbieter kapseln | in_progress | P01a1-Adapter und P01b1-Katalog verified/integrated: PR9 als1995a5c, PR14 alse2eecd53 mit23 Katalogtests/175 Gesamtprüfungen und voller CI; reale Session/MPD-Übergabe/Hardware offen |
| P02 | Quellenwechsel als Hardwareversuch | planned | Noch keine Produktumsetzung |
| P03 | Playlist- und Queue-Speicherung | verified | Alle 15 Speicheraktionen, 36 Storetests + 22 Contracts, Python 3.9–3.13 und Review bestanden; PR 4/5/6 integriert, transportfreier Slice |
| P04 | Serialisierte Wiedergabe und Abbruch | planned | Noch keine Produktumsetzung |
| P05 | ARMv6-Spotify-Anbieter integrieren | blocked | Soloist ungeeignet für Zero W; Alternative und Geräteprobe vor Implementierung |
| P06 | Playlistaktionen und Offline-Regeln | planned | Noch keine Produktumsetzung |
| P07 | RFID, GPIO und Timer an gemeinsame Steuerung führen | planned | Noch keine Produktumsetzung |
| P08 | Connect-Modus und Wiederherstellung | planned | Noch keine Produktumsetzung |
| S01 | ARMv6-Anbieterprobe und Ausgabebasis | in_progress | Quellenstand17.10mit gepinntem librespot19959512 und sechs Primärquellen aktualisiert: RustARMv6-Ziel/Featurewahl geklärt, Raspbian13-ARMv6-Sysroot/echter Build/ELF-/Auth-/Gerätebeleg weiterhin offen |
| S02 | Web-API-OAuth | planned | Noch keine Produktumsetzung |
| S03 | Katalog, Linkvalidierung und seitenweiser Import | planned | Noch keine Produktumsetzung |
| S04 | Ablauf und erneute Anmeldung | planned | Noch keine Produktumsetzung |
| U01 | Visuelles Konzept anhand der Vorlage | verified | Tatsächliches Nutzerbild und Entwurf von Root sowie unabhängigem Reviewer anhand echter Screenshots verglichen; u01-design-spec.md |
| U02 | Shell, Theme und Navigation | in_progress | U02a/b als gerätefreie Vorschau verified/integrated: e61a63e (PR11), vollständiger Web-/Chromiumpass und beide Pythonmatrices; Liveanschluss offen |
| U03 | Lokale Bibliothek anzeigen | in_progress | U03a1/a2 verified/integrated: PR15 als769a46a3 und PR16 alsb5190698;196 Pythonprüfungen,24 Bibliotheks-Jesttests, volle Web-/Chromium-/Pythonmatrizen und Desktop/Mobilsichtprüfung; X01 als6b872011 mit echter nginx1.24-Abnahme integriert; Geräte-/Produktionsanschluss offen |
| U04 | Upload und Indexierung | planned | Noch keine Produktumsetzung |
| U05 | Liveplayer, Warteschlange und Playlists | planned | Noch keine Produktumsetzung |
| U06 | Spotify-Unterseite | planned | Noch keine Produktumsetzung |
| U07 | Energieansicht und Akkuanzeige | planned | Noch keine Produktumsetzung |
| B01 | Socketstatus und Fähigkeiten | in_progress | B01a bei fb2a7d0 reviewed, CI 38966180905 erfolgreich, PR 8 als 5057f0b integriert; 20 Tests, Modellprofile/Hardware/Runtime offen |
| B02 | Begrenzte Energieaktionen | planned | Noch keine Produktumsetzung |
| B03 | Hersteller-GUI unter Geräteadresse | planned | Noch keine Produktumsetzung |
| I01 | Minimaler Setupzugang | in_progress | I01a lesender Slice verified/integrated: PR13 als87ee99b4, finales Folgereview und beide Pythonmatrices grün; LAN/Setup/Gerät offen |
| I02 | Persistente Aufträge und privilegierter Worker | planned | Noch keine Produktumsetzung |
| I03 | Audio-/RFID-Wizard als erster kompletter Pfad | planned | Noch keine Produktumsetzung |
| I04 | Optionale Plugins im Wizard | planned | Noch keine Produktumsetzung |
| I05 | Verwaltung, HTTPS und Netzwechsel | planned | Noch keine Produktumsetzung |
| I06 | Abbruch und Wiederaufnahme | planned | Noch keine Produktumsetzung |
| M01 | Lesende V2-Inventur und Vorschau | planned | Noch keine Produktumsetzung |
| M02 | Import mit Sicherung und Rückweg | planned | Noch keine Produktumsetzung |
| Q01 | Unabhängige Regressionen | in_progress | Zwei zusätzliche Storeproben reviewed, CI 38963718947 erfolgreich, PR 7 als caa8ca9 integriert; Gesamt-Q01 offen |
| Q02 | Browser und Referenzabnahme | in_progress | U02a/b: echte Chromiumtests, React-Screenshots und Desktop-Sichtprüfung bestätigt; vollständige Live-/Geräteabnahme offen |
| Q03 | Exklusive Hardwareabnahme | planned | Noch keine Produktumsetzung |
| R01 | Updatepfad und passende Artefakte | in_progress | R01a/PR18 alsfc995afb und R01b/PR19 als2002cc2c verified/integrated: passende CI-Bundles und sichere private lokale Übernahme. R01b:39neue/250Gesamttests,2vollePythonmatrizen, Reviews geschlossen. Vollständiger Update-/Rollbackpfad offen |
| R02 | Gesamt-Review und Releasevorbereitung | planned | Noch keine Produktumsetzung |

## Bekannte Startvoraussetzungen

- Git-CLI-Netzwerkzugriff ist aktuell blockiert; F01 benötigt einen zulässigen ausführbaren Entwicklungsarbeitsplatz.
- V3-Objekte sind erreichbar; feature/foundation und future3/modern-ui bestehen. develop bleibt unverändert.
- Connector-Schreibweg einschließlich Workflowdatei bestätigt; CI-Korrektur 83b0c01 nach Review und Bookworm-Runnererfolg als b2be3f3 integriert.
- Zero W ARMv6, Pi OS Lite 32 Bit, Raspbian 13 trixie (DEBIAN_VERSION_FULL=13.6), HiFiBerry MiniAmp und PiSugar 2 (2 LEDs) bestätigt; exaktes Abbild, aktive Audioanbindung/Reader und Spotify-Zugang offen. Test-SD wird vom Nutzer vor Gerätetests geklärt.
- Referenzgrafik seit 17.10.2026 als Nutzerkopie reference/template.webp sichtbar; F05 verified, U01 beschrieben.

## Ressourcenregister

| Ressource | Besitzer | Ticket | Zustand / Freigabe |
| --- | --- | --- | --- |
| Zielbox und Audioausgabe | Nicht vergeben | Keines | Zero W ARMv6 / Raspbian 13 trixie 32 Bit, HiFiBerry MiniAmp festgelegt; aktive Konfiguration und Gerätezugriff offen |
| Test-SD und V2-Kopie | Nutzer | Q03 | Separate SD wird geklärt, sobald Gerätetests anstehen; unabhängige Entwicklung läuft weiter |
| Spotify-Sitzung und Konto | Nicht vergeben | Keines | Zugang noch nicht bereitgestellt |
| Kontrolliertes Testnetz | Nicht vergeben | Keines | Nicht eingerichtet |

## Verbindliche Arbeitsregeln

- Kein Astra. Sol ausschließlich für Koordination, Planung und Review; Luna erstellt alle ausführbaren Projektartefakte einschließlich Tests, Workflows und Konfiguration.
- Koordinator plus ein bis zwei Worker nur bei unabhängigem Nutzen. Ein Codeowner je Datei; Coding und Abschlussreview desselben Slices seriell. Aktuell: R01b-Autor und unabhängige Reviewer abgeschlossen; kein Codingworker aktiv. Root dokumentiert die geprüfte Integration. Nächster eigenständiger Auftrag ist I01b-dev.
- Teilstages sind keine vollständigen Checkouts. GitHub Actions prüft jeweils einen vollständigen Checkout; Root veröffentlicht nur die exklusiven Pfade als mechanische Übernahme auf vollständigem Basisbaum und liest exakte Inhalte/SHAs zurück.
- Git-CLI-Netzwerk, lokaler Vollcheckout/Worktrees, gh-Authentifizierung und WSL waren nicht verfügbar. Der authentifizierte GitHub-Connector funktioniert. Keine erneuten Umgehungsversuche ohne geänderte Voraussetzung.
- Writable Workspace: G:/Entwicklung. C:/Users/nehme/phoniebox-work ist ein fremder V2-Arbeitsstand und bleibt unberührt.
- Vorhandene Entwicklungsfreigabe deckt begrenzte reversible Slices und geprüfte Integration auf future3/modern-ui. Gerätestarts, Systemänderungen, LAN-/TLS-Promotion und Kontozugriffe sind separate Nachweise.
- Fünf-Stunden-Kontingent sparsam einsetzen. Kein verlässlicher Restkontingent-/Resetwert und kein bestätigter Scheduler verfügbar; keine automatische Wiederaufnahme behaupten. Details: [Ressourcenregeln](resource-policy.md).

## Aktueller Remote- und Integrationsstand

- Produktbranch future3/modern-ui: 2002cc2c2de3daa8f0b2b06e6f9513cd71c92886, geprüfter Baum 3dd4b2240cca9ebf729050a919cd3207074fd5b2. R01a/PR18 und R01b/PR19 integriert; tatsächliche Source-CI und identische Mergebäume bestätigt.
- develop bleibt unverändert auf 42d5023e37dbf8de6477fef5ebcd6eae3cb5087d. V3-Basis v3.6.0 ist 4fa84fd50750fd4b52984d51aa7c95466cf5b241; Herkunft und frühere Integrationen sind in den Einzelberichten belegt.
- U03a2: [PR16](https://github.com/Motrish/RPi-Jukebox-RFID/pull/16), Merge b5190698a7b39abc8e5dc1062cee8334261474fc. Echte Bibliotheksroute #/design-preview/library in bestehender Shell; Paging, Verfügbarkeit, Zugangscode nur im Componentspeicher, Abort/Generation/Timeout und sichere Fehlerzustände.
- X01: [PR17](https://github.com/Motrish/RPi-Jukebox-RFID/pull/17), Merge 6b872011c2e79263f61ca5384908b23251178a6b. Drei exklusive Pfade: nginx.library-loopback.conf, nginx_library_smoke.py und bestehender Webworkflow. Optionaler echter IPv4-Loopback-nginx mit festem Buildroot/APIziel; globale Defaultsite und Installer unverändert.
- Der tatsächlich geprüfte X01-Head ist 8aa64245c2bd7569d124853d8b95aad16296fdab. Beide Mergeobjekte, Eltern, Produktrefs, unverändertes develop und identische geprüfte Bäume wurden remote bestätigt. Für X01 stimmen zusätzlich alle drei lokalen Git-Blobs bytegenau mit dem Remote-Baum überein.
- Dokumentationsbranch: docs/development-plan. Letzter vor diesem Abschluss bestätigter Head war 2e0e3933bd3a0f8b7be57de28c6a66ba2041656e; den aktuellen Head beim Wiederaufnehmen remote lesen. Keine eigene Commit-ID in den Inhalt dieses Commits vorausberechnen.

## Letzte vollständige Nachweise

| Slice | Tatsächliche Abnahme |
| --- | --- |
| U03a1 | PR15 als769a46a3:21 APItests bei196 Pythonprüfungen, volle3.9–3.13-Matrizen, unabhängiges Review und echter Linux-Katalog/HTTPpfad |
| U03a2 | Head8faef107, Web39039000758/Job117414476131 completed/success: Build,24/24 Bibliotheks-Jest,12/12 Web- und22/22 Pythonverträge, unveränderte Preview-/Legacy-Chromiumabnahme und neuer echter Katalogbrowser |
| U03a2 Python | Beide Läufe39039004880 und39039000739 jeweils3.9–3.13 plusfinish vollständig completed/success |
| U03a2 Bilder/Review | Frische Desktop- und390px-Langnamen-PNGs tatsächlich durch Root gesehen;320/768/1024 zusätzlich im Browser geprüft. Alle ursprünglichen3P1/3P2 und der F7-Folgebefund geschlossen; Source-/Harnessreview PASS |
| X01 | Head8aa64245, Web39040992426/Job117420299870 completed/success: alle bisherigen Prüfungen plus exaktes nginx-t/Start, nginx1.24.0 (Ubuntu), echte API-/Katalog-/Browserabfrage, HTTP-/Host-/Origin-/URI-/Methoden-/Auth-/TTL-/Fehlermatrix und gestoppter Upstream |
| X01 Python | Beide Läufe39040996371 und39040992424 jeweils3.9–3.13 plusfinish vollständig completed/success |
| X01 Review | Unabhängiges gesamtes Source-/Testreview und enger Folgepass schließen2P1+1P2. Vorlagenhashb48a14c9, Harness6636090f, Workflow19f13820; genaue volle Hashes im Bericht |

Der zusätzlich durch die neue Ressourcendatei gestartete unveränderte Bookworm-ARMv7-Installerlauf39040992456 lief bei Integration noch. Er ist ausdrücklich kein Bestandteil der opt-in Loopback-Abnahme und kein ARMv6-Gerätebeleg. Bei späteren Aussagen zum Installer seinen tatsächlichen Endzustand prüfen. Auch automatisch nach Merge ausgelöste Läufe sind ohne gelesenen Endzustand keine weiteren Passnachweise.

## Wichtige Korrektur- und Vertragsentscheidungen

U03a2 wurde test-first begonnen: tatsächlicher Missingmodule-RED39035764388 und korrigierter RED39036483971 vor Produktmodulen. Die neue Bibliothek folgt auf RFID, beide Navigationsgruppen trennen bei6; die bisherige Tastaturfolge und der alte Browserharness bleiben erhalten. Dateinamen folgen dem Backendvertrag inklusive maximal255 UTF8-Bytes und erlaubter reiner Leerzeichen. Leere Ansicht wird semantisch über ihre Überschrift geprüft. Nach401/Vergessen Fokusflag vor Stateupdates setzen; Refresh/Paging stehlen keinen Fokus. Browserlocale de/en vor jedem Start wie im bestehenden Harness, statt die Netzallowlist für en-US blind auszuweiten. Mobile Fotos warten das geschlossene Menü samt CSS-Übergang ab. Realer Katalogerfolg und kontrollierte Fetchfehler bleiben getrennte Nachweise.

X01 hatte tatsächlichen Missingtemplate-RED39039862627/Job117416955521 vor Vorlagenerstellung. Das erste nginx-t39040497230/Job117418879133 scheiterte real an unzitierten Regexklammern. Korrektur: alle fünf Regexkeys zitieren, feste Backendauthority vor Headeraufbau verwenden, nicht upstream_addr; rohe Testanfragen verlangen Connection close. Zählerbaseline vor URIproben neu setzen und Browserguards auch nach Upstreamausfall prüfen. Alle fünf nginx-HTTP-Temppfade liegen im eigenen Prefix. CI extrahiert das tatsächliche nginx-Binärpaket ohne Installation/Maintainerskripte oder Dienstaktivierung; nginx-core war für Ubuntu Noble nur ein Metapaket.

Originruling: Standard-nginx unterscheidet im leeren Variablenwert fehlendes und ausdrücklich leeres Origin nicht. Nur der exakt gültige nichtleere äußere Origin wird fest umgeschrieben. Der leere Fall reicht ursprüngliche Originheader ohne eigenen/geerbten Override weiter; die unveränderte API akzeptiert fehlend und verwirft leer vor Autorisierung/Katalogzugriff. Für explizit leer/Whitespace darf der Backendankunftszähler steigen, Authorizer/Katalog bleiben0. Fremde und doppelte Origins/Hosts müssen vorher scheitern. Dies ist am tatsächlichen nginx1.24 geprüft, keine reine Masterquellenannahme. Timeouts sind Inaktivitätsgrenzen; die CI hat eine zusätzliche Stepdeadline.

## Nächste getrennte Aufträge und offene Grenzen

1. I01b-dev: lokalen Entwicklerstart mit verifiziertem Bundle, I01a-Preflight und eigenem Loopback-nginx umsetzen. R01b-Abhängigkeit erfüllt, Handoff i01b-bootstrap-plan.md. Web-CI muss für diesen Checkout ein neues passendes Bundle erzeugen; kein Node/npm-/CRA-Build auf dem512-MB-Zero-W.
2. I05/X: tatsächlichen LAN-/HTTPS-/Einmalzugangsweg getrennt konkretisieren; vorhandene Entwicklerloopbacks sind keine LAN-/Installationsfreigabe. Bedienplattformen/vertrauenswürdiger CA- oder Proxyweg bleiben offen.
3. I02/I03: persistente feste Installationsjobs und privilegierte Schritte getrennt umsetzen. Audio/Testton, RFID/Testscan und Musikpfad/Selbsttest bleiben eigene Fenster. Keine freien Shellbefehle aus Browserdaten.
4. S01/P02: ARMv6-Spotify-Build, Auth, MiniAmp-Ausgabe und bestätigten Quellenwechsel auf gesicherter Test-SD nachweisen. [Spotifyoptionen](armv6-spotify-options.md) sind Quellenprüfung, kein erfolgreicher Build/Gerätetest. Soloist/Raspotify nicht als ARMv6-kompatibel voraussetzen.
5. PiSugar-, lokale MPD-/GPIO-/RFID-/Timer- und Mischqueue-Liveanbindung bleiben offen. Der sichtbare Player und Akkustatus sind weiterhin als Vorschau gekennzeichnet; echte Bibliotheksdaten machen sie nicht automatisch live.

Bestätigt: originaler Zero W ARMv6, Raspbian GNU/Linux13 trixie32Bit (DEBIAN_VERSION_FULL=13.6), HiFiBerry MiniAmp, PiSugar2 mit2LEDs. Separate SD klärt der Nutzer vor Gerätetests; aktive Audio-/Readerkonfiguration und Spotify-Zugang sind noch nicht belegt. Keine Hardware-, Systemdienst-, LAN-, TLS- oder Kontomutation in diesen Slices vorgenommen.

## Gezielt zu ladende Berichte

- U03: [Plan](u03-library-ui-plan.md), [Autoren-/Ausführungsbericht](u03-library-ui-report.md), [Testreview](u03-library-ui-review.md), [Source-/Folgereview](u03-library-ui-source-review.md).
- X01: [Plan und Originruling](x01-nginx-integration-plan.md), [Autoren-/Ausführungsbericht](x01-nginx-report.md), [Testreview](x01-nginx-review.md), [Source-/Folgereview](x01-nginx-source-review.md).
- Folgende Abhängigkeiten: [Bootstrapgrenze](i01-bootstrap-seam-plan.md), [Quelleninventur](f03-source-inventory.md), [Verträge](a01-contracts.md), [Ressourcenregeln](resource-policy.md).

Die ausführlichen Einzelberichte und GitHub-Commits enthalten Befunde und Korrekturrunden. Lokale mechanische Diffpakete sind Reviewartefakte; die vollständigen veröffentlichten Änderungen stehen in PR16/17. Die ältere operative Chronologie bis U03a1 bleibt außerdem in der Dokumentationshistorie bei998d4d3e erhalten. Diese gekürzte Datei ist weiterhin die einzige operative Statusliste.

## Geprüfter Abschluss R01a/R01b und nächster Auftrag

R01a/PR18: Mergefc995afb397164364541e53fd6c7dd4bed79c0e9. Actual Web39044627838/Job117430793469 und vollePythonmatrix39044627823 bestanden. Das CI-Artefakt12104499265 enthält das echte Webarchiv1370736Bytes/SHA256dc82205b56e1269b9b5ee17be5d1e6f5384a368c495f9f69a5394f185fe5e652 und bindet exakt diesen Commit/Fork. Upload, Download derselben Artefakt-ID in frisches Verzeichnis und erneute Prüfung tatsächlich bestanden. Authentifiziertes Artefakt läuft24.10.2026ab; kein öffentlicher Releaseendpunkt.

R01b/PR19: Sourcehead617d2fd13cde686c1d5b7d0c9bef9ca0327e7618, Integration2002cc2c2de3daa8f0b2b06e6f9513cd71c92886, gleicher geprüfter Baum3dd4b2240cca9ebf729050a919cd3207074fd5b2. Genau2neue Pfade: installation/websetup/bundle.py und test/websetup/test_bundle.py. stdlib-Contextmanager kopiert/verifiziert lokale reguläre Eingaben privat, liest engen regulären TAR-/PAX-Pfadausschnitt mit festen Grenzen und liefert frisches temporäres Webroot. Eigene Bereinigung, Callerdateien/-fehler bleiben erhalten. Keine Installation/Aktivierung/Netzwerk-/Kontomutation.

Tatsächlicher R01b-Missingmodule-RED39045338774/Job117432825524 vor Produktmodul. Unabhängige Testreviews samt engen Rootrulings vor Source abgeschlossen; erstes ganzes Sourcereview4P2, minimale neue Regressionen zunächst lokal rot, Korrekturen und unabhängiger Folgepass schließen alle Befunde. SourceSHA2566e66a3b49cb5c71240cecbb046bfd136bc069d8cd950490f23b1fe1fa874dd9d; TestSHA256d7a3176bf8d300a4fa0d2348d5c5b0496658a783f54f16ecc54103584f40b465. Root hat beide finalen Remoteinhalte bytegleich gelesen.

R01b-Abnahme: Beide Vollcheckout-Pythonläufe39058605235 und39058602622 bestehen jeweils3.9–3.13plusfinish (117472316458/117472313297). Gelesener3.9Job117471631711:250/250Prüfungen bestanden, darunter alle39Intakefälle und echteLinux-FIFO/umask-/DEFLATE-/C1-/Consumerregressionen. Lokal39Intakefälle mit2Windows-Skips,15R01a mit2Windows-Skips,10I01a undV3lint bestanden. Mergeobjekt/Eltern fc995afb+617d2fd1, identischer Sourcebaum, Produktref und unverändertes develop42d5023e... bestätigt.

Auch der automatische Merge-Pythonlauf39058968526 an2002cc2c ist tatsächlich completed/success:alle3.9–3.13 undfinish117473390031. Der separat gestartete unveränderte ARMv7-Installer39058968556 ist kein weiterer Intake-/Gerätebeleg. Ältere zusätzliche ARMv7-Installerläufe sind keine R01b-Abnahme oder ARMv6-/Geräteprobe. Kein neuer Weblauf für reine Intakepfade: altesfc995afb-Bundle bleibt anfc995afbgebunden. I01b-dev muss im tatsächlichen Webworkflow ein passendes Bundle für seinen neuen Checkout erzeugen und über echten lokalen Starter/nginx prüfen; alte Manifestidentitäten nicht umschreiben.

S01-Quellenstand17.10als Prosa aktualisiert: sechs Primärquellen, nochmals tatsächlich aufgelöster librespotdev-Commit19959512c212cbc48a3ff64382fe204f52c659a7 mit3passenden Dateiblobs. RustARMv6-Ziel und TLSfeaturebezeichnungen geklärt; veraltetes Buildbeispiel nicht ungeprüft übernehmen. Nächster separater Nachweis ist reproduzierbarer externer Build mit echtem Raspbian13-ARMv6-Sysroot/ELFprüfung. Noch kein Build, Kontoauth, MiniAmp-/Stop-/Quellenwechsel- oder Gerätenachweis.

Nächster konkreter Auftrag: I01b-dev mit5geplanten Pfaden gemäß Handoff. LANtrust, privilegierte persistente Jobs, Audio-/RFID-/Spotify-/PiSugar-Liveanbindung und echte Geräteschritte bleiben getrennt. Test-SD erst vor Gerätearbeit klären; kein neuer Benutzerbeitrag für den gerätefreien Entwicklerstarter erforderlich. Kein aktiver Hintergrundworker nach diesem Abschluss behauptet.

Gezielte Unterlagen: [R01a-Plan](r01a-web-bundle-plan.md), [R01a-Bericht](r01a-web-bundle-report.md), [R01a-Testreview](r01a-web-bundle-review.md), [R01a-Sourcereview](r01a-web-bundle-source-review.md), [R01b-Plan](r01b-bundle-intake-plan.md), [R01b-Bericht](r01b-bundle-intake-report.md), [R01b-Testreview](r01b-bundle-intake-review.md), [R01b-Sourcereview](r01b-bundle-intake-source-review.md), [I01b-Handoff](i01b-bootstrap-plan.md), [Spotifyquellen](armv6-spotify-options.md). Diese Datei bleibt die einzige operative Statusliste.

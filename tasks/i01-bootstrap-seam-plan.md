# I01 – kleinste Bootstrap-/Preflightgrenze

Stand: 17.10.2026. **Lesende Vorbereitung; die spätere enge Root-Freigabe steht unten. Keine Dienstfreigabe.** Basis `e61a63e4b1322f47c252aad281176ec618e77831`, Tree `4e72f86b0319b37a9e4c292a05ad6a57c9161480`. Hauptplan I01/I02/I03 und F03-Inventur zuerst gelesen; danach genau fünf gezielte Remotequellen. Ziel ist ursprünglicher Zero W, ARMv6, Raspberry Pi OS Lite 32 Bit. Tatsächliche OSversion, Audiogerät und separate Test-SD fehlen; ARMv7-Installer-CI ist kein ARMv6-Beleg.

## Bestand: was sich wirklich wiederverwenden lässt

| Quelle am Basiscommit | Blob / Zeilenbefund |
| --- | --- |
| installation/install-jukebox.sh | c3610662b46f58fd4bc0947e45db2c08f4e96594 – 32–38 Logdateiumleitung, 89–99 Abbruch bei bestehendem Installationsverzeichnis; 101–123 Download eines Branch-Tarballs; 125–133 source aller Includes/Routinen; 137 Logging bereits vor Bestandsprüfung. Kein nebenwirkungsfreies Preflight. |
| installation/routines/install.sh | 4ff3e1ac969002cbd2f5844f8c9f3e3627270bba – 1–20 interaktiver Gesamtablauf: OSänderungen, Core, MPD, Samba vor Webapp; danach RFID/weitere Einrichtung. Erfüllt nicht „Setup vor Player“. |
| installation/routines/setup_jukebox_webapp.sh | f95e547f18c41e127a2f9c99cacc6e3b1cb408f7 – 8–10 Node20/inoffizieller ARMv6-Pin; 14–85 Installation/lokaler Build; 87–107 Upstream-Releaseasset mit optionalem latest-Fallback; 110–127 apt/nginx-Defaultsiteersatz, Homechmod und Dienstrestart. |
| installation/routines/setup_jukebox_core.sh | 6624d89ce6a2e96bd179e3faf423d955af99e94e – 12–22 privilegierte Pakete, 24–112 native Builds/venv/pyzmq; 115–118 überschreiben Defaultsettings; 120–129 kopieren Benutzerunit und daemon-reload/enable. Kein Job-/Rollbackvertrag. |
| resources/default-settings/nginx.default | d664f4cdde092d09ae241ee6078238d8f6c11a19 – 2–5 HTTP80 und vorhandener build-root; 23–31 /logs-Autoindex; 34–38 fehlendes Bundle zeigt Buildanleitung. Keine Setupauth-/HTTPS-Grenze. |

Vorhandene Bibliothek-/Konfigpfade, Unitname jukebox-daemon.service, nginx und Bundleziel sind belegte spätere Anschlusspunkte. Die Shellfunktionen sind wegen globalem Installationskontext, source-Abhängigkeiten und direkten Mutationen keine geeigneten Preflightimporte. Defaultconfig/Unittemplate selbst wurden im Fünfquellenbudget nicht zusätzlich gelesen; konkrete SYSTEMD_USR_PATH-Auflösung, Unitabhängigkeiten und Startverhalten bleiben vor I02/X zu prüfen. Kein automatischer Aufruf vorhandener Installerfunktionen aus Browserdaten.

## Empfehlung I01a: lesender erster Browserkontakt, vier neue Dateien

Ein später eng freizugebender erster Slice liefert nur Bestands-/Voraussetzungsanzeige, noch keine Konfiguration. Alle Namen Vorschläge; keine bestehende Datei mit A02b/Luna teilen.

| Exklusiver Pfad | Enger Auftrag |
| --- | --- |
| installation/websetup/preflight.py | Python-stdlib: kleine injizierbare Probe-/Auswertungsschicht; OSrelease als Daten lesen, Architektur/Pointerbreite, Python, Speicher/Platz, Repo-/Bestandsmarker. Fehlender/gesperrter Wert bleibt UNKNOWN mit eigenem Grund. Kein subprocess/sudo, Paketimport des Players, Konfigsourcen oder Netzprobe. |
| installation/websetup/server.py | Explizit manuell gestarteter unprivilegierter, nur an 127.0.0.1 gebundener stdlib-Server; ausschließlich feste GET-Seite und redigierter Preflightreport. Keine freie Dateiauslieferung/Dateipfadparameter, POST-/Installaktion oder Dienstregistrierung. Keine Raw-RPC-/PubSubimporte. |
| installation/websetup/index.html | Kleine ausgelieferte Statusseite ohne Buildschritt/externe Assets: Befund, unbekannte Voraussetzungen und „Noch keine Änderungen möglich“. Kein zweiter Wizard-/Frontendframeworkentwurf. |
| test/websetup/test_preflight.py | stdlib-Tests mit synthetischen Proben/temp-Verzeichnissen; Parser-/UNKNOWN-/Bestandsfälle plus feste HTTPgrenze und unveränderte Dateien prüfen. |

Das ist bewusst nur der lesende I01a-Teilschritt. Auf dem Zielgerät setzt er eine geprüfte vorhandene Python3-stdlib voraus; Pythonverfügbarkeit ist wegen unbekanntem OS noch kein gesicherter Bootstrapfakt. Er kann bei ersten Entwicklerprüfungen per ausdrücklich eingerichtetem SSH-Tunnel im Browser erreicht werden; das ist **nicht** der endgültige Nutzerpfad ohne weiteres SSH. Keine LANfreigabe, Ports/systemd/Rechteänderung oder Durchführung jetzt. Eine sichere LAN-/HTTPS-/Einmalzugangsfreigabe gehört in den nächsten getrennten I01b/X-Auftrag, nicht verdeckt in diese vier Dateien.

## Nutzerpfad und harte Abhängigkeiten

Ziel bleibt clone/geprüfter Bootstrap → Browser öffnen → konfigurieren. Der heutige Upstreaminstaller darf dafür nicht unverändert vorgeschaltet werden: er ändert bereits das System und installiert Playerabhängigkeiten, bevor Setup erreichbar ist. Nach I01a benötigt I01b einen expliziten Bootstrapvertrag: unterstütztes OS, geprüfte Minimalpakete, geschützter zeitlich begrenzter Einmalzugang, automatische Schließung und vorhandener-nginx-Anschluss. Ein falscher/abgelaufener Zugang muss abgewiesen sein, bevor Gerätezustand/Verwaltung angeboten wird. A01s vertrauenswürdiger HTTPS-Weg bleibt für echte Verwaltung/OAuth maßgeblich.

Auf 512-MB-Zero-W **kein Node/npm-/CRA-Build und keine inoffizielle Nodeinstallation als Pflicht**. Minimalstatus-HTML ist direkt auslieferbar; vollständiger Reactclient benötigt ein CI-vorgebautes, zum Fork-Backendcommit passendes Artefakt mit geprüftem Manifest/Hash. Ein konkretes solches Release-/Bootstrapartefakt liegt diesem Auftrag nicht vor. Der vorhandene Downloader bindet an Upstreamrelease/version/verkürzten HEAD und kann latest wählen; im gelesenen Ablauf kein Artefaktmanifest-/Digestvergleich. Diese Routinen sind daher keine freigegebene Forklieferkette. R01/Bundlebereitstellung ist Voraussetzung für den späteren vollständigen Webzugang; keinen Buildfallback anbieten.

I02 muss vor jeder Installation einen serialisierten persistenten Auftrag mit Lock/commandId, festen Schritten, Privilegiengrenze, redigierten Logs und Recovery nach Crash bereitstellen. apt, Konfigersatz, chmod, daemon-reload/enable/restart/reboot gehören ausschließlich dorthin; vorhandene Routinen erst nach expliziter Parametrisierung/Idempotenzprüfung übernehmen. I03 bleibt geteilt in Audio/Testton, Reader/Testscan und Musikpfad/Testdatei. Testton braucht die Audioreservierung; fehlender OS-/Audio-/SD-Nachweis blockiert seine Hardwarefreigabe.

## Abnahme und Ende des ersten Slices

Unitnachweise: armv6l/32bit als beobachteter Zieltyp, nicht pauschales SUPPORTED; anderes/unbekanntes OS oder ABI sichtbar, keine Gleichsetzung armhf=ARMv6-kompatibel. Wenig RAM/Platz, unlesbares os-release, fehlendes Bundle und installierte Settings von einem bloßen Quellclone unterscheiden. shared/settings als Verzeichnis allein genügt nicht: der bereits inventarisierte Quellbaum enthält dort .gitkeep; der gelesene Coreinstaller erzeugt erst jukebox.yaml/logger.yaml. Nicht belegte V2-/Fremdbestandsmarker bleiben UNKNOWN statt erfundener Erkennung. Fehlendes Python verhindert bereits den Start dieses Python-Slice und muss im späteren Bootstrap vorab behandelt werden; kein behaupteter Selbsttest ohne Interpreter. Kein Lesen/Publizieren von Konfiginhalten, Secrets, Logs, Host-/Bibliothekslisten. Vorhandene Installation unverändert; keine Write-/Install-/Restartmöglichkeiten. HTTPtests nur Loopback, feste Pfade/Methoden, keine fremden Dateizugriffe. Ein positiver Bericht bestätigt nur gelesene Fakten, nie Installationstauglichkeit unbekannter nativer Abhängigkeiten.

Getrennte reale Abnahme: frische separate SD mit genau benanntem Pi-OS/Python, ursprünglicher Zero W, Setup erreichbar bei gestopptem/nicht vorhandenem Player; danach Einmalzugang/HTTPS, wiederholter Bootstrap ohne Überschreiben und später Crash-/Browserende-/Neustartfortsetzung. Bis diese OS-/Hardwareprüfungen und I01b/I02 erfolgen, ist Gesamt-I01 offen. Es wurden fünf gezielte Quellen gelesen und nur dieser Plan geschrieben; kein Script, Server, Dienst, Test oder Konfigartefakt erstellt/ausgeführt.

Quellen: [Installer](https://github.com/Motrish/RPi-Jukebox-RFID/blob/e61a63e4b1322f47c252aad281176ec618e77831/installation/install-jukebox.sh), [Webroutine](https://github.com/Motrish/RPi-Jukebox-RFID/blob/e61a63e4b1322f47c252aad281176ec618e77831/installation/routines/setup_jukebox_webapp.sh), [Core-/Unitanschluss](https://github.com/Motrish/RPi-Jukebox-RFID/blob/e61a63e4b1322f47c252aad281176ec618e77831/installation/routines/setup_jukebox_core.sh).

## Root-Freigabe I01a

Der lesende Vier-Dateien-Slice wurde auf dem genannten e61a63e4-Basisstand für einen eigenen Luna-Worker im Teilstage G:/Entwicklung/phoniebox-staging/i01a freigegeben. Exklusive Änderungen: preflight.py, server.py, index.html und test/websetup/test_preflight.py an den oben benannten Pfaden. Keine vorhandenen Installer-/CI-/Vertragsdateien; kein geteilter Schreibpfad mit A02b. Root veröffentlicht erst nach Freeze, gezielter Prüfung und vollständiger Python-CI.

Lokale Entwicklung bleibt read-only, fester Loopback, keine Konfiginhalte, kein Setup-/Installkommando. Feste HTTPziele und Host-/Originprüfung verhindern fremde Hostnamen; markerbezogene Berechtigungsfehler müssen UNKNOWN bleiben. Sichtbare Seite deutsch, Browserprüfung auf dem Entwicklungshost und Hardwaregrenze ausdrücklich getrennt. Abnahme benötigt Repository-V3lint ohne Schwellenwertausnahme, echte neue RED/GREEN-Regressionen und unveränderte Fixturedateien. I01 als Ganzes sowie sicherer LANzugang, privilegierter Worker und Geräte-/OSabnahme bleiben offen.

## Spätere bestätigte Hardwareangaben

Der Nutzer hat inzwischen den originalen Zero W mit Raspbian GNU/Linux13 trixie32Bit (DEBIAN_VERSION_FULL13.6), HiFiBerry MiniAmp und PiSugar2 mit2LEDs benannt. Frühe Aussagen dieses historischen Plans zu unbekannter OSversion/Audiomodell sind damit ersetzt. Konkretes Abbild, aktive Audio-/Readerkonfiguration, separate Test-SD und Nachweis der Laufzeitabhängigkeiten bleiben offen. I01a wurde als rein lesender Slice integriert; ein vollständiger sicherer Browserbootstrap ist weiterhin der nächste getrennt zu planende Anschluss und wird durch U03a2/X01 nicht bereits geliefert.

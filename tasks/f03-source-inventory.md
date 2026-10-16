# F03 – Quelleninventur und CI-Baseline

Stand: 16.10.2026. Teilinventur; noch keine vollständige F03-Abnahme.

## Unveränderte Quelle

Basis: Upstream v3.6.0, Commit 4fa84fd50750fd4b52984d51aa7c95466cf5b241, Tree 14c8a895c4c5e6903315096a75c6b918228b6fa1. feature/foundation zeigt auf diesen Release. Der separate Branch future3/ci-baseline enthält einen mechanischen Integrationscommit 58826fcf880f521292c56c43b682fa67cfdc2418 mit exakt demselben Tree. Eltern sind der unveränderte Fork-develop-Stand und der Release-Commit. Es wurde kein Produktcode oder Workflow verändert.

Die Integration auf einem separaten Prüfbranch löst die vorhandenen future3-Pushworkflows aus. Damit ist ein vollständiger Checkout auf GitHubs Runnern prüfbar, ohne einen lokalen Quellbaum aus API-Einzeldateien nachzubauen. Dies ersetzt noch keinen interaktiven lokalen Entwicklungscheckout oder die Worktree-Isolation für Implementer.

## Belegte Einhängepunkte

Alle Links beziehen sich auf den unveränderlichen Basiscommit.

| Bereich | Quelle | Befund / Folge |
| --- | --- | --- |
| Webclient | [package.json](https://github.com/Motrish/RPi-Jukebox-RFID/blob/4fa84fd50750fd4b52984d51aa7c95466cf5b241/src/webapp/package.json) | React 17, MUI 5, react-scripts 5; vorhandenen Client schrittweise erweitern |
| Browserendpunkte | [config.js](https://github.com/Motrish/RPi-Jukebox-RFID/blob/4fa84fd50750fd4b52984d51aa7c95466cf5b241/src/webapp/src/config.js) | Direktes ws zu Port 5556/5557, keine same-origin-Anbindung |
| Nachrichten | [sockets/index.js](https://github.com/Motrish/RPi-Jukebox-RFID/blob/4fa84fd50750fd4b52984d51aa7c95466cf5b241/src/webapp/src/sockets/index.js) | jszmq Req/Sub, Request-ID und Topicereignisse; eigene dokumentierte Einschränkung bei parallelen Requests |
| Webserver | [nginx.default](https://github.com/Motrish/RPi-Jukebox-RFID/blob/4fa84fd50750fd4b52984d51aa7c95466cf5b241/resources/default-settings/nginx.default) | Statisches Web-Bundle auf Port 80 und Logroute; in diesem Serverblock keine vorgeschaltete Auth-/TLS-Grenze |
| Playerbefehle | [rpc_command_alias.py](https://github.com/Motrish/RPi-Jukebox-RFID/blob/4fa84fd50750fd4b52984d51aa7c95466cf5b241/src/jukebox/components/rpc_command_alias.py) | Aliase spielen/pausieren/skippen über Paket player und Plugin ctrl; Volume/Timer/Host getrennte Ziele |
| Playerhelfer | [player/__init__.py](https://github.com/Motrish/RPi-Jukebox-RFID/blob/4fa84fd50750fd4b52984d51aa7c95466cf5b241/src/jukebox/components/player/__init__.py) | Liefert Musikpfad aus MPD-Konfiguration; nicht mit vollständigem Controller verwechseln |
| Jingles | [jinglemp3](https://github.com/Motrish/RPi-Jukebox-RFID/blob/4fa84fd50750fd4b52984d51aa7c95466cf5b241/src/jukebox/components/jingle/jinglemp3/__init__.py) | mpg123 als zusätzlicher Audioerzeuger; Audiohoheit darf diesen Pfad nicht übersehen |

Weitere vorhandene Bereiche laut vollständiger Treeabfrage: components/playermpd, rfid, gpio, volume, mqtt, publishing sowie jukebox/rpc und publishing. Deren vollständige Aufrufer-/Alias-/Konfigurationsauflösung ist noch offen. Bluetooth, evdev, WAV-Jingles und Timer müssen bei der Fortsetzung ebenfalls inventarisiert werden; Existenz im Baum allein beweist keine umfassende Prüfung.

## Vorhandene CI

| Workflow | Ausführung / Grenze |
| --- | --- |
| pythonpackage_future3.yml | Push future3/** mit Python-/Requirementsänderungen; Python 3.9–3.13, apt Audioabhängigkeiten, venv, run_pytest.sh mit Coverage, run_flake8.sh |
| test_build_webapp_v3.yml | Push future3/** mit Webapp-/Buildactionänderungen; vorhandene Buildaction setzt Node 20 und ruft run_rebuild.sh -u auf |
| test_docker_debian_v3.yml | Push future3/** mit Installer-/CI-/Konfigänderungen; vorhandene Jobs für Bookworm/Bullseye armv7 |
| markdown_v3.yml | Push future3/** mit Markdownänderungen; bestehendes markdownlint |

Keine dieser geprüften Dateien bietet workflow_dispatch. Der isolierte Integrationscommit löst die betreffenden Pfadfilter durch die unveränderte vollständige V3-Übernahme aus. Exakte Jobresultate werden separat protokolliert; gestartete Jobs sind noch kein bestandener Build. Die Releaseautomatik mit Upstream-Ownerbindung gehört nicht zum verwendeten Baseline-Test und wird nicht für den Nutzer-Fork als funktionierend behauptet.

## Architekturentscheidungen für A01/A02

- Geschützter same-origin-Zugang ist konkret neu anzubinden. Raw-RPC-/PubSub-Ports dürfen nicht als bereits abgesicherte API dargestellt werden.
- Bestehende Paket-/Plugin-Aliase sowie sämtliche Audioquellen müssen bei der zentralen Playerhoheit berücksichtigt werden.
- Transport-, Snapshot- und Reconnect-Verträge sind mit dem vorhandenen Req/Sub-Verhalten abzugleichen.
- Baseline-CI, lokaler vollständiger Checkout, Browserprüfung und reale Zielhardware bleiben verschiedene Nachweise.

## Offene Voraussetzungen

Lokaler Gittransport und Worktrees bleiben blockiert. Beide aktiven Subagenten meldeten ein Nutzungslimit; Luna-Coding kann deshalb aktuell nicht fortgesetzt werden. Astra und Sol-Coding werden nicht als Ersatz verwendet. Geräteangaben und sichtbare Referenz fehlen weiter.

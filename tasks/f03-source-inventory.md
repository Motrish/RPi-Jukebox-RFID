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

## Zusätzliche bestätigte Player-Einhängepunkte

- resources/default-settings/jukebox.default.yaml ordnet modules.named.player dem Paket playermpd zu; seine Defaultkonfiguration setzt RPC-WebSocket auf 5556 und Pub/Sub-WebSocket auf 5557.
- components/playermpd/__init__.py registriert PlayerMPD unter Pluginname ctrl. Start/Stop/Pause, Seek, Play-Folder/Album/Single und Playliststatus sind dort gebündelt; remove/move sind am Basiscommit noch nicht implementiert.
- _mpd_status_poll sendet playerstatus; ein adaptereigener Stop ersetzt keine zentrale Generation-/Queuehoheit.

## Architekturentscheidungen für A01/A02

- Geschützter same-origin-Zugang ist konkret neu anzubinden. Raw-RPC-/PubSub-Ports dürfen nicht als bereits abgesicherte API dargestellt werden.
- Bestehende Paket-/Plugin-Aliase sowie sämtliche Audioquellen müssen bei der zentralen Playerhoheit berücksichtigt werden.
- Transport-, Snapshot- und Reconnect-Verträge sind mit dem vorhandenen Req/Sub-Verhalten abzugleichen.
- Baseline-CI, lokaler vollständiger Checkout, Browserprüfung und reale Zielhardware bleiben verschiedene Nachweise.

## Offene Voraussetzungen

Lokaler Gittransport und Worktrees bleiben blockiert. Die frühere Limitmeldung ist historisch; Luna-Coding wurde nach dem Reset auf isolierten Remote-Branches fortgesetzt. Geräteangaben und sichtbare Referenz fehlen weiter. Die gültige eingeschränkte Arbeitsweise steht unten sowie in tasks/todo.md.

## Tatsächlicher CI-Zwischenstand

- Webbuild am unveränderten V3-Tree: bestanden (Run 38955136477).
- Pythonmatrix 3.9 bis 3.13: bestanden (Run 38955136500).
- V3-Markdown: bestanden (Run 38955136416).
- Installationsworkflow 38955136828: Bullseye-armv7-Basisimage schlägt beim apt-Paketdownload mit mehreren HTTP-404-Antworten fehl; Buildexit 100. Der Installer wurde in diesem Job nicht erreicht. Es handelt sich um einen Fehler der unveränderten Baseline, nicht um neu implementierten Code.
- Historischer Zwischenstand Bookworm-armv7: damals im Aufbau; aktueller Abschluss siehe unten.
- Markdownprüfung des Dokumentations-PRs nach Formatkorrektur: bestanden (Runs 38955705551 und 38955697813).

## Ergänzte lesende Inventur für A01

Diese Ergänzung basiert auf gezielten Connectorabrufen am unveränderlichen Release-Commit `4fa84fd50750fd4b52984d51aa7c95466cf5b241`. Der vollständige rekursive Gitbaum enthält 514 Einträge und meldet truncated false. Die nachfolgend genannten Quellfamilien wurden tatsächlich gelesen; ihre Zielgeräte-Konfiguration und Laufzeitabnahme bleiben offen. Es wurde kein Checkout aus Einzeldateien konstruiert.

| Wiedergabeschreiber / Verbraucher | Im Release gelesener Weg | Folgeauftrag |
| --- | --- | --- |
| Browser und CLI-RPC | `src/webapp/src/commands/index.js` sowie `src/jukebox/run_rpc_tool.py` erreichen registrierte Playerfunktionen über `jukebox/rpc/server.py`; as_thread ist ebenfalls möglich | A02/P04/X: eine schreibende Controllergrenze, alte direkte Adaptermethoden nicht zusätzlich offen lassen |
| RFIDscan und Kartenentfernung | `components/rfid/reader/__init__.py` ruft Kartenaktionen direkt aus Readerthreads über plugs.call_ignore_errors auf; Removalwatchdog benutzt gebundene Aktion | P07a/P07b: Scan-/Removalidentität und Controllerübergabe |
| Second Swipe | `components/playermpd/__init__.py` vergleicht last_played_folder und ruft direkte toggle/next/rewind/replay-Methoden bzw. Customaktion | P04/P07: Listen-/Kartenidentität anstelle ausschließlich MPD-Ordnerzustand |
| GPIO | `components/gpio/gpioz/plugin/__init__.py` baut Eingaben; `core/input_devices.py` bindet Aktionen ausdrücklich mit dereference=True | P07a/P07b: gebundene Funktionen umgehen Pluginlock und spätere Registryänderung; Controller selbst muss serialisieren |
| Bluetoothtasten | `components/controls/bluetooth_audio_buttons/__init__.py` bindet toggle/next/prev ebenfalls mit dereference=True; `common/evdev_listener.py` führt Listenerthreads aus | Eigenes P07-Eingabeunterticket |
| Optionale evdev-Geräte | `components/controls/event_devices/__init__.py` bindet konfigurierbare Aktionen mit dereference=False, Aufruf aus Listenerthread | P07a/P07b: zusätzlich zu GPIO berücksichtigen |
| Optionales MQTT | `components/mqtt/__init__.py` führt MQTTkommandos über plugs.call_ignore_errors aus; `mqtt_command_alias.py` besitzt Legacy- und aktuelle Player-/Timeraliasse | P07/A02: beide Aliassätze umleiten; kein stilles Aktivieren optionaler Plugins |
| Timerstop und Shutdown | `components/timers/__init__.py` ruft player.ctrl.stop bzw. host.shutdown; `volume_fadeout_shutdown_timer.py` schreibt globale Lautstärke und löst Shutdown aus | P07/P04: Anbieterstop bestätigen, keine neue Ausführung nach Stop |
| Idlecheck | `components/timers/idle_shutdown_timer.py` vergleicht player.ctrl.playerstatus und steuert Shutdown | P07: kanonischer Gesamtplayerstatus statt ruhendem MPD während Spotify |
| Daemonshutdown | `jukebox/daemon.py` terminiert RPC, stoppt player.ctrl und führt Pluginfinalizer aus | P04/P07/P08: Annahme schließen, bestätigter Stop, Persistenz und begrenzte Finalisierung |
| MPD-Initialisierung und eigene Queue | `components/playermpd/__init__.py` kann vorhandene Queue löschen; Folder-/Albumstart befüllt mehrere MPD-Einträge; MPD steuert Random/Repeat/Autoadvance | P01/P02/P04/P08: genau eine Fortschrittshoheit, externe lokale MPD-/mpc-Schreiber am Zielgerät prüfen |
| Jingles | `components/jingle/__init__.py` startet Startupjingle asynchron und Shutdownjingle synchron; `jingle/alsawave/` nutzt ALSA, `jingle/jinglemp3/` einen mpg123-Prozess | P02/P04/P07: weitere Audioproduzenten und temporäre Volumeänderung explizit koordinieren |
| Sprachansage | `components/hostif/linux/__init__.py` say_my_ip benutzt `jukebox/speaking_text/` und eigenen subprocess | P07/I03: Sprach-/Testtonausgabe braucht Audiogrenze |
| Kartensynchronisation | `components/synchronisation/rfidcards/__init__.py` registriert direkt an components.playermpd.play_card_callbacks und ruft update_wait | P07/M01/U04: Callbackkopplung und verzögerte Bibliotheksindexierung erhalten |
| Globales Audio | `components/volume/__init__.py` verwaltet PulseAudio-Lautstärke und Sinkumschaltung einschließlich Geräteanschluss | P02/P05/I03: Soloist und MPD teilen denselben Ausgabepfad |

Quellen: [GPIOdirektbindung](https://github.com/Motrish/RPi-Jukebox-RFID/blob/4fa84fd50750fd4b52984d51aa7c95466cf5b241/src/jukebox/components/gpio/gpioz/core/input_devices.py), [Bindesemantik](https://github.com/Motrish/RPi-Jukebox-RFID/blob/4fa84fd50750fd4b52984d51aa7c95466cf5b241/src/jukebox/jukebox/utils.py), [RFID](https://github.com/Motrish/RPi-Jukebox-RFID/blob/4fa84fd50750fd4b52984d51aa7c95466cf5b241/src/jukebox/components/rfid/reader/__init__.py), [Bluetooth](https://github.com/Motrish/RPi-Jukebox-RFID/blob/4fa84fd50750fd4b52984d51aa7c95466cf5b241/src/jukebox/components/controls/bluetooth_audio_buttons/__init__.py), [MQTT](https://github.com/Motrish/RPi-Jukebox-RFID/blob/4fa84fd50750fd4b52984d51aa7c95466cf5b241/src/jukebox/components/mqtt/__init__.py), [MPD](https://github.com/Motrish/RPi-Jukebox-RFID/blob/4fa84fd50750fd4b52984d51aa7c95466cf5b241/src/jukebox/components/playermpd/__init__.py), [Jingle](https://github.com/Motrish/RPi-Jukebox-RFID/blob/4fa84fd50750fd4b52984d51aa7c95466cf5b241/src/jukebox/components/jingle/__init__.py).

### Präzisierte Quell-/Buildgrenzen

- Upstream registriert `player: playermpd`; `components/player/__init__.py` ist nur Bibliothekspfadhelfer. remove/move/map_filename_to_playlist_pos sind im MPD-Modul nicht implementiert, queue_load ist leer. Der JSONzustand unter shared/settings/music_player_status.json ist kein transaktionaler Queue-/Resumecontract.
- Pub/Sub besitzt Last-Value-Cache; dieser ist kein Eventjournal und kein atomarer Snapshot über mehrere Topics. Playerstatus wird alle 250 ms aus MPD-status/currentsong aktualisiert; bootId, generation, executionId und Eventfolge müssen neu ergänzt werden.
- `src/webapp/package.json`: React 17, CRA/react-scripts 5, MUI 5, React Router 6/HashRouter. Neue features-Verzeichnisse sind Vorschläge; bestehender Einstieg ist components plus commands/sockets/context.
- Der vollständige Baum und gelesene Browser-/nginx-Grenze zeigen keinen vorhandenen V3-Uploadendpunkt. U04 muss Wiederverwendung konkret nachweisen oder einen begrenzten neuen Upload-/Indexierungsslice erhalten; V2-PHP ist kein V3-Bestand.
- `requirements.txt` ist überwiegend unversioniert; pyzmq ist dort absichtlich auskommentiert. Piinstaller verlangt libzmq 4.3.5 mit Draft-API und pyzmq kleiner 26 mit entsprechendem Build. lg/lgpio wird aus Quellen gebaut; RPi.GPIO wird ausgeschlossen.
- `packages-core.txt` verlangt unter anderem ALSAheaders/-Werkzeuge, PulseAudio/Bluetooth, mpg123, ffmpeg, espeak, python3-venv/-dev, swig und rsync. MPD/mpc werden separat eingerichtet. MPD, PulseAudio und Jukebox laufen laut V3-Installer als Benutzerdienste.
- Buildaktion `.github/actions/build-webapp/action.yml` setzt Node 20.x und CI=false. `src/webapp/run_rebuild.sh -u` verwendet npm install und npm run build, liest Linux-/proc-Daten und kann Swap anpassen. Eine unveränderte npm-ci-basierte Reproduzierbarkeit darf daraus nicht behauptet werden.
- Pythonprüfbefehle im Root: `./run_pytest.sh --cov --cov-report xml --cov-config=.coveragerc` und `./run_flake8.sh`; Skripte aktivieren .venv. Bestehende test-Unterbereiche sind cfghandler, evdev und gpioz/twinbutton. setupTests.js allein ist kein UI-/Browsernachweis. Der Webbuild und die Pythonmatrix wurden laut obenstehenden Runprotokollen im CI ausgeführt, nicht in diesem lesenden Teilauftrag.
- Der Gitbaum enthält kein gebautes Webbundle. Bundleprüfsumme und Forkmanifest fehlen weiterhin. Releaseinstaller nutzt Upstreamkonstanten und kann auf latest zurückfallen; I01/R01 müssen Backend und passende Assets koppeln.
- Der Hauptplanwert HTTP 409 ist für bestehendes ZMQ-RPC nicht direkt anwendbar. Contractfehler benötigen einen stabilen RPCcode; 409 gilt erst an einer wirklich implementierten HTTP-Grenze.
- Bestehende HTTP-/Raw-WS-Konfiguration ist nicht ausreichend für vertrauenswürdiges HTTPS, OAuth oder privilegierte Verwaltung. Raw-RPC bindet an alle Adressen; nginx bietet eine Logroute. Auth muss sämtliche alten administrativen Zugänge einschließen.

### Arbeitsgrenze nach Rücksetzung des Limits

Die frühere Angabe eines verbrauchten Nutzungslimits ist historischer Zwischenstand; der Nutzer hat das Limit inzwischen zurückgesetzt. Lokaler Gittransport/Worktrees sind weiterhin nicht verfügbar. Ein begrenzter Remoteweg mit exklusiven Featurebranches und vollständigem Checkout im vorhandenen Actions-CI ist architektonisch vertretbar, wenn jedes Artefakt auf exaktem geprüftem SHA basiert, Headbewegungen erkannt werden und Integrationstests am tatsächlichen Commit laufen. Lokale neue Module sind ausdrücklich Staging-/Teilnachweise. G0 bleibt teilweise; daraus folgt keine Runtime-, Installations- oder Hardwarefreigabe.

Der erste fachlich abgegrenzte Anschluss ist [A01 CONTRACT 1](a01-contracts.md): transportfreie stdlib-Verträge und danach SQLite-Store. Produkt-/Workflowmutationen und Integration sind weiterhin Luna/X-Aufträge; dieser Bericht hat keine solchen Dateien geändert.

### Unabhängiges Diffreview des begrenzten CI-Anschlusses

Geprüft: Commit `83b0c01f655f7943ed238371d14574e5129a6d21`, Elterncommit `58826fcf880f521292c56c43b682fa67cfdc2418`, Tree `2602fce044672797fb9a6c54ede654c33514aca1`. GitHub-Commitdiff und vollständige geänderte Workflowdatei wurden lesend abgeglichen. Genau eine Datei ist geändert: `.github/workflows/test_docker_debian_v3.yml`; null hinzugefügte und sechs gelöschte Zeilen entfernen ausschließlich den aktiven Bullseye-armv7-Job. Bookworm-armv7, Event-/Pfadfilter und Concurrency bleiben unverändert. Keine Produktdatei, Berechtigung, Secretnutzung oder Releaseaktion kommt hinzu.

Ergebnis: kein freigabesperrender Befund in diesem engen Diff. Die Änderung beschränkt die Installationsprüfmatrix auf Bookworm; sie repariert den zuvor beobachteten Bullseye-apt-404-Fehler nicht. Der ursprüngliche Baselinefehler bleibt dokumentiert; ein erfolgreicher Bookworm-Installerlauf oder neue Hardwarekompatibilität folgt aus dem Diff nicht. Dieses Review ist statisch und gilt exakt dem genannten Commit, nicht späteren Änderungen.

Quelle: [exakter CI-Commitdiff](https://github.com/Motrish/RPi-Jukebox-RFID/commit/83b0c01f655f7943ed238371d14574e5129a6d21).

## Abgeschlossene Cloudnachweise

Der unveränderte Bookworm-Baselinelauf 38955136828 hat Imagebuild und alle fünf Installerprüfungen erfolgreich abgeschlossen; der Gesamtworkflow bleibt wegen des separat dokumentierten Bullseye-Fehlers fehlgeschlagen. Die isolierte Bookworm-Matrixkorrektur 83b0c01 bestand anschließend Imagebuild, alle fünf Prüfungen und cleanup im Lauf 38957569477 und wurde nach unabhängigem Review in PR 2 integriert. Weder Zielhardware noch ein neuer Webinstaller wurden damit abgenommen.

Transportfreie Contracts und Playlist-/Queue-Speicherung sind durch Luna implementiert, unabhängig reviewed und auf future3/modern-ui integriert. Die Pythonmatrix 3.9–3.13 einschließlich finish bestand für die jeweiligen geprüften Code-SHAs (38959948228, 38960469965, 38961153409, 38962176404). Verbindliche SHAs und zusätzliche neue Regressionen stehen in tasks/todo.md und den Ticketberichten; diese Inventur verdoppelt die operative Liste nicht.

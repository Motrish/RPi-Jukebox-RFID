# I02b – Anschluss des dauerhaften Setup-Journals

Vorbereitung nach I02a, keine Code- oder Gerätefreigabe durch dieses Dokument. Maßgeblich bleiben A01, I02 und die getrennten I03-Untertickets. Konkrete Implementierung erhält eigenen begrenzten Auftrag und unabhängiges Review.

## Tatsächlich geprüfte Anschlussquellen

Stand 01359cc3800d86ba8150705ad0b1ecd65c393972, gelesen am 18.10.2026:

- [Konstanten](https://github.com/Motrish/RPi-Jukebox-RFID/blob/01359cc3800d86ba8150705ad0b1ecd65c393972/installation/includes/00_constants.sh), Blob 574febed302af02167011f59fab5fa78367caa23: SYSTEMD_USR_PATH ist /usr/lib/systemd/user, Einstellungen liegen im gemeinsamen shared/settings-Verzeichnis.
- [Coreinstaller](https://github.com/Motrish/RPi-Jukebox-RFID/blob/01359cc3800d86ba8150705ad0b1ecd65c393972/installation/routines/setup_jukebox_core.sh), Blob 6624d89ce6a2e96bd179e3faf423d955af99e94e: JUKEBOX_SERVICE_NAME ergibt /usr/lib/systemd/user/jukebox-daemon.service. Die Routine kopiert mit sudo die Unit, ersetzt den Installationspfad, setzt Rechte und führt systemctl --user daemon-reload/enable aus. Defaultsettings werden zuvor mit cp -f überschrieben. Diese Funktionen sind keine nebenwirkungsfreien Importhelfer.
- [Bestehende Playerunit](https://github.com/Motrish/RPi-Jukebox-RFID/blob/01359cc3800d86ba8150705ad0b1ecd65c393972/resources/default-services/jukebox-daemon.service), Blob 7898088e2009ff6d4885bb1430b4da799b766ec2: After für Netzwerk, Sound, MPD und PulseAudio; Requires für MPD und PulseAudio. Start über run_jukebox.sh im Installationsverzeichnis, Restart always, WantedBy default.target. NoNewPrivileges ist auskommentiert, der alte Player führt selbst sudo shutdown/reboot aus. Das ist keine geeignete Workerunit als unveränderte Kopie.
- [Installereinstieg](https://github.com/Motrish/RPi-Jukebox-RFID/blob/01359cc3800d86ba8150705ad0b1ecd65c393972/installation/install-jukebox.sh), Blob c3610662b46f58fd4bc0947e45db2c08f4e96594: Zielbenutzer aus SUDO_USER beziehungsweise whoami, Home aus getent; Includes und Routinen werden global gesourced. Nicht aus Browserdaten aufrufen.

Diese Quellen klären die früher offene Pfadauflösung und Startabhängigkeit. Sie bestätigen weder einen erfolgreichen Zero-W-/Trixie-Boot noch die passende MiniAmp-Ausgabe.

## Nächste getrennte Entwicklungsschritte

1. Worker-Lebenszyklus und exklusiven Prozessbesitz festlegen: genau ein Ausführer, Besitz vor Reconciliation erwerben, früheren Worker sicher ausschließen, Lock während Beobachtung und Wirkung halten. Eine SQLite-Transaktion alleine sperrt keine bereits laufenden Systemprozesse. Abbruchsignal nur an sicherer Grenze behandeln; Browserende besitzt keine Workerlebenszeit.
2. Feste interne Schritthandler mit eindeutigem Beobachtungsvertrag definieren. Keine freien Befehle, Parameterpfade oder Handlernamen aus HTTP. Vor der Wirkung Intent committen, Wirkung unabhängig beobachten, dann bestätigen. Ungewisser Erfolg wird zur sichtbaren Inspektionsentscheidung und nie zu einem blinden Wiederholungsaufruf. Zunächst temporäre Fakes mit echten Prozess-/Crashprüfungen; noch keine alte Installationsroutine sourcen.
3. Privilegiengrenze separat umsetzen: unprivilegierte Web-/Statusseite und begrenzter privilegierter Worker, eigene Serviceunit und feste kontrollierte Ressourcen. Kein pauschales Root-Webbackend oder generisches sudo-/Shellgateway. Bestehende Playerunit und deren frühere Shutdownrechte gesondert behandeln; Player darf für Setup nicht benötigt werden.
4. Geschützten Auftragsanschluss an die lokale Setupseite entwickeln: unveränderliche erlaubte Konfiguration, commandId, Reload mit aktuellem Jobzustand, sicher begrenzte Statusanzeige und Fehlercodes. Erst nach Auth-/Origin-/CSRF-Entscheidung verbinden. Die derzeitige Setupseite bleibt lesend, I02a stellt keinen HTTP-Schreibendpunkt bereit.
5. I03a, I03b und I03c jeweils separat: Audio/Testton, Reader/Testscan, Musikpfad/Testdatei. Idempotente Beobachtung vorhandener Einstellungen vor Ersatz, Sicherung und Rückweg. HiFiBerry MiniAmp nicht blind mit einer ungeprüften Standardausgabe gleichsetzen.

## Zu erbringende Nachweise

Zwei Workerstarts dürfen keinen doppelten Schritt ausführen; Neustart nach Intent, nach realer Wirkung und vor Bestätigung muss sicher beobachtet werden. Persistente Jobs über Browserende erhalten; unbekannter Erfolg bleibt blockiert. Eingaben mit Shellzeichen erzeugen keinerlei freien Befehl. Prozessrechte und Unitreihenfolge unter Linux testen. Ein späteres Gerätesetup benötigt separate SD, exaktes Raspbian-13-Abbild und Zugriff auf den ursprünglichen Zero W; bestehende Nutzerdaten nicht durch allgemeine Fortsetzung überschreiben.

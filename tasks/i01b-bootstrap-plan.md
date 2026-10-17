# I01b – begrenzter Bootstrap nach R01a

Stand 17.10.2026. Prosa-Handoff ohne Implementierung oder Gerätefreigabe. Ausgangspunkt ist future3/modern-ui bei 6b872011c2e79263f61ca5384908b23251178a6b; R01as spätere integrierte, grüne SHA wird Arbeitsbasis. Status bleibt ausschließlich in tasks/todo.md. Planer: unabhängiger Sol-Prosaagent; Root hat den Handoff gespeichert.

Empfehlung: zuerst R01b als vertrauensgebundene lokale Bundleannahme mit sicherer Extraktion, danach I01b-dev als lokaler Entwicklerstart. Echter LANzugang folgt getrennt mit I05/X. Fehlende Trust- und Geräteinformationen blockieren diese beiden Softwareslices nicht.

## Geprüfter Anschluss

Gelesen wurden der historische I01a-Plan, die vier vorhandenen I01a-Dateien im lokalen Teilstage, R01as Vertrag, A01s HTTPS-/Workergrenze und die Backlogabschnitte I01/I02/R01/R02. Mutable R01a-Quellen wurden vom Planer nicht geprüft.

I01a besitzt preflight.py, server.py, index.html und test/websetup/test_preflight.py. Der Server bindet fest an 127.0.0.1, kennt ausschließlich GET / und /api/preflight, prüft Host/Origin und liefert redigierte Fakten. Seite und Report sind wiederverwendbar; Assetserver, Sitzung und Installationsaktionen fehlen. X01 liefert optionalen Loopback-nginx mit React und lesender Bibliotheks-API, aber keinen Setupanschluss. Hauptplayer und Batterie bleiben Vorschau. Der globale Upstreaminstaller mit latest-Fallback und nginx-Defaultersatz ist kein geeigneter Bootstrap.

Ziel bleibt Repository holen → kleiner Startbefehl → Website → konfigurieren, ohne Node/npm/CRA-Build auf dem 512-MB-Zero-W. Bestätigt: ursprünglicher Zero W ARMv6, Raspbian 13 trixie 32 Bit, DEBIAN_VERSION_FULL=13.6, MiniAmp und PiSugar2 mit zwei LEDs. Praktischer OS-/Python-/nginx-Nachweis und separates Testabbild fehlen; SD vor Gerätearbeit klären.

## 1. R01b: lokale Bundleannahme und sichere Extraktion

Abhängigkeit: integriertes, unabhängig geprüftes R01a mit tatsächlichem CI-Bundle-Rundlauf. Zwei neue exklusive Pfade:

| Pfad | Auftrag |
| --- | --- |
| installation/websetup/bundle.py | R01a-Prüfer nutzen; lokale Archiv-/Manifestdateien annehmen und ausschließlich in eigenes privates Staging extrahieren. |
| test/websetup/test_bundle.py | Echte Producerfixtures und bösartige Archive; fremde Dateien und eigene Fehlerbereinigung prüfen. |

Entwickler laden das konkrete Artefakt eines benannten erfolgreichen CI-Laufs angemeldet voraus. Fork, voller Checkoutcommit und Artefaktidentität werden gegen den geprüften Lauf abgeglichen. Erwarteter Fork/Commit kommen unabhängig vom Manifest zum Prüfer. Ein beliebiges Manifest mit passendem SHA authentifiziert keinen Hersteller. GitHub verlangt angemeldeten Zugriff; Artefakte laufen ab: [Workflow-Artefakte](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts). Keine Zugangsdaten auf der Box, in Fixtures oder URLs.

Eingaben sind ausschließlich die beiden inneren R01a-Dateien. Keine Netz-, Shell-, Installations- oder Aktivierungsfunktion. Vor Schreiben Format, erwarteten Fork/Commit, Größe und Digest mit R01a prüfen. Prüfung und Extraktion müssen dieselben privaten stabilen Eingabebytes verwenden.

Nur reguläre relative Dateien; Eltern-/Absolut-/Backslash-/Steuerzeichenpfade, Links, Sonderdateien, sparse-Dateien, Namensduplikate und Datei-/Verzeichniskollisionen ablehnen. Für lange Buildnamen nur tatsächlich benötigte TAR-Erweiterungen zulassen. R01a-Grenzen: 64 MiB komprimiert, 256 MiB reguläre Nutzdaten, 4096 Dateien, 16 KiB Manifest. Zusätzlich gesamten dekomprimierten TAR-Strom einschließlich Header-/Erweiterungsdaten begrenzen; vorgeschlagen 272 MiB, gegen echten Produceroutput bestätigen. Tatsächliche Bytes, fileCount und index.html prüfen.

Nur eigene neue Dateien mit festen nicht ausführbaren Modi schreiben. Keine bestehenden Ziele ersetzen oder Zielpfadlinks verfolgen. Fehler entfernen ausschließlich eigenes Staging. Kein Ersatz von src/webapp/build, keine Update-/Rollbackbehauptung. Versionsabhängige tarfile-Defaults ersetzen diese Grenze nicht: [Python-Extraktionsdokumentation](https://docs.python.org/3/library/tarfile.html#extraction-filters).

Abnahme: echtes R01a-Archiv ergibt bytegleiches privates Staging. Falsche Identität, manipulierte/abgeschnittene Bytes, unzulässige Mitglieder und Grenzen scheitern geschlossen. Tests beweisen keinen Ausbruch, kein Überschreiben, eigene Bereinigung und unveränderte Installation. Tatsächlicher Missingmodule-RED vor Implementierung; danach gezielte Tests, I01a-/R01a-Regressionen, V3lint, voller CI-Checkout und unabhängiges Review am exakten Integrationscommit. Kein Zielgerät erforderlich.

## 2. I01b-dev: lokaler Start mit vorausgeladenem Bundle

Abhängigkeiten: R01b grün, vorhandenes Python und nginx auf dem Entwicklungsrechner. Fünf exklusive Pfade; Workflow erst nach serieller Übergabe von R01a:

| Pfad | Auftrag |
| --- | --- |
| installation/bootstrap-web.sh | Kleiner Einstieg: Interpreter prüfen, festen Pythonstarter aufrufen; kein Download/Paketmanager. |
| installation/websetup/launch.py | Lokale Artefaktpfade und erwartete Identität annehmen; R01b-Staging, I01a-Server und eigenen unprivilegierten nginx betreuen. |
| resources/default-settings/nginx.bootstrap-loopback.conf | Vollständige opt-in Entwicklervorlage: IPv4-Loopback, privater Prefix, feste Staging-/Preflightziele. |
| test/websetup/test_launch.py | CLI-/Prozess-/echte-nginx-/Browserabnahme mit Tempdaten und endlichen Laufzeiten. |
| .github/workflows/test_build_webapp_v3.yml | Bestehenden Build und nginx-/Browserwerkzeuge für Bootstrapnachweis nutzen. |

Start prüft Bundle und erstellt privates Staging vor dem äußeren Listener. /setup/ liefert I01as Seite, /api/preflight deren Report. nginx bildet Host/Origin auf den festen Preflightupstream ab. Reactassets stammen ausschließlich aus geprüftem Staging. Starter nennt Setupadresse und bestehenden React-Vorschaupfad. Der Preflightbericht über src/webapp/build bleibt Bestandsbeobachtung, kein Aktivierungsnachweis. Keine Bibliotheksauth neu erfinden oder RPC-/WS-/Log-/Verwaltungsroute hinzufügen. Unbekannte APIpfade scheitern ohne SPA-HTML. X01s Bibliotheksintegration bleibt eigener Nachweis.

Fehlendes Python/nginx oder ungültiges Bundle ergibt Diagnose ohne Installationsfallback. Vordergrundbetrieb, Portkollision als Fehler, Stoppen ausschließlich eigener Prozesse; kein systemd-, Firewall- oder Defaultsiteeingriff.

Abnahme: tatsächlicher R01a-CI-Reactbuild lädt über echten lokalen nginx; I01a-Fakten erscheinen ohne Player. Fremde/mehrfache Host-/Originwerte, Pfadausbrüche, unerlaubte Methoden und unbekannte Verwaltungsrouten scheitern. Keine externen Browseranfragen oder Secrets in Logs. I01a/X01/R01a bleiben grün. Abbruch/Startfehler hinterlassen keine eigenen Prozesse; Bestandsdateien/globales nginx bleiben unverändert. Ergebnis ist Entwicklerstart ohne Node auf dem Empfänger; Konfigurationswizard, ARMv6 und LAN bleiben offen.

## 3. LANeinrichtung und endgültige Lieferung

A01 verlangt vertrauenswürdiges HTTPS auf jedem Bediengerät, bevorzugt lokale CA mit Gerätezertifikat, alternativ vorhandene vertrauenswürdige Proxyorigin. Es fehlen Bedienplattformen, stabiler Gerätename und sicherer CA-Verteilweg. Für eine Proxyalternative fehlen Adresse, Eigentum und Betriebsumgebung; für Domain/DNS-01 fehlen kontrollierter Domainname, DNSzugang und Erneuerungsweg. [Let's Encrypt DNS-01](https://letsencrypt.org/docs/challenge-types/) erfordert kontrollierte DNSänderungen. Keine Infrastruktur voraussetzen.

Lokale CA konkretisieren, sobald Bediengeräte feststehen; vorhandenen HTTPSproxy nutzen, falls vorhanden. CAinstallation kann zusätzliche Trustschritte erfordern, etwa auf [Applegeräten](https://support.apple.com/en-us/102390). Ein selbstsigniertes Leaf ohne vertrauten Anker und ungeschütztes .local erfüllen A01 nicht. Ersttransport des Ankers benötigt unabhängig überprüften Weg. Ein [SSH-Forward](https://man.openbsd.org/ssh#L) schützt bei geprüfter SSH-Hostidentität den Transport zum Pi-Loopback, setzt aber SSHzugang und laufenden Clienttunnel voraus und beweist kein LAN-/Smartphone-HTTPS. Hier wird kein Tunnel eingerichtet.

Erst nach Trustentscheidung LAN-Slice auf höchstens fünf konkrete Pfade begrenzen. Reale Abnahme: falscher/abgelaufener/verbrauchter Einmalzugang scheitert vor Zustandszugriff; endliche Sitzung und automatische Schließung funktionieren; gesamte exponierte Origin einschließlich rawRPC-/Logs ist geschützt. Setup läuft ohne Player. I02 behält persistente Jobs, commandId/Lock, feste privilegierte Schritte und Recovery. apt, Dienste, Konfigersatz, Neustart und Installation gehören nicht zum Launcher.

Für den endgültigen Weg ohne Vorausladen fehlt ein dauerhafter vertrauenswürdiger anonymer Bundleendpunkt. Späterer Retrievalslice prüft festen Fork/vollen Commit, sicheren Manifestbezug und begrenzten HTTPSdownload; kein latest-/Buildfallback. Öffentliche Releasebereitstellung erfolgt im später autorisierten R02-Releaseauftrag. Diese Lücken blockieren R01b und I01b-dev nicht. Keine Geräte-, Dienst-, Netzwerk- oder Kontomutation durch diesen Plan.

## Nachgewiesener Anschluss am17.10.2026

R01a/PR18ist alsfc995afbintegriert und mit tatsächlichem commitgenauem Web-Artefaktrundlauf geprüft. R01b/PR19ist als2002cc2c2de3daa8f0b2b06e6f9513cd71c92886integriert, Baum3dd4b2240cca9ebf729050a919cd3207074fd5b2; beide vollen Python3.9–3.13-Matrizen samt250Prüfungen,39Intakefällen und unabhängiger Reviewabschluss bestanden. Contextmanager staged_bundle mit archive_path,manifest_path,expected_repository,expected_commit,staging_parent liefert ein privates Webroot für seine Lebensdauer. Bestehende Installation unverändert.

Damit ist die R01b-Abhängigkeit dieses Plans erfüllt; I01b-dev beginnt künftig auf2002cc2coder dessen neu gelesenem Folgehead. Seine Workflowänderung muss die eigenen Bootstrap-Pfade in beide passenden Pfadfilter aufnehmen und vor Artefaktveröffentlichung ein frisches zum tatsächlichen Checkout passendes R01a-Bundle über den echten Starter/nginx prüfen. Das bisherige R01a-Artefakt fürfc995afbist kein Bundle für2002cc2c. Keine alte Manifestidentität umschreiben. Sonstige LAN-/Trust-/Geräte-/Releasegrenzen dieses Plans bleiben bestehen.

# I01b: lokaler Web-Setupstarter

Stand 18.10.2026. [PR20](https://github.com/Motrish/RPi-Jukebox-RFID/pull/20) ist als `741085f902c88aaa2fa74ef5dcd473ba993427e3` in `future3/modern-ui` integriert. Der Mergebaum `167270d05665b96c9f9c44f3ef26e9d96891d20e` stimmt exakt mit dem unabhängig geprüften Sourcehead `5150de984e523cd23d26230e064dfb9d45eb3d2d` überein. Eltern sind die vorherige Produktbasis `2002cc2c2de3daa8f0b2b06e6f9513cd71c92886` und dieser Sourcehead. Produktref und unverändertes develop `42d5023e37dbf8de6477fef5ebcd6eae3cb5087d` wurden nach dem Merge gelesen.

## Ergebnis

Der kleine Shell-Einstieg prüft vorhandenes Python3.9+ und delegiert an einen festen Launcher. Dieser übernimmt ausschließlich ein vorausgeladenes lokales Bundle mit unabhängig erwarteter Fork-/Commitidentität, nutzt R01bs private Prüfung und Extraktion und betreut eine eigene unprivilegierte nginx-Instanz im Vordergrund. Auf dem Empfänger ist kein Node-/npm-/CRA-Build erforderlich. nginx bleibt eine vorhandene Voraussetzung.

Unter derselben IPv4-Loopbackadresse liefert /setup/ die unveränderte I01a-Statusseite und /api/preflight deren redigierte Systemdaten. Die bestehende React-Vorschau ist über den ebenfalls ausgegebenen Hashpfad erreichbar. Die Seite bleibt schreibgeschützt; die Beobachtung zu src/webapp/build ist keine Aktivierungsbestätigung.

Der Starter prüft die Portverfügbarkeit nach erfolgreicher Bundleprüfung. Die anschließende Bereitschaft verlangt eine passende zufällige Markierung aus der Antwort des eigenen nginx; sie wird dem angefragten Dienst nicht im Request verraten. Nichtblockierendes Headerlesen besitzt eine gemeinsame monotone Deadline, maximal 8192 Bytes und 64 Felder; Antwortbodies werden dabei nicht gelesen. Unsichere Dollarzeichen in privaten nginx-Pfaden werden vor Listenern verworfen. Rohe Systemfehler werden durch feste öffentliche Diagnosen ersetzt. Stoppen und Fehlerbereinigung betreffen nur eigene Prozesse und temporäre Dateien.

## Genau fünf Produktpfade

| Pfad | Rolle |
| --- | --- |
| installation/bootstrap-web.sh | Einstieg unabhängig vom Aufrufverzeichnis, Gitmodus 100755 |
| installation/websetup/launch.py | Prüfung, private Laufzeit, Prozess-/Listenerlebensdauer |
| resources/default-settings/nginx.bootstrap-loopback.conf | Feste Loopbackrouten, Headergrenze, eigener Prefix |
| test/websetup/test_launch.py | Unit-, Prozess-, echter nginx- und Browsernachweis |
| .github/workflows/test_build_webapp_v3.yml | Passendes tatsächliches Checkoutbundle vor Veröffentlichung prüfen |

Alle fünf Remoteinhalte wurden bytegleich zum Luna-Stage gelesen. Bestehende I01a-/R01a-/R01b-/X01-Module blieben unverändert. Ausschließlich Luna erstellte Code, Tests, Shell, Workflow und Konfiguration; Root koordinierte, prüfte und übernahm exakte Inhalte. Unabhängige Sol-Reviews schrieben Prosa.

## Tatsächliche Abnahme am geprüften Sourcehead

| Nachweis | Ergebnis |
| --- | --- |
| [Web39078642625](https://github.com/Motrish/RPi-Jukebox-RFID/actions/runs/39078642625), Job117530908018 | completed/success |
| Linux-Setup/Intake |61 von 61 Fällen erfolgreich, keine Plattformskips |
| R01a/Verträge |15 Bundlefälle, 22 Pythonverträge, 12 Webverträge erfolgreich |
| React/Bibliothek | Bestehender CRA-Build,24 Bibliotheks-Jestfälle, Preview-/Katalog-/nginx-Chromiumprüfungen erfolgreich |
| Neuer Bootstrap | Tatsächliches frisches CI-Bundle durch Shell/Launcher und nginx 1.24.0: HTTPmatrix, geladene I01a-Fakten, Reactassets, keine Fremdrequests, SIGINT/SIGTERM, unerwarteter nginx-Ausfall, aktive fremdeHTTP200-Portkollision, Sonderpfade und eigene Bereinigung erfolgreich |
| [Python39078642618](https://github.com/Motrish/RPi-Jukebox-RFID/actions/runs/39078642618) |3.9–3.13 und finish117531583697 vollständig completed/success |
| [Python39078645963](https://github.com/Motrish/RPi-Jukebox-RFID/actions/runs/39078645963) |3.9–3.13 und finish117531492489 vollständig completed/success |
| Gelesener Python3.9-Job117530908192 |262 Tests bestanden; eine vorhandene runpy-Warnung aus unverändertem library_api-CLI-Test |
| Root lokal |61Setupfälle insgesamt,5 Windows-Skips, Exit0; V3lint Exit0 |

Das Source-CI-Artefakt12118400475 gehört ausschließlich zu5150de984e523cd23d26230e064dfb9d45eb3d2d. Das innere Webarchiv ist1370736Bytes groß, SHA256dc82205b56e1269b9b5ee17be5d1e6f5384a368c495f9f69a5394f185fe5e652. Upload, Download genau derselben Artefakt-ID in ein frisches Verzeichnis und erneute Identitäts-/Digestprüfung wurden tatsächlich ausgeführt. Gleiche Buildbytes machen Manifestidentitäten nicht austauschbar. Auch der [Merge-Weblauf39078909520](https://github.com/Motrish/RPi-Jukebox-RFID/actions/runs/39078909520), Job117531676291, ist tatsächlich vollständig completed/success. Er erzeugte das eigene zu741085f902c88aaa2fa74ef5dcd473ba993427e3 passende Manifest und prüfte erneut den echten Bootstrap-/Browserpfad vor Upload. Artefakt12117814330 enthält das1370736Bytes große Archiv mit derselben obigen SHA256; ZIPgröße1371589Bytes. Upload und Download genau dieser Artefakt-ID mit erneuter Prüfung des Mergecommits sind bestätigt. Ablauf24.10.2026um23:26:43UTC. Artefakte benötigen GitHub-Lesezugriff und laufen ab; es wurde kein öffentlicher Release veröffentlicht.

## Review und Fehlernachweise

Die Testvorstufe war vor Produktdateien tatsächlich rot: Web39076557354/Job117524799774 meldete fehlendes installation.websetup.launch. Das unabhängige Testreview mit zwei engen Fixrunden schloss Fixture-, Browserallowlist-/Selektor-, Readiness-, Cleanup-, Bericht- und Negativroutenbefunde.

Das ganze Sourcereview benannte fremde200-Readiness, Dollarvariablen und Pfadfehlermeldungen. Gezielte Regressionen reproduzierten die Fehler vor Korrektur. Ein enger Folgepass schloss Pfad-/Diagnosefehler und erkannte die verbleibende fremde204-Readiness sowie unbeschränktes Lesen. Diese tragende Grenze wurde ausdrücklich weiter korrigiert. Der spätere echte nginx-Lauf zeigte außerdem, dass der HTTPtest generische nginx-Fehlerseiten fälschlich als React-SPA wertete. Jetzt vergleicht er mit dem wirklichen verifizierten Index und behält alle negativen Statusforderungen.

Das abschließende [Ownershipreview](i01b-bootstrap-ownership-review.md) gibt beide Achsen frei; keine wichtigen offenen Befunde. Die sechs gezielten Regressionen sind grün. Das [gesamte Sourcereview](i01b-bootstrap-source-review.md), die [enge Zwischenprüfung](i01b-bootstrap-source-rereview.md) und der [abschließende Autorenbericht](i01b-bootstrap-ownership-closure-report.md) dokumentieren den begrenzten Verlauf. Reviewfreigabe und tatsächliche CI sind getrennte Nachweise.

## Entscheidungen und Grenzen

1. Vorhandenen isolierten Teilstage plus authentifizierten Connector und vollständige CI-Checkouts fortgeführt, da lokaler Vollcheckout/Worktrees blockiert bleiben. Kosten: reale Integration erst durch CI nachweisbar.
2. Eine operative Liste und dauerhafte Berichte/Stages behalten. Kosten: kleiner zusätzlicher Speicherbedarf; kein destruktiver Skill-Cleanup.
3. I01a im eigenen Thread mit gehaltenem port0-Socket und nginx als einzigem Vordergrundkind gewählt. Kosten: spätere Dienste-/LANintegration benötigt eigenen Entwurf.
4. Portverfügbarkeitsprüfung mit zufälligem Antwortmarker kombiniert; Bindprobe allein genügt wegen des Freigabe-/Neubindungsfensters nicht. Kosten: ein zusätzlicher fester Template-/Headerparameter und dessen Regressionen.
5. Tragenden Ownershiprest trotz erreichtem finalem Reviewfixzyklus weiter korrigiert. Kosten: ein zusätzlicher enger Fix-/Prüfzyklus; keine Integration eines bekannten Fehlers.

Nächster fachlicher Auftrag sind I02s persistente serialisierte Setupjobs mit commandId, festem Schrittkatalog, Privilegiengrenze und Recovery. I05/X behandelt echten LAN-/HTTPS-/Einmalzugang gesondert. I03 Audio/RFID, SpotifyARMv6, PiSugar-Liveintegration, öffentliche Bundlebereitstellung und Geräteabnahme bleiben offen. Für dieses gerätefreie Ergebnis waren keine neuen Nutzerdaten erforderlich.

Bestätigtes Ziel bleibt ZeroW ARMv6, Raspbian13 trixie32Bit13.6, HiFiBerryMiniAmp und PiSugar2 mit2LEDs. Es gab keinen Gerätezugriff, Paket-/Dienst-/Firewall-/Defaultsiteeingriff oder Konto-/LAN-/TLS-/Releasevorgang. Separate SD erst vor Gerätetests klären. Es ist kein Timer/Scheduler eingerichtet und keine automatische Hintergrundfortsetzung behauptet.

# U02b – kleiner React-Anschluss

Stand: 17.10.2026. **Root hat U02b1 und U02b2 unten seriell freigegeben.** Die folgende Quellanalyse begründet U02b1: akzeptierte Shell als ausdrücklich simulierte View im vorhandenen Reactclient, vor Auswertung des Geräteimportgraphen ausgewählt. Liveanschluss folgt separat.

## Tatsächliche Quellgrenze

Sechs Dateien vollständig am Commit `1995a5c21e1e41f33a5cc61c6a27a3f5c803f871` gelesen, zusätzlich Tree zur Pfadprüfung. U02a-Commit 7820c608 ändert diese Reactquellen nicht.

| Quelle unter src/webapp/src | Blob / Befund |
| --- | --- |
| index.js | eb5d1f84e19d7f2a0a986d9ce4f26e23531b1766 – ein ReactDOM.render nach #root, vorhandene Theme-/StyledEngineProvider, CssBaseline und i18n. |
| App.js | a51529381aaf01c30b558103a223916ad106a891 – statische Imports und unbedingtes Mounten von PubSub-, Player-, AppSettingsProvider und Router; vorhandenes Suspense. |
| router.js | e2b10a1e145e3c8c712429c77686fd3fcc4d7e81 – HashRouter, Index=Player, library/*, cards/*, settings/*; Navigation außerhalb Routes. Grid xs12/md6 mit 64px unterem Abstand. Kein gemeinsamer Header oder persistenter Player an diesem Einstieg. |
| context/pubsub/index.js | 802a2f05fc3cfdabd5322b044902d89418cdae92 – statischer sockets-Import; Mount registriert Themen außer playerstatus; kein Effectcleanup. |
| context/player/index.js | ac5ee2e8f487c3c2a71d0bc1cf20a07cc6cbd126 – statischer sockets-Import; Mount registriert playerstatus; kein Effectcleanup. |
| sockets/index.js | fedc57a05d8532195fddf8fdb3ac6f8e91f2c589 – schon Import erzeugt zmq.Sub, subscribt und verbindet PUBSUB_ENDPOINT; initSockets registriert nur Listener. socketRequest verbindet/sendet bei Aufruf. |

**Ein neuer Routeintrag oder nicht gemountete Provider verhindern den Socketstart deshalb nicht.** Header/index.js existiert laut Tree (Blob 1c2234d98f4e12f8a13ca6ea3b9aa8ce557f7b92); seine inneren Seiteneinbindungen und Playerunterkomponenten wurden im Abrufbudget nicht zusätzlich gelesen. Wiederverwendbarkeit/Effektfreiheit werden nicht behauptet; dieser Slice importiert sie nicht.

## Empfohlener Auftrag: höchstens fünf exklusive Dateien

Neue Namen sind Vorschläge. Bestehende index.js, Legacyrouter, Gerätecontexts und statische Vorschau bleiben bestehen.

| Datei | Auftrag |
| --- | --- |
| src/webapp/src/App.js | Initiale Bootwahl für #/design-preview und Unterpfade. Vier bisherige Provider-/Routerimports per React.lazy erst im Legacyzweig laden; vorhandenes Suspense nutzen. Preview rendert ausschließlich neue View. |
| src/webapp/src/components/DesignPreview/index.js (neu) | Akzeptierte Shell/Nav/Header/Hero/Cover und fester Vorschauplayer als Reactkomponente, vorhandenes MUI/react-router-dom. Ein HashRouter zur Laufzeit; alle Previewseiten unter /design-preview. Unbekannte Previewpfade bleiben harmlos in der Preview. |
| src/webapp/src/components/DesignPreview/styles.css (neu) | Übernommenes responsive Design, auf Shellklasse begrenzt; Fokus/reduced motion. Globales Theme unverändert. |
| src/webapp/src/components/DesignPreview/previewModel.js (neu) | Sideeffectfreie Beispieldaten/lokaler Reactzustand, gemeinsame Track-/Queuereihenfolge und benannte Demoaktionen/Capabilities. Kein Transport. |
| tests/design-preview/react_smoke.py (neu) | Akzeptierten Playwright-Ablauf für den gebauten Reactpfad übernehmen; Netz-/Socketprüfung ergänzen. |

Derselbe ReactDOM-root/CRA-Build, keine zweite App, iframe, Dependency, Framework oder Port. Bootwahl bleibt bis Reload stabil; Previewnavigation lädt keine Legacyprovider nach. Legacybetrieb bleibt eigener bestehender Modus und wird nicht als gerätefrei beschrieben.

## Anfang, Ende, Abnahme und offene Grenzen

Anfang: isolierte public-Vorschau; React bootet unbedingt Gerätecontexts. Ende U02b1: expliziter Reactpreviewpfad mit lokal simuliertem Player, vorhandener Legacyzugang erhalten. Kein neuer Livebetrieb.

Abnahme im vollständigen Remotecheckout: vorhandener Webbuild/Lint grün; direkter Previewboot, sieben Seiten und Browserregressionen für Brand per Tastatur, Queue gegen Weiter/Vor/Zurück/Mix, Playererhalt über Routen, Suchleerzustand, drei Akkuzustände, Escape/Tab, 320px-Überlauf und Screenshots 390/768/1440. Kein WebSocket oder Backend-/Host-/Audio-/OAuth-/Remoteassetrequest, auch nach Interaktionen; gleichoriginige Backendrequests mitprüfen, lokale Build-/Übersetzungsassets erlauben. Legacyrouten/Providerstruktur mit gemocktem Transport auf Erhalt prüfen. theme/i18n sind noch nicht vollständig effektauditiert; unerwartete Geräteimporte dort erfordern eigenen Folgeslice statt verdeckter Scopeausweitung.

Offen: A02b-JS-Konformität/Validierung, revisionsgebundene Storekommandos, P04-Generation/Idempotenz/Capabilityhoheit und X als einziger autorisierter Transportanschluss. Preview importiert keine commands, sockets, Gerätecontexts oder bisherigen Gerätekomponenten; kein neuer MPDschreiber. Demozustand ist kein bestätigter Provider-/Queuestatus, Demofähigkeit keine Echtfähigkeit. Lokales Staging bleibt Teilmodulnachweis, vollständiger Build liegt bei CI; Runtime-/Hardwarefunktion bleibt unbelegt. Root entscheidet den nächsten Codingauftrag.

Quellen: [App](https://github.com/Motrish/RPi-Jukebox-RFID/blob/1995a5c21e1e41f33a5cc61c6a27a3f5c803f871/src/webapp/src/App.js), [Router](https://github.com/Motrish/RPi-Jukebox-RFID/blob/1995a5c21e1e41f33a5cc61c6a27a3f5c803f871/src/webapp/src/router.js), [Socketgrenze](https://github.com/Motrish/RPi-Jukebox-RFID/blob/1995a5c21e1e41f33a5cc61c6a27a3f5c803f871/src/webapp/src/sockets/index.js).

## Root-Freigabe für zwei aufeinanderfolgende Teilslices

Am 17.10.2026 freigegeben auf Integration afe41e50d016f6d0a3334b1cc4cdf64692582c36, Tree aa144756480c4cbf94f864ed4b6063eccf995788. U02b1 ändert ausschließlich App.js und die drei vorgeschlagenen neuen DesignPreview-Dateien; Theme/i18n zuerst auf Importeffekte lesen. App wählt den Preview-Boot vor den lazy Legacy-Imports. Ein ReactDOM-root, vorhandener Build, React17/MUI5, ein aktiver HashRouter; kein iframe oder neuer Transport. Unbekannte Preview-Unterpfade bleiben in der gerätefreien Vorschau.

U02b2 ergänzt anschließend genau tests/design-preview/react_smoke.py und die vorhandene .github/workflows/test_build_webapp_v3.yml. Der vollständige CI-Checkout baut und prüft die tatsächliche Reactansicht in Chromium. Der Harness darf den fertigen Build über einen nur lokal gebundenen stdlib-Testserver bereitstellen und muss dessen Lebenszyklus beenden. Keine WebSockets und keine Backend-/Hostrequests im Previewzweig; erlaubte lokale Build-/Übersetzungsassets ausdrücklich begrenzen. Legacyzweig mit gemocktem Transport auf Erhalt prüfen. Screenshots bei 390/768/1440, Überlauf320 und vorhandene funktionale Regressionen gehören zur Abnahme.

Da der lokale V3-Build nicht verfügbar ist, bleiben vollständige Screenshots normale CI-Artefakte. Für Roots tatsächliche Sichtprüfung darf der Harness optional genau einen auf höchstens 1 MB begrenzten Desktop-PNG-Screenshot als klar markiertes Base64-Logfeld ausgeben. Nur synthetische Vorschauinhalte; Standardausführung ohne Flag schreibt keine Bilddaten ins Log. Root liest das Log über den vorhandenen authentifizierten Connector und zeigt ausschließlich das dekodierte Bild an. Das benötigt weder Repo-Schreibrechte im Workflow noch einen weiteren Dienst. Browser-/Buildjobs bleiben ohne zusätzliche Schreibberechtigungen; bestehende Buildschritte bleiben erhalten.

Alle sechs ausführbaren Dateien schreibt Luna in zwei getrennten Phasen und Übergabelisten, keine zusätzlichen Dependencies/Lockfiles/Server im Produkt. Vollständige CI und unabhängiges Review des finalen SHAs sind vor Integration erforderlich. Neues Codingbudget standardmäßig ein Worker; kein automatischer Gerätenachweis und keine automatische Resume-Zusage.

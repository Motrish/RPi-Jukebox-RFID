# U02b – integrierte React-Designvorschau

Stand: 17.10.2026. Der gerätefreie React-Teilslice ist reviewed, integrated und für die unten genannten Nachweise verified. PR 11 wurde als `e61a63e4b1322f47c252aad281176ec618e77831` in `future3/modern-ui` gemerged. Der Integrationsbaum `4e72f86b0319b37a9e4c292a05ad6a57c9161480` entspricht exakt dem geprüften Head `6ccab3333dbd665f347bcc6a8621a911076d04a4`. `develop` blieb bei `42d5023e37dbf8de6477fef5ebcd6eae3cb5087d`.

## Verhalten und Grenzen

Der vorhandene React-Client öffnet die neue Oberfläche über `#/design-preview` und sieben Unterseiten. App.js wählt den Bootzweig vor dem Import der verbindenden Legacy-Gerätemodule. Ein ReactDOM-root, derselbe Build und genau ein aktiver HashRouter bleiben erhalten. Ein frischer Aufruf des bisherigen Einstiegs lädt weiterhin die bisherige Provider-/Routerstruktur.

Sidebar, Suche, großer violetter Hero, Cover und feste Playerleiste setzen die akzeptierte Bildreferenz im bestehenden Client um. Playerauswahl, Pause, Lautstärke, Queue, Suche und drei PiSugar-Anzeigezustände sind lokaler React-Demozustand. Die mobile Navigation wartet auf die sichtbare, eingeschobene Sidebar, fokussiert ihren aktiven Link und gibt den Fokus beim Schließen zurück. Unbekannte Preview-Unterpfade bleiben in der Vorschau.

Die sichtbaren Hinweise nennen Beispieldaten und fehlendes Audio. Es werden keine Gerätecontexts, Kommandos, MPD-, OAuth- oder PiSugar-Verbindungen aus der Vorschau importiert. Lokale Übersetzungs-/Buildassets sind erlaubt; sonstige HTTP- und sämtliche WebSocketversuche führen im Previewtest bis zur letzten Aktion zu Fehlern. Dies belegt weder Livewiedergabe noch einen Spotify- oder Zielgeräteanschluss. Gesamte U02-/Q02-Liveabnahme bleibt offen.

## Exakte Luna-Artefakte

Root veröffentlichte ausschließlich die folgenden sechs Dateien aus dem isolierten Teilstage `G:/Entwicklung/phoniebox-staging/u02-react`. Das Stage ist kein vollständiger Checkout. Alle finalen Remoteinhalte wurden identisch zurückgelesen; Quellreview und Reviewfolgen stehen in u02-react-review.md.

| Datei | Finaler roher Stage-SHA256 |
| --- | --- |
| src/webapp/src/App.js | 37d7c4766ed4902a1c12700af26a350220d2e20587e53729dcfa710d1b7df6ed |
| src/webapp/src/components/DesignPreview/index.js | 3078d43bb947f04c2f5fcd634512964732e71fb13aebd34c966d7cf5b1699e4e |
| src/webapp/src/components/DesignPreview/styles.css | 0fda7f1120a43c86bb0528ba307a3daba9733cb1e24ba83005010f7213deb332 |
| src/webapp/src/components/DesignPreview/previewModel.js | cd9df3733a8b61a7281cb120536ab6c1fd17e4ebbee7585f54493668f09102a7 |
| tests/design-preview/react_smoke.py | d6520dcf89903de8c08acdb6b9409d059af67cdb6c2bd3d75a41f73b529041ca |
| .github/workflows/test_build_webapp_v3.yml | 27667945363454e72e403c9ad9ae5bbb0a9cc3e1d7d3bd915a9d25c1dea71aa9 |

Root schrieb keine dieser ausführbaren Dateien. Der erste Quellcommit war `7a2ac0bde8eb5dbcd3e0be9c268b953cd06931ca` auf vollständiger Basis `afe41e50d016f6d0a3334b1cc4cdf64692582c36`. Folgende Korrekturen wurden jeweils von Luna verfasst, eingefroren, mechanisch veröffentlicht und unabhängig nachgeprüft.

## Vollständige Nachweise am finalen Head

- Web-/Chromiumlauf 39019221148: vollständiger vorhandener CRA-Build und alle sechs Browserprüfgruppen erfolgreich. Die Prüfung umfasst sieben Routen, unbekannte Unterpfade, Brandnavigation, Playererhalt, Queuefolge, Suche, drei Akkuanzeigen, mobiles Enter/Space/Escape/RFID-Wiederöffnen und Fokus, geschlossene Tabreihenfolge, 320px-Überlauf, Screenshots 390/768/1440, späte verbotene Anfrage, finale Netz-/Browserfehlerfreiheit sowie sauberen Kontext-/Browserabschluss.
- Der Legacytest rendert Router und bestehende Navigation mit vier lokal gehaltenen WebSocket-Mocks. Deren Frames werden lokal verworfen; `connect_to_server` wird nicht verwendet. Das ist kein Legacy-Gerätefunktionstest und keine simulierte gültige ZWS-Geräteantwort.
- Pythonläufe 39019221187 und 39019223912: jeweils alle fünf Versionen 3.9–3.13 plus finish erfolgreich.
- Lokaler V3-Flake8, Python-Syntax, CLI-Hilfe und Modell-JS-Syntax erfolgreich. Lokaler Stage wurde nicht als kompletter CRA-Build ausgegeben.
- Root hat den echten 1440px-React-Screenshot aus dem CI-Log angesehen und mit der Vorlage/akzeptierten statischen Shell verglichen. Der finale Screenshot ist byteidentisch mit diesem gesehenen Bild. Drei Screenshotgrößen liegen als CI-Artefakte vor; eine tatsächliche Sichtprüfung aller React-Mobilbilder wird nicht behauptet.

Der Harness stellt den vollständigen CI-Build nur an Loopback bereit. Browserstep: maximal drei Minuten, Buildjob: maximal zehn Minuten; zusätzliche Aktions-/Navigations- und Probegrenzen und geflushte Fortschrittsmarker erleichtern die Diagnose. Normale CLI-Aufrufe geben keine Bilddaten aus. Der optionale eindeutig markierte einzelne Desktop-PNG-Logeintrag bleibt unter 1 MB und enthält nur Demodaten. Der Workflow erhält keine zusätzlichen Repo-Schreibrechte oder Secrets.

## Frühere Befunde und Ressourcencheckpoint

Die unabhängigen P2 zum mobilen Fokus und zur fehlenden abschließenden Netzfehlerauswertung sind behoben. Die echte CI reproduzierte danach einen Fokusfehler während der CSS-Sichtbarkeitstransition. Eine lokale Chromium-Minimalprobe half bei der Diagnose; erst der anschließende echte Reactlauf bestätigte die Korrektur.

Der begrenzte Lauf 39018713268 bestand bereits alle Previewphasen, hing aber im Legacyboot. Das Ersetzen des sofort geschlossenen Mocks durch einen offenen lokalen Nachrichtensink führte im finalen Lauf zum vollständigen Erfolg. Eine genaue interne Reconnect-Ursache der gepinnten jszmq-Version wird daraus nicht behauptet. Root bestätigte an der tatsächlichen Basis jszmq 0.1.2 im Lockfile (Blob 218e67ab76bb891056844a2cba57a201f08886bc) sowie den sofort verbindenden Socketimport (Blob fedc57a05d8532195fddf8fdb3ac6f8e91f2c589).

Der frühere unbegrenzte Lauf 39018216900 wurde inzwischen tatsächlich beendet: Ein von Luna verfasster, unabhängig durch Root geprüfter Zweiminuten-Wartungsjob auf einem isolierten Branch prüfte zuerst den exakten alten Commit/Branch und forderte nur dessen Abbruch an. Lauf 39026680909 und Job117378929085 waren erfolgreich; die GitHub-API bestätigt completed/cancelled. Nur dieser Wartungsjob hatte actions:write, kein checkout oder contents:write; der Browserworkflow erhielt keine zusätzlichen Rechte. Der Wartungsworkflow wurde danach entfernt: Cleanupcommit 626b7722e8e799bdf20a5d7b26e39d67637d76a8 stellt exakt den ursprünglichen Tree 4e72f86b0319b37a9e4c292a05ad6a57c9161480 auf dem Wartungsbranch wieder her, ohne Produktmerge. Spätere Browserläufe bleiben hart begrenzt. Der Nutzer erlaubt inzwischen Root plus ein bis zwei unabhängige Worker bei Sparsamkeit; Code/Review desselben Slices bleibt seriell. Keine Timer-/Quota-Automation wird zugesagt.

Livecontroller, JavaScript-Konformitätsanschluss A02b, revisionsgebundene Storekommandos, Spotify auf ARMv6, Installer und PiSugar-Geräteintegration folgen separat. F01 und die offenen Zielgerätedaten bleiben bestehen.

Quellen: [PR 11](https://github.com/Motrish/RPi-Jukebox-RFID/pull/11), [Web-/Browserlauf](https://github.com/Motrish/RPi-Jukebox-RFID/actions/runs/39019221148), [Python Push](https://github.com/Motrish/RPi-Jukebox-RFID/actions/runs/39019221187), [Python PR](https://github.com/Motrish/RPi-Jukebox-RFID/actions/runs/39019223912).

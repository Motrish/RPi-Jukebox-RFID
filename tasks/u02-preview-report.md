# U02a – Isolierte Designvorschau

Stand: 17.10.2026

Die statische Designvorschau liegt als eigener Slice unter `G:/Entwicklung/phoniebox-staging/u02-preview`. Dieser Stage enthält nur die vier neuen Projektdateien und lokale Browser-Screenshots; er ist kein vollständiger Phoniebox-Checkout. Die angegebene Remote-Basis für die spätere mechanische Übernahme ist Commit `1995a5c21e1e41f33a5cc61c6a27a3f5c803f871`, Tree `e565397f5a125e8c8d13e6db51489912e1d2ecf6`.

Implementiert sind die semantische Einzeldatei-Vorschau, das responsive dunkle Layout mit violettem Lieblingsmix, sechs selbst gestalteten CSS-Covern, Quellenkennzeichnung, Suche samt Leerzustand und Reset, Navigations-Platzhalter, persistenter Vorschauplayer mit Queue und Lautstärkeregler sowie die drei PiSugar-Demozustände. Die Kennzeichnung `Designvorschau · Beispieldaten` bleibt sichtbar. Alle Interaktionen ändern nur Browserzustand. Es werden keine externen Ressourcen angefordert. Die geschlossene mobile Navigation ist für Sichtbarkeit und Tastaturfokus verborgen; ein funktionsloser Hero-Zähler ist entfernt.

Neue Projektdateien:

- `src/webapp/public/design-preview/index.html`
- `src/webapp/public/design-preview/styles.css`
- `src/webapp/public/design-preview/preview.js`
- `tests/design-preview/browser_smoke.py`

Der zuerst gemeldete Browser-PASS bezog sich auf die frühere Smoke-Skript-Version ohne den vollständigen Einstellungs-Navigations- und Tastaturfokustest. Die erweiterte Version deckte einen ungültigen Testablauf auf: Sie klickte nach Auswahl von RFID auf Einstellungen, obwohl das Menü dabei korrekt geschlossen wurde. Der Test öffnet das Menü nun erneut, bevor er Einstellungen auswählt. Zusätzlich prüft er, dass die geschlossene Sidebar bei Tab-Fokus unerreichbar bleibt. Der Fehler lag im Harness-Ablauf.

Der finale Stage-Browserlauf wurde mit Python Playwright 1.64.0 und Chromium durchgeführt. Verwendete Befehle:

```powershell
python -m http.server 8000 --bind 127.0.0.1
python tests\design-preview\browser_smoke.py --url http://127.0.0.1:8000/index.html --output-dir artifacts
```

Ergebnis: PASS. Geprüft wurden alle sieben Navigationseinträge, mobiles Menü samt Escape, Fokus-Rückgabe und Ausschluss der geschlossenen Sidebar vom Tab-Fokus, `/`-Suchkürzel, Filter/Leerzustand/Reset, lokale und Spotify-Quelltexte, Playerzustand über Navigation, Pause, Queue, Lautstärke, aktive/unbekannte/deaktivierte PiSugar-Anzeige, kein Prozentwert bei unbekanntem Zustand, fehlender Akkuindikator bei deaktiviertem PiSugar, Seitenbreiten ohne horizontalen Überlauf bei 320 px sowie keine Browserfehler oder externen Requests. Flake8 auf der Harness-Datei mit den Repository-Regeln: Exit 0.

Die tatsächlich angesehenen Chromium-Screenshots liegen lokal unter `phoniebox-staging/u02-preview/artifacts/`: `preview-320.png`, `preview-390.png`, `preview-768.png` und `preview-1440.png`. Das dunkle Seiten-/Navigationslayout, der violette Hero, die Coverreihen und der feste Player folgen der Hierarchie der bereitgestellten Referenz; Cover sind eigenständige geometrische Illustrationen.

Grenze des Slice: U02a ist bewusst keine React-/Router-/Backendintegration. Der CRA-Build, unabhängige Veröffentlichung und Review auf dem publizierten SHA stehen außerhalb dieses isolierten Vorschau-Arbeitsgangs und bleiben für die Gesamtaufgabe offen. Es gab keine Remote-Mutation.

## Root-Verifikation und Veröffentlichung

Am 17.10.2026 führte Root den eingefrorenen Browser-Smoke gegen einen separat gestarteten Loopback-Server auf Port 8872 vollständig erfolgreich aus. Die erste Wiederholung über den Serverhelper lieferte ERR_EMPTY_RESPONSE; das war kein erfolgreicher Produktnachweis. Mit eigenständigem python-http.server und bestätigter Startausgabe lief der komplette Harness mit Exit 0. Separates V3-Flake8 für browser_smoke.py sowie node --check für preview.js: jeweils Exit 0.

Root hat die finalen Screenshots preview-1440.png und preview-390.png unter artifacts/root-final tatsächlich angesehen. Dunkle Navigation, violette Mixfläche, Coverreihen und feste Playerleiste sind sichtbar an die Nutzerreferenz angelehnt. Mobile Darstellung nutzt zwei Coverspalten und einen kompakten Player; die alten funktionslosen Slidezahlen sind entfernt. Keine Behauptung einer identischen Kopie, eines Liveplayers oder einer bereits integrierten React-App.

Vier Luna-Dateien mechanisch veröffentlicht als aef2356b6bca4eb792bc8e2b00fd332e1d96cc81, Tree bd85046ab7ec22c246ee0dfb779deec0ed9419e6, Branch future3/feature-design-preview, Draft-PR 10. Alle vier Inhalte am SHA unverändert zurückgelesen. Unabhängiges Review und vollständiger bestehender Webbuild sind beim Schreiben dieses Checkpoints offen.

## Folgefixes nach Review `aef2356`

Vor Änderungen an den Vorschauartefakten wurden die neuen Regressionen gegen den weiterlaufenden Loopbackserver `http://127.0.0.1:8872/index.html` ausgeführt. Echte RED-Ergebnisse: Brand per Shift+Tab/Enter aus RFID und Einstellungen ließ Breadcrumb/Nav/Ansichtsflächen unverändert (bei beiden Fällen: „Brand link did not return“, Start nicht aktiv, Hero verborgen, Platzhalter sichtbar). Nach Auswahl von Leise Wellen zeigte die Queue Leise Wellen statt Kleiner Komet; Weiter stimmte damit nicht mit der sichtbaren ersten Queuezeile überein. Entsprechende Inkonsistenzen wurden nach Vor/Zurück erneut reproduziert. Die erste Regressionfassung hatte einen falschen Shift+Tab-Schritt für Einstellungen; der Fokuspfad wurde vor der aufgezeichneten RED-Ausführung korrigiert. Es wurden keine erzwungenen Klicks verwendet.

Geändert wurden ausschließlich die vier freigegebenen Dateien:

- `index.html`: Brand bleibt nativer `href`-Link, trägt `data-view="start"`; das Hero ist das `#start`-Ziel.
- `preview.js`: dieselbe `uniqueTracks`-Reihenfolge und `currentTrack` bestimmen die nächsten zwei Queueeinträge. Queue wird nach Coverwahl, Mixstart, Vor/Zurück und beim Öffnen neu erstellt; Texte werden über `textContent`/`replaceChildren` eingesetzt. Brand nutzt denselben `setView("start")`-Pfad wie die Navigation; die aktive Titelauswahl wird beibehalten. Akkuanzeige, Prozenttext und Balken nutzen denselben Beispielsatz 82; der Balken skaliert relativ zum inneren nutzbaren Füllraum.
- `styles.css`: Akkuinnenfüllung besitzt feste obere/untere Innenabstände und skaliert vom unteren Rand über den berechneten Beispielwert.
- `browser_smoke.py`: reale Tastatur-Regressionen für Brand aus RFID/Einstellungen, Queue-/Weiter-Abgleich für Auswahl/Vor/Zurück/Mixstart und Prozent-/Innenfüllkonsistenz ergänzt. Bestehende Browserprüfungen bleiben erhalten.

Nach Fix: Chromium-Smoke gegen denselben Server, Befehl `python -B tests\design-preview\browser_smoke.py --url http://127.0.0.1:8872/index.html --output-dir artifacts\author-fixed`, **PASS / Exit 0**. V3-Flake8 separat mit Repositoryparametern: **Exit 0**. `node --check src\webapp\public\design-preview\preview.js`: **Exit 0**. Die vier neuen Screenshots wurden unter `artifacts/author-fixed/preview-{320,390,768,1440}.png` erzeugt.

Root-Folgeprüfung nach den Reviewkorrekturen: vollständiger Browser-Smoke mit Ausgabe artifacts/root-fixed, separates V3-Flake8 und node --check jeweils Exit 0. Root hat den aktualisierten Mobil-Screenshot tatsächlich angesehen. Korrigierter Folgecommit 7820c608b7fb23df4a768c826d363b08abb4c96f, Tree aa144756480c4cbf94f864ed4b6063eccf995788; alle vier Dateien unverändert zurückgelesen. Folgereview und vollständige neue CI sind beim Schreiben noch offen.

Abschluss U02a: Folgereview7820c608 ohne offene Blocker. Webbuild39015928794 und vollständige Pythonmatrizen39015928795/39015932043 einschließlich finish erfolgreich. PR10 als afe41e50d016f6d0a3334b1cc4cdf64692582c36 integriert; Tree aa144756480c4cbf94f864ed4b6063eccf995788 entspricht exakt dem geprüften Head. Gesamt-U02 bleibt offen; nativer Reactanschluss ist der folgende separate Slice. Die lokale statische Vorschau läuft für Sichtprüfung auf Loopback8872.

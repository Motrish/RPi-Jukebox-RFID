# U02a – unabhängiges Review der Designvorschau

Stand: 17.10.2026. Geprüfter Commit `aef2356b6bca4eb792bc8e2b00fd332e1d96cc81`, Tree `bd85046ab7ec22c246ee0dfb779deec0ed9419e6`, Parent `1995a5c21e1e41f33a5cc61c6a27a3f5c803f871`. **Zwei funktionale P2-Befunde bleiben für diesen SHA offen.** Der vorhandene Browser-Smoke besteht, deckt diese beiden Aktionen jedoch nicht inhaltlich ab. Kein Backend-, Geräte- oder Sicherheitsblocker wurde im geprüften Slice gefunden.

## P2 – sichtbare Warteschlange folgt dem Vorschauplayer nicht

`index.html:130` enthält unveränderlich „Als Nächstes: Leise Wellen · Spotify; Kleiner Komet · Eigene Musik“. `preview.js:108–144` verändert bei Titelauswahl und Vor/Zurück nur aktuellen Track/Player; kein Pfad aktualisiert die Queueeinträge. Der Queuebutton blendet lediglich das vorhandene Panel ein.

Nach Auswahl von „Leise Wellen“ zeigt der Player diesen Titel, die Queue bezeichnet denselben Titel weiterhin als unmittelbar nächsten. Tatsächlich würde die implementierte nächste Aktion gemäß uniqueTracks/currentTrack zu „Kleiner Komet“ wechseln. Nach weiteren Titeln bleibt dieselbe Abweichung bestehen. Das ist innerhalb der ausdrücklich simulierten Vorschaufunktion widersprüchlich; dazu ist keine echte Backendqueue erforderlich. Entweder muss die Vorschauqueue aus derselben lokalen Reihenfolge abgeleitet werden oder ihr Text muss eindeutig als unveränderliche Beispielansicht statt tatsächlichem „Als Nächstes“ ausgewiesen sein. Autorregression: Track wählen, Vor/Zurück und Queueinhalt miteinander vergleichen. Der bestehende Smoke prüft nur Öffnen/Schließen des Panels.

## P2 – Brandlink kehrt aus Unteransichten nicht zu Start zurück

`index.html:16` bietet einen echten Link mit `aria-label="Phoniebox Start"` und `href="#start"`. Der Handler in `preview.js:177–182` führt Ansichtswechsel ausschließlich für Elemente mit data-view aus; der Brandlink trägt dieses Attribut nicht. Es gibt keinen hashchange-Handler. Die UI-Sektionen werden durch setView ein-/ausgeblendet und haben kein entsprechendes Start-Fragmentziel.

Aus RFID oder Einstellungen verändert der Brandlink somit lediglich den URLhash; Breadcrumb, aktive Navigation und sichtbare Platzhalteransicht bleiben auf der bisherigen Unteransicht. Das beschriftete Homeziel erfüllt seine Aktion nicht. Autorregression: aus RFID/Einstellungen den Brandlink per Tastatur aktivieren und tatsächliche Startansicht samt aktivem Navigationseintrag prüfen. Die sieben getesteten Navigationsbuttons ersetzen diesen Linktest nicht.

Beide Befunde wurden am veröffentlichten Quellfluss nachvollzogen; es wurde kein zusätzlicher Reproducer oder Testcode durch den Reviewer geschrieben. Die Korrektur kann vollständig innerhalb des bereits freigegebenen statischen Slice erfolgen. Dieses Review verlangt keine React-/Router-/Backendintegration.

## Remoteabgleich und ausgeführte Prüfung

Der vollständige Designvertrag `tasks/u01-design-spec.md` und `tasks/u02-preview-report.md` wurden gelesen. GitHub-Commitmetadaten bestätigen SHA, Tree und Parent. Alle vier veröffentlichten Dateien wurden am unveränderlichen SHA gelesen und gegen den eingefrorenen Stage verglichen. Nach UTF8-Dekodierung und CRLF→LF-Normalisierung stimmt der Inhalt jeweils exakt mit dem Remoteinhalt überein; unabhängig berechnete Git-Blobhashes:

| Datei | Blob |
| --- | --- |
| src/webapp/public/design-preview/index.html | 34a79d5fb9704439445473df04a043fec022748b |
| src/webapp/public/design-preview/styles.css | e91ac93386b115ccf15abf922f05f54a6e9850db |
| src/webapp/public/design-preview/preview.js | 6cfea2a681ae11e5b6b2a2b9d12e3a873b06e637 |
| tests/design-preview/browser_smoke.py | 7a282448c89f03812ecab1d5e627ed9ad5d580b7 |

Unabhängig ausgeführt gegen Roots bereits laufenden lokalen Server: `python -B tests/design-preview/browser_smoke.py --url http://127.0.0.1:8872/index.html --output-dir artifacts/review`. Ergebnis: **PASS, Exit 0**. Keine zweite Serverinstanz, kein externer Dienst und kein Gerätezugriff. Der vorhandene Harness erzeugte seine Screenshots unter `phoniebox-staging/u02-preview/artifacts/review`.

Der Lauf prüft reale Chromiuminteraktionen für die sieben Navigationsbuttons, mobile Menüöffnung/Schließen/Escape/Fokusrückgabe, Ausschluss der geschlossenen Sidebar vom Tabfokus, Suchleerzustand/Reset, Playerauswahl/Pause/Erhalt über Navigation, Queueöffnung, Lautstärkedemo und PiSugarzustände. Bei 320/390/768/1440 px wurde kein horizontaler Seitenüberlauf festgestellt. Keine abgefangenen Console-Errors, Page-Errors oder Requests an fremde Origins. Root meldet separat JS-Syntax und V3-Flake8 grün; diese beiden Checks wurden im Review nicht erneut ausgeführt. Die historischen Fehlversuche in der Übergabe werden durch diesen aktuellen PASS nicht getilgt.

## Sichtprüfung und Vorlagenbezug

Das tatsächliche `reference/template.webp` sowie alle vier Root-Screenshots `artifacts/root-final/preview-{320,390,768,1440}.png` wurden mit dem Bildwerkzeug angesehen. Desktop übernimmt nachvollziehbar die dunkle schmale linke Navigation, den ruhigen Kopf, die dominante violett/magentafarbene Mixfläche, quadratische Coverreihen und den festen unteren Player. Die selbst gestaltete Schallplatte ersetzt das Referenzfoto; Cover sind eigene geometrische Formen. Schrift, Rundungen, Seitenabstände und Phoniebox-Inhalte sind eine bewusst abgeleitete Gestaltung, keine Pixelreproduktion.

Bei 768 px wird die Navigation zur schmalen Iconleiste, Cover stehen dreispaltig. Bei 390/320 px erscheinen Menü, zweizeiliger Kopf mit Suche, zweispaltige Cover und kompakter fester Player. Die betrachteten Ausschnitte zeigen lesbaren Hero-/Quelltext; normaler Scrollbedarf bleibt. Kürzungen im kompakten Player sind vorhanden; ausführlichere Titelnamen bleiben in den Musikbuttons zugänglich. Ein vollständiger Accessibility-, Kontrast-, Zoom- oder Screenreader-Audit ist damit nicht belegt.

## Ehrlichkeit, Eingaben und Freigabegrenzen

Die Seite kennzeichnet Designvorschau/Beispieldaten sichtbar; der Player trägt „Beispiel · ohne Audio“. RFID und Einstellungen beschreiben ausdrücklich ihre fehlende Gerätewirkung. Musik/Spotify/Playlists verwenden bewusst dieselbe freigegebene gemeinsame Musikvorschau. Titelauswahl und Pausezustand bleiben bei Ansichtswechseln im vorhandenen DOM erhalten; Persistenz über Neuladen wird nicht behauptet.

Suchtext wird ausschließlich zum Vergleich mit lokalen Beispielstrings verwendet. Track-/Ansichtstexte werden über textContent, createTextNode und replaceChildren eingesetzt; kein innerHTML, eval, Remoteasset oder Backendrequest ist in diesem Slice enthalten. Native Buttons/Inputs, fokussierbare Navigation, sichtbare Fokusregeln und reduced-motion-CSS sind vorhanden. Die geschlossene mobile Sidebar ist visibility:hidden und im vorhandenen Browserlauf nicht per Tab erreichbar. Vollständige Modal-Fokusführung ist nicht geprüft und wird nicht als vorhanden behauptet.

PiSugar bekannt zeigt 82 Prozent ausdrücklich als Beispieldatum. Nicht erreichbar zeigt unbekannt, blendet den Prozentwert aus und setzt die große grafische Füllung zurück; deaktiviert entfernt den Kopfindikator. Kein Ladezustand, keine Energieaktion und keine tatsächliche Hardwaremessung werden ausgelöst. Diese Zustände belegen UIanzeige, keine B01-Geräteintegration.

Die vier public-/Harnessdateien bilden den freigegebenen isolierten U02a-Slice. Kein vorhandener Reactclient, Router, RPC, MPD, Audio-, OAuth- oder Installationspfad wird angebunden. Gesamt-U02 bleibt offen; lokale Browserprüfung ist kein vollständiger Checkout-/Webbuildnachweis. Root beurteilt die vollständige Web-CI separat. Nach Behebung der zwei P2-Befunde ist ein enges Folgecommitreview sinnvoll; keine zusätzliche Designkampagne ist erforderlich.

Quelle: [geprüfter Commit](https://github.com/Motrish/RPi-Jukebox-RFID/commit/aef2356b6bca4eb792bc8e2b00fd332e1d96cc81).

## Kleiner Konsistenzhinweis zum Akkubalken

`setBatteryMode("active")` setzt den sichtbaren Text auf 82 Prozent, die große Füllfläche aber hart auf CSS-height 72%. Das ist nicht automatisch ein sichtbar zu 72 Prozent gefüllter Akku: die absolute Prozenthöhe bezieht sich auf den Behälter, während bottom:5px, Rand und gedachte obere Innenluft die nutzbare Füllhöhe verändern. Beim Desktopbehälter mit 89px Außenhöhe und 3px Rand ergibt dies näherungsweise eine Füllung von 82 Prozent des innen nutzbaren Bereichs; beim kleineren mobilen Behälter verändert sich dieses Verhältnis. Deshalb kein weiterer gleichrangiger Blocker und keine Behauptung einer gemessenen sichtbaren 72-Prozentanzeige. Der Balken ist eine Akkuillustration zum Prozentwert; für eine eindeutige Darstellung sollte der Autor denselben Beispielwert auf einen konsistent definierten inneren Füllbereich anwenden. Reale Batteriemessung oder zusätzliche Hardwareanforderungen folgen daraus nicht.

## Abschluss des Folgereviews am Commit 7820c608

Geprüfter Folgecommit: `7820c608b7fb23df4a768c826d363b08abb4c96f`, Tree `aa144756480c4cbf94f864ed4b6063eccf995788`, direkter Parent `aef2356b6bca4eb792bc8e2b00fd332e1d96cc81`, PR 10. **Die beiden ursprünglichen P2-Befunde sowie der kleine Akkubalken-Konsistenzhinweis sind für diesen Folgecommit behoben. Im engen Folgereview bleiben keine Blocker offen.** Die früheren Befunde bleiben als Historie des alten SHA erhalten; dieser Abschluss bewertet ausschließlich den freigegebenen statischen U02a-Slice.

Der exakte Remotevergleich umfasst Änderungen nur an den gleichen vier freigegebenen Dateien. Alle vier veröffentlichten Blobs wurden gelesen und mit dem eingefrorenen Stage abgeglichen. Nach UTF8-Dekodierung und CRLF→LF-Normalisierung stimmen die Texte jeweils exakt überein; unabhängig errechnete Git-Blobhashes:

| Datei | Blob am Folgecommit |
| --- | --- |
| src/webapp/public/design-preview/index.html | 0b31b27a937ade077241a29cb97deb3d76555b00 |
| src/webapp/public/design-preview/styles.css | 44d9b22d1bd17238436a81984d20695408721750 |
| src/webapp/public/design-preview/preview.js | 96e552fc3236a8e892c41649a485a78fe59dc3c2 |
| tests/design-preview/browser_smoke.py | 1faf53551d0022e908f6d96900538c329cf68c92 |

Commitmetadaten bestätigen Parent und Tree. Der aktualisierte Übergabebericht wurde gelesen; seine RED-Beschreibung enthält die ursprünglichen Fehler und den zuvor korrigierten Tastaturtestpfad. Der Reviewer behauptet keinen eigenen RED-Lauf.

Brand bleibt ein nativer Link, erhält jetzt `data-view="start"` und nutzt damit denselben tatsächlichen setView-Pfad wie die Startnavigation. Das sichtbare Hero besitzt das reale Fragmentziel `id="start"`. Die vorhandenen neuen Regressionen erreichen den Link aus RFID und Einstellungen mit Shift+Tab und aktivieren ihn mit Enter. Sie prüfen Breadcrumb, aktiven Startbutton, sichtbares Hero, verschwundenen Platzhalter und unveränderte Titelauswahl. Damit ist der ursprüngliche wirkungslose Homepfad konkret abgedeckt.

Die nächsten zwei Queueeinträge entstehen jetzt aus derselben uniqueTracks/currentTrack-Reihenfolge wie Vor/Zurück. Nach Titelauswahl, Mixstart, Vor/Zurück und Öffnung wird die Queue aktualisiert. DOMtexte werden über createElement, textContent und replaceChildren eingesetzt; es entsteht kein neuer HTML-Interpretationspfad. Der erweiterte Harness prüft nach Leise Wellen den nächsten Titel Kleiner Komet, vergleicht die Queue mit tatsächlichem Weiter, kehrt zurück, vergleicht erneut und prüft anschließend Mixstart/Weiter. Die Quelle und der umlaufende Indexpfad sind im engen Diff konsistent; eine echte Backendqueue wird weiterhin nicht behauptet.

Akkuanzeige, Prozenttext, ARIAtext und Füllfaktor verwenden denselben Beispielwert 82. Der Füllbereich hat nun feste innere Abstände und skaliert mit scaleY(0.82) vom unteren Rand; die frühere Abhängigkeit einer hart codierten 72-Prozenthöhe von der Behältergeometrie entfällt. Unbekannt/deaktiviert setzen den Faktor auf null und behalten die vorhandene Text-/Sichtbarkeitslogik. Der Harness prüft Prozenttext und exakt denselben inneren Füllfaktor.

Unabhängig ausgeführt gegen den bereits laufenden Rootserver: `python -B tests/design-preview/browser_smoke.py --url http://127.0.0.1:8872/index.html --output-dir artifacts/review-fixed`. Ergebnis: **PASS, Exit 0** einschließlich neuer funktionaler Regressionen und aller bisherigen Browserprüfungen. Keine Console-/Page-Errors, fremden Requests oder horizontalen Seitenüberläufe in den geprüften Breiten gemeldet. Root meldet separat erfolgreiche Node-Syntaxprüfung und V3lint; diese wurden im Folgereview nicht erneut ausgeführt. Root-Screenshots unter artifacts/root-fixed bei 1440 und 390 px wurden tatsächlich angesehen; die bestehende Vorlagenhierarchie und der feste Player sind erhalten. Der lokale Harness erzeugte außerdem aktuelle Screenshots unter artifacts/review-fixed.

Ergebnis: fachlich kein offener Reviewblocker für diesen U02a-Folgecommit. Gesamt-U02, React-/Router-/Backendanschluss, tatsächliches Audio/OAuth/PiSugar und vollständiger Webbuild bleiben außerhalb dieses Abschlusses. Root liest die vollständige CI separat und entscheidet über Integration. Keine Code-, Test-, CI- oder Designänderung wurde durch den Reviewer vorgenommen; ergänzt wurde nur dieser Bericht, zusätzlich entstanden die vom vorhandenen Harness erzeugten lokalen Prüfbilder.

Quelle: [Folgecommit](https://github.com/Motrish/RPi-Jukebox-RFID/commit/7820c608b7fb23df4a768c826d363b08abb4c96f), [exakter Fixdiff](https://github.com/Motrish/RPi-Jukebox-RFID/compare/aef2356b6bca4eb792bc8e2b00fd332e1d96cc81...7820c608b7fb23df4a768c826d363b08abb4c96f).

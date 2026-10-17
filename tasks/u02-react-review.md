# U02b React-Anschluss – unabhängiges Review

Stand: 17.10.2026. PR 11, Head `38385382fb8a21077df1946762768196dd4a1930`, Tree `3ea6383c993b953f964354d93a3f194f4e1f9c2e`, Vergleichsbasis `afe41e50d016f6d0a3334b1cc4cdf64692582c36`. **Zwei P2-Befunde offen; keine Freigabe dieses SHA.** Vollständiger Build-/Browser-CI-Nachweis und tatsächliche React-Sichtprüfung sind beim Abschluss dieses Reviews offen und werden von Root separat bewertet.

## P2 – mobiles Menü verliert den bisherigen Tastatureinstieg

`src/webapp/src/components/DesignPreview/index.js:241–266`, außerdem `235–237`: Der Menübutton setzt nur menuOpen=true. Die Sidebar steht im DOM vor dem Button; beim Öffnen erfolgt weder Fokuswechsel in die Sidebar noch eine andere Anpassung der Tastaturreihenfolge. Der konkrete Pfad bei 390 px lautet: Menübutton per Tastatur fokussieren, Enter/Space zum Öffnen, danach Tab. Der Fokus bleibt zunächst auf dem Toggle und Tab führt weiter zur Suche/Restseite, statt in die gerade geöffneten Navigationslinks. Diese sind im DOM bereits passiert. Nach Linkauswahl schließt closeMenu ebenfalls ohne definierte Fokusrückgabe und kann den fokussierten Link verbergen.

Die akzeptierte statische Vorschau fokussierte beim Öffnen den aktiven Navigationslink und gab beim Schließen den Fokus an den Toggle zurück. Hier liegt eine funktionale Tastaturregression vor. Der neue Harness `react_smoke.py:235–253` prüft sichtbare Navigation, Escape-Rückgabe und geschlossene Tabunerreichbarkeit, aber keinen Tastatureinstieg in die geöffnete Sidebar. Korrektur und Autorregression: reales Öffnen über Enter/Space, Fokus im sichtbaren Menü, danach Linkauswahl und ein sinnvoller sichtbarer Fokus bei geschlossener Sidebar. Ein vollständiger neuer Modal-/Designumbau ist dafür nicht nötig.

## P2 – später Previewfehler kann trotz Netzwerkguard mit PASS enden

`tests/design-preview/react_smoke.py:290–315`: Die gesammelten Preview-WebSockets, blockierten HTTP-Requests, Console- und Page-Errors werden in 290–294 ausgewertet. Anschließend folgen weitere Energyinteraktionen, drei neue vollständige page.goto-Boots/Screenshots und die 320px-Phase. Deren Ereignisse werden weiter im selben Report gesammelt und unerlaubte Transporte zwar blockiert, aber vor endgültigem PASS nicht mehr ausgewertet.

Eine verbotene Aktivität oder ein Pageerror erst in einem dieser späteren Boots kann deshalb im PASS-Report stehen, solange die danach ausgeführten DOM-/Screenshotbedingungen noch erfüllt sind. Die Abnahme verlangt die Netz-/Fehlerfreiheit der gesamten Previewphase. Finale Assertions gehören nach deren letzten Schritt vor context.close. Die Autorregression soll einen ausschließlich späten verbotenen Request/WebSocket oder Pageerror sichtbar als FAIL nachweisen. Dies ist eine Nachweislücke, kein Nachweis, dass die vorliegende Produktansicht selbst Geräteverkehr auslöst.

Beide Befunde sind aus dem exakten Quellfluss abgeleitet. Der Reviewer hat keinen neuen Testcode/Reproducer verfasst und keinen gebauten Browserlauf vorgetäuscht. Root wurde vorab informiert und sieht eine serielle Luna-Korrekturrunde vor.

## Integrität und gelesene Quellen

Alle sechs Dateien wurden vollständig am Head gelesen. Der Remotevergleich enthält genau diese Pfade. UTF8-dekodierter Stageinhalt nach CRLF→LF-Normalisierung stimmt jeweils exakt mit dem Remotetext überein; unabhängig errechnete Git-Blobhashes:

| Datei | Blob |
| --- | --- |
| .github/workflows/test_build_webapp_v3.yml | 173af66527ce935a43ed3d6f181468f83e1b4127 |
| src/webapp/src/App.js | d819daecb69fd8c9013fea9d7b63c788dc13dc68 |
| src/webapp/src/components/DesignPreview/index.js | c830acc9eeb8d3afcc9d855f2cda640143910708 |
| src/webapp/src/components/DesignPreview/previewModel.js | e3d2ee01e5fb2dabbae8288e9a81375a75c952af |
| src/webapp/src/components/DesignPreview/styles.css | d6992b299a906342febe481b3bc69b8ec4aa13e5 |
| tests/design-preview/react_smoke.py | 5b6762b2278853c31c30b9b21d24594c098793c3 |

Commitmetadaten bestätigen den Tree; direkter Parent ist der erste Teilcommit 7a2ac0bde8eb5dbcd3e0be9c268b953cd06931ca, der Gesamtvergleich erfolgt gegen die oben genannte Integrationsbasis. Zusätzlich gelesen an dieser Basis: index.js `eb5d1f84e19d7f2a0a986d9ce4f26e23531b1766`, theme.js `b2704c66789377556bb824bcf4ac85062789bcea`, i18n.js `d374abae352135ad4fad1f4c6824fcd90548a31d`, router.js `e2b10a1e145e3c8c712429c77686fd3fcc4d7e81`, sockets/index.js `fedc57a05d8532195fddf8fdb3ac6f8e91f2c589` und alle drei unmittelbaren Contextprovider. Plan und Übergabebericht wurden gelesen.

## Nachvollziehbare Schutz- und Integrationsgrenzen

App.js entscheidet mit einem einmaligen useState-Initializer vor der Auswertung der lazy Legacyimporte über den Previewboot. Der Präfixvergleich trennt /design-preview und dessen Unterpfade von ähnlich benannten Legacyhashes. Preview benutzt ausschließlich seinen eigenen UI-/Modellgraphen; ein bloßer späterer Hashwechsel wechselt die Bootentscheidung nicht. Der vorhandene einzige ReactDOM-root, ThemeProvider und CssBaseline bleiben bestehen. Theme erzeugt nur MUIkonfiguration; i18n verwendet die bestehende lokale Übersetzungsladung. Der bekannte sofortige zmq.Sub-connect in sockets/index.js liegt hinter den vier lazy Legacygrenzen und wird vom Previewcode nicht importiert.

Legacyprovider-Reihenfolge und Routereinbindung sind im Diff erhalten; bestehende Routerseiten und Navigation werden nicht ersetzt. Der Legacy-Harnessteil beweist allerdings nur Router-/Navigationsmount und Erreichen eines gemockten Transports, keine funktionierende Geräteantwort oder vollständige Regression aller Legacyseiten. Der Mock schließt abgefangene WebSockets, ruft kein connect_to_server auf und lässt keine Geräteverbindung absichtlich durch. Seine Consolefehler werden gesondert protokolliert; deren Fehlen wird nicht behauptet.

Previewrouten bleiben innerhalb des HashRouter-basename /design-preview; unbekannte Unterpfade leiten intern zu Start. Track, Pause, Suche, Queue, Lautstärke und Akku liegen im Shellzustand und überstehen normale Routenwechsel. Queue und Vor/Zurück verwenden dieselbe lokale Reihenfolge. Texte werden als Reacttext ausgegeben, keine HTMLinterpretation und kein Backend-/MPD-/OAuthaufruf ist eingeführt. Beispieldaten-/Ohne-Audio-Hinweise und die drei Akkuanzeigen bleiben ehrlich. Styles sind unter .design-preview begrenzt, Fokus und reduzierte Bewegung sind vorhanden; daraus folgt kein vollständiger Accessibilityaudit. Die oben genannte Menüregression bleibt davon unberührt.

Der stdlib-Testserver bindet an 127.0.0.1 mit zufälligem Port und wird im Kontextabschluss beendet. HTTPguard begrenzt auf lokale Build-/Übersetzungsassets; WebSocketversuche werden vor Verbindung aufgezeichnet/geschlossen. Screenshots und optionaler markierter Base64-Desktoplog sind begrenzt; die Standard-CLI emittiert keine Bilddaten. Der Workflow behält den bestehenden Buildschritt, ergänzt die freigegebene Playwright/Chromium-Prüfung und sieben Tage Artefaktaufbewahrung. Keine Produktdependency-/Lockfileänderung, neuen Secrets oder zusätzlichen Workflow-Schreibrechte im Diff. Dies ist keine weitergehende Supply-Chain-Prüfung bestehender Actions.

## Ausführung und Abschlussgrenzen

Unabhängig lokal ausgeführt: `python -B tests/design-preview/react_smoke.py --help`, Exit 0. Kein vollständiger CRA-Build liegt im Teilstage vor; deshalb wurde der React-Browserharness hier nicht gegen einen Ersatz/Stub ausgeführt. Die frühere statische Vorschau ist kein Nachweis für diesen Reactbuild. Eine tatsächliche Sichtprüfung von Reactscreenshots wird noch nicht behauptet; Referenz und akzeptierte statische Screenshots wurden im vorherigen abgeschlossenen U02a-Review angesehen.

Nach Korrektur der zwei P2 sind ein exaktes Folgecommitreview sowie Roots vollständiger Build-/Browser-CI-Nachweis erforderlich. Livecontroller, A02b-Konformität, revisionsgebundene Kommandos, P04-/X-Transporthoheit und Hardwareabnahme bleiben offen. Es wurden nur dieser Prosa-Bericht geschrieben und vorhandene Quellen/CLI gelesen; keine Produkt-, Test-, Schema- oder CI-Datei verändert.

Quelle: [Head](https://github.com/Motrish/RPi-Jukebox-RFID/commit/38385382fb8a21077df1946762768196dd4a1930), [Gesamtdiff](https://github.com/Motrish/RPi-Jukebox-RFID/compare/afe41e50d016f6d0a3334b1cc4cdf64692582c36...38385382fb8a21077df1946762768196dd4a1930).

## Enges Folgereview am Commit 4fe22d62

Geprüfter Folgecommit `4fe22d62c89eb71d93a609d01310d46c0e8bbdf8`, Tree `74cfa7c8dd95c4bc1ba1475c681bf60d352b3ea6`, direkter Parent `38385382fb8a21077df1946762768196dd4a1930`. Der exakte Remotevergleich ändert ausschließlich DesignPreview/index.js und react_smoke.py. **Beide oben beschriebenen P2 sind im Quellfluss behoben; im gezielten Folgereview kein neuer Codeblocker. Die vollständige Browserabnahme dieses SHA bleibt ausdrücklich offen.** Die frühere Sperre/Befunde am alten SHA bleiben historisch erhalten.

| Datei | Remote-Blob / unabhängig bestätigter roher Stage-SHA256 |
| --- | --- |
| src/webapp/src/components/DesignPreview/index.js | 97ea3e83e4ec53c43f00f19e39b12d7c5b387a75 / 74132b38a09dbf138f61b1c782ec703c83e441016ccd661c4641fc758f9f678d |
| tests/design-preview/react_smoke.py | d57f133644a4cb7552bc5f2fa94c23b94d0576ff / 8053719b09bb11e176c720151f2e3458034f453be8973af56c9277ef78d51ead |

Beide veröffentlichten Dateien wurden erneut gelesen und gegen Stage abgeglichen: nach UTF8-Dekodierung und CRLF→LF-Normalisierung jeweils exakt identischer Text und Git-Blobhash. Die rohen Stage-SHA256 stimmen unabhängig mit Roots eingefrorenen Werten überein. Commitmetadaten bestätigen Parent und Tree. Der beim Lesen noch ältere Harness-Prüfwert 1738c107... war ein Zwischenstand; Root hat den Übergabebericht während dieses Abschlusses auf final 8053719b... korrigiert. Für dieses Review gelten ausschließlich die obigen unabhängig bestätigten Werte.

Die zusätzliche Menu-Effectfunktion fokussiert nach Öffnung den aktiven Navigationslink, ersatzweise den ersten. Damit liegt der Fokus im vor dem Toggle angeordneten Menü, statt beim nächsten Tab in den übrigen Seiteninhalt zu springen. closeMenu gibt beim Schließen/Linkklick den Fokus an den sichtbaren mobilen Toggle zurück; Desktop-Links werden nicht auf einen ausgeblendeten Toggle fokussiert. Der Toggle kann jetzt auch ausdrücklich schließen. Escape verwendet weiterhin seine definierte Rückgabe.

Die vorhandene ergänzte Regression öffnet tatsächlich per Enter, wartet auf den aktiven Linkfokus, schließt mit Escape, öffnet per Space, tabbt viermal bis RFID, aktiviert den Link und prüft nach Navigation die geschlossene Sidebar und den Togglefokus. Erneutes Öffnen muss RFID als aktiven Link fokussieren. Die Hilfsfunktionen warten auf Reactzustand und tatsächliche CSSverborgenheit; wait_for_function verwendet korrekt den Keywordparameter arg. Damit prüfen sie die angesprochene Tastaturfolge statt nur Sichtbarkeit nach einem Mausklick. Diese Tests wurden vom Reviewer nur gelesen, nicht als bereits bestanden ausgegeben.

assert_preview_clean bündelt HTTP-/WebSocket-/Console-/Pagefehlerprüfungen und wird zusätzlich erst nach den Screenshotboots, 320px-Prüfung und dem späten Selfcheck unmittelbar vor Preview-context.close aufgerufen. Damit kann die bislang ungeprüfte zweite Previewphase nicht allein wegen erfüllter DOMbedingungen PASS liefern. Der Selfcheck nutzt eine separate Seite mit separatem Fehlerreport, installiert denselben Requestguard, sendet erst am Ende einen same-origin /api/__u02_late_guard_probe, verlangt dessen Blockierung und Aufzeichnung und verlangt anschließend den spezifischen Assertionfehler derselben finalen Guardfunktion. Der Request wird durch die Playwrightroute abgebrochen, kein Backendhandler benötigt; der erwartete Probeeintrag verschmutzt nicht den regulären Produktreport. Andere Fehlerarten würden den Selfcheck nicht als passenden Erfolg passieren lassen. Ein tatsächlicher RED-Lauf vor dem Fix wird daraus nicht behauptet.

Unabhängig lokal erneut ausgeführt: `python -B tests/design-preview/react_smoke.py --help`, Exit 0. Root berichtet für den bisherigen CI-Lauf 39017135403 erfolgreichen CRA-Build und fehlgeschlagenen Chromiumtest am alten unmittelbaren Menüschließ-Assert. Das ist kein Browser-PASS; der neue vollständige CI-Lauf ist beim Abschluss dieses Folgereviews noch nicht bewertet. Lokaler Stage ist weiterhin kein Vollcheckout, deshalb kein Ersatzbrowserlauf gegen statische Vorschau/Stub und keine behauptete React-Screenshotabnahme. Root liest neue CI und tatsächliche Bilder separat am Checkpoint.

Ergebnis: Quellreview der beiden P2-Korrekturen abgeschlossen. Endfreigabe/Integration setzt weiterhin den vollständigen Build-/Browsernachweis des neuen SHA voraus. Kein zusätzlicher Architektur-/Designauftrag, keine Code-/Test-/CI-Datei durch den Reviewer verändert; ergänzt wurde ausschließlich dieser Bericht.

Quelle: [Folgecommit](https://github.com/Motrish/RPi-Jukebox-RFID/commit/4fe22d62c89eb71d93a609d01310d46c0e8bbdf8), [exakter Fixdiff](https://github.com/Motrish/RPi-Jukebox-RFID/compare/38385382fb8a21077df1946762768196dd4a1930...4fe22d62c89eb71d93a609d01310d46c0e8bbdf8).

## Begrenztes Fokus-Folgereview am Commit 82179282

Geprüft: `82179282b2c5fd201e8061914102f79a2ae0685f`, Tree `2d96f61924fae89359a3eaf3a7c3698d282a647e`, Parent `4fe22d62c89eb71d93a609d01310d46c0e8bbdf8`. Exakter Diff umfasst nur die zwei angekündigten Dateien. **Kein neuer Quellblocker in dieser kleinen Timing-/Diagnosekorrektur; die wirksame Behebung des realen Fokusfehlers ist bis neuer CI unbewiesen.** Die frühere Quellfreigabe ersetzt diesen ausstehenden Browsernachweis nicht.

| Datei | Remote-Blob / unabhängig bestätigter roher Stage-SHA256 |
| --- | --- |
| src/webapp/src/components/DesignPreview/index.js | 690282d2ce8a2aac9f0209ae76964590d9496c29 / b3709a38abaaa4dc665e838f13daf9ea72d1c39a0aaca9bf6c5accd0e080ae0c |
| tests/design-preview/react_smoke.py | 4e9bc05f276d0ea195e2b1315a28ec854d8450ac / 02320dd4095a07c9126a6ae361a7402df1b81d833bddeee1a3462ce278d111bd |

Beide vollständigen Remotetexte erneut zurückgelesen, nach UTF8-/CRLF-Normalisierung exakt mit Stage identisch; Git-Blobhashes und die eingefrorenen rohen SHA256 unabhängig bestätigt. Commitmetadaten bestätigen Tree und Parent.

Der Menu-Effect plant den vorhandenen aktiven-Link-/Erster-Link-Fokus nun in genau einem requestAnimationFrame. Cleanup storniert diesen Frame bei geändertem menuOpen oder Unmount; nach Schließen kann somit kein noch geplanter Fokus gegen die verborgene Sidebar nachlaufen. Kein Polling, Timerloop, Transport oder weiteres globales Ereignis wurde hinzugefügt. Das ist eine plausible Korrektur für Paint-/Sichtbarkeits-/native Aktivierungsreihenfolge, kein bewiesener Rootcause-Nachweis des CIfehlers.

Der Harness wartet weiterhin exakt auf document.activeElement===Ziel. Der neue Timeout beträgt ausdrücklich fünf Sekunden; bei dessen Überschreitung werden nur aktive/zielbezogene synthetische DOMinformationen, Sidebar-Klasse/-Sichtbarkeit und aria-expanded diagnostiziert und anschließend AssertionError ausgelöst. Es gibt weder Fallbackfokus aus dem Test noch tolerierte falsche Ziele. Sämtliche strikten Enter-/Escape-/Space-/Vier-Tab-/RFID-/Wiederöffnungs-/Rückgabe-/geschlossenen-Tabassertions sind unverändert enthalten. Auch tatsächliche CSSverborgenheit beim Schließen, finaler Netzwerkguard und dessen später Selfcheck wurden nicht abgeschwächt.

Root berichtet zum vorangegangenen Lauf 39017568156: vollständiger CRA-Build und Python erfolgreich, Chromium scheiterte am Fokus nach Space; vorheriger Enterfokus, Escape-Rückgabe und Space-aria-expanded=true waren erfolgreich. Diese Beobachtungen begrenzen die Hypothese, beweisen sie aber nicht. Der Reviewer hat keinen Browser-PASS oder einen selbst ausgeführten RED-Lauf behauptet. Lokal erneut nur bestehende CLI `python -B tests/design-preview/react_smoke.py --help` ausgeführt, Exit 0; Stage bleibt Teilcheckout.

Abschluss: gezielte Quellprüfung dieser zwei Änderungen ohne neuen Blocker beendet. Endnachweis bleibt der vollständige Browserlauf am neuen SHA samt tatsächlicher Sichtprüfung durch Root. Ausschließlich dieser Bericht wurde ergänzt.

Quelle: [Fokus-Folgecommit](https://github.com/Motrish/RPi-Jukebox-RFID/commit/82179282b2c5fd201e8061914102f79a2ae0685f), [enger Diff](https://github.com/Motrish/RPi-Jukebox-RFID/compare/4fe22d62c89eb71d93a609d01310d46c0e8bbdf8...82179282b2c5fd201e8061914102f79a2ae0685f).

## Ein-Datei-Sichtbarkeitskorrektur am Commit c30b0bfd

Geprüft: `c30b0bfdefa76eb41ce0966d8e4aefcee44f0160`, Tree `f6ae235691b9566c3489ee85aaf0b186c8f5362a`, Parent `82179282b2c5fd201e8061914102f79a2ae0685f`. Exakter Diff ändert nur DesignPreview/index.js. **Kein neuer Quellblocker in diesem begrenzten Fokus-Lifecyclefix; der tatsächliche React-Browsernachweis bleibt offen.**

Remote-Blob `41ef354026e795832ec1efa724da67c5460473e5` wurde zurückgelesen und mit Stage verglichen: exakt identischer UTF8-Text nach CRLF→LF-Normalisierung und unabhängig errechneter Git-Blobhash. Roher Stage-SHA256 stimmt mit dem Freeze überein: `3078d43bb947f04c2f5fcd634512964732e71fb13aebd34c966d7cf5b1699e4e`. Der lokale Harness hat unverändert `02320dd4095a07c9126a6ae361a7402df1b81d833bddeee1a3462ce278d111bd`; der Remotevergleich verändert ihn nicht. Commitmetadaten bestätigen Tree und Parent.

Der Menueffect in index.js:196–214 versucht den Fokus nun erst, wenn die vorhandene Sidebar computed visibility=visible und left>=0 erreicht. Solange sie noch verborgen/links eingeschoben ist, wird genau der nächste Animationframe eingeplant; die Variable frame hält dabei die zuletzt ausstehende ID. Cleanup bei Schließen oder Unmount storniert diesen letzten Frame. Nach erreichtem sichtbarem Zustand und vorhandenem aktiven/ersten Link wird einmal fokussiert und kein weiterer Frame geplant. Die Schleife läuft nur während dieses geöffneten Menu-Effects; es gibt keine zweite Schedulerinstanz, Geräteaktion oder CSSänderung. Bei dauerhaft nie erreichter Sichtbarkeit würde sie bis Schließen/Unmount weiter warten; im vorliegenden festen Sidebarlayout ist das kein zusätzlicher Freigabeblocker.

Die Korrektur behandelt konkret den zuvor möglichen still wirkungslosen focus-Aufruf im ersten noch verborgenen Frame. Die strikten Tastaturassertions, fünfsekündige Diagnose, finale Guards und später Selfcheck bleiben vollständig unverändert. Es wurde weder eine Assertion entfernt noch das Testziel durch einen erzwungenen Testfokus ersetzt.

Root berichtet für den vorangegangenen echten CI-Lauf 39017927905 erfolgreichen Spacepfad und RFIDnavigation, danach Timeout beim erneuten Öffnungsfokus: Toggle aktiv, aktiver RFIDlink vorhanden, aria-expanded=true und Sidebar nach fünf Sekunden sichtbar. Luna hat den still fehlschlagenden ersten focus bei derselben hidden→visible-CSSprimitive dreimal lokal in Chromium reproduziert. Diese Beobachtung stützt die engere Timingursache; die Primitive ist jedoch kein bestandener tatsächlicher Reactlauf und wird hier nicht so bezeichnet. Der Reviewer hat diesen Zusatzreproducer nicht selbst ausgeführt und keine neue Testdatei geschrieben.

Abschluss: Ein-Datei-Quellprüfung ohne neuen Blocker beendet. Root wartet den vollständigen neuen CI-/Sichtnachweis am exakten SHA ab; keine automatische Laufzeit-/Integrationsfreigabe. Nur dieser Bericht wurde ergänzt.

Quelle: [Sichtbarkeits-Folgecommit](https://github.com/Motrish/RPi-Jukebox-RFID/commit/c30b0bfdefa76eb41ce0966d8e4aefcee44f0160), [Ein-Datei-Diff](https://github.com/Motrish/RPi-Jukebox-RFID/compare/82179282b2c5fd201e8061914102f79a2ae0685f...c30b0bfdefa76eb41ce0966d8e4aefcee44f0160).

## QA-Zeitgrenzen und Phasenmarker am Commit 8964d087

Geprüft: `8964d087ebeba2bfd42cddf2dc90a54af97726e4`, Tree `77ad60e80124b2d774b14e34d13b66e3ae6cdc07`, Parent `c30b0bfdefa76eb41ce0966d8e4aefcee44f0160`. **Kein neuer Quellblocker in diesem reinen QA-Diff; kein Browser-PASS behauptet.** Remotevergleich enthält ausschließlich Harness und bestehenden Webworkflow. Beide Texte nach UTF8-/CRLF-Normalisierung exakt mit Stage identisch, Git-Blobs und rohe SHA256 unabhängig bestätigt:

| Datei | Remote-Blob / roher SHA256 |
| --- | --- |
| .github/workflows/test_build_webapp_v3.yml | 01b8c31e382d7f1f47435fad3def0ff3fc019041 / 27667945363454e72e403c9ad9ae5bbb0a9cc3e1d7d3bd915a9d25c1dea71aa9 |
| tests/design-preview/react_smoke.py | 887dd99ce937a9cb04d30d04a0c1af5c8cc131f8 / debd53ad3337472f0cea8671a20d969a97f40e999971eecba21edb50baa883e8 |

Produktdatei unverändert, lokal erneut bestätigt mit SHA256 3078d43bb947f04c2f5fcd634512964732e71fb13aebd34c966d7cf5b1699e4e. Commitmetadaten bestätigen Parent/Tree. Bestehende Tastatur-, Struktur-, Queue-, Akku- und finale Netzwerk-/Fehlerassertions werden nicht entfernt oder abgeschwächt. HTTP-Allowlist und sämtliche WebSocketguards/Mocks bleiben unverändert; kein neuer Backendpfad ist erlaubt.

Phasenmarker verwenden flush=True und der Workflow startet Python zusätzlich mit -u. Marker liegen vor/nach den wesentlichen Preview-/Legacyphasen sowie nach Screenshots und Abschlüssen. Haupt- und Legacypage erhalten 15 Sekunden Aktions-/Navigationstimeout. Die separate Probe-Page erhält diesen Pageoverride nicht; sie bleibt durch die Gesamt-CI-Frist begrenzt. Die späte fetch-Probe liefert durch Promise.race nach fünf Sekunden allenfalls timeout; require akzeptiert weiterhin ausschließlich blocked. Timeout ist somit Fehler, kein alternativer Erfolg. Promise.race unterbricht den eigentlichen fetch oder einen vollständig blockierten Browserthread nicht; genau deshalb ist die äußere CI-Zeitgrenze weiterhin nötig.

Chromiumstep ist auf drei Minuten, der gesamte Buildjob auf zehn Minuten begrenzt. Das begrenzt einen weiteren Hänger, ohne ihn als bestandene Abnahme umzudeuten. Keine zusätzliche Berechtigung, Dependency oder Produktänderung. Der frühere Close-Mock bleibt unverändert; es wird keine unbelegte Reconnectursache für den Hänger erfunden.

Root berichtet zum alten Lauf 39018216900 mehr als sechs Minuten ohne Abschluss seit Chromiumstart und nicht verfügbare Logs (BlobNotFound/404). Das klärt die Hängerursache nicht; kein Abbruch dieses alten Laufs wurde durch den Reviewer versucht oder behauptet. Der nächste begrenzte CI-Lauf muss zunächst die erreichte Phase und den tatsächlichen Ausgang belegen. Lokal nur bestehende CLI --help erneut ausgeführt, Exit 0. Ausschließlich diesen Bericht ergänzt.

Quelle: [QA-Folgecommit](https://github.com/Motrish/RPi-Jukebox-RFID/commit/8964d087ebeba2bfd42cddf2dc90a54af97726e4), [QA-Diff](https://github.com/Motrish/RPi-Jukebox-RFID/compare/c30b0bfdefa76eb41ce0966d8e4aefcee44f0160...8964d087ebeba2bfd42cddf2dc90a54af97726e4).

## Harness-only Legacy-Mock am Commit 6ccab333

Geprüft: `6ccab3333dbd665f347bcc6a8621a911076d04a4`, Tree `4e72f86b0319b37a9e4c292a05ad6a57c9161480`, Parent `8964d087ebeba2bfd42cddf2dc90a54af97726e4`. **Kein neuer Quellblocker im engen Harnessdiff; vollständiger Legacy-/CI-Erfolg bleibt offen.** Genau react_smoke.py geändert, keine Produkt-/Workflowdatei.

Remote-Blob `a6919d6e114eba958373c23c6b94d05fb7022b17` vollständig zurückgelesen, UTF8-/CRLF-normalisierter Text exakt Stage-identisch; Git-Blobhash unabhängig bestätigt. Roher Stage-SHA256: `d6520dcf89903de8c08acdb6b9409d059af67cdb6c2bd3d75a41f73b529041ca`, entspricht dem endgültigen Freeze. Frühere Handoffwerte gelten nicht. Commitmetadaten bestätigen Tree/Parent.

Der abgefangene Legacy-WebSocket wird nun offengehalten und erhält ausschließlich einen lokalen on_message-Handler, der Clientframes zählt und verwirft. Kein connect_to_server, Weiterleiten oder synthetischer Backend-Erfolg wird hinzugefügt. Alle WebSockets bleiben von derselben bereits installierten Playwright-Route erfasst; HTTP-Allowlist/Blockierungen unverändert. Kontext-/Browserabschluss und die bestehende Drei-Minuten-CI-Frist begrenzen weiterhin die Lebensdauer. Der Diff fügt zusätzliche Phasenmarker ein und bestätigt das Erreichen des Mocks früher; er entfernt keine bisherigen Router-/Navigations-/NoPreview-/Mockreached-/HTTP-/Pageerrorassertions. Kein unbegründetes Socketzahllimit ist im veröffentlichten Diff enthalten. Der Framezähler dient dem lokalen Handlerzustand; daraus wird keine beantwortete RPC oder funktionierende Gerätekommunikation abgeleitet.

Root berichtet für den begrenzten Lauf 39018713268: tatsächliche komplette Previewphase bestanden und echter Desktop-PNG angesehen (698104 Base64zeichen); danach letzter Marker „legacy mocked-transport boot started“ bis zum Drei-Minuten-Timeout. Dies ist ein Previewnachweis dieses früheren Laufs, kein vollständiger CI-PASS. Die Änderung des bisherigen sofortigen Close-Mocks ist eine begründete Testtopologie-Hypothese; eine Close-/Reconnectursache in der exakten jszmq-Implementierung ist nicht bewiesen. Der bekannte Lockstand jszmq 0.1.2 und sockets-Importbefund werden durch diesen Harnessdiff nicht verändert. Die von Luna berichtete Chromiumprimitive mit offenem Mock und lokal verworfenem Clientframe ist kein voller Clientnachweis und wurde hier nicht selbst ausgeführt.

Abschluss: Harness-Quellprüfung ohne Abschwächung der vorhandenen Abnahmebedingungen beendet. Root wartet neuen begrenzten CI-Ausgang und Legacystrukturprüfung ab. Kein Produktcode, neue Tests oder weitere Geräte-/Backendaktionen durch den Reviewer; nur dieser Bericht ergänzt. Der separat noch laufende alte Job wurde nicht verändert oder abgebrochen.

Quelle: [Harness-Folgecommit](https://github.com/Motrish/RPi-Jukebox-RFID/commit/6ccab3333dbd665f347bcc6a8621a911076d04a4), [Ein-Datei-Diff](https://github.com/Motrish/RPi-Jukebox-RFID/compare/8964d087ebeba2bfd42cddf2dc90a54af97726e4...6ccab3333dbd665f347bcc6a8621a911076d04a4).

## Root-Integrationscheckpoint U02b

Root meldet PR 11 integriert als `e61a63e4b1322f47c252aad281176ec618e77831`, Tree `4e72f86b0319b37a9e4c292a05ad6a57c9161480`. Vollständiger Web-/Chromiumlauf 39019221148 sowie beide Pythonmatrizen 39019221187/39019223912 erfolgreich (je fünf Jobs plus finish). Root hat den echten 1440px-React-PNG angesehen. Damit sind die zuvor offenen vollständigen CI-/Sichtnachweise laut Roots Checkpoint erbracht; die Fehlversuche und SHA-bezogenen Quellbefunde bleiben historisch erhalten. Der Reviewer hat diese CI-Läufe nicht selbst erneut abgefragt und behauptet weiterhin keine Hardware-/Livecontrollerfreigabe.

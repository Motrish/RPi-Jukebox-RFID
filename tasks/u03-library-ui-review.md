# U03a2 – unabhängiges Schnittstellenreview

Stand: Phase 0, 17. Oktober 2026. Geprüft wurden ausschließlich der U03a2-Plan sowie der festgelegte Baseline-APIserver und der bestehende DesignPreview-Index im Teilstage. Keine veränderlichen Test-, Harness-, Workflow- oder Produktdateien wurden geprüft oder ausgeführt.

Im geprüften Plan ist kein konkreter Blocker, P1- oder P2-Befund nachgewiesen. Die beschriebenen Schnittstellen lassen sich innerhalb der sieben freigegebenen ausführbaren Pfade umsetzen.

Der feste äußere Testursprung und der APIursprung sind verschiedene Authorities. Der Baseline-APIserver verlangt genau einen Host entsprechend seiner eigenen Authority; ein vorhandener Origin muss ebenfalls seinem eigenen Ursprung entsprechen. Die geplante Reihenfolge – äußere Host-/Originwerte zuerst prüfen, anschließend auf feste Backendwerte umschreiben – passt dazu. Ein bloßes ungeprüftes Umschreiben wäre kein gleichwertiger Nachweis. Das bleibt im eingefrorenen Harness konkret zu prüfen.

Der vorhandene HashRouter mit basename /design-preview erlaubt eine zusätzliche interne Route /library neben den sieben bisherigen Ansichten. Die Navigation gruppiert die bestehenden Einträge derzeit über slice(0, 5) und slice(5); beim Ergänzen muss die Gruppengrenze passend mitgeführt werden. Das ist innerhalb des erlaubten Indexpfads lösbar und kein Planblocker. Die echte Bibliothekskomponente muss an die eigene Route gebunden bleiben, damit ihr Unmount den Zugangszustand tatsächlich beendet; ein dauerhaft montierter versteckter Bereich würde diese zugesagte Lebensdauer nicht erfüllen.

Der geplante 43-Zeichen-Code passt zum API-Bearerformat. Der APIserver kann die Berechtigung auch unmittelbar vor der Antwort erneut verwerfen; der vorgesehene 401-Pfad muss deshalb Daten und Zugang auch nach zuvor erfolgreichen Seitenabrufen löschen. Abort allein garantiert nicht, dass ein bereits aufgelöstes Promise keine Daten mehr setzt. Der zusätzlich verlangte Generationsschutz und die Tests für späte Antworten, neuen Code, Vergessen und Unmount decken diese Grenze auf Planebene ab. Ob sämtliche Zustandsänderungen und Timer diesen Schutz einhalten, ist erst im eingefrorenen Quellstand prüfbar.

Phase 1 kann einen aussagekräftigen RED am fehlenden Produktmodul liefern, während der vorherige Build weiterhin funktioniert: Die neuen Module bleiben abwesend und der unveränderte Index importiert sie noch nicht. Dazu muss der gezielte Jestlauf die neue Testdatei tatsächlich auswählen und wegen des fehlenden Moduls scheitern. Ein anders verursachter CIfehler wäre kein solcher Nachweis. Vor dem Freeze wurde keine entsprechende Ausführung behauptet oder geprüft.

Der geplante Linux-Browserpfad mit echten Temporärdateien, LibraryCatalog, make_server und make_read_authorizer kann den relativen Browserrequest über dieselbe äußere Origin bis zum echten Katalog belegen. Kontrollierte Fehlerfälle bleiben gesonderte Fixtures. Diese Prüfung belegt weder einen bereits vorhandenen nginxanschluss noch Produktion, LAN, HTTPS, Gerätebetrieb oder ARMv6; der Plan grenzt diese Aussagen ausdrücklich und widerspruchsfrei aus.

Offen für das anschließende serielle Review sind die exakten eingefrorenen Test-/Workflowdateien, der tatsächliche RED-Nachweis und danach die Produktimplementierung mit GREEN- und Browsernachweisen. Die Prüfung hier bestätigt ausschließlich die begrenzte Machbarkeit des beschriebenen Plans gegenüber den gelesenen Baselines.

## Phase 1 – eingefrorene Tests, Harness und Workflow

Geprüfter Stand: f204a478861462464e1d220b0c0d19b638350786, Tree f72eb1cd078650e28449cd83dcdaf11288e0bb14, PR 16. Grundlage sind das exakte Dreidateien-Diffpaket, der Plan und der Autorenbericht. Ergänzend wurden nur die relevante A02-Identifiergrenze, Katalogregistrierung/-sortierung und der vollständige eingefrorene Workflow gelesen. Root hat die kanonische Paketlage unabhängig bestätigt. Keine Ausführung und keine Änderung ausführbarer Dateien durch den Reviewer.

Spezifikationsurteil: noch nicht erfüllt. Qualitätsurteil: Änderungen erforderlich. Die zwei P1 verhindern einen belastbaren späteren GREEN-Browserlauf; die P2 betreffen ausdrücklich vereinbarte Verhaltensnachweise. Vor Produktimplementierung sollte Luna diese begrenzten Test-/Harnesslücken beheben, erneut einfrieren und der tatsächliche Build-vor-Jest-RED separat belegt werden.

### P1 – falsche Pythonimportgrenze verhindert den echten Browserpfad

In library_smoke.py, catalog_fixture, wird src/jukebox in sys.path aufgenommen, danach aber jukebox.components.library_catalog beziehungsweise jukebox.components.library_api importiert. Die kanonischen Pakete liegen unter src/jukebox/components; src/jukebox/jukebox enthält das getrennte jukebox-Paket einschließlich contracts. Damit existiert der angeforderte jukebox.components-Pfad auch im vollständigen Checkout nicht. Root hat diese Lage gegenüber dem Repository bestätigt. Der Harness scheitert vor Serverstart am Import und kann den angekündigten echten Katalogpfad nicht beweisen. Minimale Korrektur: die vorhandene Paketgrenze entsprechend den APItests verwenden; keine Produkt- oder APIänderung.

### P1 – strikte und zufallsabhängige Locator verhindern zuverlässiges Paging

In library_smoke.py, run_browser, verlangt get_by_text("Vorhanden", exact=True).wait_for() einen einzelnen Treffer. Die erste Seite enthält 20 Einträge, davon mindestens 19 AVAILABLE; eine korrekte Ansicht produziert somit eine Playwright-Strictnessverletzung. Nach Zurück wird außerdem get_by_text("same.mp3", exact=True).wait_for() verwendet. LibraryCatalog vergibt UUIDbasierte IDs und sortiert nach library_id, nicht nach Registrierung oder Name. Auf Seite 1 können daher null, ein oder zwei same.mp3 liegen; sowohl null als auch zwei sind korrekte Katalogergebnisse, die diesen Wait scheitern lassen. Auch die bloße Sichtbarkeit von "Seite 2" garantiert noch nicht, dass die neue Antwort bereits als Zeilen gerendert ist; die anschließenden synchronen count-Aufrufe können den Ladezwischenstand lesen.

Minimale Korrektur: die von register_file zurückgegebenen IDs behalten, daraus die tatsächlichen Seiten erwarten und mit mehrtreffertauglichen, bis zum fertigen Zeilenbestand wartenden Assertions prüfen. Das behebt die zufällige Annahme und belegt zugleich die im Plan geforderte Unterscheidung gleicher Titel durch ihre echten IDs. Der bisherige generische lib_-Zähler beweist diese Zuordnung nicht.

### P2 – Timeout und Schutz nach Berechtigungsverlust bleiben ungetestet

Die zehn Jesttests enthalten keinen Zeitablauf, keine Fake-Timer-/Deadlineassertion und keinen Nachweis, dass ein erledigter oder verworfener Request seinen 10s-Timer räumt. Der Unmounttest prüft nur signal.aborted bei einem niemals aufgelösten Promise. Der Vergessentest läuft nach bereits fertiger Antwort. Der einzige späte Antworttest behandelt einen neueren Refresh, aber weder einen ausstehenden Request nach Vergessen noch einen neuen Code nach Berechtigungsverlust. Eine Implementierung ohne Timeout oder mit wiederauftauchenden Daten nach Vergessen könnte diese Tests erfüllen.

Minimale Ergänzung: gezielte Tests für den 10s-Abbruch samt sicherem Zustand und Timercleanup sowie für eine trotz Abort noch aufgelöste alte Antwort nach Vergessen und nach erneuter Codefreigabe. Der bestehende Refresh-Racetest kann erhalten bleiben; eine breite neue Testmatrix ist dafür nicht nötig.

### P2 – kombinierte ungültige Antwort maskiert fehlende Validatoren

Der einzige ungültige Erfolgsbody des echten Clients enthält zugleich ein unerlaubtes Listenfeld und doppelte IDs. Ein Client, der ausschließlich privateDebug als Extrafeld zurückweist, besteht den Test auch ohne Duplikatprüfung. Unsichere IDs, widersprüchlicher nextCursor, ungültige Zeilenform und fehlgeschlagenes JSONparsing werden gar nicht unabhängig geprüft; der tatsächliche Client erhält außerdem keinen gültigen UNKNOWN-Fall. Das sind die im Plan ausdrücklich genannten geschlossenen Antwortgrenzen.

Minimale Korrektur: bestehende Clienttests so aufteilen beziehungsweise gezielt ergänzen, dass die genannten voneinander unabhängigen Ablehnungsregeln jeweils allein den Fehler verursachen; ein gültiger UNKNOWN-Datensatz bleibt erfolgreich. Die vorhandenen kurzen lib_-Testwerte sind mit der gelesenen A02-Grammatik [A-Za-z0-9_-]{1,128} kompatibel. Eine Verschärfung auf die heutige UUIDform wäre durch diesen Vertrag nicht gedeckt.

### P2 – wesentliche vereinbarte Browserzustände fehlen

run_browser prüft den echten Erfolgspfad, Paging und Zugangsdatenverlust durch Routewechsel/Reload. Es gibt keinen kontrollierten Browserfall für 401 mit bereits sichtbaren Daten, 503, leeren Katalog, fehlerhaften Erfolgsbody, sichtbares Laden oder späte alte Antwort nach Vergessen; Vergessen selbst wird im Browser nicht betätigt. Diese Fälle sind im Plan ausdrücklich Teil der Chromiumabnahme und werden durch isolierte Componenttests nicht vollständig ersetzt. Der Überlaufdurchlauf lässt zudem die vereinbarten 1024px aus.

Minimale Ergänzung: die ausdrücklich erlaubten kontrollierten Fetch-/Fixturefälle als solche kennzeichnen und nach dem unverändert echten Erfolgs-/Pagingpfad prüfen; 401 muss sichtbare alte Daten und den Code entfernen und eine danach freigegebene alte Antwort darf nichts zurückbringen. Erwartete HTTPfehler dürfen dabei nicht als unerwartete JSausnahme gezählt werden. Bei Fehlersimulation über den Backendpfad ist zusätzlich zu beachten: forward_api fasst auch urllib.error.HTTPError unter Exception und ersetzt jede echte 401/503 durch 502. Soll dieser Weg den Status prüfen, muss er den Backendfehlerstatus samt begrenztem Body weiterreichen; reine Fetchkontrolle ist laut Plan ebenfalls zulässig.

### P2 – Netzwerkverbot erfasst WebSockets nicht

network_guard prüft geroutete HTTPrequests. Ein WebSocket wird darüber nicht verlässlich abgefangen oder als verboten protokolliert; es gibt keinen eigenen WebSocketbeobachter. Die Assetentscheidung berücksichtigt außerdem keine Requestmethode. Damit ist die berichtete GET-only-/keine-Sockets-Eigenschaft stärker als die tatsächlich geprüfte Grenze. Minimale Korrektur: jeden Socketversuch ausdrücklich scheitern lassen und auch erlaubte Assets auf die beabsichtigte Methode begrenzen. Die feste Host-/Originprüfung vor dem Backendrewrite und das Relay genau des browsergelieferten Authorizationwerts sind dagegen im vorliegenden Diff richtig angelegt; es wird kein Zugangscode in den Request injiziert.

### P2 – explizites Browsercleanup liegt nur im Erfolgspfad

context.close() und browser.close() stehen am Ende von run_browser hinter allen Assertions. Ein früh scheiternder Locator oder eine fehlgeschlagene Assertion überspringt beide Aufrufe; dies erfüllt das im Plan verlangte finally-Cleanup für Browser und Kontext nicht. Servercleanup ist beim regulär zurückgegebenen Fixture über die vorhandenen Kontextmanager/finally-Pfade angelegt. Minimale Korrektur: die explizite Browser-/Kontextfreigabe auch im Fehlerpfad sicherstellen, ohne zusätzliche Listener oder HTTPkontrollrouten.

Der Workflow ergänzt den gezielten Jestlauf nach dem Build und erhält die alten Prüfschritte im Diff. Der fehlende Modulimport ist ein geeigneter beabsichtigter RED-Grund; der tatsächlich beobachtete Remote-RED war zum Reviewzeitpunkt noch nicht Teil des Pakets. Root meldet V3lint und Inhaltsreadback als bestanden; der Reviewer hat diese Befunde nicht erneut ausgeführt. Dieses Review behauptet weiterhin keinen nginx-, Produktions-, LAN-, ARM- oder Gerätenachweis.

Nachgereichter Rootnachweis: Weblauf 39035764388, Job 117405105177 hat Build Web App erfolgreich abgeschlossen; der anschließende gezielte Jestlauf scheiterte mit Cannot find module './libraryClient'. Damit ist der geplante Build-vor-Jest-RED für diesen Head belegt. Er hebt die oben festgestellten Harnessblocker und fehlenden Verhaltensnachweise nicht auf. Nach den ausschließlich von Luna vorgenommenen Testkorrekturen sind erneuter Freeze und Readback sowie der RED des dann aktuellen Heads erforderlich.

## Phase 1 – Korrekturrunde 1, serielles Rereview

Geprüft wurde ausschließlich das eingefrorene Korrekturdiff f204a478861462464e1d220b0c0d19b638350786 → 1938d2a654002c69c355b34488ad851175e61b19, Tree 9df3aa64ce1c5aef927a77e1408f627949017af0, zusammen mit dem aktualisierten Autorenbericht und den bereits gelesenen relevanten Vertragsgrenzen. Root bestätigt V3lint und identischen Remoteinhalt der drei Dateien. Keine ausführbaren Änderungen oder Probes durch den Reviewer. Der aktuelle Build-vor-Jest-RED ist noch offen; der ältere Nachweis wird nicht auf diesen Head übertragen.

| Bisheriger Befund | Urteil zum Korrekturdiff | Begründung |
| --- | --- | --- |
| P1 Pythonimportgrenze | ADDRESSED | Imports verwenden nun components.library_catalog und components.library_api unter dem vorhandenen Sourcepfad. |
| P1 strikte/zufällige Paginglocator | ADDRESSED | Der Harness wartet mit einer mehrtreffertauglichen Textlistenassertion auf die exakten erwarteten Seiten-IDs; die mehrdeutigen Einzel-Waits entfallen. |
| P2 Timeout und Berechtigungsverlustrace | ADDRESSED | Neue Jestfälle prüfen den 10s-Abbruch mit Abortreaktion, sicheren Fehler und leere Timerliste, Timercleanup nach Erfolg sowie eine alte Antwort nach Vergessen und erneuter Freigabe. |
| P2 maskierte Antwortvalidatoren | ADDRESSED | Duplikat, unsichere ID, Cursorwiderspruch, Zeilenform und Listenextrafeld werden einzeln abgelehnt; ungültiges JSON und gültiges UNKNOWN sind ergänzt. |
| P2 fehlende Browserzustände/1024 | ADDRESSED | Gekennzeichnete kontrollierte Fälle für Laden, Leer, 401 nach Daten, 404, 503, fehlerhaftes JSON und alte Antwort nach Vergessen/Freigabe sind hinzugefügt; 1024px wird geprüft. Die neue Helpervertragsverletzung steht gesondert unten. |
| P2 Netzwerk-/Socketgrenze | ADDRESSED | HTTPfreigabe verlangt GET und bekannte Assets beziehungsweise die feste APIroute; eigene WebSocketroute weist Socketversuche zurück und erfasst sie. |
| P2 Browsercleanup | ADDRESSED | Seiten schließen in finally; Kontext und Browser schließen über verschachteltes finally auch bei fehlgeschlagenen Assertions. |

Die kontrollierte UUIDvergabe ersetzt keinen Katalog und keine API: Nur der UUIDgenerator während echter Dateiregistrierungen ist gepatcht. Die registrierten IDs werden behalten, das Ergebnis von LibraryCatalog.list_media wird gegen diese erwartete Reihenfolge geprüft, und der echte Browserpfad vergleicht seine sichtbaren IDs mit den beiden echten Katalogseiten. Dateifingerprints, entfernte Datei, Katalogspeicher, APIserver, Authorizer und der browsergelieferte Authorizationwert bleiben im echten Pfad. Der Patch ist vor Serverstart beendet. Damit bleiben reale Dateiidentität und die geforderte Browser/API/Kataloggrenze erhalten; die frühere zufällige Sortierungsannahme entfällt. HTTPError wird jetzt mit seinem tatsächlichen Status und begrenztem Body weitergereicht.

### Neuer P2 – kontrollierter Fetchhelper verletzt den Promisevertrag

In library_smoke.py, CONTROLLED_FETCH, ersetzt eine gewöhnliche, nicht asynchrone Funktion window.fetch. Die meisten kontrollierten Zweige geben eine Response direkt zurück, darunter empty, unauthorized, unavailable, malformed und der erste Erfolg von first-then-unauthorized. Die Fetchschnittstelle gibt dagegen Promise<Response> zurück. Ein korrekter Produktclient darf fetch(...).then(...) benutzen; mit diesen Fixtures erhält er stattdessen eine Response ohne then und scheitert. Ein Client mit await fetch(...) würde zufällig funktionieren, weil await auch unmittelbare Werte akzeptiert. Der Test darf diese zulässige Implementierungswahl nicht vorgeben.

Minimale Korrektur ausschließlich im Harness: Jeder kontrollierte Zweig muss denselben Promisevertrag wie echtes Fetch liefern, beispielsweise durch einen asynchronen Wrapper. Verzögerte Antworten sollen weiterhin nach Abort auflösbar bleiben, damit der Generationstest seine Aussage behält. Keine zusätzliche Testmatrix oder Produktänderung ist dafür nötig.

Spezifikationsurteil: Die sieben bisherigen Korrekturaufträge sind umgesetzt; die kontrollierten Nachweise sind wegen des neuen Helperfehlers noch nicht zuverlässig vertragskonform. Qualitätsurteil: eine begrenzte Harnesskorrektur erforderlich. Anschließend genügt ein erneuter Freeze mit gezieltem Review genau dieser Helperkorrektur und dem aktuellen Build-vor-Jest-RED, bevor Produktmodule entstehen. Jest und Chromium bleiben bis zum späteren GREEN eine Ausführungsgrenze dieses reinen Diffreviews; es wird kein Produktions- oder Gerätenachweis abgeleitet.

Root-Ruling zur engen Nachkorrektur: Bleiben Jestdatei und Workflow gegenüber 1938d2a654002c69c355b34488ad851175e61b19 bytegleich und beide Produktmodule abwesend, kann der noch zu bestätigende tatsächliche RED dieses Heads den identischen Jestinput auch nach der ausschließlichen Fetchwrapperkorrektur belegen. Der neue Harnessinhalt gilt dadurch nicht als ausgeführt; sein Ausführungsnachweis folgt im gemeinsamen GREEN-Lauf. Für diese einzelne Harnesskorrektur wird kein weiterer identischer Jest-RED oder redundanter vollständiger Matrixlauf verlangt. Der korrigierte Helper wird vor Phase 2 gezielt gelesen und eingefroren.

## Phase 1 – Korrekturrunde 2, enges Abschlussreview

Geprüft wurde nur das im zweiten Reviewpaket dokumentierte Einzeilendiff: window.fetch erhält einen asynchronen Wrapper. Root bestätigt ansonsten identischen Harnessinhalt und SHA-256 47d9cb49d0d5cf2bfaf55463be39f9b41bdd85eb2c801fb4446adec605ec9f69; Jest und Workflow sind unverändert, beide Produktmodule weiterhin abwesend.

Der allein verbliebene Fetch-Promise-P2 ist ADDRESSED. Der asynchrone Wrapper liefert für unmittelbare Responsewerte nun Promise<Response>; vorhandene Promisezweige und der echte Fetchrückgabewert werden übernommen. Damit funktionieren sowohl await als auch eine zulässige then-Kette. Die absichtlich verzögerte, trotz Abort noch auflösbare Antwort behält ihre Aussage für den Generationstest. Im engen Fixdiff ist keine neue Vertragsverletzung erkennbar.

Spezifikationsurteil für Phase 1: die geprüften Test-/Harnesskorrekturen sind erfüllt. Qualitätsurteil für dieses eingefrorene Testpaket: keine offenen konkreten P1/P2 aus dem seriellen Review. Dies ist keine vorgezogene GREEN-Abnahme der noch fehlenden Produktmodule.

Root hat Weblauf 39036483971, Job 117407292781 bestätigt: Build erfolgreich, danach gezielter Jest-RED mit Cannot find module './libraryClient'. Nach dem dokumentierten Ruling belegt dies die unveränderten Jest-/Workfloweingaben und fehlenden Produktmodule; der korrigierte Harness wird dadurch ausdrücklich nicht als ausgeführt dargestellt. Autor meldet py_compile und V3lint bestanden. Der Reviewer führte keine Probes aus und änderte ausschließlich diese Prosa. Der vollständige gemeinsame GREEN mit dem aktualisierten Harness und das spätere Quellreview bleiben vor Integration erforderlich.

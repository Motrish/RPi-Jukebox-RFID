# A02b1 – unabhängiges Review der eingefrorenen Testphase

Stand: 17.10.2026. PR 12, Head `6aaebb2c8e29098b6caf3553c1f00da8e799b84b`, Tree `37fc61cde7e010089d01a9592a7cd8b771b4c206`, Parent/Basis `e61a63e4b1322f47c252aad281176ec618e77831`. **Ein wichtiger P2-Testbefund und kleine explizite Randfallergänzungen vor Phase 2 offen.** Das absichtlich fehlende v1.js ist kein Befund; echter erwarteter CI-RED bleibt Roots separater Checkpoint. Keine Produktimplementierung geprüft oder vorweggenommen.

## P2 – positiver Pythonvergleich prüft nicht den ursprünglichen Inhalt

`src/webapp/src/contracts/v1.test.js:102–135`: Nach dem JSvalidatoraufruf erhält Python bei Erfolg ausschließlich javascript.value. Die ausdrücklichen ok=true-Prüfungen und Python-Revalidierung sind vorhanden und sinnvoll. Sie belegen jedoch nur, dass die vom JSvalidator ausgegebene Struktur gültig ist, nicht dass die gültige Eingabe vollständig erhalten blieb. Beispielsweise könnte eine Implementierung einen zulässigen Namen kürzen, Einträge verlieren oder ein anderes gültiges Kommando zurückgeben; Python validiert anschließend genau diese veränderte Struktur und der Helper sieht Gleichheit.

Vor dem JSaufruf den sicheren ursprünglichen Input serialisieren/sichern. Diesen unverändert mit dem Original-Pythonvalidator prüfen und die vollständige kanonische JSausgabe mit dessen validierter Struktur vergleichen. Zusätzlich die bereits vorhandene JSausgabe-Revalidierung erhalten. Den Input nach JSaufruf gegen seinen gesicherten Vorzustand auf unerlaubte Mutation prüfen. Ein erst nach JSaufruf erstellter Oracleinput würde die gleiche Lücke für mutierende Implementierungen behalten. Root hat den Befund angenommen; Autorfix bleibt seriell vor Phase 2.

## Kleine vertraglich wichtige Randfälle ergänzen

- `309/339/375–379`: Version 2 ist getestet, sichere Integer 0/-1 fehlen als Versionsfälle. Python _version unterscheidet ausschließlich echten Integer versus anderen Typ und liefert für jeden anderen echten Integer UNSUPPORTED_VERSION; negative Revision/Position bleibt dagegen VALIDATION_ERROR. Eine gemeinsam verwendete nichtnegative Integerhilfe könnte den Versionsfehler unbemerkt ändern.
- `310–313/344`: Die Doppelarmprobe benutzt ein wahrheitswertiges Errorobjekt. Zusätzlich APPLIED plus error:null und REJECTED plus result:null abweisen. Gegenfelder sind laut A01 auch mit null verboten; eine bloße truthiness-Prüfung würde die bisherige Probe bestehen. Dies verlangt keine größere neue Objektfamilie oder Corpusausweitung.

Diese Punkte bewerten die Testabnahme, keine bereits vorhandenen Fehler einer JSimplementierung. Der Reviewer schreibt keine zusätzlichen Tests.

## Exakter Abgleich und Bestand

Alle drei Remotedateien am SHA vollständig gelesen und Stage unabhängig abgeglichen. Test/Workflow stimmen als UTF8-Text und Git-Blob überein; Fixture stimmt einschließlich ihres vorhandenen gemischten CRLF-Endes exakt überein. Keine bloße Bytegleichheit nach versehentlich veränderter EOF-Normalisierung behauptet. Rohe SHA256 stimmen mit dem Freeze überein:

| Datei | Remote-Blob / roher Stage-SHA256 |
| --- | --- |
| src/webapp/src/contracts/v1.test.js | 0f091717c302aa3e65989a7d3a9ec82dbd7fae06 / 9f8fb28b4c3c0f50885314bfa8f7de181a41f079901d2b86078981ce28706877 |
| test/contracts/fixtures/v1.json | 809ea0373a5d48a6f071b9c9306c6b71c6583fd2 / 239bde183e5c12e5993626554110bc8ca825ec981980b338b460a686176b1a0b |
| .github/workflows/test_build_webapp_v3.yml | 4bbf9acc906537c5fb702d8c53a47275592cb96e / 0d443e3ffbc61fdb9218ea2128b67156adef9644c36b15df7e80ba5db36f2815 |

Commitmetadaten bestätigen Parent/Tree. Die vier bisherigen Fixturewurzeln wurden unabhängig strukturell gegen die Basis verglichen und sind unverändert; ausschließlich js_conformance kommt hinzu. Der tatsächliche Pythonvertrag mit neun Validatoren (Blob 2c050deaa8863ae1450be83b891cf565566f56d8), seine 22 Tests und der abgegrenzte A02b1-Plan bleiben die semantische Referenz. Keine Änderung an Python oder A01 im Diff.

## Bereits aussagekräftige Tests und sichere Grenzen

Node-Jest-Environment ist gesetzt. Repositoryroot wird vom tatsächlichen Testverzeichnis vier Ebenen nach oben aufgelöst; gemeinsame Fixtures werden per fs gelesen. Der Bridgequelltext ist ein festes Literal mit fester Validatornamensliste, keine Payloadinterpolation oder eval/exec. Werte gehen ausschließlich über JSON-stdin; execFileSync verwendet Argumentarray, Repository-cwd, explizites PYTHONPATH, 30 Sekunden Timeout und 32 MiB Buffer. Kein Shell-/Transport-/GUIimport. Ein unerwarteter Pythonfehler lässt den Test scheitern; es wird keine Ersatzantwort akzeptiert.

Alle 15 Schreibfamilien, beide Resultarme und alle 13 Error-Detailsfamilien sind als positive Prüfungen vertreten. Weitere Tests behandeln reale Auswahl-/Herkunft-/Duplikat-/Positionsfehler, vollständige ASCIIregex einschließlich LF, 10000/10001, MAXsafe, Boolean/Null/Nichtinteger, Astralzeichen und die tatsächlichen Python-Whitespaceunterschiede. Detached-copy-Assertions prüfen mehrere verschachtelte Familien. NaN/Infinity/undefined und geerbte Objektfelder werden ausdrücklich JS-seitig geprüft; sie werden nicht als gültige gemeinsame JSONinputs ausgegeben.

Rawfälle 1.0/1e0/-0.0 sind ausdrücklich als nach JSON.parse verlustbehaftete Floatlexeme klassifiziert. Der Bridge setzt den originalen numerischen Rawtext auf Pythonseite wieder ein; rohe Pythonablehnung wird damit unabhängig von JSstringify sichtbar. Akzeptierte kanonische JSausgaben daraus werden zusätzlich erneut von Python akzeptiert. Große Versionswerte/supportedVersions außerhalb des sicheren JSbereichs sind ausdrücklich mit fehlendem Fehlerparitätsanspruch klassifiziert. Dies ist keine beliebige Raw-JSON-Parität und keine Losslessparserimplementierung.

Der Workflow erhält vorhandenen vollständigen Build und Browserprüfung, ergänzt den gezielten Jestlauf nach Pythonsetup im tatsächlichen src/webapp und nimmt die gemeinsame Fixture in die Pfadfilter auf. Vorhandenes npm-Testskript/Jest wird genutzt; kein Package-/Lockfile-/Dependency- oder Berechtigungswechsel. Andere Tests werden nicht abgeschaltet. Die fehlende v1.js soll im echten TDDlauf rot werden; dieser Zustand darf weder als fertiger A02b-Erfolg noch als unerwartete Produktregression bezeichnet werden.

Abschluss: wichtige Helperkorrektur und die genannten kleinen Randfälle durch Luna, danach exaktes Test-Folgereview und tatsächlicher RED-Checkpoint vor Implementierungsphase. Kein neuer lokaler Jest-/Pythonbridge-PASS behauptet; der Teilstage ist kein vollständiger Checkout. Nur dieser Prosa-Bericht wurde geschrieben, keine A02-/I01- oder sonstige Produktdatei verändert.

Quelle: [geprüfter Testcommit](https://github.com/Motrish/RPi-Jukebox-RFID/commit/6aaebb2c8e29098b6caf3553c1f00da8e799b84b), [enger Vergleich](https://github.com/Motrish/RPi-Jukebox-RFID/compare/e61a63e4b1322f47c252aad281176ec618e77831...6aaebb2c8e29098b6caf3553c1f00da8e799b84b).

## Lokaler Abschluss der korrigierten Phase-1-Tests

Geprüfter eingefrorener Stage ohne neu benannten Remote-SHA: Jest-SHA256 `5006fb3f68c501cf501881c8131b4f0e6654fc814f40f5e25d2eb8bb73bd622e`, Workflow `dc72a2b4796eddd5b6d27fca9ae3e1d5667f459446281a5c3a7fdac3985b6c3c`, Fixture unverändert `239bde183e5c12e5993626554110bc8ca825ec981980b338b460a686176b1a0b`. Alle drei Werte unabhängig bestätigt.

Der P2-Helperbefund ist im Stage geschlossen: ursprüngliche Inputs werden vor dem JSaufruf serialisiert und von Python validiert. Nach JSaufruf wird Inputmutation geprüft; akzeptierte kanonische JSstrukturen werden vollständig mit dem unabhängigen Python-Originalresultat verglichen und anschließend weiterhin nochmals von Python revalidiert. Positive ok=true-Anforderungen bleiben erhalten. Die ausdrücklich klassifizierten Rawlexemfälle behalten ihre separate kanonische Ausgabe-Revalidierung und behaupten keine Rawtextparität.

Version 0/-1 wird nun explizit als UNSUPPORTED_VERSION geprüft; negative Revision/Position bleibt VALIDATION_ERROR. Beide verbotenen null-Gegenarme und die null-eigenen Ergebnis-/Fehlerarme sind als Ablehnungen enthalten. Der Workflow ergänzt den unveränderten Python-Vertragstest vor dem gezielten Jestlauf und erhält Build/Browserabnahme. Keine Python-/Spec-/Fixturesemantik geändert.

Damit keine offenen Quellblocker aus dem bisherigen Phase-1-Review in diesen lokalen Hashes. Dies ist keine neue Remote-SHA-Freigabe und kein tatsächlicher RED-/GREEN-Nachweis; fehlendes v1.js bleibt beabsichtigter TDDzustand. Root bewertet Veröffentlichung und echten CI-RED separat. Nur dieser Bericht ergänzt.

## Phase-2-Quellreview am Commit 77793a23

Geprüft ausschließlich neues `src/webapp/src/contracts/v1.js`: Head `77793a2364f06b6c405eb908aa6437e265c575c4`, Tree `ccc1cebffc7eebc5a98a998151f1f9e2cf37c1f6`, Parent `0508ef45f075976f4b0ab8a831c693fae8aa9a77`. Remotevergleich bestätigt genau eine hinzugefügte Datei. Remote-Blob `0787f6881d22798fd6dea77cca846de5d4266444`, lokal unabhängig errechnet identisch; vollständiger UTF8-Text einschließlich Zeilenenden exakt Stage-identisch. Roher Freeze-SHA256 `bb095aa184ab78af9c2e7a7df3077adaed277350d9a0baab4cf623abc68e7ff5` bestätigt. Tests unverändert mit SHA256 `5006fb3f68c501cf501881c8131b4f0e6654fc814f40f5e25d2eb8bb73bd622e`.

**Zwei P2 offen, keine Quellfreigabe dieses SHA.** Bewertung gegen unveränderten Pythonvertrag und den genehmigten kanonischen JS-Writerbereich, keine Rawtext-Vollparität.

### P2 – dünn besetzte Arrays umgehen die Elementprüfung

`v1.js:227–250`, `296–312`, `360–366`, `377–394`: forEach/map/some überspringen nicht vorhandene Arrayindizes. Die Arraygrenzen verlangen bisher nur Array.isArray und Länge, keine vollständige Indexbelegung. Konkretes Beispiel: Error UNSUPPORTED_VERSION mit details.supportedVersions als Array(1). some besucht keinen Wert, die Prüfung akzeptiert; Spread erzeugt supportedVersions:[undefined]. JSON.stringify liefert [null], was Python _details_versions ablehnt. Gleiches Risiko bei einem Loch in command.items oder conflicts: map erhält das Loch, die kanonische Ausgabe enthält null und Python lehnt ab. Bei Snapshotentries überspringt forEach Löcher sogar vollständig und verkürzt still den Inhalt.

Das ist eine JS-only-NichtJSONeingabe, aber Teil der ausdrücklich verlangten Annahmegrenze: der Writer darf sie nicht erfolgreich annehmen und dann eine von Python abgelehnte/inhaltlich verkürzte kanonische Ausgabe liefern. Root bestätigt diese Einordnung. Enger Autorfix an den Arraygrenzen: fehlende Indizes vor erfolgreichen Prüfungen ablehnen und gezielte Regressionen für diese Familien; keine stillen Filters/Nullersatzwerte. Der Reviewer hat keine zusätzlichen ausführbaren Gegenproben geschrieben.

### P2 – akzeptiertes negatives Null bleibt im Rückgabewert nicht kanonisch

`v1.js:117–121`: integer akzeptiert -0 als sicheren nichtnegativen Integer und gibt -0 unverändert zurück. Der bereits eingefrorene Rawfall -0.0 erzeugt deshalb eine Ausgabe mit revision=-0. JSON.stringify macht daraus revision=0. Die vorhandene Rawprüfung vergleicht diese kanonisch geparste Struktur direkt mit javascript.value über Jest.toEqual und unterscheidet dabei 0/-0; ebenso wird der kanonische Pythonwert gegen den noch negativen JSnullwert verglichen.

Damit besteht ein konkret aus Quelle und vorhandenem Test vorhergesagter Abnahmefehler. Dies ist kein selbst ausgeführter CI-RED. Für den freigegebenen Writer die akzeptierte Null im validierten Ausgabewert kanonisch vereinheitlichen; den Rawfall und seine Python-Revalidierung nicht entfernen oder abschwächen. Andere Floatlexeme und unsichere Versionsinteger bleiben weiterhin ausdrücklich außerhalb vollständiger Rawparität klassifiziert.

### Sonstiger enger Quellbefund und Nachweisgrenzen

Maps/Sets vermeiden geerbte action/code-Treffer; eigene Pflichtfelder und geschlossene normale Objekte werden geprüft. Normale dichte Snapshots, Commands und Errorfamilien werden strukturell neu aufgebaut; verschachtelte Kopien sind im gelesenen Pfad unabhängig. Fehlerarme/-details und Reihenfolge orientieren sich am Pythonbestand. Python-Whitespace enthält die relevanten Kontroll-/Unicodezeichen und schließt FEFF aus; Array.from zählt Codepoints. fullMatch vergleicht den ganzen Treffer mit dem Eingabestring und verhindert den JS-$-LF-Sonderfall. Diese Befunde heben die beiden konkreten P2 nicht auf.

Root bestätigt den echten abschließenden Phase-1-RED 39027441324: CRA und 22 Pythonprüfungen erfolgreich, Jest am absichtlich fehlenden v1-Modul fehlgeschlagen. CI 39027661137 am jetzigen Head läuft beim Reviewabschluss noch; kein GREEN/PASS daraus behauptet. Keine neuen Tests, ausführbaren Diagnosesnippets, Produkt- oder CIänderungen durch den Reviewer. Nach seriellen Autorfixes exaktes Folgecommitreview und vollständigen bestehenden Testlauf verlangen. A02b-Gesamtparität/Transport bleiben weiterhin offen. Nur diesen Bericht ergänzt, Review beendet.

Quelle: [Phase-2-Commit](https://github.com/Motrish/RPi-Jukebox-RFID/commit/77793a2364f06b6c405eb908aa6437e265c575c4), [Ein-Datei-Diff](https://github.com/Motrish/RPi-Jukebox-RFID/compare/0508ef45f075976f4b0ab8a831c693fae8aa9a77...77793a2364f06b6c405eb908aa6437e265c575c4).

## Enges lokales Folgereview: beide Phase-2-P2 geschlossen

Eingefrorene Autorstände unabhängig über rohe SHA256 bestätigt: v1.js `4413dcbed9325b0e412b7bcaa34b77c8c37d5821bc20b31fdbc050d5ca3aa8ea`, v1.test.js `0785e92b4bc77e55bb582772706bfe6d647e9d8520b6f27e0a1446dbc07255df`. Noch kein neuer veröffentlichter Commit für diesen Abschluss benannt. Den vollständigen engen Textvergleich gegen die beiden veröffentlichten Dateien am historischen Head 77793a2364f06b6c405eb908aa6437e265c575c4 durchgeführt: ausschließlich Nullnormalisierung, denseArray samt vier Aufrufstellen und zwei neue Regressionstests. Gemeinsame Fixture `239bde183e5c12e5993626554110bc8ca825ec981980b338b460a686176b1a0b` und Workflow `dc72a2b4796eddd5b6d27fca9ae3e1d5667f459446281a5c3a7fdac3985b6c3c` unverändert bestätigt.

Der Sparsearray-P2 ist auf Quellebene geschlossen: denseArray (v1.js:172) verlangt jeden eigenen numerischen Index vor forEach/map/some. Snapshotentries (240), Commanditems (307), supportedVersions (369) und conflicts (386) benutzen dieselbe Grenze. Löcher werden mit ContractValidationError abgewiesen; keine stille Verkürzung, Filterung oder null-Ersatzwerte. Die neue JS-only-Regression (v1.test.js:476) übergibt echte Array(1)-Löcher an Playlist, Queue, Command und beide Errorfamilien und verlangt diese Ablehnung. Sie serialisiert die Löcher nicht versehentlich vor dem Validator.

Der −0-P2 ist ebenfalls auf Quellebene geschlossen: integer (v1.js:121) gibt jede akzeptierte Null als positive Null zurück; andere gültige Zahlen und Validierungsregeln bleiben gleich. Der neue Test (v1.test.js:416) unterscheidet mit Object.is ausdrücklich die unveränderte negative Inputnull von der positiven Ausgabenull. Der frühere Raw-−0.0-Fall, vollständige Strukturvergleiche und die unabhängige Python-Revalidierung kanonischer Ausgaben bleiben vollständig erhalten. Keine Assertion entfernt oder gelockert; keine Python-/Specsemantik geändert.

Root meldet inzwischen den tatsächlichen vorherigen CI-Lauf am historischen Head als 9 Tests erfolgreich und genau einen −0-Fehler. Dies bestätigt den alten Befund, ist aber kein GREEN für die neuen Hashes. Für diese eingefrorenen zwei Dateien keine offenen Blocker aus dem engen Folgereview; Quellfreigabe für Veröffentlichung und den unveränderten vollständigen Abnahmelauf. Remoteidentität am neuen SHA und tatsächlicher Jest-/Build-/Python-CI-PASS bleiben Roots nachfolgender Checkpoint. Keine beliebige Raw-JSON-Parität, Transport- oder Laufzeitfreigabe daraus abgeleitet. Reviewer hat keine neuen Tests/Diagnosesnippets ausgeführt oder geschrieben und ausschließlich diesen Bericht ergänzt. Review beendet.

## Veröffentlichung desselben Fixstands

Nach obigem lokalen Abschluss veröffentlicht: PR12 Head `18428caf43e461e287f6e3f14de0a241b562aee6`, Tree `314e7b057bd811f3b578e3791dc531b2c8e0755f`, einschließlich I01-Mergebasis. Beide finalen Remote-Dateien unabhängig vollständig gelesen: v1.js Blob `af2f70178be79c2e381a02d27806c7187352065d`, v1.test.js Blob `72351ef1976fbc49736fd1b8e91041054c8fd8e8`. Beide Texte einschließlich Zeilenenden exakt identisch mit den oben geprüften Freezehashes. Die enge Quellfreigabe gilt damit ausdrücklich diesem veröffentlichten Head. Neuer vollständiger CI-GREEN weiterhin nicht behauptet; Root prüft ihn separat.

Root bestätigt außerdem I01-PR13-Merge nach zwei vollständigen Python3.9–3.13-Matrizen einschließlich Abschlussjob erfolgreich (39027696042/39027699443); Mergetree identisch zum geprüften f88747f4d6834fa688cd4bd29782d36a94d5dc7d. Dies ist ein zugeordneter Root-CI-Beleg und kein Hardware-/ARMv6-Nachweis.

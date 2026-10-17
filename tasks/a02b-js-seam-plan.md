# A02b1 – kanonischer JS-Writer ohne Transport

Stand: 17.10.2026. Prosa-Plan am integrierten `e61a63e4b1322f47c252aad281176ec618e77831`. Root bevorzugt ausdrücklich den begrenzten Bereich dekodierter JS-Werte mit kanonischer JSON-Ausgabe: JS akzeptiert nur endliche sichere Ganzzahlwerte in Integerfeldern; jede akzeptierte, mit JSON.stringify serialisierte Ausgabe muss nach Python-JSONparse vom unveränderten V1-Validator akzeptiert werden. Das ist eine gerichtete Verträglichkeitsgarantie, keine beliebige Raw-JSON-/Gesamt-A02-Parität. Die Freigabe und Reihenfolge stehen im Root-Abschnitt unten.

## Fünf gelesene Quellen

| Quelle am gepinnten Commit | Blob / entscheidender Bestand |
| --- | --- |
| src/jukebox/jukebox/contracts/v1.py | 2c050deaa8863ae1450be83b891cf565566f56d8 – vorhandene neun öffentliche Validatoren, geschlossene Formen und Fehlerdetails. |
| test/contracts/test_v1.py | f62233aceb571944fb7d824063bc3c2504a724c5 – 22 Tests, ausdrücklich Float-/Booleanablehnung, alle 15 Kommandos, Resultarme, Kopien und LIMIT_EXCEEDED-Details. |
| test/contracts/fixtures/v1.json | be573867052586a36cb4d9d64b3cad724dc8a48b – bisher nur gültige MediaRefs, gemischte Playlist/Queue und leere Queue; keine umfassende negative Konformitätsmatrix. |
| src/webapp/package.json | 1619a8c60e38d6b9f5f7f4a19f29bd562dbb26d7 – React17, react-scripts5, vorhandenes test-Skript/Jest; kein package type=module. |
| src/webapp/src/setupTests.js | 8f2609b7b3e0e3897ab3bcaad13caf6876e48699 – nur bestehender jest-dom-Import, keine Geräteimports. |

Zusätzlich lokale A01-Prosa gelesen. Keine Änderung an Pythonimplementierung, bisheriger Semantik oder A01 vorgesehen.

## Entscheidende Semantikgrenzen

Python verwendet type(value) is int; seine Tests verwerfen 1.0/0.0 für Version/Revision. JSON.parse verliert den Unterschied zwischen 1, 1.0 und 1e0, außerdem zwischen -0 und -0.0. Ein JSvalue-Validator kann diese lexikalische Herkunft nicht rekonstruieren. Im freigegebenen Zielbereich darf der JSwert 1 akzeptiert und als kanonisches 1 serialisiert werden; dies beweist gerade keine Parität zum ursprünglichen Rawtext 1.0. Solche Rawfälle werden im Corpus ausdrücklich als verlustbehaftete Eingangslexeme klassifiziert und mit ihrer Pythonablehnung dokumentiert. Kein handgeschriebener Losslessparser, keine neue Dependency.

Revision/Positionen sind in Python bis 9007199254740991 begrenzt. JS muss Number.isSafeInteger verwenden und Boolean, nichtendliche, negative und gebrochene Werte ablehnen, ohne vorherige JSON-Sanitization. JSON.parse kann große oder grenznahe gebrochene Literale bereits runden. Version und supportedVersions sind ein zusätzlicher Unterschied: Python verlangt dort echte Integer, hat für supportedVersions aber keine Safeintegerobergrenze; andere echte Versioninteger ergeben UNSUPPORTED_VERSION. Außerhalb des sicheren JSbereichs wird deshalb explizit außerhalb A02b1 klassifiziert, keine still behauptete gleiche Fehlerklasse oder exakt erhaltene Zahl.

Python len zählt Unicodecodepoints; JS String.length zählt UTF16-Einheiten. Namen/Titel/Fehlertexte müssen die tatsächlichen Pythonlängen 256/1024 spiegeln, etwa mit Codepointzählung, ohne NFC-Normalisierung oder Texttrimmung. Python prüft zusätzlich strip auf allen vier Textfamilien, auch Titel. JS trim bzw. \s hat eine andere Whitespace-Menge (unter anderem FEFF gegenüber 0085/001C–001F); dies gezielt nachweisen statt unbemerkt verengen/erweitern. ASCII-IDs/Spotifyregex müssen den gesamten String treffen: JS-$ kann vor abschließendem LF passen, Python fullmatch/\Z nicht. Keine Pfade/Unicode-IDs akzeptieren.

Geschlossene Objekte verlangen eigene vorhandene Schlüssel; Arrays/null, fehlend/undefined und zusätzliche Felder nicht per Serialisierung verstecken. Prototypebezeichner wie __proto__/constructor/toString dürfen keine Aktions-/Fehler-Map umgehen. Null bleibt nur an ausdrücklich erlaubten Stellen zulässig. Doppelte Medien mit verschiedenen entryIds erlaubt; gleiche entryId, Positionslücken, fremde currentEntryId und ungepaarte Sourcefelder abweisen. Tief abgelöste Ausgabekopien erhalten.

## Ein konkreter Auftrag, höchstens vier Dateien

| Exklusiver Schreibpfad | Aufgabe |
| --- | --- |
| src/webapp/src/contracts/v1.js (neu) | Reines ES-Modul mit den vorhandenen V1-Prüfungen und sicherem eigenem ContractValidationError; keine UI-/Transportimports, keine neuen Objektfamilien wie Playback/Battery/Setup/LIST. |
| src/webapp/src/contracts/v1.test.js (neu) | Vorhandenes CRA-Jest mit Node-Testumgebung; fs/path/child_process aus Node-stdlib. Gleiche kanonische Fixtures lesen; keine Geräte-/Appimporte. |
| test/contracts/fixtures/v1.json (bestehend) | Alte Schlüssel/Beispiele erhalten, zusätzliche benannte Konformitätsfälle und eindeutige Bereichsklassifikation ergänzen. Ein gemeinsames Corpus, keine JS-Kopie im Webclient. |
| .github/workflows/test_build_webapp_v3.yml (bestehend) | Nach vorhandenem Build/Pythonsetup gezielten Jestlauf ergänzen; bestehende vollständige Build-/Browserabnahme erhalten. Keine anderen Tests deaktivieren; keine Paket-/Lockfileänderung. |

Jest verwendet ausdrücklich Node-Testumgebung für fs/path/child_process. Der Test löst den Repositoryroot vom tatsächlichen Verzeichnis src/webapp/src/contracts aus vier Ebenen nach oben auf und liest dort test/contracts/fixtures/v1.json per fs; weder cwd-Raten noch eine Fixturekopie. Produktcode importiert sie nicht. react-scripts transformiert das ES-Modul; kein direkter Node-ESM-Aufruf und keine package-Typumstellung nötig. CI-Befehl im vorhandenen src/webapp-Arbeitsverzeichnis: CI=true npm test -- --watchAll=false --runInBand --testPathPattern=src/contracts/v1.test.js.

## Aussagekräftiger sprachübergreifender Nachweis

Der Jesttest startet mit execFileSync einen festen, testinternen Python-stdlib-Bridgeaufruf, der ausschließlich die unveränderten freigegebenen v1-Validatoren anhand einer festen Namensliste importiert/ausführt. Bridge-Quelltext ist fest im Test hinterlegt; keine Payloadinterpolation in Quelltext/Argumentcode und kein Python-exec/eval. Payload ausschließlich über JSON-stdin. Kein zusätzlicher Pythonpfad/Runner. Inputs/Outputs werden über JSON-stdin/stdout übertragen, Ausführung begrenzt; keine Shell-/Netz-/Dateimutationen außer üblichen Testartefakten.

Für **jede JSakzeptierte Ausgabe**: erst validieren, dann JSON.stringify, Python json.loads plus Originalvalidator, erneut validierte Struktur vergleichen. Im gemeinsamen darstellbaren Bereich zusätzlich gültig/ungültig und code/retryable/operation/details samt field/reason vergleichen; stabile Fehlermeldung nicht als Raw-Exceptiontext gewinnen. Verarbeitungsreihenfolge beachten: unbekannte Felder vor fehlenden, fehlende Schlüssel lexikografisch, bestehende action/kind/status-Prüfung vor Detailform. LIMIT_EXCEEDED muss field/limit statt field/reason besitzen; APPLIED/REJECTED haben ausschließlich result/error ohne null-Gegenarm.

Corpus/Tests müssen alle 15 Kommandofamilien/Resultarme, alle Error-Details, 10000/10001, MAX/MAX+1, Boolean/Null/Nichtinteger, Astralzeichen/Whitespace, Regex-Ende, Auswahl/Herkunft/Duplikate und detached copies tatsächlich abdecken. Große Listen dürfen testintern aus deklarierten synthetischen Fällen entstehen. NaN/Infinity/undefined sind explizite JS-only-Ablehnungsfälle, keine gültigen JSONfixtures. Rawlexeme und Python-gültige Zahlen außerhalb JSdarstellbarkeit erhalten eigene ausgewiesene Klassifikation/Assertions statt stillen Skip. Die alten 22 Pythonprüfungen müssen unverändert grün bleiben.

Ende: getestete gerichtete Writerkompatibilität im benannten Bereich, keine Runtime-/GUIzustandsänderung. Arbiträre Raw-JSON-Parität, beliebig große Pythoninteger und gesicherter Transport bleiben offen; A02 als Ganzes nicht erledigt. Root legt diese Grenze im Codingbriefing ausdrücklich fest und bewertet Folgecommit/CI.

Quellen: [Pythonvertrag](https://github.com/Motrish/RPi-Jukebox-RFID/blob/e61a63e4b1322f47c252aad281176ec618e77831/src/jukebox/jukebox/contracts/v1.py), [bestehende Tests](https://github.com/Motrish/RPi-Jukebox-RFID/blob/e61a63e4b1322f47c252aad281176ec618e77831/test/contracts/test_v1.py), [gemeinsame Fixtures](https://github.com/Motrish/RPi-Jukebox-RFID/blob/e61a63e4b1322f47c252aad281176ec618e77831/test/contracts/fixtures/v1.json).

## Root-Freigabe und Reihenfolge

A02b1 ist auf Basis e61a63e4b1322f47c252aad281176ec618e77831, Tree 4e72f86b0319b37a9e4c292a05ad6a57c9161480, für genau die vier genannten Dateien freigegeben. Exklusiver Autor ist Luna im Teilstage G:/Entwicklung/phoniebox-staging/a02b; kein Vollcheckout, keine Root-/Sol-Codeautorschaft, keine Remoteaktionen durch den Worker. Root besitzt weiterhin Aufgabenstatus und mechanische Veröffentlichung.

Phase 1 schreibt ausschließlich Jesttests, Corpus und Workflow (drei Dateien), während v1.js fehlt. Nach Freeze/Hashübergabe veröffentlicht Root den Stand und bestätigt den tatsächlichen erwarteten CI-Fehler am fehlenden Modul. Erst danach erhält Phase 2 die Freigabe zur Implementierung von v1.js. Keine behauptete lokale Jestabnahme ohne vorhandene Dependencies und kein vorgetäuschter RED-Lauf. An späteren Änderungen folgen gezielte Regressionen und vollständige CI, bevor integriert wird.

Die Pythonbridge verwendet festen Quelltext und JSON-stdin, keine Shell-/Payloadcodeinterpolation; Timeout und begrenzter Ausgabepuffer müssen gültige 10000-Einträge-Randfälle ermöglichen. Der Workflow erhält den echten Build-/Browsercheck und seine Grenzen, ergänzt den gezielten Jestlauf im tatsächlichen Webappverzeichnis und berücksichtigt gemeinsame Fixtureänderungen in seinen Pfadfiltern. Keine neuen Produktdependencies, Paketdateien oder Losslessparser. Vollständige bidirektionale Raw-JSON-Parität und der spätere sichere Geräteanschluss bleiben außerhalb dieses Slices.

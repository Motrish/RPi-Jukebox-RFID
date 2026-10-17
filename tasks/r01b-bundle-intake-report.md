# R01b phase-one test freeze

Stage: `G:/Entwicklung/phoniebox-staging/r01b-bundle-intake`

The only new publishable executable path is `test/websetup/test_bundle.py` (25 unittest cases). The required product module `installation/websetup/bundle.py` is absent. The unconditional module-level import of `installation.websetup.bundle` remains before all tests, so publication to the complete Linux checkout must produce the intended missing-module RED. The tests are not skipped and no product behavior is mocked.

The unchanged local R01a dependency is `tools/web_bundle.py`, copied from `../r01a-web-bundle/tools/web_bundle.py`. Both copies have SHA-256 `b45005aa629c2ed7ed2b66a0bdb02acb3f4f636395d1d84063c3e04df8fc48ee`. The R01a producer creates the success bundle used by the behavioral fixture, including a zero-byte asset. Malformed TAR fixtures rewrite a bounded R01a manifest with the matching digest so tests reach intake parsing.

Frozen test SHA-256: `461fd23e807b7d80e186ae4b799cfa42f7b04a6a171b0f32f99764b7dbc2af04`.

Local evidence: `python -m py_compile test_bundle.py` passed. V3 flake8 passed with `PYTHONPATH=G:\Entwicklung\phoniebox-tools\python`, max line length 127, max complexity 12, ignores `E126,E127,E128,W503,F824`, and per-file ignore `__init__.py:F401`. The unit tests were not run on Windows; Root's required full Linux checkout RED remains the next acceptance evidence. Existing baseline reported by Root: full CI green at `future3/feature-bundle-intake`, `fc995afb` (Web39044627838; Python39044627823, Python 3.9–3.13).

Review focus: confirm the `MAX_TAR_STREAM_BYTES` test seam matches the implementation constant; verify the complete Linux run shows `ModuleNotFoundError` at the unconditional product import; review TAR fixture validity and behavior against the approved bounded-PAX contract. No source implementation, workflow, dependency, status, or Git changes were made.

Generated Python cache (`test/websetup/__pycache__/test_bundle.cpython-312.pyc`) is local staging output. Optional cleanup was rejected by sandbox policy; only the two approved source paths were published.

## Tatsächlicher Phase1-RED und Testkorrekturauftrag

Root hat den eingefrorenen Test bytegleich auf vollständigem fc995afb-Baum publiziert: PR19, Branch future3/feature-bundle-intake, Head238d5a6aa9ab38e81fee292bd4a15a44e04897e1, Baum8609646dca587e7129297b1d0a9ba07e3f88db2e. pyc ausgeschlossen; exakt ein neuer publishbarer Pfad. Root wiederholt V3flake8 erfolgreich und prüft Produktabwesenheit.

Tatsächlicher Linuxlauf39045338774/Job117432825524 endet bei pytestcollection nach211gesammelten Bestandsfällen mit genau ModuleNotFoundError installation.websetup.bundle in test/websetup/test_bundle.py:25. Damit beabsichtigter Missingmodule-RED belegt, keine bestehende Implementierung übersprungen. Andere Matrixjobs sind teilweise fail-fast-cancelled und keine vollständige Abnahme.

Unabhängiges Testreview liefert2P1-/4P2-Abnahmegruppen: private stabile Kopien, belastbare Ressourcenproben, korrekte Typ-/PAX-/Endfixtures, sichere Pfad-/Installationssentinels, tatsächliche Producerkompatibilität ohne feste Verzeichnistiefe/unnötige Linux-Casefaltung sowie präzise Lebenszyklus-/Fehlerbehauptungen. Dies sind Testlücken, keine bereits vorhandenen Produktfehler. Luna korrigiert ausschließlich Tests gesammelt; Source bleibt abwesend bis direktem engem Folgepass. Reviewprosa wurde nach Schreibfehler des Reviewers von Root gespeichert.

## Endgültiger Testvertrag vor Phase2

Finaler Testfreeze aaede173d17bdcb5ecd8043afc1fc63d6293ade3585c1114aa1bfba3b45463a9 mit35Fällen. Die ursprünglichen6Reviewgruppen und engen Restpunkte sind geschlossen: pre-payload Readpositionen/Größen/gelieferte Bytes außerhalb Produktfehlerbehandlung geprüft, große Reads vor Delegation blockiert; private Verifierinputs liegen im selben eigenen0700-Unterbaum; Existenz-/Modiprüfung erfolgt noch im aktiven Context;0644nur extrahierte Dateien, Caller0600bleibt unverändert. Root hat diese engen letzten Änderungen direkt gelesen. Grenzkonstanten und öffentlicher stdlib-Gzipreader gemäß explizitem Rootruling im Plan; keine Behauptung eines generischen TARimporters.

Kompilation und V3flake8 laut Luna bestanden; Root wiederholt V3lint auf dem vorherigen engen Freeze, letzter Fix verschiebt ausschließlich Assertions in den noch aktiven Context. Früher Import unverändert und Source vor Freigabe nachweislich abwesend. Tatsächlicher vorhandener Linux-RED bleibt nach Plan gültig; die korrigierten35Tests wurden noch nicht ausgeführt. Root gibt jetzt ausschließlich installation/websetup/bundle.py an Luna zur Implementierung frei. Quellcode-/Regressions-/CI-/Gesamtreviewnachweise folgen vor Integration. Nach Nutzerfortsetzung wurde remote bestätigt: Produktfc995afb und DraftPR19head238d5a6a unverändert.

## Sourcefreeze, lokale Nachweise und vier geschlossene Sourcebefunde

Erster Producer-Intake-Sourcefreeze589a572c... mit unverändertem35Testfreezeaaede173... wurde exakt als PR19headf4de3536036346e350c154ab961f970a97c1cfb4/Baumcc06a493c69b01170f4ea8e43207ac4c0930b05d veröffentlicht. Beide vollständigen Remoteinhalte bytegleich zurückgelesen. Root führt35neue Tests erfolgreich aus (Windows-FIFO übersprungen), dazu15R01a-Tests (2Windows-POSIXskips),10I01a-Tests und V3lint. Bestandsregressionen laufen in ihren eigenen vorhandenen Teilstages; ein erster Root-Aufruf aus dem falschen Teilstage fand den R01a-Testordner nicht und zählt nicht als Produktfehler oder Pass. Korrigierte getrennte Aufrufe bestehen tatsächlich.

Frisches unabhängiges Gesamtsourcereview fand4P2: Consumer-Ausnahmen in Intakeübersetzung, unbehandeltes zlib.error, umaskabhängiger Outputmodus und akzeptierte C1-Steuerzeichen. Luna fügt zuerst minimale Regressionen hinzu und beobachtet lokal tatsächlichen RED gegen589a... für ValueError-/OSError-Identität, ungültigen DEFLATE und U+0085; POSIX-umask ist auf Windows übersprungen und wird durch Linux-CI abgenommen. Dann ausschließlich die2Whitelistdateien korrigiert.

Finale SourceSHA2566e66a3b49cb5c71240cecbb046bfd136bc069d8cd950490f23b1fe1fa874dd9d, TestSHA256d7a3176bf8d300a4fa0d2348d5c5b0496658a783f54f16ecc54103584f40b465. Root wiederholt39neue Fälle: OK,2OSskips (FIFO/umask); V3lint auf beiden Pfaden bestanden. Luna meldet zudem erneut15R01a-/10I01a-/py_compilepass. Enger unabhängiger Folgepass liest alle4Korrekturen samt betroffenen Pfaden: alleP2geschlossen, keine Rest-P1/P2. Yield liegt außerhalb Intakeübersetzung bei eigener finally-Bereinigung, zlib.error wird sicher übersetzt, POSIXfchmod setzt0644, Pfade verwerfen alle Unicode-Cc-Zeichen.

Korrigierter Sourcehead617d2fd13cde686c1d5b7d0c9bef9ca0327e7618, Baum3dd4b2240cca9ebf729050a919cd3207074fd5b2. Exakt2Remoteinhalte erneut bytegleich. Vollständige aktuelle Pythonläufe39058605235/39058602622 laufen; vorherige39058298986/39058297193 an f4de3536 sind inzwischen success, aber keine Abnahme der neuen39Fälle. Automatischer unveränderter ARMv7-Installer39058297166 nochin_progress, neuer39058602698pending; globale Installer wurden nicht verändert und sind außerhalb dieses lokalen Intake-Slices. Kein ARMv6-/Gerätenachweis aus diesen automatischen Läufen.

## Vollständige Sourceabnahme und Integration

Beide aktuellen Vollcheckout-Pythonläufe39058605235 und39058602622 am Sourcehead617d2fd13cde686c1d5b7d0c9bef9ca0327e7618 sind tatsächlich completed/success: jeweils3.9,3.10,3.11,3.12,3.13 undfinish (117472316458 bzw.117472313297). Gelesener3.9Job117471631711 meldet250/250bestandene Tests, darunter alle39Intakefälle und die auf Windows übersprungenen FIFO-/umaskfälle sowie C1-/DEFLATE-/Consumerregressionen. Keine Linux-Skips aus diesen Fällen.

Root bestätigt vor Merge: Produktbasisfc995afb, develop42d5023e37dbf8de6477fef5ebcd6eae3cb5087d unverändert; Sourcecommitbaum3dd4b2240cca9ebf729050a919cd3207074fd5b2; PRdiff exakt2neue Pfade, keine pyc/Abhängigkeiten/Workflows. Nach abgeschlossenen Review-/CIbedingungen PR19ready gesetzt und mit erwartetem Sourcehead gemergt. Integration2002cc2c2de3daa8f0b2b06e6f9513cd71c92886 hat exakt Elternfc995afb.../617d2fd1... und denselben geprüften Baum3dd4b2240cca9ebf729050a919cd3207074fd5b2. Produktref und unverändertes develop remote zurückgelesen. R01b als begrenzter lokaler Intake-/Extraktionsslice verified/integrated; vollständigesR01/Installer/Setup/LAN/Gerät bleiben offen.

Automatisch nach Integration gestarteter Pythonlauf39058968526 und unveränderter ARMv7-Installer39058968556 sind bei diesem Nachtrag noch kein zusätzlicher Passnachweis. Vorherige Installerläufe liegen außerhalb des2Pfad-Intakes. Die bestehenden Webassets wurden nicht verändert, daher kein neuer Weblauf für2002cc2c durch die engen Pfadfilter; das vorhandene R01a-Artefakt bleibt ausschließlich anfc995afbgebunden. I01b-dev muss über seinen eigenen tatsächlichen Webworkflow ein zum dann aktuellen Checkout passendes Bundle erzeugen. Keine Umdeklarierung alter Manifestcommits und kein anonymer Releaseendpunkt.

## Tatsächlicher Integrationsnachweis

Auch der automatisch gestartete Pythonlauf39058968526 am Integrationscommit2002cc2c2de3daa8f0b2b06e6f9513cd71c92886 ist inzwischen tatsächlich vollständig completed/success:3.9–3.13 undfinish117473390031. Somit Source- und Integrationscheckout beide abgenommen. Keine ergänzende Installer-/Gerätebehauptung. Der Dokumentationslauf9a5bca42 scheiterte ausschließlich an einem Tabzeichen in der alten Cacheprosa; dieses wird als reine Markdownkorrektur entfernt.

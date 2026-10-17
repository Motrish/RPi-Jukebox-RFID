# P01a LocalProvider Übergabe

Implementiert wurde ein synchroner, transportfreier `LocalProvider` gegen injizierte Session-, Resolver-, monotonic-Clock- und Capability-Bindings. Der Resolver ist in Python als Callable gebunden und wird mit `libraryId` aufgerufen; damit bildet er die Vertragsoperation `resolve(libraryId)` ab, ohne eine vorhandene Resolverklasse zu behaupten.

Der Adapter nutzt unveränderte A02-Validatoren für Medienreferenzen und IDs; ProviderReceipt und ProviderError besitzen den eigenen P01-Vertrag und werden nicht als vom Store-Resultvalidator akzeptiert behauptet. Er führt Guard-, Lease-, Epoch- und Deadlineprüfungen vor jedem Protokollaufruf aus und prüft die verbleibende Frist auch nach Guard- und Epoch-Lesevorgängen. START erzwingt Single-Track-Optionen und bindet die Wiedergabe an die `addid`-Song-ID. Ein erstmaliger START gilt nur bei frischem Status `play` als bestätigt; ein wiederholter START derselben aktiven Identität darf `pause` beobachten, ohne den Track neu zu starten. Unsichere Wirkungen behalten die Identitätsreservierung bis zu einem bestätigten expliziten STOP. OBSERVE meldet bei `hasError=true` `PROVIDER_STATE_MISMATCH`; ein beobachteter STOP wird weder als natürliches Ende ausgelegt noch zur Freigabe der Reservierung verwendet.

Die vier von Luna neu verfassten Projektdateien sind:

- `src/jukebox/components/local_provider/__init__.py`
- `src/jukebox/components/local_provider/adapter.py`
- `test/local_provider/test_adapter.py`
- `test/local_provider/fixtures/v1.json`

Für lokale Importe lagen zusätzlich A02-Contracts aus dem Integrationsstand `5057f0b60c4e85f595fd09450be8341f1f377c48` im Stage. Diese zwei Abhängigkeitsdateien sind keine Teil des Produkt-Diffs. Beim Bereinigen eines Stage-Endezeilenartefakts wurde nur deren abschließende Zeilenendung normalisiert; der Codeinhalt wurde nicht geändert.

Die gezielten Unit-Tests liefen mit Exitcode 0: 15 Tests decken unter anderem den echten `addid`-Pfad, Wiederholungs-START, reservierte Identität bei unklarer Wirkung, Epoch-Wechsel, Deadlineablauf nach Guard, initial pausierten Status, aktuelle Backendfehler bei OBSERVE, bestätigten STOP und die Bindung von Pause/Resume/Seek an die Song-ID ab. Der RED-Schritt vor der Implementierung lief tatsächlich und endete mit Exitcode 1, weil `LocalProvider` noch nicht importierbar war.

Der gezielte Flake8-Aufruf mit den V3-Regeln (`max-line-length=127`, `max-complexity=12`, die vereinbarten Ignorierungen und `__init__.py:F401`) lief mit Exitcode 0. Es wurde kein Runtime-Anschluss, keine reale Session oder Resolverklasse, kein RPC/MPD-Code, kein Queue-/Thread-/Registry-Verhalten, keine Dependency oder CI-Konfiguration geändert. Es gab keinen Hardwarelauf und keinen vollständigen V3-Checkout; die Übernahme in GitHub und die vollständige Branch-CI liegen bei Root.

Veröffentlichung durch Root: 7ede9cfac2c91f1c889b55d31a938d85e4b560dc, Tree af274160533d8d37dbb4605486447d802a06ac14, PR 9 gegen future3/modern-ui. Compare zeigt exakt vier neue Dateien; alle vier Textinhalte wurden am SHA unverändert zurückgelesen. Root führte dieselben 15 Unittests und gezieltes V3-Flake8 erfolgreich aus. Unabhängiges Review und vollständige CI sind beim Schreiben dieses Checkpoints offen.

## P01a1 Abschlusskorrektur nach Commit 7ede9cf

Der Kontextabschluss wurde Teil der Bestätigungsgrenze. `_session` prüft jetzt Guard, epoch und Frist erst nach normalem Exit von `session.transaction`; ein Exit-Fehler wird weiterhin in sichere Sessionfehler übersetzt. START, PAUSE/RESUME, SEEK und STOP setzen ihre internen Erfolgsmarker erst nach erfolgreicher Rückkehr aus dieser Klammer. Damit bleibt nach einem möglichen Schreibaufruf `_uncertain` gesetzt, bis auch Exit und Abschlussprüfungen gelungen sind. STOP setzt `_confirmed_stopped` ebenfalls erst danach. Ein fehlgeschlagener Abschluss kann daher weder die neue START-Identity zurückrollen noch die STOP-Freigabe vorziehen. OBSERVE gibt bei fehlerhaftem Abschluss keinen CONFIRMED-Beleg zurück.

Die Fake-Session kann nun einen tatsächlichen `SessionFailure` nach erfolgreichem `yield` auslösen oder bei normalem Exit epoch/Clock ändern. Das erste gezielte RED lief mit 20 Tests und Exitcode 1; sechs Assertions scheiterten in den Exitregressionen: initialer START wurde als REJECTED statt UNCONFIRMED gemeldet, Replacement-START stellte die alte Identity wieder her, STOP markierte trotz UNCONFIRMED als gestoppt, und normaler Exit mit epoch-/Fristwechsel lieferte CONFIRMED. Diese Fehler reproduzieren den echten `__exit__`-Pfad des Context-Managers nach den Schreib-/Statuscalls.

Nach der Korrektur liefen dieselben 20 Tests mit Exitcode 0. Sie prüfen außerdem TIMEOUT und UNAVAILABLE beim STOP-Abschluss, dass initialer START trotz Timeout seine neue Identity samt Song-ID für gezielten Cleanup behält, dass Replacement-START nach bestätigtem Alt-STOP keine alte Identity wiederherstellt und dass PAUSE/RESUME/SEEK bei Abschlussfehlern UNCONFIRMED samt gesetzter Unsicherheit bleiben. OBSERVE liefert dann REJECTED statt CONFIRMED. Der gezielte V3-Flake8-Aufruf lief erneut mit Exitcode 0.

Der Prüfstand blieb auf die vier freigegebenen Projektdateien begrenzt; in dieser Korrekturrunde geändert wurden nur `adapter.py` und `test_adapter.py`. Keine A02-Abhängigkeit wurde geändert. Keine GitHub-Mutation, Gesamt-CI, Runtime-/Hardwareprüfung oder neue Schnittstelle wurde durchgeführt. Die vier Projektdateien sind für die Übergabe eingefroren; eine neue Reviewrunde und Veröffentlichung bleiben Root vorbehalten. Ein finaler Runtime-Context-Exit kann nur geprüft werden, wenn die Session ihren Context nach Exit noch als Live-epochquelle zugänglich lässt; genau diese injizierte Vertragsform bildet der Fake ab. Ein blockierender realer `__exit__` wird dadurch nicht unterbrechbar und bleibt der Sessionimplementierung vorbehalten.

## P01a1 abschließender terminaler STOP-Randfall

Eine weitere Regression reproduzierte die Wiederholung eines bereits bestätigten terminalen STOP: `STOPPED`-Status ohne MPD-Schreibaufruf, danach TIMEOUT beim Context-Exit. Der neue Test lief vor der Korrektur tatsächlich rot (1 Test, Exitcode 1): Receipt war STOP_UNCONFIRMED, aber `_confirmed_stopped` blieb true. Dadurch hätte ein neuer START die alte Freigabe benutzt.

Die STOP-Operation setzt `_confirmed_stopped` nun innerhalb des Sessionkörpers wieder auf false, sobald der zugeordnete frische Status stop ohne Fehler bestätigt ist. Erst nach normalem `transaction.__exit__` und den finalen Guard-/epoch-/Deadlinechecks setzt sie den Marker wieder auf true. Der Wiederholungs-STOP-Test wurde grün: der Zwischen-START wird mit EXECUTION_CONFLICT abgewiesen; ein erfolgreicher erneuter STOP gibt danach den neuen START frei. Ein alter/fremder STOP bleibt vor Status-/Mutationszugriff abgewiesen und verändert die aktuell zugeordnete Identity nicht; dafür enthält die bestehende Old-STOP-Regression jetzt eine Zustandsassertion.

Finale Stage-Prüfung nach dieser letzten Korrektur: **21 Unit-Tests, Exitcode 0**, gezieltes V3-Flake8 **Exitcode 0**. Es wurden weiterhin keine Remote-Mutationen oder CI-/Hardwareläufe ausgeführt. Dieser kleine Fix änderte nur `adapter.py` und `test_adapter.py`; alle vier Projektdateien sind jetzt endgültig eingefroren und bereit zur Root-Veröffentlichung sowie separaten Reviewrunde.

Folgecommit 82d9547f5c4431e77ef9312f1ca5fbc1e5fe54d6, Tree e565397f5a125e8c8d13e6db51489912e1d2ecf6: Context-Abschlusskorrektur und enger Stopgate-Fix gemeinsam mechanisch durch Root veröffentlicht. Genau adapter.py und test_adapter.py geändert; beide Inhalte unverändert zurückgelesen. Root 25 Tests und Lint Exit 0. Unabhängiges SHA-Review ohne weitere Sperrbefunde, ebenfalls 25 Tests Exit 0. Vollständige CI des Folgecommits noch queued; keine Integration bis zum Abschluss. Details zum frischen Ownerwechsel und echten RED in p01-stop-gate-report.md.

Abschluss: Pushlauf 38970100321 und PR-Lauf 38970106609 mit allen fünf Pythonversionen und finish erfolgreich. PR 9 am geprüften 82d9547 als 1995a5c21e1e41f33a5cc61c6a27a3f5c803f871 gemerged; Tree e565397f5a125e8c8d13e6db51489912e1d2ecf6 exakt erhalten. Transportfreier P01a1-Slice verified; reale Providerbindung und Hardware bleiben offen. Frühere queued-/Sperrnotizen oben sind historische Checkpoints.

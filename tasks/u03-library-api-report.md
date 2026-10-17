# U03a1 Entwicklungsbericht

## Phase 1 – eingefrorene HTTPtests

Am 17.10.2026 wurde die portable Loopback-HTTPtestsuite in `G:/Entwicklung/phoniebox-staging/u03-api/test/library_api/test_server.py` angelegt. Sie enthält 16 unittest-Fälle für Listen-/Einzelabruf, kanonisches Paging, Host-/Origin-/Bearerablehnung, zweimalige strikte Autorisierung, 900-Sekunden-TTL vor und während einer Bearbeitung, geschlossene Antwortprojektion, sichere Fehler, Routen-/Methoden-/Body-/Header-/Antwortgrenzen, Loopbackbindung und Lebenszyklus des injizierten Katalogs. Die vier von P01b übernommenen Katalog- und Contractdateien liegen als Seedkopien unverändert in der Stage; die drei U03-Produktdateien sind weiterhin abwesend.

Der eingefrorene Testdatei-SHA256 lautet `7B62BB020A94B9B00CBA0E41DB797A8171B101DDF6D213ED868A30740DBF8`. Die isolierte Flake8-Prüfung der Testdatei war erfolgreich. Der tatsächliche Windows-Console-Pytestlauf endete bei der Sammlung erwartungsgemäß rot mit `ModuleNotFoundError: No module named 'components.library_api'`. Damit ist der geforderte lokale RED für diesen portablen HTTPpfad belegt; ein separater Remote-RED wurde gemäß Rootfreigabe nicht benötigt. Der Lauf erzeugte eine lokale `__pycache__`-Datei, die gemäß Stageanweisung nicht bereinigt wurde.

Die Implementierung der drei Produktdateien hat noch nicht begonnen und bleibt bis zur Rootbestätigung dieses Testcheckpoint ausgesetzt.

## Phase 1 – Reviewerkorrekturen

Die Testprüfung vom Root am 17.10.2026 fand doppelte automatische/gesetzte Hostheader, fehlende Zählerbereinigung vor dem zweiten Autorisierungslauf und fehlende Import-/CLI-/Linux-Interopabdeckung. Der HTTPclient sendet nun Host ausschließlich explizit; die Autorisierungstests prüfen getrennt genau zwei Aufrufe. Hinzu kamen unbekannte Methode, doppelter Origin, Connection-close, wirkungsfreier Import, sichere Nicht-TTY-Verweigerung, Ablehnung einer leeren Datenbank vor Listeneröffnung und Linux-only HTTPzugriff auf einen echten temporären Katalog mit registrierter regulärer Datei. Der Linuxfall wird auf Windows ausdrücklich übersprungen und läuft unter Linux als tatsächlicher Interoptest.

Der korrigierte Teststand enthält 20 Fälle. Sein SHA256 ist `8D45DA345C965F9169983A20300DACF83170DB0CB78F0AB9B00ADE04DCA0AB03`. Flake8 bestand erneut; der tatsächliche Console-Pytestlauf blieb vor Produktcode erwartungsgemäß bei `ModuleNotFoundError: No module named 'components.library_api'` rot. Die frühere, inzwischen überholte 16-Fälle-Hashangabe oben bleibt als Verlauf erhalten; dieser Abschnitt ist der aktuelle eingefrorene Stand. Die drei Produktdateien sind weiterhin abwesend.

## Phase 2 – Implementierung und lokale Prüfung

Die drei freigegebenen Produktdateien wurden am 17.10.2026 ergänzt. `make_server(catalog, read_authorizer, port, origin_host)` bindet ausschließlich an `127.0.0.1`, bedient seriell und besitzt den injizierten Katalog nicht. Es gibt nur die zwei geplanten GET-Routen; Listenparameter sind kanonisch validiert, unbekannte Methoden werden mit sicherem JSON-405 beantwortet, HEAD bleibt körperlos. Host und optionale Origin müssen exakt zum gebundenen Authoritywert passen. Ein einzelner `Authorization: Bearer`-Credential wird validiert; der injizierte Authorizer muss bei exakt Boolean-True vor dem Katalogzugriff und nach Projektion/JSONserialisierung zustimmen. `make_read_authorizer` vergleicht das 43-stellige URLsafe-Token mit `compare_digest` und verfällt nach 900 monotonen Sekunden.

Die Antwortprojektion akzeptiert nur die geschlossenen P01b-Felder für Bibliotheksmetadaten, prüft Identifier, Verfügbarkeit und Displayname und erzeugt Fehlertexte ohne Backenddetails. Anfragen begrenzen Target auf 2048 Zeichen, Header auf 8192 Bytes und 32 Felder, setzen 5 Sekunden Socket-Inaktivitätstimeout und verweigern GET-Bodies. Antworten begrenzen JSON auf 256 KiB und setzen JSON, `no-store`, `nosniff`, feste Länge und `Connection: close`. Request-/Fehlerlogs werden unterdrückt. Die CLI verlangt explizite Datenbank, Musikroot und Port; sie prüft SQLite `user_version=1` per `mode=ro`, danach prüft der Katalog sein vollständiges Schema und seine Rootbindung. Sie startet nicht ohne interaktives stdin und stdout, erstellt keinen Ersatzkatalog, scannt/registriert nicht und schließt Server sowie selbst erzeugten Katalog in `finally`.

Der exakte Windows-Console-Aufruf `python -m pytest -q G:\Entwicklung\phoniebox-staging\u03-api\test\library_api\test_server.py` bestand mit **19 passed, 1 skipped, 45 subtests passed**. Der übersprungene Fall ist ausschließlich die Linux-deskriptorbasierte Interaktion mit echtem temporärem `LibraryCatalog`; diese Abnahme muss in Linux-CI tatsächlich laufen. Der nicht übersprungene Windowslauf umfasste echte Loopback-HTTPrequests, Import-/CLIprüfungen, TTL und Parsergrenzen. Die exakte V3-Prüfung `python -m flake8 --max-line-length=127 --max-complexity=12 --ignore=E126,E127,E128,W503,F824 --per-file-ignores=__init__.py:F401 G:\Entwicklung\phoniebox-staging\u03-api\src\jukebox\components\library_api G:\Entwicklung\phoniebox-staging\u03-api\test\library_api` bestand nach dem Komplexitätsrefactor.

Aktuelle Datei-SHA256:

- `src/jukebox/components/library_api/__init__.py`: `F543855FC907CDE27D798970704EB4407D156425C732F77A88D57152012A0B1D`
- `src/jukebox/components/library_api/server.py`: `94326C7911B423C3F3B29609E6AD22F810821C583073D464020FB31560A2C5DE`
- `src/jukebox/components/library_api/__main__.py`: `6C3F89F93E77B3AF2EBA29FE70A6A2266926E5A9302710A87F483A18BDC43328`
- Frozen `test/library_api/test_server.py`: `8D45DA345C965F9169983A20300DACF83170DB0CB78F0AB9B00ADE04DCA0AB03`

Die vier kopierten Seeddateien stimmen bytegenau mit P01b überein: `library_catalog/catalog.py` SHA256 `AC42E035ADF8F9C23232BCB2...`, `library_catalog/__init__.py` `A6AB8559ACA3C4A5E9EBCEA0...`, `contracts/v1.py` `89CEEB1837DBE3DA07EB666B...` und `contracts/__init__.py` `9572D86AD4D8083AA605FDF5...` (jeweils Stage und P01b identisch).

Die lokale Stage belegt Windows-Python 3.12. Linux-Interop wurde hier nicht ausgeführt; keine Linux-CI-, Python-3.9–3.13-Matrix-, Remote-/Geräte-, HTTPS-/nginx- oder LANabnahme wird daraus abgeleitet. Sockettimeout begrenzt Inaktivität, nicht die Gesamtdauer von SQLite-/Dateisystem-I/O; der einzelne serielle Server kann dadurch blockieren. Headergrößen werden nach dem stdlib-Parsing kontrolliert und sind keine vorgelagerte Allokationsgrenze. Diese Entwicklung bleibt ausschließlich für loopbackgebundenen manuellen Devbetrieb bestimmt; Proxy-/HTTPS-/Gerätepromotion bleibt separat.

### Vollständige Seedhashes und ausführbare Prüfaufrufe

Die zuvor abgekürzten Seedhashes lauten vollständig:

- `src/jukebox/components/library_catalog/catalog.py`: `AC42E035ADF8F9C23232BCB26F254CAD9196C401B23DF7213F6DF3FA1C6371C0`
- `src/jukebox/components/library_catalog/__init__.py`: `A6AB8559ACA3C4A5E9EBCEA003145E305202E4E31A3C60FA41232D4BCBF2DC52`
- `src/jukebox/jukebox/contracts/v1.py`: `89CEEB1837DBE3DA07EB666B9DFA1F032AE3E19AC154D29FC621D8CE2FBF3C48`
- `src/jukebox/jukebox/contracts/__init__.py`: `9572D86AD4D8083AA605FDF5165022A79AA3F7B1A5ADBF9E3C4F486E44FADDD8`

Ab Stagewurzel `G:\Entwicklung\phoniebox-staging\u03-api` waren die tatsächlich ausgeführten Prüfungen:

`$env:PYTHONPATH='G:\Entwicklung\phoniebox-tools\pytest-check;G:\Entwicklung\phoniebox-tools\python'; python -m pytest -q 'G:\Entwicklung\phoniebox-staging\u03-api\test\library_api\test_server.py'`

`$env:PYTHONPATH='G:\Entwicklung\phoniebox-tools\python'; python -m flake8 --max-line-length=127 --max-complexity=12 --ignore=E126,E127,E128,W503,F824 --per-file-ignores=__init__.py:F401 'G:\Entwicklung\phoniebox-staging\u03-api\src\jukebox\components\library_api' 'G:\Entwicklung\phoniebox-staging\u03-api\test\library_api'`

Jede der vier Seeds wurde per SHA256 gegen denselben P01b-Pfad verglichen; Stage und P01b stimmen überein.

## Source review – CLI Server-Cleanup-RED

Die serielle Quellprüfung fand, dass der CLI-`finally`-Pfad `_close_quietly(server)` aufruft, obwohl der stdlib-`HTTPServer` die gebundene Socketressource über `server_close()` freigibt. Der Produktcode blieb unverändert. In der bestehenden Suite wurde ein kontrollierter CLI-Lifecycletest ergänzt: ein fester synthetischer Token und ein Fake-Katalog/HTTPserver prüfen normalen `serve_forever`-Rücklauf, `KeyboardInterrupt` und `RuntimeError`; für jeden Fall müssen `server_close()` und Katalog-`close()` genau einmal aufgerufen werden. Das Token bleibt nur in einem TTY-Testpuffer und ist synthetisch.

Der tatsächliche Console-Aufruf nur für diese Regression endete erwartungsgemäß rot: `3 failed, 1 passed`; in allen drei Exitfällen war `server.server_close_calls` `0` statt `1`, an der Assertion in `test_server.py:716`. Der Katalog wurde in jedem Ablauf genau einmal geschlossen. Der neue Teststand hat SHA256 `12BD077D97B1701E0391B0E066CF225910254F959C1C7712420F69A1855B1CF6`; die 20 vorherigen Testfälle blieben im selben Testmodul erhalten. Der Testdatei-V3-Lint besteht. Eine Produktkorrektur wartet auf die Root-RED-Freigabe.

## Source review – Servercleanup korrigiert

Nach Rootfreigabe wurde ausschließlich `src/jukebox/components/library_api/__main__.py` geändert: der CLI-eigene HTTPServer wird jetzt über `server_close()` freigegeben, der vom CLI erzeugte Katalog über `close()`. Verschachteltes `finally` garantiert den Katalogabschluss auch dann, wenn Servercleanup fehlschlägt. Das bestehende Lifecycle-Regressionstestszenario deckt normalen Rücklauf, `KeyboardInterrupt` und `RuntimeError` ab.

Der vollständige tatsächliche Windows-Consolelauf nach dieser Änderung bestand: `20 passed, 1 skipped, 48 subtests passed`. Der einzige Skip bleibt die Linux-only echte Katalog-/Datei-Interopprüfung. Pytest meldete einen Runpy-RuntimeWarning beim Test, der ein bereits importiertes `components.library_api.__main__` erneut als `__main__` ausführt; der Test bestand. Die vollständige V3-Prüfung mit `--max-complexity=12` bestand ebenfalls.

Finale SHA256: `__init__.py` `F543855FC907CDE27D798970704EB4407D156425C732F77A88D57152012A0B1D`; `server.py` `94326C7911B423C3F3B29609E6AD22F810821C583073D464020FB31560A2C5DE`; `__main__.py` `899C48D311C1D376BB6905F623FA203F04CAF793020A9C44B6554319429C55D4`; eingefrorene Testdatei `12BD077D97B1701E0391B0E066CF225910254F959C1C7712420F69A1855B1CF6`.

Ausgeführt ab `G:\Entwicklung\phoniebox-staging\u03-api`:

`$env:PYTHONPATH='G:\Entwicklung\phoniebox-tools\pytest-check;G:\Entwicklung\phoniebox-tools\python'; python -m pytest -q 'G:\Entwicklung\phoniebox-staging\u03-api\test\library_api\test_server.py'`

`$env:PYTHONPATH='G:\Entwicklung\phoniebox-tools\python'; python -m flake8 --max-line-length=127 --max-complexity=12 --ignore=E126,E127,E128,W503,F824 --per-file-ignores=__init__.py:F401 'G:\Entwicklung\phoniebox-staging\u03-api\src\jukebox\components\library_api' 'G:\Entwicklung\phoniebox-staging\u03-api\test\library_api'`

Die 19 früheren positiven Funktionsfälle und ursprüngliche `__main__.py`-Hashangabe oben sind durch dieses Reviewupdate überholt. Linux-CI muss den tatsächlichen Interopfall weiterhin ausführen; ansonsten gelten die zuvor dokumentierten Nicht-Promotion- und Sockettimeoutgrenzen.

## Root-Abnahme und Integration

Root hat den anfänglichen Console-RED und den neuen Lifecycle-RED tatsächlich nachgewiesen; nach engem Fix liefen lokal20Tests plus48Subtests erfolgreich bei genau einem ausdrücklich Linux-only Skip. V3lint einschließlich maxcomplexity12 besteht. Die vier unveränderten finalen Artefakte wurden als34abc741da381564596b947072cb92ca263bf96f veröffentlicht und jeweils identisch zurückgelesen. Beide vollständigen Linux-CI-Matrizen39032712428/39032701807 sind samt Python3.9–3.13, finish und Repositorylint erfolgreich. Tatsächlich gelesenes Log117396235147 enthält196passed und alle21 APIcases einschließlich registrierter echter Tempdatei über LibraryCatalog und LoopbackHTTP. Der dokumentierte Runpy-Warning wurde nicht unterdrückt und ist kein weiterer fehlgeschlagener Test.

PR15 wurde als769a46a31a1fbc423fae4bdda1f78beda6b02ec5 integriert. Root bestätigt den exakt identischen Mergebaum e852667f70781399948ce3fbc76a8f8b7fa8af33; develop blieb42d5023e37dbf8de6477fef5ebcd6eae3cb5087d. U03a1 ist für diese lokale Entwicklungsgrenze verified. React/Same-origin-nginx, produktive Anmeldung/HTTPS, realer Controller und Geräteabnahme bleiben ausstehend; kein kompletter U03- oder Phonieboxpass. Keine echten Produktsecrets in Tools ausgegeben, kein Gerät geändert.

Die erste historische Hashabschrift oben war verkürzt. Tatsächlich eingefrorener initialer Testhash:7b62bb020a94b9b00cba0e41db797a8171b101ddf6d213e23ed868a30740dbf8; nach Testreview8d45da345c965f9169983a20300dacf83170db0cb78f0ab9b00ade04dca0ab03; final nach Lifecycle-Regression12bd077d97b1701e0391b0e066cf225910254f959c1c7712420f69a1855b1cf6. Die vorherigen negativen Prüfschritte bleiben historische Nachweise.

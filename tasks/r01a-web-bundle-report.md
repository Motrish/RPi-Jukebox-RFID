# R01a Phase 1 freeze

Phase 1 contains only the requested test file and workflow edit. `tools/web_bundle.py` is absent. The executable paths are limited to the planned three paths; the product path intentionally has no file yet.

SHA-256 at freeze:

- `test/web_bundle/test_web_bundle.py`: `08090e0ebaa45845536b3cb5838fdc5d9d1a41776c3474e8ac391616eb056ddd`
- `.github/workflows/test_build_webapp_v3.yml`: `f1f15dcbb20c072b69d6db2836cde817626d76693f71b927fdbd798851477788`

Local checks passed on Windows:

- `python -m py_compile test/web_bundle/test_web_bundle.py`
- `$env:PYTHONPATH='G:\Entwicklung\phoniebox-tools\python'; python -m flake8 --max-line-length=127 --max-complexity=12 --ignore=E126,E127,E128,W503,F824 --per-file-ignores='test/web_bundle/test_web_bundle.py:F401' test/web_bundle/test_web_bundle.py`

The unit suite was deliberately not run here. The next required check is the workflow's actual Ubuntu run: the existing web build should succeed, then `python -m unittest discover -s test/web_bundle -p test_web_bundle.py -v` should fail at the absent `tools.web_bundle` import. That is the Phase 1 RED sentinel. Independent test review is also pending.

The product implementation will need the tested CLI shape: `package --build-dir PATH --output-dir PATH --repository OWNER/REPO --commit HEX40` and `verify --archive PATH --manifest PATH --repository OWNER/REPO --commit HEX40`. The boundary tests patch module constants `MAX_FILES`, `MAX_TOTAL_INPUT_BYTES`, `MAX_ARCHIVE_BYTES`, and `MAX_MANIFEST_BYTES`, and call `main(argv)` expecting a nonzero integer on failure. The producer tests inspect only trusted archives it created itself.

The workflow adds the two new paths to both trigger filters, runs the sentinel after Python setup, keeps all current checks, and only then packages, verifies, uploads, downloads by the upload action's artifact ID to a separate runner-temp path, and verifies again. The artifact name includes `git rev-parse HEAD` in full. No release or write permission was added.

## Phase1 tatsächlicher RED und gebündelte Korrektur

Root hat Weblauf39043364778/Job117427131261 gelesen: bisheriger Build und24Jest bestanden, dann ModuleNotFoundError tools.web_bundle im unveränderten setUpClass-Import, Ran0Tests. Pythonlauf39043364773/Job117427131142 endet ebenfalls wegen genau dieses Imports nach186 bestandenen Tests; kein vollständiger Pythonpass. Damit tatsächlicher Missingmodule-Ausgangszustand belegt, keine erneute Voll-RED-Runde für unveränderten frühen Sentinel erforderlich.

Luna hat die fünf Testreviewbefunde gebündelt bearbeitet und die Tests eingefroren: SHA256 c97418b224f198b3781f2345f72f1a87b2cd4fcd9241a0d94ea3294dc580697a. Workflow unverändert f1f15dcbb20c072b69d6db2836cde817626d76693f71b927fdbd798851477788; Producer bleibt abwesend. py_compile und V3flake8 laut Autor bestanden, Root hat den V3flake8pass eigenständig wiederholt. Enges unabhängiges Folgereview läuft. Schreiben dieses Reports war dem Autor verweigert; Root hat ausschließlich diese Prosa ergänzt, keine Codeänderung.

## Phase1 Abschlussentscheidung

Root hat die zwei engen Restbefunde am eingefrorenen Test b1d6a04c44beda12ea1dcce8bef0d2b0372781d637059a2472431e3931cdc02a selbst gelesen: exakte Achtfeldmenge wiederhergestellt, Backslashfixture vor isolierter Steuerzeichenprobe entfernt; nur POSIX-Namenproben werden auf Windows übersprungen, Missing-index bleibt plattformübergreifend. Producer bleibt zu diesem Zeitpunkt tatsächlich abwesend. Alle5P2 samt2Restpunkten geschlossen. Früher unveränderter Import-Sentinel und tatsächlicher Linux-RED reichen nach dem expliziten Planruling; keine Behauptung, die später korrigierten Tests seien schon auf Linux ausgeführt. Phase2 an Luna freigegeben: ausschließlich tools/web_bundle.py. Vollständiger Source-/Testpass einschließlich Linux-Sonderdateiproben folgt vor Integration.

## Phase2 Sourcefreeze und tatsächliche lokale Prüfung

Luna erstellt ausschließlich tools/web_bundle.py, SHA256 b45005aa629c2ed7ed2b66a0bdb02acb3f4f636395d1d84063c3e04df8fc48ee. Tests final b1d6a04c44beda12ea1dcce8bef0d2b0372781d637059a2472431e3931cdc02a, Workflow unverändert f1f15dcbb20c072b69d6db2836cde817626d76693f71b927fdbd798851477788. verify_bundle(archive_path, manifest_path, expected_repository, expected_commit) liefert validiertes Manifest oder BundleError, ohne TARparser oder Extraktion.

Root hat am eingefrorenen Stage alle15 unittests ausgeführt: OK, zwei ausdrücklich auf diesem Windows fehlende POSIX-Namen/FIFO-Proben übersprungen; Symlinkproben liefen erfolgreich. V3flake8 auf Tool und Tests bestanden. Luna meldet zusätzlich py_compilepass. Keine Linux-/Gerätebehauptung daraus.

Exakt3Dateien mechanisch auf vollständigen vorhandenen Baum übernommen: Head eebe58ae1c254abbabf7724b8dae681001ae1ee1, Baumad4360507504956274fdb02224399e56445c0203, PR18. Alle3vollen Remoteinhalte bytegleich zurückgelesen und Featurehead bestätigt. Unabhängiger frischer Sol-Sourcereviewer arbeitet erst nach Luna-Freeze; tatsächlicher Weblauf39044139548 und Pythonläufe39044143182/39044139474 starten am exakten Head. Bestehender Produktbranch6b bleibt während Abnahme unverändert.

## Enger Workflowfolgebefund und Korrektur

Unabhängiges vollständiges Sourcereview findet genau1P2, keine weiteren P1/P2 in Producer, Prüfer oder Tests: actions/download-artifact@v4 legt bei artifact-ids ohne merge-multiple die Dateien im Artefaktnamen-Unterordner ab, der nachfolgende Prüfer erwartet direkte Downloadpfade. Offizielle Implementierung und Bericht: r01a-web-bundle-source-review.md. Luna ergänzt ausschließlich merge-multiple: true. Root hat durch Entfernen exakt dieser einen Zeile Bytegleichheit zum vorherigen Workflow geprüft; keine anderen Änderungen.

Realer erster Weblauf39044139548/Job117429395004 bestätigt:15/15 neue Tests auf Linux ohne Skips bestanden; alle bisherigen Build-/Jest-/Vertrags-/Chromium-/nginxschritte bestanden; echtesCRA-Archiv1370736Bytes, SHA256 dc82205b56e1269b9b5ee17be5d1e6f5384a368c495f9f69a5394f185fe5e652 für eebe58ae... erstellt und vor Upload erfolgreich geprüft; Upload12105610434 und Download gelingen, erneute Prüfung scheitert erwartungsgemäß mit manifest could not be read. Dieser Lauf ist insgesamt failure, kein vollständiger Webpass.

Finale KorrekturSHA642023df7bd55e0fc15040fcef42afcc758e6f1f, Baum3da2f3b54aaa9fb137dcc9bf51b41f8c0e05d485. WorkflowSHA256 b4ff2aa2517d9c36c5302a8f6676b693850611e29d321412b0ad092a8f2e0035, Source/Testhashes unverändert. Alle3Remoteinhalte erneut bytegleich zurückgelesen. Unabhängiger enger Folgepass schließtP2; tatsächlicher Weblauf39044317830 und neue Pythonmatrizen bleiben vor Integration abzuwarten. Keine redundante lokale Wiederholung für reine Einzeilen-Workflowkorrektur; veränderten realen Rundlauf übernimmt CI.

## Sourceabnahme und Integration

Finaler Weblauf39044317830/Job117429904263 ist tatsächlich completed/success:15/15Linux-Bundletests ohne Skips,24Bibliotheks-Jest,22Python- und12JS-Verträge, alle3bestehenden Chromium/nginxprüfungen und echterCRA-Paket-/Upload-/Download-/Prüfrundlauf. Archiv1370736Bytes, SHA256 dc82205b56e1269b9b5ee17be5d1e6f5384a368c495f9f69a5394f185fe5e652. Dieselbe erwartete Forkidentität und voller Sourcecommit642023df... werden vor Upload und nach Download bestätigt. Artefakt12104738430, Name phoniebox-webapp-642023df7bd55e0fc15040fcef42afcc758e6f1f, nicht abgelaufen, läuft24.10.2026ab. ZIP-Containerdigest4c86c6142f24427e90a623a43cb1224d189bda89d1964fb67dd1d076b4f44127 ist ausdrücklich nicht der innere Archivdigest.

Python-PR-Lauf39044321784 besteht tatsächlich3.9,3.10,3.11,3.12,3.13 undfinish. Jobs117429916510/305/517/532/519 und117430580608 jeweilscompleted/success. Vollständiger3.9Log:211Prüfungen bestanden. Die vorherigen Push-/PRmatrizen39044139474/39044143182 bestanden ebenfalls, enthalten aber den älteren Workflowhead; am reinen Workflowfix wurde nur der PR-Pythonlauf ausgelöst, kein zweiter Pushlauf behauptet.

Root hat Mergefähigkeit, unveränderte Basis6b872011, Reviewabschluss und genauenSourcebaum geprüft, PR18 ready gesetzt und mit erwartetem Sourcehead integriert. Merge fc995afb397164364541e53fd6c7dd4bed79c0e9 besitzt exakt Eltern6b872011.../642023df... und identischen geprüften Baum3da2f3b54aaa9fb137dcc9bf51b41f8c0e05d485. Produktref bestätigt; develop unverändert42d5023e37dbf8de6477fef5ebcd6eae3cb5087d. PRdiff besteht genau aus3Whitelistpfaden. Integrations-Weblauf39044627838 muss jetzt ein Manifest für den neuen Mergecommit selbst erzeugen; Python39044627823 läuft ebenfalls. Diese automatisch gestarteten Läufe sind noch kein weiterer Passnachweis.

## Verifizierter Integrationscommit

Am Merge fc995afb397164364541e53fd6c7dd4bed79c0e9 bestehen nun auch tatsächlich Web39044627838/Job117430793469 sowie Python39044627823 (alle3.9–3.13 undfinish117431333968) vollständig. Neues Bundle12104499265 heißt phoniebox-webapp-fc995afb397164364541e53fd6c7dd4bed79c0e9 und bindet im Manifest exakt diesen Integrationscommit und Motrish/RPi-Jukebox-RFID. Archivdigest dc82205b56e1269b9b5ee17be5d1e6f5384a368c495f9f69a5394f185fe5e652,1370736Bytes; vorUpload und nachDownload erfolgreich geprüft. Authentifiziertes CI-Artefakt, Ablauf24.10.2026 15:22UTC. Damit R01a als begrenzter Producer-/Prüfer-/CI-Lieferslice verified/integrated. VollständigesR01, sichere Extraktion, anonymer Lieferweg, Installation, LAN undGerät bleiben offen. R01b startet separat mit genau2neuen Pfaden und frischer Luna-Testphase.

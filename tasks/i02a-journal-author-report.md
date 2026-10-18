# I02a Autorenbericht

Autor: Luna. Basis 741085f902c88aaa2fa74ef5dcd473ba993427e3. Ausschließlich installation/websetup/jobs.py, test/websetup/test_jobs.py und die drei neuen Pfade in beiden Triggerfiltern des vorhandenen Webworkflows. Ollama-Vertragstests separat durch Root übernommen.

## RED und Umsetzung

Tatsächlicher RED vor jobs.py: im Teilstage python -B -m unittest discover -s test/websetup -p test_jobs.py. ImportError: cannot import name jobs from installation.websetup; eine Modulkollektion, null ausgeführte Tests. Der zuvor verwendete Aufruf test.websetup.test_jobs hatte einen falschen Discoverypfad und gilt nicht als RED. Root übernimmt diese vom Autor gemeldete Ausführung; der Koordinator hat die historische Reihenfolge nicht erneut ausgeführt.

17 Autorentests: geschlossenes Snapshotformat/JSON und defensive Kopien; Eingaben; gleicher Auftrag nach Fortschritt/Abschluss und abweichender Inhalt; aktiver Konflikt und Wiederverwendung abgelehnter ID; geordnete Schritte und dauerhaftes Intent; Revisions-/Übergangskonflikte; fehlgeschlagener Schritt mit Erhalt vorheriger Bestätigungen; explizite Recovery nach Wiederöffnung, idempotente Wiederholung, kein automatischer Neustart; terminale Persistenz; Threadrennen; zwei echte Windows-spawn-Prozesse für einen Auftrag; SQLite-Trigger als Rollbackfehler; fremdes Schema; kontrollierter Revisionsüberlauf.

Der Trigger BEFORE UPDATE ON jobs erzeugt einen privaten Fehlertext; erwartet STORE_UNAVAILABLE, keine Textweitergabe und unveränderten Zustand. Recovery simuliert Wiederöffnung eines RUNNING-Jobs und explizite Reconciliation. Kein Kill-at-commit-Test und kein Hardwarecrashnachweis.

## Ursprüngliche Verifikation

17 neue Journaltests bestanden. Autor-Aufruf im test/websetup-Verzeichnis: python -B -m unittest test_jobs test_preflight test_bundle test_launch; 78 Tests, fünf erwartete Windowsskips. V3-Flake8 bestanden. Root prüft die endgültige gesamte Testsuite nach Reviewfixes erneut.

Ursprünglich eingefrorene SHA-256: jobs.py 36c792495e95fdd5a62542c6ff2bcc9bbc48e16fa5c5e370a7addea1c73fe6e8; test_jobs.py 8e7073f044143f6d2d78f75010fcb787c1f7c786ccbfb1260d138ef625cd57ad; Workflow ed3eb07b8a4af078137af89522e8e1ea2faa4ac7eb1c39cfd524e1bee1ad0461. Dies sind die Erstabgabehashes, keine Behauptung über noch ausstehende Reviewfixes.

## Einschränkungen

Keine HTTP-/Worker-/Privilegeintegration, keine realen Konfigurationswirkungen. Früherer Worker muss vor Recovery unabhängig sicher beendet sein. Vollständiger Checkout und Linuxregressionen folgen erst in CI. Autorbericht war nach fehlerhaftem PowerShell-Here-String zunächst leer; Root erkannte dies durch tatsächliche Längenprüfung und schrieb diesen Bericht aus der nachgereichten Autorennachricht.

## Endgültige Korrekturen nach Review und CI

Beide P2-Korrekturen von Luna: None als Fehlercode vor Transaktion abweisen; eigene kanonische Schemaobjekte exakt prüfen und fremde Definitionen ohne Mutation ablehnen. Zusätzliche Regressionen: None bewahrt aktiven Slot; falscher Revisionstyp bewahrt Datei; konkurrierende Revision besitzt einen Gewinner. Starker Rollbacktest benutzt AFTER UPDATE/RAISE(FAIL), danach Trigger entfernen und unveränderten Snapshot erneut öffnen. 20 Autorentests plus vier lokale Qwen-Tests.

Vollständige pytest-CI zeigte anschließend einen Importkonflikt im multiprocessing-Test. Gezielte Luna-Korrektur ausschließlich im Test: zwei echte unabhängige Python-Kinder mit festem Code, expliziten Argumenten, JSON-Ausgaben, begrenztem Warten und Aufräumen; keine Auslassung oder Zeitverlängerung. Lokales pytest war nicht installiert und wird nicht als lokaler Nachweis behauptet. Reviewer und Root bestätigen 24 Tests und Flake8; endgültiger pytest-Nachweis folgt im vollständigen CI-Checkout.

Endgültige SHA-256: jobs.py c405d623c1a224b73fdc82abe556ea88a4c0b5a634a6221304374c3b030d22e0; test_jobs.py 4c36000b57c7cc93632a5c744c291467828d739d4d4a60f3b267bfe43dd2cf9c; Qwen-test_job_contract.py 7771d77a77edd750b6adee98366b26406e5939cdb39d139673791316959839df; Workflow ed3eb07b8a4af078137af89522e8e1ea2faa4ac7eb1c39cfd524e1bee1ad0461. Finaler Sourcecommit 2045a753435c952731d9ee577530dfe956a1cb2c.

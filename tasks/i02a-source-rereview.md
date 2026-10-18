# I02a – scoped Nachreview

Reviewer gpt-6.1-sol: APPROVE für die exakt eingefrorenen vier Dateien. Beide P2 behoben, keine neue wichtige Abweichung in den Fixes. Kein ausführbarer Code durch Sol erstellt.

fail_step mit None wird vor der Transaktion abgewiesen; Regression belegt INVALID_REQUEST und unveränderten RUNNING-Snapshot. Initialisierung vergleicht kanonische Definitionen der eigenen Tabellen und des aktiven Indexes, unbekanntes Schema wird abgewiesen. Regression mit falschem Revisionstyp bewahrt die Datenbank bytegleich. Reviewer bestätigte separat auch Ablehnung eines falsch definierten aktiven Indexes ohne Dateiänderung.

Dauerhafte Tests für gleichzeitigen Übergang auf derselben Revision und Rollback nach AFTER UPDATE/RAISE(FAIL) schließen die früheren Nachweislücken. Reviewer führte 24 Journal-/Vertragstests unabhängig aus: alle bestanden. Root führte endgültige gesamte Setup-Discovery aus: 85 Tests, fünf erwartete Windowsskips; Flake8 bestanden. Vollständiger CI-Checkout bleibt Integrationsgrenze.

Endgültige SHA-256: jobs.py c405d623c1a224b73fdc82abe556ea88a4c0b5a634a6221304374c3b030d22e0; test_jobs.py 596de117f9a78aa06eed611d07030d52d8e65355df27e8b5171ad0b03e96b2e7; Ollama-test_job_contract.py 7771d77a77edd750b6adee98366b26406e5939cdb39d139673791316959839df; Workflow ed3eb07b8a4af078137af89522e8e1ea2faa4ac7eb1c39cfd524e1bee1ad0461. Alle vier vom Reviewer geprüft und nach Commit 01359cc3800d86ba8150705ad0b1ecd65c393972 von Root remote exakt zurückgelesen.

## CI-Testkorrektur

Vollständiger pytest-Checkout zeigte einen Importkonflikt des Spawn-Pickletargets test.websetup.test_jobs mit dem Python-Testnamensraum; direkte unittest-Discovery im vollständig erfolgreichen Weblauf39100155111 war nicht betroffen. Beide Pythonmatrizen scheiterten am selben Prozessprüfungs-Harness,285übrigeTests bestanden. Luna ersetzte nur diesen Harness durch zwei gleichzeitig gestartete unabhängige Python-Popen-Kinder mit festem Code, expliziten JSON-/Pfadargumenten und begrenztem Abwarten/Aufräumen. Kein Skip, kein erhöhter Timeout, kein Produktionscode geändert.

Scoped 6.1-sol-Review: APPROVE. Beide Prozesse starten vor dem ersten Warten und müssen dieselbe Job-ID liefern; terminate/kill/reaping sind begrenzt. Reviewer und Root führten24Tests erfolgreich aus; Root-Flake8 bestanden. Endgültiger test_jobs.py-Hash4c36000b57c7cc93632a5c744c291467828d739d4d4a60f3b267bfe43dd2cf9c. Sourcecommit2045a753435c952731d9ee577530dfe956a1cb2c; exakt zurückgelesen. Tatsächliches pytest-Integrationsergebnis noch in neuer CI zu bestätigen.

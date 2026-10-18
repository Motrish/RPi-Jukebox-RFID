# I02b1 Autoren- und lokaler Prüfnachweis

Basis ec56e0c18f73009de6ff7a3d215bd6d5c7061688. Komplexe Implementierung und Tests durch Luna, drei kleine portable Vertragstests durch lokales qwen2.5-coder:14b. Root übernahm lokale Modellantworten nur in die fest zugewiesene Datei und entfernte abschließend Whitespace einer leeren Zeile. Keine funktionale Logik durch Sol geschrieben.

## Test-first und Erstabgabe

Luna meldete tatsächlichen RED: python -m unittest discover -s test/websetup -p test_worker.py -v scheiterte am fehlenden worker-Modul; test_jobs.py führte22Tests aus, zwei neue wait_for_inspection-Fälle scheiterten an der fehlenden Methode. Dies ist historischer Autorenbeleg, nicht vom Root nachträglich reproduzierter Ablauf.

Root bestätigte nach Erstabgabe und finalem kleinen Qwen-Test: python -B -m unittest discover -s test/websetup -p test_*.py -q,105Tests,19erwartetePlattformskips. V3-Flake8 für die fünf Pythondateien bestanden. Neue reale Worker-/flock-/Killprüfungen wurden unter Windows nicht ausgeführt und werden nicht als bestanden behauptet. Das separate WSL-Startup des Autors war nicht zulässig; keine weitere WSL-Wiederholung, tatsächliche Linuxprüfung im vollständigen GitHub-Checkout.

## Unabhängige Korrekturgrenze

6.1-sol-Erstreview meldete vier deterministische Linux-Testfehler in drei Fixturegruppen und zwei Fehlergrenzen der Infrastruktur; zusätzlich fehlte der robuste Nachweis tatsächlicher beobachteter Marker und dauerhaftem Intent vor Wirkung. Vollständiger Bericht i02b-source-review.md. Fixrunde1 ist auf worker.py und test_worker.py begrenzt; Journalmethode, ihre Tests, Workflow und Qwen-Vertragstests bleiben eingefroren. Kein Push der nicht freigegebenen Erstabgabe.

Endgültige Nachweise, Hashes, unabhängiges Nachreview und vollständige Linux-CI werden erst nach tatsächlicher Ausführung ergänzt. Kein produktiver Handler, keine Privilegien oder Geräteänderung.

## Korrigierte und eingefrorene Abgabe

Alle sechs Erstbefunde wurden im begrenzten Worker-/Worker-Testdiff behoben. Nachreview fand anschließend nur einen Marker-Polling-Race. Eigentümerschaft für diese einzelne Korrektur ging nach dem Einfrieren von Luna an lokales Qwen; Root änderte nur die Darstellung der vom Modell gelieferten Zeile, keine funktionale Logik. Frühere lokale Modellkandidaten mit falscher Operatorbindung wurden verworfen. Endgültig gilt die Deadline für fehlende und noch unvollständige Marker. Reviewer rekonstruierte durch Rücktausch genau einer Bedingung den vorherigen Hash und bestätigte so den engen Diff.

Finale statische Freigabe: APPROVE durch6.1-sol. Root bestätigte106Setupprüfungen mit20Plattformskips und Flake8. Das reale Linux-Ergebnis bleibt bis zum vollständigen CI-Lauf offen.

SHA-256: worker.py ab57e1e87a774c209996f1160eaccfd5e582f3a42c756961598d13c9a1db3c44; jobs.py28026e60796bdaa97ce1054c0a1872cd8085fce144f2899d9a13c5a57387b352; test_worker.py55ac78731ecbdc6f60eaaa48b57a0497afa5870a8a3755937d9ce56f4f7274d4; test_jobs.py12b6a73100821fd301b340ff62641541cfd81ee70c16b9fcfb8c78027c9d1f53; test_worker_contract.pya15bf7efdaddb8d656fbdfcdc227d5f4b93cde707823b10b63a026663afa1b23; Workflow b50aa07f34bdcc586eb416e39cc5a74c13a419e0293d2c498ece6a3ae36b34a0.

Source6c378a67570ab04d51e374dd12f177d706573eba, Treec89937c1d56f614d0c7b1806e875a84bf954e34e, PR22. Exakt sechs erwartete Pfade, alle Remoteinhalte unverändert zurückgelesen. Vollständiger Checkout läuft in CI. Keine tatsächliche Systeminstallation oder Geräteänderung.

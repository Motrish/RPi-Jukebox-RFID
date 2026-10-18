# I02b1 – Integrationsnachweis des Worker-Kerns

Stand: Source vollständig geprüft und [PR22](https://github.com/Motrish/RPi-Jukebox-RFID/pull/22) als55b472b8c7191adea3288d3352a18b982c0fc216 nach future3/modern-ui integriert. Merge-Web- und Python-CI ebenfalls vollständig bestanden. Gesamtinstaller, privilegierte Handler und Webanschluss bleiben offen.

## Verhalten und Grenzen

Der neue Linuxworker bearbeitet pro Aufruf höchstens einen bereits persistenten Setup-Schritt. Eine nichtblockierende Prozesssperre wird aus dem kanonischen DB-Pfad abgeleitet, über Lesen/Recovery/Intent/Wirkung/Beobachtung/Commit gehalten und über einen eigenen Dateideskriptor freigegeben. Die Lockdatei wird nicht gelöscht. Änderungen von DB-/Leaseidentität, uninitialisierte Datenbanken und ungeeignete Pfade werden kontrolliert abgewiesen.

Persistiertes Intent entsteht vor dem internen synchronen apply. Dessen Rückgabewert gilt nicht als Bestätigung; eine neue unabhängige observe-Ausführung entscheidet über bestätigte Wirkung, Fehler oder WAITING_USER. Unterbrochene Schritte werden nur beobachtet und nie automatisch wiederholt. Neue Journalmethode wait_for_inspection hält unklare Wirkung ausdrücklich fest. Jeder Handler erhält eine unabhängige Konfigkopie; Fehler bleiben typisiert und Rohkontext wird unterdrückt.

Dies ist ein transportfreier Kern mit synthetischen Testhandlern. Verbindliche Voraussetzungen: vertrauenswürdiges privates lokales Stateverzeichnis, unveränderte Pfadkette, alle relevanten Writer unter demselben Workerbesitz, synchrone Handler ohne überlebende Hintergrundarbeit. Die Sperre ist keine Sandbox und kein Fencing gegen privilegierte Angreifer oder überlebende Kindprozesse. Produktive Paket-/Audiohandler benötigen vorher ihre eigene Privilegien- und Prozesslebenszeitgrenze. Kein HTTP-Endpunkt, Dienst oder echter Installationsschritt wurde aktiviert.

## Herkunft und abgegrenzte Dateien

Basis ec56e0c18f73009de6ff7a3d215bd6d5c7061688. Source6c378a67570ab04d51e374dd12f177d706573eba, Treec89937c1d56f614d0c7b1806e875a84bf954e34e. Genau sechs Pfade: worker.py, jobs.py, test_worker.py, test_jobs.py, test_worker_contract.py in den bestehenden websetup-Verzeichnissen sowie der vorhandene Webworkflow. jobs.py ergänzt ausschließlich die neue Warteentscheidung; test_jobs.py nur zwei zugehörige Regressionen. Workflow nur sechs Pfadfilterergänzungen, bestehende Discovery bleibt erhalten. Vollständiger Basisbaum erhalten, alle sechs Remoteinhalte exakt zurückgelesen.

Luna schrieb komplexe Laufzeit und Tests. Lokales Qwen2.5-Coder14B schrieb drei kleine Vertragstests und nach expliziter Eigentumsübertragung eine einzige Pollingkorrektur. Root orchestrierte mechanische Übernahme und minimale Whitespaceformatierung. 6.1-sol prüfte Architektur, Gesamtänderung und Korrekturen unabhängig. Kein Astra, kein Sol als Autor ausführbarer Logik.

## Review und tatsächliche Ausführung

Erstreview REQUEST CHANGES: vier Linux-Testfehler in drei Fixturegruppen, fehlende Redaktion zweier Infrastrukturgrenzen und unzureichender beobachteter Crashnachweis. Fixes auf worker.py/test_worker.py begrenzt. Nachreview verlangte noch die sichere Abfrage vollständigen Markerinhalts statt bloßer Dateiexistenz. Endgültige lokale Modellzeile schützt fehlende und teilweise geschriebene Marker durch dieselbe Deadline. Verwerfene falsche Zwischenkandidaten wurden nicht veröffentlicht. Finaler statischer Review APPROVE; Reviewer rekonstruierte den Vorgängerhash durch Rücktausch genau einer Bedingung.

Root bestätigte106lokaleSetupprüfungen mit20Plattformskips und Flake8. Dies allein ist kein Linuxnachweis. Tatsächlicher vollständiger Linux-Checkout: Python3.11-Job117689775057 bestätigt307bestandeneTests und288Subtests, eine bereits bekannte library-CLI-runpy-Warnung. Alle16Workerfälle bestanden, darunter echte gegenseitige Prozesssperre, beide Killgrenzen, frischer unabhängiger Journalread vor Wirkung, beobachtete Marker, keine erneute apply-Ausführung, Rebinding, FD-Fehler und Ausnahmefreigabe. Source-Web39132297782 und beide vollständigen Pythonmatrizen39132297648/39132301241 erfolgreich einschließlich3.9–3.13 und finish117690548958/117690448214. Alle erforderlichen Source-Jobs wurden mit tatsächlichem Endstatus gelesen.

## Nachfolgende notwendige Arbeit

I02b2 benötigt den separat laufenden Workerhost und seine Privilegien-/Prozesslebenszeitgrenze. Ein künftiger synchron aufgerufener Paketprozess kann beim Tod seines Elternworkers trotzdem weiterlaufen; vor echten Paket-/Systemhandlern muss daher ein nachgewiesener Ausschluss überlebender Arbeit hinzukommen. Bestehende Playerunit darf dafür nicht unverändert übernommen werden. Anschließend geschützter Webanschluss und I03-Audio-/RFID-/Dateipfadschritte, jeweils begrenzt und mit unabhängiger Abnahme.

Keine Geräte-, Konto- oder Releaseaktion. Ein echter Zero-W-/MiniAmp-/PiSugar-Aufbau auf separater SD bleibt eine eigene Hardwareabnahme.

## Verifizierte Integration

Merge55b472b8c7191adea3288d3352a18b982c0fc216 enthält exakt Basisec56e0c18f73009de6ff7a3d215bd6d5c7061688 und reviewedSource6c378a67570ab04d51e374dd12f177d706573eba als Eltern. Treec89937c1d56f614d0c7b1806e875a84bf954e34e ist gleich der freigegebenen Source. Produktref zeigt auf diesen Merge, develop unverändert42d5023e37dbf8de6477fef5ebcd6eae3cb5087d. Tatsächlicher Merge-Web39132678457 und Merge-Python39132678449 sind vollständig erfolgreich, einschließlich3.9–3.13 und finish117691637274.

## Abschließende Abnahme und Artefakt

[Source-Web](https://github.com/Motrish/RPi-Jukebox-RFID/actions/runs/39132297782), [Source-Python1](https://github.com/Motrish/RPi-Jukebox-RFID/actions/runs/39132297648) und [Source-Python2](https://github.com/Motrish/RPi-Jukebox-RFID/actions/runs/39132301241) vollständig bestanden. Auch [Merge-Web](https://github.com/Motrish/RPi-Jukebox-RFID/actions/runs/39132678457), Job117690871657, und [Merge-Python](https://github.com/Motrish/RPi-Jukebox-RFID/actions/runs/39132678449) mit allen fünf Versionen und finish117691637274 sind vollständig grün. Endstatus aller relevanten Jobs tatsächlich ausgelesen;106Linux-Setuptests und307Gesamttests samt echten Prozess-/Killfällen bestätigt. Bekannte vorbestehende library-CLI-runpy-Warnung bleibt dokumentiert.

Passendes Bundle zur Mergeidentität55b472b8c7191adea3288d3352a18b982c0fc216: Artefakt12138531831, ZIP1371591Bytes, inneres Archiv1370736Bytes, SHA-256 dc82205b56e1269b9b5ee17be5d1e6f5384a368c495f9f69a5394f185fe5e652. Identität und Artefaktrundlauf tatsächlich geprüft. Ablauf25.10.2026,13:44:03UTC, GitHublesezugang nötig; kein veröffentlichtes Release.

Die zusätzlich automatisch gestarteten alten ARMv7-Installersmokes39132297677/39132678458 waren beim Nachlesen noch in_progress. Sie sind ein separater Bestandsinstaller-Nachweis, keine globale Passbehauptung und kein ARMv6-/Trixie-/Gerätebeleg. Keine weiteren Tests manuell wiederholt.

I02b1 als abgegrenzter unprivilegierter Softwarekern verified/integrated. I02 als Gesamtauftrag bleibt in_progress. Nächster begrenzter Auftrag ist die Workerhost-/Privilegien-/Prozesslebenszeitgrenze, danach geschützter Webanschluss. Keine Hintergrundworker dieses Entwicklungsauftrags aktiv, keine Geräte-/Konto-/Releaseänderung.

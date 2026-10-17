# I01a – unabhängiges Review des lesenden Preflight

Stand: 17.10.2026. Vier eingefrorene Stagedateien geprüft gegen `i01-bootstrap-seam-plan.md`. Root meldet Veröffentlichung als PR 13, Head `04cf12d9c9f6cff4090d32a5b75946af9a824fc6`, Tree `315be0d79a79e6465ab4031febe1b8ff7157b656`; kein eigener vollständiger Vier-Blob-Remoteabgleich in diesem lokalen Review behauptet. **Ein P2-Collectionbefund offen; vor Freigabe serieller Autorfix und tatsächliche vollständige CI erforderlich.**

## P2 – Console-pytest kann die Namespacequelle nicht importieren

`test/websetup/test_preflight.py:10` importiert installation.websetup ohne den Repositoryroot ausdrücklich bereitzustellen. unittest läuft vom Repository-/Stageroot und findet die Namespacequelle. Der tatsächliche bestehende Runner verwendet hingegen Console-pytest; pytest.ini setzt importlib-Modus. Root-conftest.py erweitert sys.path nur um src/jukebox, nicht um den Repositoryroot. Gepinnte Quellen am veröffentlichten Head gelesen: run_pytest.sh Blob c944419ae82046633fd3711d7a3e443d14b836e7, pytest.ini 031a084ad1c1a05c36e850046401317a6bfb0d40, conftest.py b8ff16f0613cf9748ce7b22ec29b6cbe40dd7faa und Pythonworkflow c18c45005f6a402e10e12f8f24e85e1792144e42. Im Workflow kein ausgleichender Repositoryroot-PYTHONPATH.

Konkreter unabhängiger Nachweis am geprüften Stage: Mit Roots ausdrücklicher Erlaubnis pytest 9.1.1 isoliert unter `G:/Entwicklung/phoniebox-tools/pytest-check` installiert; keine Projektdatei geändert. Cwd `G:/Entwicklung/phoniebox-staging/i01a`, PYTHONPATH ausschließlich auf dieses Toolverzeichnis, PYTHONDONTWRITEBYTECODE=1. Tatsächlicher Consoleaufruf:

`G:/Entwicklung/phoniebox-tools/pytest-check/bin/pytest.exe --import-mode=importlib -p no:cacheprovider --collect-only -q test/websetup/test_preflight.py`

Ergebnis: Exit 1, ModuleNotFoundError: No module named 'installation', null Tests gesammelt. Dies ist ein tatsächlicher Console-RED im Teilstage, kein behaupteter bereits gelesener vollständiger CIfehler. Die vollständigen CI-Läufe bleiben separat. Der enge Autorfix gehört in die Testdatei: Rootpfad vor dem Import ausdrücklich bereitstellen, entsprechend vorhandenen Contracttests; keine globale pytest-/CI-Ausnahme und keine geänderte Produktschnittstelle.

## Geprüfte Freezehashes und vorhandene Tests

| Datei | Unabhängig errechneter roher SHA256 |
| --- | --- |
| installation/websetup/preflight.py | 6f0701f8011eb897bfd6ea89426bb0b18295b1eea1cdb82dd58684f467faa9e2 |
| installation/websetup/server.py | f096492335fb8135c5b3fb246acd4c98d7ddc9925bd17526d10d3ead0289818e |
| installation/websetup/index.html | 87a46a6bc535c671800e449242a97ce4ca99736f1dc58d208ac21f9ad17b9aea |
| test/websetup/test_preflight.py | 59d8869e9dfee4657ad55c2c574825a97764ed01d0c3e038950053d797390a2e |

Unabhängig vorhandene Tests ausgeführt: `python -B -m unittest discover -s test/websetup -p test_preflight.py -v`, Stage als cwd. **10 Tests, Exit 0.** Der unittest-PASS hebt den Collectionbefund nicht auf.

## Sonstiger enger Quellbefund

Keine weiteren Blocker im geprüften lesenden Slice gefunden. OSrelease wird begrenzt als Daten geparst; keine Shell-/Konfigauswertung, kein sudo/subprocess, keine Geräte-/Playerimporte, Paketinstallation oder Dienstmutation. Datei-/Settingsmarker verwenden stat: fehlende Pfade ergeben beobachtet false, Permission-/OSfehler unknown mit eigenem sicheren Grund. .gitkeep allein gilt nicht als installierte YAMLkonfiguration; unbekannte Einzelmarker bleiben unterscheidbar. Testdaten/Antworten enthalten keine Konfiginhalte, Dateipfade oder Rawexceptions.

Server bindet ausschließlich an IPv4loopback. GET prüft genau einen erlaubten Host, gegebenenfalls gleichoriginigen Origin und relative feste Zielform vor Reporterzeugung. Fremde/mehrfache Hosts und Origin, absolute Ziele und Queries werden vor report_factory abgewiesen; zwei feste Lesepfade, keine freie Dateiauslieferung/Installmethode und keine CORSfreigabe. Der vorhandene Zählertest beweist für seine Badrequestfälle, dass kein Reportprobe aufgerufen wird. Frontend verwendet textContent und meldet ausdrücklich „Noch keine Konfiguration“; kein Build/Node/Remoteasset nötig.

Quellformen verwenden stdlib und keine erkennbar erst nach Python3.9 eingeführte Syntax/API. Ein echter Python3.9-Matrixlauf und ARMv6-Ausführung werden hier nicht daraus abgeleitet. Unbekannte OS-/Hardwarewerte bleiben Fakten mit unknown statt pauschalem Unterstützungsversprechen. Die von Luna berichteten Browserbilder sind Entwicklungshostnachweise, keine eigene Sichtprüfung dieses Reviews und kein Gerätebeleg.

Abschluss: nach P2-Autorfix gezielte Collection erneut und vollständige Python-CI am neuen SHA nachweisen. Gesamt-I01, LAN-/Einmalzugang/HTTPS, privilegierter Worker, vorgebautes Vollbundle und echte Zero-W-/OS-/SD-Abnahme bleiben offen. Keine Produkt-/Test-/CI-Datei durch den Reviewer verändert. Außer der ausdrücklich genehmigten isolierten Toolinstallation nur Quellen gelesen, vorhandene Tests ausgeführt und dieser Prosa-Bericht geschrieben. Weitere Suche beendet.

## Root bestätigt vollständigen CI-RED

Nach Abschluss der lokalen Probe hat Root die tatsächlichen GitHublogs gelesen: Lauf 39027502923 / Job 117381281843 (Python3.12) und Lauf 39027505383 / Job 117381288907 (Python3.10) melden jeweils „collected 142 items / 1 error“, an test/websetup/test_preflight.py:10 ModuleNotFoundError: installation. Damit ist der P2 auch im vollständigen Checkout belegt, nicht nur in der lokalen Consoleprobe. Root hat den Test-only-Fix bereits an Luna übergeben. Keine weitere Review-/Sucharbeit durchgeführt.

## P2 geschlossen am Folgesha 9883657b61c34ba0dbe2ea279ec01d1a79ce236a

Unabhängig den veröffentlichten Vergleich zum ursprünglichen Head 04cf12d9c9f6cff4090d32a5b75946af9a824fc6 gelesen: ausschließlich test/websetup/test_preflight.py geändert (+5/−1); die drei Produktdateien bleiben unverändert. Commitbaum f88747f4d6834fa688cd4bd29782d36a94d5dc7d. Der Test setzt jetzt den aus `__file__` abgeleiteten Repository-/Stageroot vor dem Namespaceimport in sys.path; noqa: E402 begrenzt die bewusst nachgelagerte Importstelle. Keine CI-/Produktausnahme und keine abgeschwächte Assertion.

Exakter Remote-Testblob f16261a74ceb38359a62f634a976bda45b88d03a vollständig gelesen und mit dem lokalen UTF8-Text einschließlich vorhandener Zeilenenden gleich abgeglichen. Roher lokaler SHA256: 4f47c1a7a48b2aef41adc2934cedf8395fc5080fa39ea2854e3513e9b5fa523a.

Den tatsächlichen Consoleaufruf unabhängig erneut ausgeführt, cwd G:/Entwicklung/phoniebox-staging/i01a, PYTHONPATH nur G:/Entwicklung/phoniebox-tools/pytest-check und PYTHONDONTWRITEBYTECODE=1:

`G:/Entwicklung/phoniebox-tools/pytest-check/bin/pytest.exe --import-mode=importlib -p no:cacheprovider -q test/websetup/test_preflight.py`

Ergebnis: **10 Tests bestanden, Exit 0 (1,16 s)**. Der ursprüngliche Collection-P2 ist damit für diesen exakten Quellstand geschlossen; enge Quellfreigabe ohne weiteren Blocker. Roots zusätzlich berichteter V3-Lint-PASS wurde hier nicht erneut ausgeführt. Vollständige CI am neuen Head bleibt Roots separater Checkpoint; Teilstage/Entwicklungshost belegen weder eine vollständige Installation noch Python3.9-/ARMv6-/Hardwarebetrieb. Historischer RED und übrige I01-Grenzen oben bleiben erhalten. Review beendet; keine Produkt-, Test- oder CI-Datei geändert.

## Root-Integrationsnachweis

Nach obigem Folgereview bestehen beide vollständigen Pythonmatrices39027696042/39027699443 mit je allen fünf Versionen3.9–3.13 plus finish. Job117381822260 bestätigt152 bestandene Tests einschließlich aller10 neuen Preflightprüfungen. PR13 ist als87ee99b42d2debbaf4a1bea9264793c168f39f31 integriert; Root hat den mit dem geprüften Head identischen Baumf88747f4d6834fa688cd4bd29782d36a94d5dc7d bestätigt. Gesamtinstaller, geschützter LANzugang und Zielgerät bleiben offen.

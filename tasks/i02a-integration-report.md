# I02a – Integrationsnachweis

Stand: Source reviewed und vollständig in CI bestanden; [PR21](https://github.com/Motrish/RPi-Jukebox-RFID/pull/21) als ec56e0c18f73009de6ff7a3d215bd6d5c7061688 nach future3/modern-ui integriert. Automatische Merge-CI ebenfalls vollständig bestanden. Gesamtinstallation bleibt offen.

## Verhalten

Neues transportfreies SQLite-Jobjournal für feste Setupkonfiguration und geordnete Schritte. Gleiche commandId mit gleichem Inhalt liefert denselben Auftrag mit aktuellem Fortschritt; anderer Inhalt, paralleler neuer Auftrag oder veraltete Revision werden atomar abgewiesen. Absicht und bestätigte Wirkung werden getrennt gespeichert. Unklarer unterbrochener Schritt wartet auf unabhängige Inspektion, kein automatisches Wiederholen. Es gibt keine Systemeffekte und keinen HTTP-Schreibendpunkt.

Recovery setzt einen unabhängig sicher beendeten Vorgängerworker voraus. Das Journal selbst beendet keine Prozesse und ersetzt keine Workerexklusivität. Echte Privilegien, Webanschluss, Geräteanwendung und vollständiger Wizard bleiben I02b/I03/I05/I06.

## Umfang und Herkunft

Basis 741085f902c88aaa2fa74ef5dcd473ba993427e3. Source 2045a753435c952731d9ee577530dfe956a1cb2c, Tree 901868334eaebfee45e02062fa8daaae448f5b79. Nur vier Pfade: installation/websetup/jobs.py, test/websetup/test_jobs.py, test/websetup/test_job_contract.py, .github/workflows/test_build_webapp_v3.yml. Workflowänderung sind sechs Pfadfilterergänzungen, die bestehende Discovery führt die neuen Tests aus. Vollständiger Basisbaum erhalten, neue Quellen remote exakt zurückgelesen.

Luna schrieb Journal, anspruchsvolle Tests und Workflowpfade. Lokales qwen2.5-coder:14b erzeugte vier kleine Vertragsprüfungen. Breite ungeeignete Erstentwürfe wurden verworfen; Root normalisierte beim endgültigen Test nur zwei Leerzeilen ohne Codetokenänderung. gpt-6.1-sol prüfte unabhängig Architektur, Quelle und Korrekturen. Kein Astra und kein Sol als Autor ausführbarer Logik.

## Bereits belegte Prüfungen

24 endgültige Journal-/Vertragstests unabhängig durch Root und Reviewer bestanden. Vor der Testharnesskorrektur endgültige gesamte lokale Setup-Discovery:85Tests,5erwarteteWindowsskips; danach gezielte24Tests und Flake8 erneut bestanden. Root führte keinen vollständigen lokalen Checkout aus, Teilstage bleibt Teilstage.

Zwei P2 aus dem Review behoben: None-Fehlercode und zu schwache Schemaerkennung. Regressionen bestätigen keine Mutation und Erhalt des aktiven Slots beziehungsweise der Datenbankbytes. Konkurrierende gleiche Revision und Rollback nach tatsächlich erfolgtem Update dauerhaft geprüft. Reale Prozesskonkurrenz durch zwei unabhängige Python-Kinder erhalten. Kein Kill während Commit und kein Hardwarecrashnachweis.

Erster voller Weblauf39100155111 für Source01359cc erfolgreich. Beide damaligen Pythonmatrizen scheiterten am pytest-spezifischen Spawnimport des Testmoduls,285andereTests bestanden. Nach Ursachenbestätigung nur Testharness korrigiert, erneut reviewed und Source2045a753 veröffentlicht; kein blinder Wiederholungslauf. Finale Web-CI39100369657 und beide Pythonmatrizen39100369592/39100371838 vollständig erfolgreich, einschließlich aller3.9–3.13-Jobs und finish117595709298/117595695329. Python3.9-Log117595229799 bestätigt286bestandeneTests, eine bekannte vorbestehende library-CLI-runpy-Warnung. Web:85Linux-Setuptests, vorhandene React-/Bibliotheks- und Browser-/nginxprüfungen sowie Bundle-Rundlauf erfolgreich. Die tatsächlichen Merge-Ergebnisse sind unten separat belegt.

## Folgeschritte

I02b-Workerplanung enthält jetzt tatsächlich geprüfte systemd-Pfade und Playerabhängigkeiten. Bestehende Playerunit benötigt MPD/PulseAudio und ist keine unveränderte Setupworkerunit. Keine Installation oder Geräteaktion ausgeführt. Separater SD-/Zero-W-/MiniAmp-/PiSugar-Nachweis bleibt offen.

## Verifizierte Integration

Merge ec56e0c18f73009de6ff7a3d215bd6d5c7061688 enthält exakt die Eltern741085f902c88aaa2fa74ef5dcd473ba993427e3 und2045a753435c952731d9ee577530dfe956a1cb2c. Tree901868334eaebfee45e02062fa8daaae448f5b79 ist gleich dem reviewed Source. Produktref zeigt auf Merge; develop unverändert42d5023e37dbf8de6477fef5ebcd6eae3cb5087d. Merge-Web39100573332 und Merge-Python39100573370 sind vollständig erfolgreich, einschließlich aller fünf Versionen und finish117596359325.

## Abschließende CI und Artefakt

[Merge-Web](https://github.com/Motrish/RPi-Jukebox-RFID/actions/runs/39100573332), Job117595824775: kompletter Build,85Linux-Setupprüfungen, vorhandene React-/Bibliotheks-/Contracttests, echte Chromium-/nginxabnahmen, Bootstrap und Artefaktrundlauf erfolgreich. [Merge-Python](https://github.com/Motrish/RPi-Jukebox-RFID/actions/runs/39100573370):3.9–3.13 und finish117596359325 vollständig erfolgreich. Source und Merge sind damit getrennt tatsächlich geprüft. Vorbestehende library-CLI-runpy-Warnung bleibt dokumentiert.

Passendes CI-Bundle zur Mergeidentität ec56e0c18f73009de6ff7a3d215bd6d5c7061688: Artefakt12125658980, ZIP1371590Bytes, inneres Archiv1370736Bytes, SHA-256 dc82205b56e1269b9b5ee17be5d1e6f5384a368c495f9f69a5394f185fe5e652. Manifestidentität und Downloadrundlauf tatsächlich geprüft. Ablauf laut Artefaktmetadaten25.10.2026,05:29:01UTC; GitHublesezugang erforderlich, kein veröffentlichtes Release. Keine Geräte- oder Kontoänderung.

I02a als transportfreier Software-Slice verified/integrated. I02 als Gesamtauftrag bleibt in_progress. Nächster begrenzter Auftrag: I02b-Workerexklusivität und Beobachtung; anschließend geschützter HTTP-/Setupseitenanschluss. Rulings: neueste Nutzerfreigabe für Parallelität und lokale einfache Codingaufgaben umgesetzt; kein erneutes Integrationsmenü wegen fortbestehender Autorisierung; Teilstages erhalten, voller Checkout in CI.

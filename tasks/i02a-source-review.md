# I02a – unabhängiges Quellcode-Review

Reviewer: gpt-6.1-sol. Erstabgabe: REQUEST CHANGES, genau zwei reproduzierbare P2-Vertragsverletzungen. Kein ausführbarer Code vom Reviewer geändert. Basis 741085f902c88aaa2fa74ef5dcd473ba993427e3, Vertrag i02a-journal-brief.md einschließlich Präzisierungen und A01-SetupJob.

## Erforderliche Korrekturen

1. jobs.py, ursprüngliche Zeilen 282–283 und 330–331: fail_step mit None umgeht die Fehlercodevalidierung. Nach begin_step wird FAILED mit error.code None und Revision 2 gespeichert, der aktive Slot freigegeben. Nur STEP_FAILED oder OBSERVATION_FAILED sind erlaubt. Alle fail-Argumente vor der Transaktion validieren; Regression verlangt INVALID_REQUEST, unveränderten Snapshot und weiterhin belegten aktiven Slot.
2. jobs.py, ursprüngliche Zeilen 187–198: Schemaerkennung prüft nur Spalten- und Indexnamen. Reproduktion: leere jobs-Tabelle mit gleicher DDL außer revision TEXT NOT NULL anstelle INTEGER NOT NULL erzeugen und korrekten aktiven Unique-Index wiederherstellen. Öffnen akzeptiert das Schema, submit liefert Stringrevision, begin_step mit 0 ergibt fälschlich REVISION_CONFLICT. Auch ein nicht eindeutiger Index namens one_active_job auf command_id wurde akzeptiert. Erwartete Typen, Nullbarkeit/Schlüssel und wesentliche Indexeigenschaften prüfen. Öffnen muss STORE_UNAVAILABLE liefern und die Datei unverändert lassen.

## Unabhängige Nachweise

17 Autorentests bestanden. Vollständige Setup-Discovery: 82 Tests, fünf erwartete Windowsskips. Vier endgültige Ollama-Vertragstests samt Hash geprüft; sie behandeln Initialzustand, unzulässige Eingabetabellen und Kopierisolation. Autorentests behandeln aktuelle Idempotenz, Inhaltsvergleich, aktive Konflikte ohne ID-Verbrauch, geordnete Schritte, Recovery, terminale Zustände, Threads, zwei echte Spawn-Prozesse und Überlauf.

Zusätzliche temporäre Reviewerproben bestanden: Zwei Instanzen beginnen gleichzeitig Revision 0; genau einmal Revision 1, einmal REVISION_CONFLICT. AFTER UPDATE mit RAISE(FAIL, privatem Text) ergibt STORE_UNAVAILABLE und unveränderten Snapshot nach Wiederöffnung. Beide Proben als Regressionen sichern. Der bisherige BEFORE-UPDATE-/RAISE-ABORT-Test alleine beweist keinen Rollback nach vollzogenem Zeilenupdate.

Recovery prüft Wiederöffnung eines gespeicherten RUNNING-Auftrags und explizite Reconciliation. Kein Kill während Commit, kein ausgeschöpfter Locktimeout, keine Linuxprobe hier. Tatsächlicher vollständiger CI-Checkout bleibt erforderlich.

Der korrigierte Autorenbericht enthält den echten RED mit fehlendem jobs-Modul; ursprünglicher falscher Discoveryaufruf ist ausgeschlossen. Als historischer Autorenbeleg akzeptiert, nicht nachträglich vom Reviewer rekonstruierbar.

## Weitere Bewertung

Transaktionsbesitz, Verbindungsende, SQLite-Serialisierung und konsistente Reads sind auf geprüften Pfaden schlüssig. Persistentes Intent vor künftigem Effekt; Konstruktor startet keine Recovery. WAITING_USER wird nicht automatisch wiederholt. Bestätigung/Fehler nach Recovery erfordern unabhängige Beobachtung und separat sicher beendeten Vorgängerworker. Replay liefert aktuellen Snapshot. Fehlerstrings und Überlaufkontrolle sonst vertragsgemäß.

Workflowdiff: genau sechs zulässige Pfadfilterergänzungen für jobs.py, test_jobs.py und test_job_contract.py in push und pull_request. Keine weiteren Änderungen.

Erstabgabehashes: jobs.py 36c792495e95fdd5a62542c6ff2bcc9bbc48e16fa5c5e370a7addea1c73fe6e8; test_jobs.py 8e7073f044143f6d2d78f75010fcb787c1f7c786ccbfb1260d138ef625cd57ad; test_job_contract.py 7771d77a77edd750b6adee98366b26406e5939cdb39d139673791316959839df; Workflow ed3eb07b8a4af078137af89522e8e1ea2faa4ac7eb1c39cfd524e1bee1ad0461. Root schrieb diesen Bericht aus der vollständigen Reviewnachricht, da der Reviewerpfad nicht beschreibbar war.

# I02b1 – exklusiver Setupworker und beobachtete Schritte

Basis future3/modern-ui ec56e0c18f73009de6ff7a3d215bd6d5c7061688, Tree 901868334eaebfee45e02062fa8daaae448f5b79. Teilstage G:/Entwicklung/phoniebox-staging/i02b-worker. Vorarbeiten i02b-worker-plan.md, A01-SetupJob und I02a gelten weiter. Dies ist ein transportfreier, unprivilegierter Worker-Kern mit synthetischen Schritthandlern; keine produktiven Audio-/Paket-/Systemhandlungen und kein HTTP-/systemd-Anschluss.

## Dateien und Arbeitsteilung

Luna besitzt installation/websetup/worker.py, installation/websetup/jobs.py, test/websetup/test_worker.py, test/websetup/test_jobs.py und .github/workflows/test_build_webapp_v3.yml. In jobs.py ausschließlich die unten beschriebene Methode ergänzen; bestehendes Schema und sonstige Journalverträge erhalten. test_jobs.py erhält passende Regressionsfälle. Workflow nur um worker.py, test_worker.py und test_worker_contract.py in beiden Pfadfiltern ergänzen. Vorhandene test_*.py-Discovery bleibt bestehen.

Root/Ollama besitzt ausschließlich test/websetup/test_worker_contract.py mit zwei bis drei kleinen Eingabe-/Journalmethodentests. Root schreibt keine ausführbare Logik. Ein Owner pro Datei. Python ab3.9, ausschließlich Standardbibliothek. Root veröffentlicht nur exakte eingefrorene Autorenartefakte. Kein Import oder Aufruf des alten Installers.

## Öffentliche Worker-API

installation.websetup.worker exportiert Worker und WorkerError. Worker(database_path, handlers) und worker.run_once() -> JobSnapshot oder None. Kein frei wählbarer Leasepfad, Store oder Handler aus HTTP. Worker ist ausdrücklich keine Sandbox für untrusted Pythoncode: handlers werden nur durch vertrauenswürdige interne Komposition eingebunden und besitzen keine freien Browserbefehle.

handlers ist exakt ein dict mit CHECK_SYSTEM, CONFIGURE_AUDIO, VERIFY_INSTALLATION. Jeder Wert ist ein Objekt mit aufrufbarem apply(config) und observe(config). mapping bei Konstruktion defensiv kopieren; jedes apply und jedes observe erhält eine eigene unabhängige Kopie der validierten desiredConfigSummary. Spätere Mutation des Caller-dict oder einer Handler-Konfigkopie darf die Zielkonfiguration und Journalwerte nicht ändern. Alle Handlerkonstruktionen vor Dateieffekten prüfen.

database_path akzeptiert nichtleeren str oder pathlib.Path, keine Bytes/None/bool/Zahl, kein :memory:. Die bereits durch JobStore initialisierte Datenbank muss existieren und regulär sein. Kein automatisches Erzeugen einer neuen Datenbank im Worker. Finalen DB-Symlink und st_nlink !=1 abweisen. Elternpfad kanonisch auflösen, dann kanonische absolute DB-Identität für alle späteren Operationen behalten. DB-Gerät/Inode bei Konstruktion speichern. Konstruktor erzeugt keinen Store und keine Lease, ruft keine Handler und keine Recovery auf. Nicht lesbare, fehlende oder ungeeignete DB wird WORKER_UNAVAILABLE; unzulässiger Argumenttyp/Mapping ist INVALID_REQUEST. Ein leerer oder :memory:-String ist INVALID_REQUEST.

WorkerError besitzt .code; feste Codes INVALID_REQUEST, WORKER_BUSY, WORKER_UNAVAILABLE, keine Pfade/SQL/Handlermeldungen in str/repr. Bestehende JobError aus Journaloperationen dürfen unverändert als feste redigierte Codes weitergegeben werden. Keine Logs mit Konfiguration oder Rohfehlertext. Ausgaben ausschließlich Snapshot/None oder typisierte Ausnahme.

## Prozessbesitz

run_once unterstützt hier Linux/POSIX mit verfügbarem fcntl.flock. Fehlt die geprüfte Sperrprimitive, WORKER_UNAVAILABLE vor irgendeiner Journal-/Handlerwirkung. Insbesondere kein wirkungsloser Windowsfallback; portable Konstruktor- und Eingabetests bleiben unter Windows möglich, reale Sperr-/Ausführungstests laufen in Linux-CI.

Leasepfad ist genau der kanonische DB-Dateipfad plus .worker.lock. Bei JEDEM run_once eigenen FD öffnen, atomar bei Bedarf erstellen, Modus0600, close-on-exec, keine Symlinks zulassen; vorhandene Lockdatei muss regulär und einfach verlinkt sein. Exklusive nichtblockierende OS-Sperre halten über Öffnen des JobStore, Recovery, Auswahl, begin, apply, observe und endgültigen Commit. Bei belegter Sperre WORKER_BUSY, keine Journalöffnung oder Handleraufrufe. Sperre/FD in finally freigeben, Lockdatei NIE löschen oder ersetzen. Vorhandene Dateien nicht truncaten oder ihre Inhalte interpretieren. Eine einmal erfolgreiche run_once darf spätere Aufrufe nicht reentrant über einen geteilten FD machen.

Vor jeder Handlerausführung und dauerhaften Journaländerung prüfen: DB-Pfad zeigt noch auf die gespeicherte reguläre einfache Datei; Lockpfad zeigt noch auf denselben regulären einfach verlinkten Inode wie der eigene FD. Auch vor der anfänglichen JobStore-Öffnung prüfen. Verlust/Rebindung führt WORKER_UNAVAILABLE ohne weitere Bestätigung/Wirkung; Zustand bleibt höchstens RUNNING zur späteren Inspektion. Nach Auswahl Store und nächste Aktion nur unter gehaltener Lease benutzen.

Verbindliche Einsatzvoraussetzung: vertrauenswürdiges lokales privates Stateverzeichnis und unveränderte Pfadkette, keine fremden Writer, Renames, Hardlinks oder direkte RUNNING-/WAITING-Schreiber außerhalb desselben Workerbesitzes. Sofortiges Elternverzeichnis unter POSIX darf nicht gruppen-/weltbeschreibbar sein und muss dem ausführenden Benutzer gehören. Handler sind synchron; sie forken/starten keine Hintergrundthreads oder überlebenden Nachkommen. CLOEXEC verhindert keine Forkvererbung. Dieser Slice behauptet keine Fencinggarantie gegen kompromittierte privilegierte Writer oder zurückgelassene Prozesse. Workerexklusivität gilt nur innerhalb dieses dokumentierten Einsatzvertrags.

## Persistente Warteentscheidung

JobStore.wait_for_inspection(job_id, expected_revision, step_id) ist die einzige neue Journalmethode. Eingaben und Revision wie bestehende Übergänge validieren. Nur RUNNING mit exakt passendem gültigem aktuellen Schritt und Revision akzeptieren: WAITING_USER, gleicher stepId und appliedSteps, nextAction genau {kind: INSPECT_SYSTEM}, error None, Revision+1 und updatedAt. Keine neue Wirkung/Bestätigung, Schema und Snapshotfelder unverändert. WAITING_USER oder falscher gültiger Schritt: INVALID_TRANSITION; veraltete gültige Revision: REVISION_CONFLICT; ungültige Werte INVALID_REQUEST; Überlauf kontrolliert und ohne Teilmutation. Kein impliziter Recoveryaufruf und kein automatisches Retry.

## Ablauf genau einer Workeriteration

1. Lease erwerben, Identitäten prüfen, erst dann JobStore öffnen und active lesen. Kein aktiver Job -> None. Keine neue Jobannahme im Worker.
2. Ist der vorhandene Auftrag RUNNING, zuerst unter Lease reconcile_interrupted aufrufen: alter Worker ist durch exklusiven synchronen Besitz ausgeschlossen. Danach aktuellen WAITING_USER-Snapshot neu lesen. Diese Recovery erhöht einmal die Revision, löst aber kein apply aus.
3. Bei WAITING_USER: ausschließlich observe des bereits begonnenen aktuellen Schritts. APPLIED -> confirm_step, NOT_APPLIED -> fail_step mit OBSERVATION_FAILED, UNKNOWN -> exakt unveränderter Snapshot ohne neue Revision. Nie apply und nie automatisch nächsten Schritt starten. Bestätigung oder Fehler bedeutet hier tatsächlich durch den internen Handler beobachtete Wirkung, keine bloße Browserbestätigung.
4. Bei QUEUED: nächsten nicht bestätigten festen Schritt wählen; Identitäten prüfen; begin_step committen, BEVOR apply aufgerufen wird. Dann synchron apply mit defensiver Konfigkopie. Anschließend immer separat observe mit neuer Kopie, auch wenn apply eine gewöhnliche Exception warf. APPLIED -> confirm_step; NOT_APPLIED -> fail_step mit STEP_FAILED; UNKNOWN -> wait_for_inspection. Nach dieser Entscheidung zurückgeben; kein weiterer Schritt im selben Aufruf.
5. observe liefert nur exakt APPLIED, NOT_APPLIED oder UNKNOWN. Gewöhnliche Exception, falscher Typ oder unbekannter Rückgabewert wird als UNKNOWN behandelt, niemals als Erfolg. apply-Rückgabe ist keine Bestätigung und wird nicht als Beweis benutzt. Terminale Zustände erscheinen nicht in active; nach finalem Erfolg liefert nächste Iteration None.
6. KeyboardInterrupt, SystemExit und Prozessabbruch nicht als gewöhnliches FAILED kaschieren. Lease in finally freigeben; persistiertes Intent bleibt zur späteren Recovery. Nicht benötigte Wiederholungs-/Daemon-/Polling-/Abbruch-APIs in diesem Slice nicht hinzufügen.

## Nachweise und Übergabe

Vor Source echte RED-Tests. Temporäre Datenbanken/Marker und Fakes genügen für Wirkungen; reale Linuxprozesse für Exklusivität/Kill/Neustart. Zwei Prozesse dürfen keine doppelte apply-Wirkung erzeugen; zweiter Besitzer ist WORKER_BUSY ohne Mutation. Gleicher Worker im selben Prozess ebenfalls nicht reentrant. Nach Kill zwischen Intent und Wirkung darf Recovery nicht blind apply wiederholen; nach Wirkung/vor Bestätigung muss beobachtete APPLIED-Wirkung ohne Wiederholung bestätigt werden. UNKNOWN bleibt dauerhaft inspizierbar; spätere Beobachtung kann auflösen. Intent vor apply durch unabhängig neu geöffneten Store belegen. Mutation der Handlerkopie/Caller-Mapping, Fehlerredigierung, Handler-/Store-/Identitätsfehler und Leasefreigabe prüfen.

Prozessharness muss unter pytest und unittest importstabil sein: feste eigenständige Popen-Kinder mit strukturierten Argumenten, begrenzte Wartezeit und Aufräumen; keine Spawn-Pickles von test.websetup. Keine Testauslassung unter Linux. Lokale Windows-Skips ehrlich benennen, notwendige Linuxprüfungen im vollständigen CI-Checkout. V3-Flake8 und bestehende Setupregressionen. Danach Dateien einfrieren, Hashes und echte Commands/Resultate berichten; unabhängiges6.1-sol-Review vor Publish und voller CI-Checkout vor Integration. Keine Geräteänderung oder Releasepublikation.

## Präzisierungen aus dem unabhängigen Architekturreview

APPROVE durch6.1-sol. Ein vorhandener Dateipfad alleine beweist kein initialisiertes Journal: vor JobStore unter gehaltener Lease read-only die Anwendungstabellen journal_meta und jobs verlangen. Auch eine nichtleere SQLite-Datei ohne Anwendungstabellen darf nicht durch den Worker gebootstrapped werden. JobStore behält die vollständige eigene Schemaerkennung; keine neue Journal-Konstruktorsemantik. Leere und nichtinitialisierte Datenbank ohne Mutation abweisen, WORKER_UNAVAILABLE.

Handlergrenzen getrennt behandeln: eine von apply/observe selbst geworfene JobError ist eine gewöhnliche Handlerexception, keine genuine Storeexception. Nur tatsächlich aus Journaloperationen stammende JobError propagieren. Infrastrukturfehler als WorkerError ohne rohe Exceptionverkettung ausgeben; keine Pfade/privaten Texte im Traceback. Unerwartete beschädigte aktive Snapshots vor Dispatch kontrolliert als WORKER_UNAVAILABLE abweisen, keine freien KeyError/IndexError.

## Geprüfte technische Quellen

Die Python3.9-Primärdokumentation beschreibt flock als OS-Sperroperation auf einem offenen Dateideskriptor; verfügbare Flags sind betriebssystemspezifisch. Der Slice prüft die echte Linuxprimitive in CI und behauptet keine Windowsausführung. Quellen: [fcntl](https://docs.python.org/3.9/library/fcntl.html), [OS-Schnittstellen](https://docs.python.org/3.9/library/os.html#os.O_CLOEXEC).

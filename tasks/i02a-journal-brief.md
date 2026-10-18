# I02a – dauerhaftes Setup-Jobjournal

Basis: future3/modern-ui, Commit 741085f902c88aaa2fa74ef5dcd473ba993427e3. Neuer Teilstage G:/Entwicklung/phoniebox-staging/i02a-journal. A01-SetupJob bleibt maßgeblich; dies ist ein enger interner, transportfreier Anschlussvertrag, keine Installationsfreigabe.

## Umfang und Besitz

Luna besitzt installation/websetup/jobs.py und test/websetup/test_jobs.py. Ollama besitzt ausschließlich test/websetup/test_job_contract.py. Root übernimmt unveränderte Autorenartefakte und Dokumentation. Keine fremden Dateien ändern. Kein HTTP, keine Prozesse, kein Audio, kein Systemdienst, keine Privilegien und keine tatsächliche Anwendung von Konfiguration. Python ab 3.9, nur Standardbibliothek. Vorhandene CI entdeckt test/websetup/test_*.py automatisch.

## API und Eingaben

Modul installation.websetup.jobs exportiert JobStore und JobError. JobStore(path) öffnet/initialisiert eine lokale SQLite-Datei; jede Operation besitzt eine abgeschlossene Transaktion und Verbindung, kein close-Aufruf nötig. Elternverzeichnis muss existieren. Mehrere Instanzen und Prozesse werden durch SQLite serialisiert, nicht nur durch Python-Threadlocks. Öffnen führt niemals Recovery oder Installation aus. Nicht gegen eine fremde Datenbank verwenden; beschädigtes/unbekanntes Schema kontrolliert als STORE_UNAVAILABLE ablehnen. Nicht lesbare oder fehlgeschlagene SQLite-Operationen geben keine internen Meldungen zurück.

submit(command_id, desired_config) akzeptiert eine command_id als ASCII-Zeichenfolge mit 1 bis 64 Zeichen aus A-Z, a-z, 0-9, Unterstrich oder Bindestrich. desired_config ist genau ein dict mit audioOutput, rfidEnabled, pisugarEnabled; audioOutput ist SYSTEM_DEFAULT oder HIFIBERRY_MINIAMP, die beiden anderen Werte echte bool. Keine zusätzlichen Felder, freien Pfade, Befehle oder Secrets. Bool ist kein erlaubter Ersatz für eine Revision. Konfigurationen werden unabhängig von Schlüsselreihenfolge verglichen.

get(job_id) liefert einen frischen Snapshot oder JOB_NOT_FOUND. active() liefert den aktuellen aktiven Snapshot oder None. begin_step(job_id, expected_revision, step_id), confirm_step(job_id, expected_revision, step_id), fail_step(job_id, expected_revision, step_id, error_code) liefern jeweils den neuen Snapshot. expected_revision ist int >= 0, kein bool. step_id ist genau CHECK_SYSTEM, CONFIGURE_AUDIO oder VERIFY_INSTALLATION in dieser Reihenfolge. fail_step akzeptiert nur STEP_FAILED oder OBSERVATION_FAILED. Nicht zulässige Typen/Werte sind INVALID_REQUEST. Job-ID ist eine nicht leere, begrenzte ASCII-ID; neu erzeugte IDs sind zufällige UUID-Hexstrings. Alle öffentlichen Eingaben vor Datenbankwirkung prüfen.

JobError besitzt .code. Ausschließlich feste Codes INVALID_REQUEST, JOB_NOT_FOUND, REVISION_CONFLICT, INVALID_TRANSITION, COMMAND_ID_REUSED, JOB_CONFLICT oder STORE_UNAVAILABLE; keine Eingaben, SQL, Pfade oder SQLite-Originalmeldungen in str/repr. Öffentliche Journalmethoden geben keine freien Diagnosefelder an den Aufrufer zurück.

## Snapshot

Genau diese Felder: contractVersion, jobId, commandId, status, stepId, desiredConfigSummary, appliedSteps, revision, createdAt, updatedAt, nextAction, error. contractVersion ist websetup.job.v1. Zeitstempel sind UTC-ISO8601 mit Z. desiredConfigSummary enthält ausschließlich die drei validierten Konfigurationsfelder. appliedSteps ist eine geordnete Liste von Objekten mit genau stepId und diagnostic, diagnostic immer CONFIRMED. nextAction ist None oder genau {kind: INSPECT_SYSTEM}. error ist None oder genau {code: STEP_FAILED} beziehungsweise {code: OBSERVATION_FAILED}. Diese lokale Fehlerform ist keine behauptete Umsetzung des allgemeinen A01-Errorobjekts. Rückgaben sind unabhängige Kopien und JSON-serialisierbar.

## Zustands- und Persistenzregeln

Neue Jobs: QUEUED, stepId None, appliedSteps [], revision 0, nextAction/error None, createdAt gleich updatedAt. Höchstens ein aktiver Job: QUEUED, RUNNING oder WAITING_USER. Andere A01-Statuswerte sind für spätere Slices reserviert und hier nicht erzeugbar.

Gleiche command_id und gleicher gültiger Inhalt liefern den aktuellen Snapshot desselben Jobs, auch nach Neustart oder Abschluss, ohne Mutation und ohne Revisionserhöhung. Gleiche ID und anderer gültiger Inhalt: COMMAND_ID_REUSED. Neuer anderer Auftrag bei aktivem Job: JOB_CONFLICT; die abgelehnte neue ID wird nicht verbraucht. Erfolgreiche Annahme, Idempotenz und Konfliktprüfung sind atomar.

begin_step ist nur für QUEUED und den nächsten noch nicht bestätigten Schritt möglich: RUNNING mit diesem stepId, Revision +1. Persistierter Intent entsteht hier vor einer möglichen späteren externen Wirkung. Bereits bestätigte Schritte dürfen nie erneut beginnen.

confirm_step ist nur für RUNNING oder WAITING_USER mit exakt passendem aktuellem stepId und Revision möglich. Es bestätigt eine vom künftigen Worker unabhängig beobachtete Wirkung. Schritt an appliedSteps anhängen; QUEUED und stepId None für weitere Schritte, nach letztem Schritt SUCCEEDED und stepId None. nextAction und error None, Revision +1.

fail_step ist für RUNNING oder WAITING_USER mit passendem aktuellen Schritt und Revision möglich: FAILED, aktuelles stepId und vorherige appliedSteps bleiben erhalten, error ist fester Code, nextAction None, Revision +1. Danach darf ein neuer Auftrag angenommen werden, alte ID bleibt reserviert. Veraltete gültige Revision: REVISION_CONFLICT. Unzulässiger Übergang oder falscher gültiger Schritt: INVALID_TRANSITION. Kein Fehler verändert den Store.

reconcile_interrupted() liefert eine Liste der tatsächlich geänderten Snapshots. Voraussetzung: Aufrufer hat separat garantiert, dass der frühere Worker beendet ist und keine alte Wirkung mehr laufen kann. Dieses Journal erkennt oder beendet keine Prozesse. RUNNING wird WAITING_USER mit unverändertem stepId und appliedSteps, nextAction INSPECT_SYSTEM, Revision +1. Wiederholter Aufruf liefert [] ohne Mutation. QUEUED/terminale Jobs bleiben unverändert. Aus WAITING_USER darf begin_step niemals neu starten; nur confirm_step/fail_step nach unabhängiger Beobachtung. Eine Browserunterbrechung ruft diese Recovery nicht automatisch auf. Recovery ist kein überlappender Workerstart und kein automatischer Retry.

## Nachweis

Zuerst echte RED-Tests vor jobs.py; dann Implementierung und gezielte Tests für Vertrag, idempotente Parallelaufrufe, zwei Instanzen/Prozesse, aktive Konflikte, Revisionsrennen, Wiederöffnung/Crash, Intent vor Bestätigung, Recovery ohne Wiederholung, Rollback bei SQLite-Fehler und redigierte Fehler. Datenbanken nur temporär. Kein Handshake mit echtem Gerät. V3-Flake8-Konventionen und vorhandene Setup-Regressionsprüfungen weiterverwenden. Am Ende Dateien einfrieren und Hashes melden. Unabhängiges 6.1-sol-Review vor Veröffentlichung; voller CI-Checkout vor Integration.

## Präzisierungen nach Architekturprüfung

Job-ID verwendet dieselbe ASCII-Tokenregel und Grenze 1 bis 64 wie command_id. Vollständige Snapshots einschließlich appliedSteps müssen innerhalb einer konsistenten Lesetransaktion entstehen. SQLite wartet höchstens fünf Sekunden auf konkurrierende Locks und gibt dann STORE_UNAVAILABLE ohne Rohdetails zurück. Revisionen bleiben im Slice int >= 0; nicht speicherbare Überläufe müssen kontrolliert und ohne Teilmutation fehlschlagen. Kein zusätzlicher JS-Vertrag wird hier behauptet.

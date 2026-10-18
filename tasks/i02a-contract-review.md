# I02a Architekturprüfung

Unabhängig durch gpt-6.1-sol geprüft: Jobjournal-only-Schnittstelle schlüssig, keine blockierende Architekturabweichung. Recovery hält Unsicherheit fest; keine automatische Wiederholung.

Akzeptierte Präzisierungen: jobId wie commandId auf ASCII-Token mit 1 bis 64 Zeichen begrenzen; zusammenhängende Snapshots in einer Lesetransaktion; SQLite-Lockwartezeit auf fünf Sekunden begrenzen. Revision int >= 0; nicht speicherbarer Überlauf kontrolliert und ohne Teilmutation.

Sliceentscheidungen: contractVersion websetup.job.v1, Idempotenz liefert aktuellen Snapshot, lokale feste Fehlerobjekte, JOB_CONFLICT verbraucht keine ID. Diese Entscheidungen ändern keine Playlist-/Queueverträge. Stopped-Worker-Voraussetzung und unabhängige Beobachtung vor Recoverybestätigung sind explizit. Dies ist Architekturprüfung, noch kein Quellcode- oder CI-Abschlussreview.

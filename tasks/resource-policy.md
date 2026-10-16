# Ressourcen- und Wiederaufnahmeregeln

Nutzervorgabe vom 16.10.2026: Das verfügbare Fünf-Stunden-Kontingent sparsam einsetzen; nach Erreichen des Limits erst nach dem tatsächlichen Reset weiterarbeiten. Diese Regel ergänzt den Mehragentenplan. Sie garantiert keine fünf Stunden Laufzeit: Restkontingent, Tokengewichtung und Resetfenster sind dem Koordinator nicht zuverlässig zugänglich.

- Standard: Koordinator plus genau ein aktiver Worker. Coding und unabhängiges Review folgen seriell; Sol wird nur für eine begrenzte Architektur-/Reviewfrage gestartet.
- Code, Tests, Skripte und Konfiguration bleiben vollständig bei Luna. Keine Astra- oder Sol-Coding-Ersatzroute. Einfache neue Luna-Aufträge können medium nutzen; Nebenläufigkeit, I/O und privilegierte Änderungen behalten die nötige höhere Prüftiefe.
- Kleine Briefings mit exaktem SHA und exklusiven Dateien; vorhandene Ergebnisse wiederverwenden. Keine permanenten Leerlaufagenten oder vollständigen Kontextkopien ohne Bedarf.
- CI nur nach relevanten Änderungen und an Übergabepunkten lesen. Keine 30-Sekunden-Pollings und keine manuellen Wiederholungen bereits bestandener Jobs ohne neuen Befund.
- Nach jedem abgeschlossenen Slice Status, Commit, Tests, offene Voraussetzungen und nächsten Schritt in todo.md bzw. Bericht festhalten. Modell-/Kontingentgrenzen niemals durch fremde Konten, Schlüssel oder verbotene Modelle umgehen.
- Bei Limitmeldung den tatsächlich genannten Resetzeitpunkt festhalten und neue Modellarbeit bis dahin einstellen. Kein geratenes Resetdatum und kein enger Retryloop.
- Automatische Wiederaufnahme ist nur dann eingerichtet, wenn ein unterstützter Scheduler/Client den Auftrag tatsächlich gespeichert und bestätigt hat. Aktuell fehlt ein entsprechendes Tool; Orca meldet not_running, Codex CLI bietet keine Scheduled-Verwaltung. Es wurde kein Timer und keine Automation erstellt. Wenn der Client den bestehenden Thread wieder startet, zuerst todo.md und die echten Branchheads lesen, dann den nächsten freigegebenen Schritt fortsetzen.

Quellen: lokale CLI-Hilfe und Orca-Statusprüfung am 16.10.2026; [offizielle Scheduled-Dokumentation](https://learn.chatgpt.com/docs/automations). Lokale Automationen benötigen laut Dokumentation einen laufenden Rechner und eine laufende App. Ein nicht eingerichteter Auftrag wird nicht als automatisch fortsetzbar behauptet.

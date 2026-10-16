# F01/F02 – Umgebung und V3-Basis

Stand: 16.10.2026

## Ergebnis

Die vorgesehene V3-Basis ist upstream `MiczFlor/RPi-Jukebox-RFID` Release `v3.6.0`, Commit `4fa84fd50750fd4b52984d51aa7c95466cf5b241`. Das Release ist als nicht-Prerelease am 04.03.2026 veröffentlicht. GitHub weist den Tag auf genau diesen Commit; die Commit-Signatur ist als gültig verifiziert. Der Commit stellt die Versionswerte `3.6.0` ein und die Releasebeschreibung empfiehlt Raspberry Pi OS Bookworm.

Der SHA wurde erst in `Motrish/RPi-Jukebox-RFID` lesend aufgelöst. GitHub lieferte dort dieselben Commit-Metadaten, denselben Tree `14c8a895c4c5e6903315096a75c6b918228b6fa1` und beide Eltern `ab1b5270b091cc4204a6b3734b7e03f3c5ffadbb` und `d97312e2e26cb488fc001f159664e13447b6ce4f`. Der Fork hatte vor der Änderung nur `develop` (`42d5023e37dbf8de6477fef5ebcd6eae3cb5087d`). Anschließend wurde im Fork der Branch `feature/foundation` exakt auf den geprüften Commit angelegt. Das erneute Lesen des Branches bestätigt denselben Head-SHA und dieselbe Commit-/Tree-/Elternhistorie. `develop` blieb unverändert.

## F01 – ausführbare lokale Entwicklungsumgebung

Ein einmaliger `git ls-remote --heads --tags https://github.com/Motrish/RPi-Jukebox-RFID.git`-Versuch in `G:\Entwicklung` scheiterte mit Exitcode 1: Verbindung zu `github.com:443` nicht möglich. Es existiert hier kein lokaler Checkout des Zielrepositories. Der GitHub-Connector kann Repositorydaten lesen und API-Schreibrechte ausweisen, stellt aber keinen vollständigen lokalen Clone, Git-Objekttransfer oder Checkout bereit. Es wurde kein Sourcebaum aus einzeln abgerufenen Dateien zusammengesetzt.

Der isolierte Dokumentations-Commit 77a7f60a2d3961c04288c0e885b62e283b127c3e auf docs/development-plan wurde veröffentlicht; alle neun Dateien und der Branch-SHA wurden zurückgelesen. Damit ist API-Schreiben geprüft; ein API-Commit ist kein Nachweis für lokalen Git-Push. Workflow-Schreibrechte sind mit den verfügbaren Connector-Lesezugriffen nicht getrennt verifiziert. Es wurde keine Workflowdatei geändert.

Mangels vollständigem lokalen Checkout konnten weder `G:\Entwicklung\phoniebox-dev` erstellt noch ein nativer Git-Worktree oder lokale Build-/Testabhängigkeiten hergestellt werden. Getrennte Worktrees sind daher noch nicht verfügbar und es gab keinen lokalen Branch-/Commit-/Push-Test. Die bestehende Sandbox wird nicht umgangen und es wurde kein Eskalationszugriff angefordert.

## Abnahme und Übergabestatus

- **F01:** Teilweise erreicht. Fork-Connector-Schreibtest liegt beim Koordinator; lokaler Git-Fetch, Checkout, Worktree, Push und Workflowrechte bleiben offen. G0 ist nicht erfüllt.
- **F02:** Remote-Basisbranch `feature/foundation` erfolgreich auf dem Upstream-Release-Commit angelegt. Die GitHub-API-Auflösung belegt, dass der Fork diesen SHA als Commitobjekt kennt. Vollständiger Checkout, lokale Prüfung der Elternhistorie und erforderlichen Dateien bleiben wegen F01 offen; F02 ist daher remote vorbereitet, aber nicht vollständig abgenommen.
- **Nächster zulässiger Schritt:** Git-fähigen Arbeitsplatz mit Netzwerkzugriff bereitstellen oder freigeben. Dort `feature/foundation` vollständig klonen/fetchen und lokal prüfen; bis dahin keine Produktcode-Tickets starten und `develop` nicht als V3-Basis verwenden.

Es wurden keine Produktdateien, Tests oder Geräte verändert. Die reale Phoniebox wurde nicht angesprochen.

## Cloud-Baseline

GitHub Actions ist im Fork aktiv. Die vorhandenen V3-Workflows besitzen future3-Branch-/Pfadfilter und keinen manuellen Dispatch. Ein separater future3/ci-baseline-Integrationscommit mit exakt originalem V3-Tree löst diese vorhandenen Prüfungen aus. V3-Webbuild ist bestanden, Python/Installation laufen noch. Vollständige interaktive lokale Checkouts und Worktrees bleiben davon getrennt offen.

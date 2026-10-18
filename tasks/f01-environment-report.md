# F01/F02 – Umgebung und V3-Basis

Stand: 16.10.2026

## Ergebnis

Die vorgesehene V3-Basis ist upstream `MiczFlor/RPi-Jukebox-RFID` Release `v3.6.0`, Commit `4fa84fd50750fd4b52984d51aa7c95466cf5b241`. Das Release ist als nicht-Prerelease am 04.03.2026 veröffentlicht. GitHub weist den Tag auf genau diesen Commit; die Commit-Signatur ist als gültig verifiziert. Der Commit stellt die Versionswerte `3.6.0` ein und die Releasebeschreibung empfiehlt Raspberry Pi OS Bookworm.

Der SHA wurde erst in `Motrish/RPi-Jukebox-RFID` lesend aufgelöst. GitHub lieferte dort dieselben Commit-Metadaten, denselben Tree `14c8a895c4c5e6903315096a75c6b918228b6fa1` und beide Eltern `ab1b5270b091cc4204a6b3734b7e03f3c5ffadbb` und `d97312e2e26cb488fc001f159664e13447b6ce4f`. Der Fork hatte vor der Änderung nur `develop` (`42d5023e37dbf8de6477fef5ebcd6eae3cb5087d`). Anschließend wurde im Fork der Branch `feature/foundation` exakt auf den geprüften Commit angelegt. Das erneute Lesen des Branches bestätigt denselben Head-SHA und dieselbe Commit-/Tree-/Elternhistorie. `develop` blieb unverändert.

## F01 – ausführbare lokale Entwicklungsumgebung

Ein einmaliger `git ls-remote --heads --tags https://github.com/Motrish/RPi-Jukebox-RFID.git`-Versuch in `G:\Entwicklung` scheiterte mit Exitcode 1: Verbindung zu `github.com:443` nicht möglich. Es existiert hier kein lokaler Checkout des Zielrepositories. Der GitHub-Connector kann Repositorydaten lesen und API-Schreibrechte ausweisen, stellt aber keinen vollständigen lokalen Clone, Git-Objekttransfer oder Checkout bereit. Es wurde kein Sourcebaum aus einzeln abgerufenen Dateien zusammengesetzt.

Der isolierte Dokumentations-Commit 77a7f60a2d3961c04288c0e885b62e283b127c3e auf docs/development-plan wurde veröffentlicht; alle neun Dateien und der Branch-SHA wurden zurückgelesen. Damit ist API-Schreiben geprüft; ein API-Commit ist kein Nachweis für lokalen Git-Push. Workflow-Schreibrechte sind mit den verfügbaren Connector-Lesezugriffen nicht getrennt verifiziert. Es wurde keine Workflowdatei geändert.

Mangels vollständigem lokalen Checkout konnten weder `G:\Entwicklung\phoniebox-dev` erstellt noch ein nativer Git-Worktree oder lokale Build-/Testabhängigkeiten hergestellt werden. Getrennte Worktrees sind daher noch nicht verfügbar und es gab keinen lokalen Branch-/Commit-/Push-Test. Die bestehende Sandbox wird nicht umgangen und es wurde kein Eskalationszugriff angefordert.

## Historischer Abnahmestand vor Cloud-Fortsetzung

- **F01:** Teilweise erreicht. Fork-Connector-Schreibtest liegt beim Koordinator; lokaler Git-Fetch, Checkout, Worktree, Push und Workflowrechte bleiben offen. G0 ist nicht erfüllt.
- **F02:** Remote-Basisbranch `feature/foundation` erfolgreich auf dem Upstream-Release-Commit angelegt. Die GitHub-API-Auflösung belegt, dass der Fork diesen SHA als Commitobjekt kennt. Vollständiger Checkout, lokale Prüfung der Elternhistorie und erforderlichen Dateien bleiben wegen F01 offen; F02 ist daher remote vorbereitet, aber nicht vollständig abgenommen.
- **Nächster zulässiger Schritt:** Git-fähigen Arbeitsplatz mit Netzwerkzugriff bereitstellen oder freigeben. Dort `feature/foundation` vollständig klonen/fetchen und lokal prüfen; bis dahin keine Produktcode-Tickets starten und `develop` nicht als V3-Basis verwenden.

Es wurden keine Produktdateien, Tests oder Geräte verändert. Die reale Phoniebox wurde nicht angesprochen.

## Cloud-Baseline

GitHub Actions ist im Fork aktiv. Die vorhandenen V3-Workflows besitzen future3-Branch-/Pfadfilter und keinen manuellen Dispatch. Ein separater future3/ci-baseline-Integrationscommit mit exakt originalem V3-Tree löst diese vorhandenen Prüfungen aus. V3-Webbuild ist bestanden, Python/Installation laufen noch. Vollständige interaktive lokale Checkouts und Worktrees bleiben davon getrennt offen.

## Remote-Cloud-Baseline-Prüfung (16.10.2026, Fortsetzung)

Der einmalige weitere `git ls-remote --heads --tags`-Versuch scheiterte erneut mit Exitcode 1 (`github.com:443` nicht erreichbar). Lokaler Git-Transport bleibt damit blockiert.

GitHub Actions kann dagegen Remote-Commits auschecken und ausführen. Ein eigens bereitgestellter Baseline-Branch `future3/ci-baseline` wurde im Runner auf exakt `58826fcf880f521292c56c43b682fa67cfdc2418` ausgecheckt. Der Runner verwendete `fetch-depth: 1`; dies belegt einen vollständigen Datei-Checkout dieses Commits, aber nicht dessen vollständige Elternhistorie. Cloud-CI kann deshalb reproduzierbare Builds und Tests auf dem remote gespeicherten Quellstand liefern, ersetzt jedoch keinen lokalen Git-Checkout oder mehrere lokale Worktrees.

Runstatus:

- `38955136500` Python Checks: abgeschlossen, erfolgreich; Test-/Lintschritte liefen mit Python 3.9–3.13.
- `38955136477` Web-App Build: abgeschlossen, erfolgreich.
- `38955136828` Installer/Debian: `bookworm armv7`-Imagebuild erfolgreich; fünf Installerskripte liefen bei letzter Statusabfrage noch. `bullseye armv7`-Imagebuild fehlgeschlagen; alle Bullseye-Testjobs wurden übersprungen.

Die konkrete Bullseye-Ursache liegt im Basistarget `ci/ci-debian.Dockerfile`, `apt-get update` gefolgt vom Paketdownload. Der Runner erhielt mehrere HTTP 404 vom Debian-Security-Pool für Bullseye-Pakete, darunter OpenSSL, ca-certificates, curl und GnuPG; APT endete mit Exitcode 100. Die Bookworm-Variante desselben Targets war erfolgreich. Debian meldete das Ende von Bullseye LTS zum 31.08.2026 ([Debian-Mitteilung](https://www.debian.org/News/2026/20260831)). Das ist ein veraltetes Testmatrixziel nach Supportende, kein bisheriger Nachweis für einen Phoniebox-Produktfehler.

Zwischenstand vor der Koordinatorfreigabe: als kleinste Korrektur war das Entfernen allein des aktiven Bullseye-Armv7-Aufrufs bei Beibehaltung von Bookworm vorgeschlagen. Die freigegebene und tatsächlich ausgeführte Änderung ist im folgenden Abschnitt mit Commit und Readback festgehalten; es gab keine Dockerfile- oder Produktcodeänderung.

### CI-Korrektur nach Freigabe durch den Koordinator

Auf Freigabe wurde der isolierte Branch `future3/fix-ci-baseline` vom exakten Basis-SHA `58826fcf880f521292c56c43b682fa67cfdc2418` angelegt. Commit `83b0c01f655f7943ed238371d14574e5129a6d21` ändert ausschließlich `.github/workflows/test_docker_debian_v3.yml`: der aktive Bullseye-Armv7-Matrixjob wurde entfernt, der Bookworm-Armv7-Job bleibt. GitHub-Compare bestätigt `ahead_by=1`, `behind_by=0`, eine geänderte Datei und sechs entfernte Zeilen; Readback bestätigt Datei-SHA `f432504cdcf8ebf3c7a020b6eb3bcc7278d55634`.

Der Folge-Workflow `38957569477` wurde beim Push automatisch ausgelöst und validiert den Workflow auf GitHub; er lief zuletzt mit dem einzigen Job `bookworm armv7 / build` noch. Kein lokaler YAML-Parser war verfügbar (`ConvertFrom-Yaml` fehlt); ein Python-One-Liner zur Parserprüfung wurde durch die Sandboxrichtlinie abgewiesen. Der Remote-Runner ist daher die YAML-/Buildprüfung. Der unveränderte Baseline-Installer-Workflow `38955136828` lief parallel weiter; Bookworm-Build war erfolgreich, fünf Bookworm-Installerjobs waren bei letzter Abfrage noch in Bearbeitung. Das ist getrennt vom Folge-Run und wird nicht als bestanden gewertet.

Änderung und Remote-Commit erfolgten über GitHub-Objekte auf dem isolierten Branch. Es gibt weiterhin keinen lokalen Checkout oder Worktree; weder Elternhistorie noch Hardwareverhalten sind durch diese Cloud-Runs bewiesen. Der Koordinator erstellt den Draft-PR gegen `future3/modern-ui`.

Status-Update für den Koordinator: bei der letzten GET-Abfrage liefen der unveränderte Installer-Baseline-Run `38955136828` (fünf Bookworm-Testschritte) und der korrigierte Workflow-Run `38957569477` (Bookworm-Imagebuild) noch. Die Rootkoordination übernimmt die spätere Abschlussabfrage; bis dahin werden keine weiteren Runs gestartet.

## Aktuelle Arbeitsentscheidung nach Limitreset

Die vorstehenden frühen Aussagen zu ungeprüften Workflowrechten und noch nicht startbaren Produktmodulen sind historische Zwischenstände. Workflow-Schreiben ist inzwischen mit Commit 83b0c01 und Dateireadback bestätigt. Die Koordination hat eng begrenzte transportfreie Modulentwicklung auf isolierten Remote-Branches freigegeben; vollständige CI-Checkouts und lokale Modulprüfungen bleiben getrennte Nachweise. F01 und G0 bleiben hinsichtlich lokaler Worktrees offen. Maßgeblich ist tasks/todo.md.

## Lesender Nachcheck am 17.10.2026

Eine vorhandene andere lokale Phoniebox-Arbeitskopie wurde ausschließlich lesend geprüft. Sie enthält nur einen Filebrowser-Arbeitsbranch, hat eigene ungesicherte Änderungen und besitzt das benötigte V3-Releaseobjekt 4fa84fd50750fd4b52984d51aa7c95466cf5b241 nicht. Sie wurde nicht verändert und ist kein Ersatz für einen vollständigen V3-Entwicklungscheckout. F01/G0 bleiben für lokale V3-Worktrees offen. Der U02a-Stage bleibt ausdrücklich eine isolierte vier-Dateien-Vorschau mit Browsernachweis und vollständigem Webbuild in GitHub Actions.

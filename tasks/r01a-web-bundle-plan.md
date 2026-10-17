# R01a – CI-Web-Bundle mit passendem Backendstand

Vorhandene Entwicklungsfreigabe und der nächste-Schritte-Auftrag decken diesen begrenzten Slice. Basis: future3/modern-ui 6b872011c2e79263f61ca5384908b23251178a6b, Baum fbf9127e7299bac52ada5fda9ce042cee7c6a9a9. Root/Sol schreiben ausschließlich Prosa und Review; Luna erstellt alle ausführbaren Artefakte. Ein Autor, nach Freeze serielles unabhängiges Review. Status nur in todo.md.

## Ziel, Wiederverwendung und Entscheidung

Vorhandenen erfolgreichen Webbuild nach allen bisherigen Prüfungen als CI-Artefakt verpacken. Ein strenger Manifest-/Hashprüfer bindet Archivbytes an den erwarteten vollständigen Backendcommit und Fork. Auf dem Zero W ist dafür kein Node/npm/React-Build vorgesehen. Aktuell unveränderte Buildaction verwendet Node20 und run_rebuild.sh; sie wird hier wiederverwendet. Der bisherige Installer lädt aus Upstreamreleases mit verkürztem Hash und möglichem latest-Fallback. Er wird hier nicht als geeigneter Forklieferweg übernommen oder verändert.

Gewählte kleine Lösung: deterministisches tar.gz aus einem bereits fertig gebauten Ordner plus Manifest, Offlineprüfung und echter CI-Upload/Download-Rundlauf. Die alternatives vollständige Release-/Update-/Rollbackautomatik hat noch offene Vorgänger und wird nicht vorgezogen. Keine bestehende Bibliotheks-, nginx-, Auth-, Installer- oder Playerquelle ändern.

Ruling: R01 als Gesamtticket verlangt I06/P08/S04. Nur der eigenständig prüfbare frühe R01a-Producer-/Manifest-Slice wird vorgezogen, weil I01b ein passendes vorgebautes Bundle benötigt. R01 bleibt nach diesem Slice in_progress, kein Update-/Rollback-/Gerätenachweis. Kosten einer späteren Vertragsänderung sind eine reversible Manifest-/Produceranpassung.

## Genau drei ausführbare Pfade

1. tools/web_bundle.py – Python-stdlib, Paketierung und reiner Manifest-/Archivbyte-Prüfer mit CLI.
2. test/web_bundle/test_web_bundle.py – stdlib-unittest, echte temporäre Builddateien und CLI-/Negativproben.
3. .github/workflows/test_build_webapp_v3.yml – bestehende Prüfungen erhalten, gezielte Tests und Paket-/Upload-/Download-/Prüfrunde ergänzen; beide Pfadfilter um Tool und Tests erweitern.

Teilstage G:/Entwicklung/phoniebox-staging/r01a-web-bundle. Keine Dependencies/Lockfiles oder bestehende Buildaction ändern. Python mindestens3.9 gemäß vorhandener Matrix; keine zusätzliche Laufzeitbibliothek. Feste neue Ausgabedateien webapp-build.tar.gz und manifest.json. Keine Herstellerbinary, Musik, Settings, Authdaten oder Repositorydateien außerhalb des expliziten fertigen Buildordners verpacken.

## Datenvertrag und Vertrauensgrenze

Manifestformat1, geschlossene Felder: formatVersion, kind, repository, backendCommit, archiveName, archiveSha256, archiveSizeBytes, fileCount. kind ist phoniebox-webapp; archiveName ist webapp-build.tar.gz. repository ist eine gültige GitHub-owner/repo-Identität; backendCommit exakt40 kleine Hexzeichen; archiveSha256 exakt64 kleine Hexzeichen. Größen/Zählwerte sind echte positive Integers, keine booleans. Maximal64MiB komprimiertes Archiv,256MiB reguläre Eingabedateien insgesamt und4096 Dateien. Manifest maximal16KiB, UTF8, keine doppelten JSON-Schlüssel/NaN/Inf/zusätzlichen Felder. Zukünftige Formate ablehnen statt erraten.

Der Prüfer verlangt erwartetes Repository und erwarteten vollen Commit als eigene vertrauenswürdige Eingaben. Falscher Fork oder Commit, falscher Archivname, Größe oder SHA256 scheitern. Archivpfad ist ein explizites CLIargument; Manifest darf keinen Pfad oder Download auswählen. Datei stückweise hashen; keine Netzwerk-, Shell-, Installations-, Extraktions- oder Aktivierungsfunktion. Ausgabe bestätigt ausschließlich Identität und Digest. SHA256 authentifiziert den Hersteller nicht; dafür braucht der spätere Downloader einen vertrauenswürdigen Manifestlieferweg. Keine Installationsfreigabe allein aus einem selbst gelieferten Manifest ableiten.

Ruling zur kleinen Grenze: Dieser Prüfer liest keinen untrusted TAR-Inhalt und extrahiert nichts. Die spätere sichere Extraktion gehört in I01b/R01b. Der Producer erstellt ausschließlich reguläre relative Builddateien. Seine Tests lesen das von ihm erzeugte vertrauenswürdige Archiv und belegen Mitglieder/Bytes. Dadurch wird kein allgemeiner Archivparser als Nebenprojekt eingeführt.

## Producerverhalten

Einen expliziten fertigen Buildordner einschließlich index.html verlangen. Nur dessen reguläre Dateien, deterministische POSIX-Reihenfolge; symbolische Links, Geräte/FIFOs und unzulässige relative Namen ablehnen. Keine absoluten/Parent-/Backslash-/Steuerzeichenpfade. Keine Dateien außerhalb des Buildroots folgen. Ein Ausgabeordner im Buildroot oder mit bereits vorhandenen Ausgabedateien muss ohne Überschreiben scheitern. Größen- und Dateizahlgrenzen während Sammlung/Streaming durchsetzen. Auf Fehler nur selbst erzeugte temporäre Dateien entfernen, keine rekursive Fremdbereinigung.

Gleiche fertige Eingabebytes plus Identitätsdaten ergeben gleiche Archiv-/Manifestbytes: feste Archivzeit, Eigentümer-/Rechtewerte und gzip-Zeit, keine Laufzeit-/Hostdaten. Das behauptet keine reproduzierbare npm-Abhängigkeitsauflösung über mehrere Builds; die unveränderte Buildaction verwendet npm install. Kein eingebettetes Git-/Nodewerkzeug für die Offlineprüfung erforderlich. Dateimodi im Archiv bleiben nicht ausführbar; der Producer gibt keine Secret-/Dateiinhalte aus.

## Test-first und tatsächliche Abnahme

Phase1 nur unittest und Workflow. Das Produktmodul bleibt abwesend. Nach erfolgreichem vorhandenen Build muss der gezielte neue Testschritt tatsächlich am fehlenden Modul rot werden. Autor friert Testphase ein; Root veröffentlicht, prüft lokalen V3lint und tatsächlichen Linux-RED. Unabhängiges Testreview vor Implementierung. Kein erneuter RED-Vollauf für Korrekturen unter unverändertem frühen Import-Sentinel, wenn Root diese Grenze konkret nachweist.

Tests: deterministische Paketierung und bytegleiche Archivmitglieder für mindestens verschachtelte JS/CSS-/JSON-/index-Dateien; gleicher Inhalt bei geänderten Quell-mtimes; gültiger Offlinecheck; falscher erwarteter Commit/Fork; manipulierte/abgeschnittene Archivbytes; abweichende Größe; unzulässige/zusätzliche/doppelte Manifestfelder und Typen/Version; ungültige Identitäten; fehlendes index; Symlink und unzulässige Namen; bestehende Ausgaben und Ausgabe im Buildroot ohne Überschreiben; Größen-/Zählgrenzen ohne riesige Testdaten; erfolgreicher und fehlgeschlagener CLIprozess mit sicherer Meldung. Nicht nur Helperimplementierung nachtesten.

Phase2 nach tatsächlichem RED und akzeptierten Tests nur neues Produktmodul erstellen. Alle lokalen relevanten unittests und V3flake8 laufen lassen. Root publiziert ausschließlich die3 Whitelistdateien, genaue SHAs und Inhalte zurücklesen, dann vollständige Web-/Pythonabnahme und frisches Source-/Gesamtreview.

CI erhält die bereits vorhandenen24 Bibliotheks-Jesttests, Verträge und alle3 Browser/nginxprüfungen. Paketierung erst nach deren Erfolg. Tatsächlichen Checkout-HEAD über git rev-parse ermitteln, nicht ungeprüft github.sha für PR-Kontexte übernehmen; Forkidentität aus vertrauenswürdigem Repositorykontext. Archiv und Manifest in frischem Runner-temp-Ordner erzeugen, offline prüfen, mit actions/upload-artifact v4 hochladen. Artefaktname enthält vollen tatsächlichen Commit. Danach dieses konkrete Upload-Artefakt über dessen ID in anderen frischen Runner-temp-Ordner herunterladen und den Offlineprüfer erneut mit demselben erwarteten Fork/Commit ausführen. Erfolgsprüfung auf tatsächlichen CRA-Build, nicht nur Fixtures. Endliche Stepdeadlines und bestehende Jobdeadline erhalten. Keine neuen Secrets, Schreibrechte, Releases, Tags oder Deployments.

## Ausführungsgrenzen und folgende Pakete

GitHub-Actions-Artefakte sind aktuell ein authentifizierter, zeitlich begrenzter CI-Lieferweg. Sie sind kein fertiger anonymer Browserbootstrap. Öffentliche Releasebereitstellung und sichere Extraktion/Installation werden später gesondert entwickelt; aktueller Slice veröffentlicht keinen Release. Primärquelle: [GitHub-Artefaktdownload](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts), [Artifact-REST-API](https://docs.github.com/en/rest/actions/artifacts), [offizielle Uploadaction](https://github.com/actions/upload-artifact).

Kein Pi-/ARMv6-/Audio-/Liveplayer-/Spotify-/PiSugar-/LAN-/HTTPS-/Update-/Rollbacknachweis. Die Webassets sind clientseitige Buildausgabe; ihre Lauffähigkeit auf dem Zielbrowser und der sichere Setupzugang bleiben separate Abnahmen. Nach dieser Grundlage I01b konkretisieren, ohne ungeschützten lokalen HTTPzugang als fertigen HTTPS-/OAuthweg auszugeben.

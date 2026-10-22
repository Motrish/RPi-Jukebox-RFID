# Modern-UI-Pilot (C9)

## Zweck und Umfang

Der Pilot ist eine isolierte Oberfläche unter `#/modern-ui`. Der Einstieg wird
getrennt vom Legacy-WebSocket-Boot ausgeführt; die moderne Ansicht benötigt
keinen `LegacyWebsocket`-Start. Die bestehende React-17-, MUI-5- und
Create-React-App-Basis bleibt erhalten. Der Pilot ist keine Ablösung der
bestehenden Oberfläche und kein produktiver Geräte- oder Installationsablauf.

### Vorhandene Funktionen

- Playlists auflisten und einzelne Playlist-Snapshots laden (`readlist`/
  `getplaylist`) sowie einen Queue-Snapshot laden (`getqueue`) mit einem
  separaten Lese-Zugangscode.
- Erweiterte Playlist-/Queue-V1-Kommandos als JSON über den separaten
  Schreib-Zugangscode senden. Eingaben und Antworten werden gegen den V1-Vertrag
  geprüft; der Client beschränkt Schreibvorgänge auf die erlaubten
  Playlist-/Queue-Kommandos.
- Bei einem Fehler wird kein automatischer Wiederholungsversuch ausgelöst.
  Falls ein Aufruf manuell erneut versucht wird, muss dasselbe Kommando mit
  unverändertem `commandId` gesendet werden; bei geändertem Inhalt ist eine neue
  ID zu verwenden.
- Der LibraryBrowser bietet Suche und Auswahl in einer einfachen,
  nicht virtualisierten Liste.
- PlayerControls sind getestet, erweitern aber nicht die verfügbaren
  Gerätefunktionen: Es entstehen keine neuen Pause-, Next- oder
  Lautstärke-Fähigkeiten.
- SettingsPage bearbeitet und validiert einen lokalen Konfigurationsentwurf.
  Ohne angeschlossenen Speicherdienst wird nichts am Daemon gespeichert oder
  wirksam. Die Oberfläche darf daher keinen erfolgreichen persistenten
  Speichervorgang suggerieren.

Zugangscodes werden nur im Zustand der Ansicht gehalten; die Requests verwenden
keinen Browser-Storage. Schreibzugriff erfordert explizit den separaten
Schreib-Zugangscode. C7 kann optional
`playlist_write_token_path` als Pfad zu einer Schreib-Token-Datei ergänzen;
dieser Pfad ist vom Lese-Token-Dateipfad getrennt. Das ist eine Konfigurations-
und Integrationsvoraussetzung, kein Grund, Lese- und Schreibberechtigung im UI
zusammenzulegen.

## Netzwerk- und Deployment-Grenzen

Der HTTP-Pilot ist ausschließlich für Loopback bestimmt. Er ist kein
LAN-Service, kein Produktions- oder Raspberry-Pi-Deployment und keine Freigabe,
den Dienst nach außen zu exponieren. Browser-Hosting erfolgt bei einem
freigegebenen bestehenden Loopback-Setup über dieselbe Origin. Dieses Dokument
liefert keine Anleitung für einen Proxy, eine LAN-Freigabe oder eine sonstige
Umgehung dieser Grenze. Es wurden dadurch keine Änderungen am Raspberry Pi
vorgenommen.

## Bewusst nicht enthalten

- Live-Wiedergabeintegration und neue Geräte-Transportfunktionen.
- Benutzerfreundliche Playlist-/Queue-Formulare für CRUD; Schreiboperationen
  werden derzeit über das erweiterte JSON-Kommando angeboten.
- Virtualisierung großer Bibliotheken.
- Persistente Daemon-Einstellungen, Storybook-Einrichtung oder eine
  Abhängigkeit-/Framework-Migration.

## Prüfungen

Der C9-Pilot-Workflow `.github/workflows/c9-pilot.yml` enthält echte Gates für
Webapp-Lint, Unit-Tests, Build und einen Chromium-Browser-Smoke-Test. Die
Build-Umgebung setzt `CI=false`, damit die bekannten CRA-Legacy-Warnungen den
Build nicht als Fehler abbrechen; Buildfehler bleiben fatal und Tests werden
nicht deaktiviert. Testergebnisse und Zählwerte sind nur aus einem tatsächlich
ausgeführten Lauf abzuleiten, nicht aus diesem Dokument.

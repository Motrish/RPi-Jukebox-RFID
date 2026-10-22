# Sprint C9 – GUI-Grundlagen: Komponenten-Inventar, Design-Tokens, Storybook, CI

Sprint-Backlog für 2 Wochen im Webapp-Ordner `src/webapp`.

| Feld | Wert |
| --- | --- |
| Zeitraum | Mo 26.10.2026 – Fr 06.11.2026 (10 Arbeitstage) |
| Branch | `codex/p04f-c9-gui` |
| Scope | `src/webapp` sowie CI-Workflow `.github/workflows/test_build_webapp_v3.yml` |
| Kapazität | 1 Entwickler, ca. 9 Personentage (1 Tag Puffer) |
| Stand | 22.10.2026 |

## Sprint-Ziel

Die GUI-Grundlagen für die moderne React-Oberfläche konsolidieren: ein
vollständiges Komponenten-Inventar der vier Kernbereiche (PlayerControls,
LibraryBrowser, Settings, CoverArt), formalisierte Design-Tokens in
`src/theme.js`, ein lauffähiges Storybook zur visuellen Dokumentation und ein
CI-Gate, das `npm run test:unit` und `npm run build` auf jedem Push ausführt.

Voraussetzung im Bestand: Die Webapp läuft auf React 17, MUI 5
(`@mui/material`), CRA (`react-scripts` 5), i18next und react-router-dom 6.
`src/theme.js` enthält derzeit nur `palette.mode: 'dark'` und
`palette.primary: teal` – Spacing und Typography sind nicht formalisiert.
Test-Script existiert nur als `npm test` (watch-modus), ein `test:unit`-Script
fehlt. Storybook ist nicht eingerichtet.

## Backlog-Übersicht

| ID | Thema | Aufwand (Tage) | Status |
| --- | --- | --- | --- |
| C9-01 | Komponenten-Inventar: PlayerControls | 1.0 | offen |
| C9-02 | Komponenten-Inventar: LibraryBrowser | 1.5 | offen |
| C9-03 | Komponenten-Inventar: Settings | 1.5 | offen |
| C9-04 | Komponenten-Inventar: CoverArt | 0.5 | offen |
| C9-05 | Design-Tokens (Farben, Spacing, Typography) | 1.5 | offen |
| C9-06 | Storybook-Setup (`npm init storybook`) | 1.5 | offen |
| C9-07 | CI-Step `npm run test:unit` + `npm run build` | 1.0 | offen |
| – | Puffer / Nacharbeit | 0.5 | – |

## Detail-Aufgaben

### C9-01 Komponenten-Inventar: PlayerControls

Ausgangslage (vorhanden unter `src/components/Player/`):

- `controls.js` – Transport-Buttons (Play/Pause, Next/Previous)
- `seekbar.js` – Fortschrittsbalken
- `volume.js` – Lautstärkeregler
- `display.js` – Player-Anzeige
- `index.js` – Zusammenspiel mit `src/context/player`

Aufgaben:

1. Ist-Inventar der Player-Controls dokumentieren (Props, Zustand, Abhängigkeit
   zum Player-Context).
2. Klare Props-Schnittstelle `PlayerControls` definieren
   (`onPlay`, `onPause`, `onNext`, `onPrevious`, `onSeek`, `onVolumeChange`,
   `disabled`), damit die Komponente ohne laufenden Player-Context testbar und
   storybar ist.
3. Storybook-Stories `PlayerControls/Default`, `/Disabled`, `/VolumeChanging`
   vorbereiten (Details in C9-06).

Akzeptanzkriterien:

- Inventar-Tabelle in dieser Datei ist vollständig (alle Dateien in
  `src/components/Player/` zugeordnet).
- `PlayerControls` ist über Props steuerbar, ohne dass ein MQ/WS-Context
  benötigt wird.
- Mindestens eine Unit-Test-Skizze (Testfälle notiert, Umsetzung in C9-06/C9-07
  nachgeschoben).

### C9-02 Komponenten-Inventar: LibraryBrowser

Ausgangslage (vorhanden unter `src/components/Library/`):

- `index.js`, `library-header.js`, `selector-header.js`
- `lists/albums/` – Album-Liste, Song-Liste inkl. Header/Controls/Headline
- `lists/folders/` – Ordner-Navigation, Folder-Link, Type-Avatar
- `DesignPreview/LibraryPage.js` mit Test `LibraryPage.test.js` und Mock-Daten
  (`previewModel.js`, `libraryClient.js`) – als Vorlage für Storybook-Fixtures
  wiederverwenden.

Aufgaben:

1. Ist-Inventar der Library-Komponenten dokumentieren (Navigationspfade,
   Datenquellen, Context-Abhängigkeiten).
2. `LibraryBrowser` als zusammenhängende Oberfläche beschreiben:
   Eingaben (aktiver Pfad, Auswahl), Ausgaben (Events) und Trennung von
   Daten-Fetching (`libraryClient`) und Darstellung.
3. Mock-Fixtures aus `DesignPreview/previewModel.js` als gemeinsame
   Storybook-Fixtures vorschlagen.

Akzeptanzkriterien:

- Alle Dateien unter `src/components/Library/` sind im Inventar erfasst.
- Grenz- und Abhängigkeits-Schnittstelle zu `context/` ist schriftlich
  festgehalten (was braucht die Komponente echt, was wird gemockt).
- Storybook-Stories `LibraryBrowser/Albums`, `/Folders`, `/SongList` sind
  vorbereitet.

### C9-03 Komponenten-Inventar: Settings

Ausgangslage (vorhanden unter `src/components/Settings/`):

- `audio/` – Maximal-Lautstärke, Outputs
- `general/` – Show-Covers-Schalter
- `status/` – Battery, CPU-Temp, Disk-Usage, IP-Address, Version
- `timers/` – Timer-Dialog, Timer-Liste
- `dialogs/` – Reboot, Shutdown
- Diverse: `autohotspot.js`, `secondswipe.js`, `systemcontrols.js`

Aufgaben:

1. Ist-Inventar der Settings-Panels dokumentieren (Gruppen: Audio, General,
   Status, Timers, System).
2. Gemeinsame Formular-Patterns identifizieren (Switch, Slider, Dialog,
   Laden-Zustand) und als Kandidaten für wiederverwendbare Basis-Komponenten
   markieren – ohne in diesem Sprint umzubauen.
3. Storybook-Stories für die zentralen Panels vorbereiten.

Akzeptanzkriterien:

- Alle Dateien unter `src/components/Settings/` sind im Inventar erfasst.
- Jedes Panel hat eine zugeordnete Story-Gelegenheit bzw. ist als
  „nicht storybar (System-Dialog)" begründet.
- Keine Verhaltensänderung im Settings-Code (nur Inventar + Stories).

### C9-04 Komponenten-Inventar: CoverArt

Ausgangslage:

- `src/components/Player/cover.js` – aktuelle Cover-Darstellung
- `src/components/Settings/general/show-covers.js` – Anzeige-Einstellung
- `src/components/DesignPreview/previewModel.js` – Cover-Platzhalter in Mocks

Aufgaben:

1. `CoverArt` als eigene, wiederverwendbare Komponente beschreiben:
   Props (`src`, `alt`, `size`, `variant`), Fallback-Platzhalter bei fehlendem
   oder defektem Bild.
2. Zustände definieren: laden, geladen, Fehler/Fallback, kein Cover vorhanden.
3. Storybook-Stories `CoverArt/Loaded`, `/Fallback`, `/NoCover` vorbereiten.

Akzeptanzkriterien:

- Fallback-Verhalten ist schriftlich definiert und deckt „kein Bild" und
  „Ladefehler" ab.
- Story mit lokalem Platzhalter-Bild ist vorbereitet (keine externen URLs).

### C9-05 Design-Tokens (Farben, Spacing, Typography)

Ausgangslage: `src/theme.js` legt nur `palette.mode: 'dark'` und
`palette.primary: teal` fest. Spacing und Typography sind nicht formalisiert.

Aufgaben:

1. Tokens in `src/theme.js` über `createTheme()` ergänzen (Konkretvorschlag
   unten).
2. Tokens zentral exportieren, damit Komponenten direkt aus dem Theme lesen
   (keine harten Farb-/Abstandswerte in Komponenten).
3. Altbestand scannen: hart kodierte Farben/Abstände auflisten und als
   Nachzieh-Aufgabe für den nächsten Sprint notieren (in diesem Sprint nicht
   umbauen).

Konkretvorschlag:

Farben:

| Token | Wert | Zweck |
| --- | --- | --- |
| `palette.primary.main` | `teal[500]` (`#009688`) | Akzent, bleibt wie Bestand |
| `palette.primary.dark` | `teal[700]` (`#00796B`) | Hover/Pressed |
| `palette.background.default` | `#121212` | Seitenhintergrund (MUI-Dark-Default) |
| `palette.background.paper` | `#1E1E1E` | Karten/Panels |
| `palette.text.primary` | `#FFFFFF` | Fließtext auf Dunkel |
| `palette.text.secondary` | `#B0B0B0` | Sekundärtext |
| `palette.error/warning/info/success` | MUI-Defaults | System-Status (Status-Panels) |

Spacing (4-px-Raster, an MUI `spacing()` angleicht):

| Token | Wert |
| --- | --- |
| `spacing.xs` | 4 px |
| `spacing.sm` | 8 px |
| `spacing.md` | 16 px |
| `spacing.lg` | 24 px |
| `spacing.xl` | 32 px |

Typography:

| Token | Wert |
| --- | --- |
| `typography.fontFamily` | Roboto, `"Helvetica Neue"`, Arial, sans-serif |
| `typography.h1` | 24 px / 700 / 1.2 |
| `typography.h2` | 20 px / 700 / 1.3 |
| `typography.body1` | 14 px / 400 / 1.5 |
| `typography.body2` | 12 px / 400 / 1.5 |
| `typography.caption` | 11 px / 400 / 1.4 |

Akzeptanzkriterien:

- `src/theme.js` exportiert das erweiterte Theme, `npm run build` bleibt grün.
- Alle vier Token-Gruppen (Farben, Spacing, Typography) sind im Theme
  repräsentiert.
- Kurze Token-Referenz in dieser Datei (oben) entspricht dem Code-Stand.

### C9-06 Storybook-Setup

Aufgaben:

1. Storybook im Webapp-Ordner initialisieren:
   `cd src/webapp && npm init storybook@latest`
2. Compatibilität klären: Die Webapp nutzt React 17. Falls das aktuelle
   Storybook React 18+ voraussetzt, auf Storybook 8.x pinnen
   (`npx storybook@8 init`) anstatt in diesem Sprint React zu upgraden.
   Entscheidung am Tag 2 dokumentieren.
3. `.storybook/main.js` und `.storybook/preview.js` einrichten:
   - Theme-Decorator mit `src/theme.js` (`ThemeProvider` + `CssBaseline`)
   - i18next-Mock, damit Stories ohne Backend rendern
   - Keine echten MQ/WebSocket-Verbindungen in Stories (Contexts mocken;
     siehe `DesignPreview/libraryClient.js` als Vorbild)
4. Stories für C9-01 bis C9-04 anlegen.
5. `package.json`: `storybook`/`build-storybook`-Scripts ergänzen,
   Storybook-Ordner werden committed (nicht ignoriert).

Akzeptanzkriterien:

- `npm run storybook` startet lokal, `npm run build-storybook` baut grün.
- Mindestens 8 Stories: PlayerControls (2), LibraryBrowser (3),
  CoverArt (3); Settings-Panels nach Kapazität.
- Kein Eingriff in Produktions-Code über das Theme hinaus (C9-05).

### C9-07 CI-Step `npm run test:unit` + `npm run build`

Aufgaben:

1. `package.json` ergänzen:

   ```json
   "test:unit": "react-scripts test --watchAll=false"
   ```

2. Workflow `.github/workflows/test_build_webapp_v3.yml` um zwei Schritte
   ergänzen (Arbeitsverzeichnis `src/webapp`, `CI=true`):

   ```yaml
   - name: Run unit tests
     working-directory: src/webapp
     run: npm run test:unit
     env:
       CI: "true"

   - name: Build web app
     working-directory: src/webapp
     run: npm run build
     env:
       CI: "true"
   ```

3. Prüfen, ob der explizite Build-Schritt den bestehenden Aufbau über
   `.github/actions/build-webapp` ersetzt oder ihn sinnvoll ergänzt; keine
   doppelte Build-Zeit ohne Nutzen.
4. Trigger-Datei pflegen: Der Workflow feuert aktuell nur bei Push auf
   `future3/**`. Damit der C9-Branch CI erhält, `codex/**` analog zum
   jüngsten Commit für `pythonpackage_future3.yml` ergänzen.
5. Bestehende Test-Schritte (`src/contracts/*.test.js`,
   `DesignPreview/LibraryPage.test.js`) laufen weiter; `test:unit` deckt
   künftig alle `*.test.js` unter `src/` ab.

Akzeptanzkriterien:

- `npm run test:unit` läuft lokal einmalig grün (bestehende Tests:
  `contracts/v1.test.js`, `contracts/playback-v1.test.js`,
  `DesignPreview/LibraryPage.test.js`).
- `npm run build` lokal grün.
- Workflow-Änderung ist auf dem Branch committet; CI läuft auf Push des
  Branches an.

## Zeitplan

| Tag | Schwerpunkt |
| --- | --- |
| 1 | C9-01 Start: Inventar Player, Storybook-Version klären |
| 2 | C9-02 Library-Inventar, Entscheidung Storybook-Version |
| 3 | C9-03 Settings-Inventar |
| 4 | C9-04 CoverArt, C9-05 Start Design-Tokens |
| 5 | C9-05 Design-Tokens abschließen |
| 6 | C9-06 Storybook-Setup (`npm init storybook`, Decorators) |
| 7 | C9-06 Stories für alle vier Bereiche |
| 8 | C9-07 `test:unit`-Script + CI-Workflow |
| 9 | CI-Grünlauf, Nacharbeit, Inventar-Doku final |
| 10 | Puffer / Review / Abschluss auf `codex/p04f-c9-gui` |

## Risiken und offene Entscheidungen

- **React 17 vs. Storybook:** Das aktuelle Storybook kann React 18+
  voraussetzen. mitigation: Pin auf Storybook 8.x; React-Upgrade ist eigener
  Sprint, kein Teil von C9.
- **CI-Trigger:** Ohne Ergänzung von `codex/**` in
  `test_build_webapp_v3.yml` läuft das neue CI-Gate auf diesem Branch nicht.
- **CRA/Node-Version:** `react-scripts` 5 ist empfindlich gegenüber sehr
  neuen Node-Versionen; CI-Node-Version unverändert lassen und lokal
  abgleichen.
- **Kontext-Gekoppelte Komponenten:** Player- und Library-Komponenten hängen
  an `context/player`, `context/appsettings` und `context/pubsub`; für Stories
  und Unit-Tests müssen diese gemockt werden – Aufwand ist in C9-01/C9-02
  kalkuliert.
- **Scope-Disziplin:** Keine Verhaltensänderungen an Komponenten in C9;
  Umbau/Refactor geht in den Folge-Sprint C10.

## Definition of Done

- Komponenten-Inventar für PlayerControls, LibraryBrowser, Settings und
  CoverArt vollständig in dieser Datei dokumentiert.
- Design-Tokens (Farben, Spacing, Typography) in `src/theme.js` umgesetzt und
  mit der Token-Tabelle oben abgeglichen.
- Storybook initialisiert, baut lokal grün, mindestens 8 Stories vorhanden.
- `npm run test:unit` und `npm run build` laufen lokal und im CI grün.
- Alle Änderungen liegen auf `codex/p04f-c9-gui`; kein Push auf
  `future3/**` oder `main` ohne explizite Freigabe.

## C9-Pilot: tatsächlicher Umfang und Komponenten-DoD

Der umgesetzte Pilot weicht vom ursprünglichen Backlog oben ab: Statt eines
Storybook-/Design-Token-Inventars entstand ein isolierter Einstieg
`#/modern-ui` mit Loopback-HTTP-Pilot. Der bestehende React-17/MUI-5/CRA-Stack
bleibt erhalten; es wurden weder Storybook noch eine Abhängigkeitsmigration
hinzuerfunden. Der tatsächliche Umfang und seine Sicherheitsgrenzen stehen in
[`docs/modern-ui-pilot.md`](../../docs/modern-ui-pilot.md).

| Bereich | Status | DoD / Abgrenzung |
| --- | --- | --- |
| PlayerControls | teilweise | Komponente und Tests vorhanden. Keine neuen Geräte-Pause-, Next- oder Lautstärke-Fähigkeiten. |
| LibraryBrowser | teilweise | Suche und Auswahl als nicht virtualisierte Liste vorhanden; keine skalierbare Virtualisierung. |
| SettingsPage | teilweise | Lokaler Konfigurationsentwurf mit Validierung; nicht daemonwirksam und kein persistentes „gespeichert“. |
| CoverArt | offen | Kein eigenständiger, abgenommener CoverArt-Bereich dieses Piloten. |

### Pilot-Abnahme und offene Restarbeit

- Isolierter `#/modern-ui`-Boot ohne LegacyWebsocket sowie Playlist-/Queue-
  Lesezugriffe und V1-JSON-Schreibzugriff mit getrenntem Schreib-Token sind der
  Pilot-Scope; Details und Grenzen siehe Pilot-Dokument.
- Der HTTP-Pilot bleibt Loopback-only. Kein LAN-/Produktionsbetrieb und kein
  Pi-Deployment sind Teil dieser Abnahme.
- Größere Restroadmap: C9-LivePlayback, benutzerfreundliche Formular-CRUD-
  Abläufe und Virtualisierung bleiben offen und sind nicht als erledigt
  abzunehmen.
- CI-Workflow `.github/workflows/c9-pilot.yml` führt Lint, Unit-Tests, Build
  und Chromium-Smoke-Test aus. `CI=false` beim CRA-Build lässt vorhandene
  Legacy-Warnungen sichtbar, macht sie aber nicht zu Buildfehlern; es schaltet
  keine Tests ab.
- Laufzahlen oder erfolgreiche Gates sind hier nicht behauptet; sie sind nur
  anhand eines tatsächlich ausgeführten CI-/Testlaufs zu bestätigen.

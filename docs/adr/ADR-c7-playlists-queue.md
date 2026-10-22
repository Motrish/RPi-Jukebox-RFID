# C7: Bestehenden Playlist-/Queue-Store über HTTP anbinden

## Status

Implementierter Pilot; abschließende Sicherheits- und Integrationsabnahme noch offen.
Kein Nachweis für Raspberry-Pi-Betrieb oder eine produktive LAN-Freigabe.

## Entscheidung

Der bestehende `PlaylistStore` und die geschlossenen V1-Verträge bleiben maßgeblich.
Die Runtime hält dieselbe Store-Instanz für Playback-Admission und Playlistzugriffe.
Es gibt keinen zusätzlichen Playback-Owner, keine Schema-Migration und keine
WebSocket-Implementierung in diesem Arbeitspaket.

Interne Tabellennamen werden nicht als HTTP-Feldnamen verwendet. Die API verwendet
camelCase und opake V1-Identifier, keine allgemeine UUID-Pflicht.

## Bestehende Tabellen

Quelle: `src/jukebox/components/playlists/store.py`.

| Tabelle | Spalten |
| --- | --- |
| `playlists` | `playlist_id`, `name`, `revision` |
| `playlist_entries` | `entry_id`, `playlist_id`, `media_ref_json`, `title`, `position` |
| `queues` | `queue_id`, `revision`, `source_playlist_id`, `source_playlist_revision`, `current_entry_id`, `repeat_mode`, `shuffle_mode` |
| `queue_entries` | `entry_id`, `queue_id`, `source_entry_id`, `media_ref_json`, `title`, `position` |
| `command_log` | `command_id`, `request_json`, `result_json` |
| `playback_intents` | `command_id`, `intent_id`, `intent_sequence`, `state`, `queue_id`, `entry_id` |

Eintragspositionen sind je Playlist beziehungsweise Queue eindeutig. Fremdschlüssel
auf Einträge verwenden Löschkaskaden. Revisions- und Positionswerte sind nichtnegativ.
Die Quellplaylist-ID und ihre Revision sind gemeinsam nullable. Wiederholmodus ist
`OFF`, `ALL` oder `ONE`, Shuffle ist `OFF` oder `ON`. Playback-Intents bleiben
`PENDING`; `queue_id` und `entry_id` sind dort gemeinsam nullable. Das ist keine
Persistenz abgeschlossener Playback-Ausführungen.

## HTTP-Vertrag

- `GET /api/playlists` mit begrenzter `limit`-/`cursor`-Pagination.
- `GET /api/playlists/{playlistId}` und `GET /api/queues/{queueId}`.
- `POST /api/playlist-commands` für die 14 öffentlichen V1-Store-Aktionen.

`QUEUE_SET_CURRENT` bleibt intern und ist über diesen Endpunkt nicht zulässig.
Playlistbearbeitung, Queuebearbeitung und Playlist-/Queue-Transfers verwenden die
bestehenden Commands, `commandId` und Revisionsprüfungen. Gespeicherte Queue-Modi
sind keine Zusage einer entsprechenden Playback-Fähigkeit.

Der maschinenlesbare Vertrag steht in `docs/openapi/playlists-v1.yaml`.
Die Python-/JavaScript-V1-Validatoren erzwingen zusätzlich die Querfeldregeln,
etwa zusammengehörige Quellfelder, Positionsfolgen und Auswahlzugehörigkeit.

## Berechtigungen und Lebenszyklus

Der HTTP-Pilot bleibt standardmäßig deaktiviert und bindet nur an Loopback.
`local_playback.http.playlist_write_token_path` aktiviert eine eigenständige
Schreibberechtigung. Ohne diesen Pfad sind Playlist-Schreibzugriffe gesperrt.
Lese-/Playback-Token und Schreibtoken müssen verschieden sein. Beide Token-Dateien
unterliegen den bestehenden Eigentümer-, Dateityp-, Längen- und `0600`-Prüfungen.
Die Autorisierung läuft nach 15 Minuten ab; es gibt keine automatische Erneuerung.

Autorisierung wird vor dem Request-Effekt und vor der Antwort geprüft. Ablauf oder
Closing nach einem Commit kann deshalb zu HTTP 401 trotz ausgeführter Mutation
führen. Niemals automatisch mit neuer `commandId` wiederholen. Bewusste Wiederholung
verwendet denselben Command und dieselbe ID.

Beim Shutdown werden neue Aufnahmen geschlossen; laufende Operationen werden vor
Ressourcenabbau und Owner-Freigabe abgewartet. Unvollständiger Drain ist kein Erfolg.

## UI und Abnahme

Die getrennte Ansicht `#/modern-ui` nutzt diesen Pilotvertrag. Zugangscodes bleiben
im Ansichtszustand. Der Settings-Editor ist nur ein Konfigurationsentwurf und schreibt
keine Daemondateien. Nicht unterstützte Playback-Aktionen werden nicht als wirksame
Gerätesteuerung angeboten.

Erforderliche Abschlussnachweise: Store-/Contract-/Runtime-/HTTP-Regressionen,
Token-Trennung und Ablauf, Drain-Rennen, React-Tests, echter Lint/Build,
Chromium-Smoke und unabhängiges Sol-Review. Erst danach gilt das Paket als abgenommen.

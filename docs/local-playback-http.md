# Local playback HTTP pilot

This is a **pilot interface**, not a deployment recipe. The feature has not
been validated on a Raspberry Pi and remains subject to the complete review
and integration gate. Do not infer production or LAN readiness from this note.

## Opt-in configuration

HTTP is disabled by default. Enable it only in the restricted local playback
profile. The playlist database path and bearer-token path are required when
enabled; the port is an integer from 1 to 65535. The loopback host defaults to
`127.0.0.1` and accepts only `127.0.0.1` or `localhost`. The command budget
defaults to 10 seconds and must be finite and positive.

```yaml
local_playback:
  enabled: true
  database_path: /path/to/library.sqlite
  library_root: /path/to/audio
  credential_path: /path/to/playback-owner-credential
  playlist_database_path: /path/to/playlists.sqlite
  http:
    enabled: false # change explicitly to true to opt in
    bearer_token_path: /path/to/http-bearer-token
    port: 8090
    origin_host: 127.0.0.1
    command_budget_seconds: 10
```

With HTTP disabled, the active local profile does not bootstrap the HTTP
listener or its separate playlist store. An HTTP opt-in in the legacy profile
is rejected rather than ignored.

## Token and network boundary

The token file must be a regular file owned by the daemon user, with exact
`0600` permissions. Its contents are exactly 43 ASCII URL-safe characters
(`A-Z`, `a-z`, `0-9`, `_`, `-`), optionally followed by one LF. The daemon
does not log the token. Do not put credentials in query strings. Read
authorization expires after 15 minutes; there is no automatic token refresh.

The listener binds only to loopback. This is not a LAN service and does not
provide TLS. Do not expose it through a network bind, reverse proxy, or port
forwarding as a deployment workaround.

## Ownership, commands, and limits

The daemon reuses the existing playback runtime and its single audio owner; it
does not create a second player or MPD owner. With HTTP enabled, playlist-store
schema initialization can occur at startup after owner acquisition. This is
not a V2 migration.

The POST wrapper's seven-field request shape represents **intent**, including
no-op intent; an accepted response does not mean playback completed. Replay
protection lasts only for the current owner lifetime. It is not restart-safe
exactly-once execution, and durable execution results are not persisted. A
server error after a crash is not a signal to automatically retry a provider
command.

Replacement first cleans up/stops the current playback before starting the
replacement. A timer-driven start is a new START operation, not a substitute
for replacement cleanup. The configured playback command budget bounds the
runtime command deadline; it is not a socket timeout and cannot impose a hard
deadline on arbitrary SQLite waiting.

If shutdown is incomplete, the daemon retains the audio owner. Do not kill
processes, delete lock files, or otherwise force-release that ownership.

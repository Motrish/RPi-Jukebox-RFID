# Local playback runtime owner

`LocalPlaybackRuntime` is an inactive, daemon-owned composition boundary for one
LOCAL playback service. Constructing it only validates and copies configuration.
The caller must explicitly call `start(deadline=...)`; no daemon, HTTP, RPC, or UI
registration is included in this change.

The runtime accepts only absolute POSIX paths for its database, media root,
credential, and optional lock-directory override. MPD is restricted to
`127.0.0.1`. The private credential file must be a regular file owned by the
daemon's effective UID, have no group or other permissions, and contain one
nonempty UTF-8 line of at most 4096 bytes. Its contents are never included in
diagnostics.

On Linux, startup acquires a nonblocking exclusive `flock` on
`audio-owner.lock` in `/tmp/phoniebox-playback-<effective-uid>` by default. The
directory must already be owned by the effective user and mode 0700; the lock
file must be regular, owned by that user, and mode 0600. The descriptor is held
until confirmed shutdown. The optional directory is for controlled composition
and tests; deployments must use the common default from every checkout.

Startup authenticates the tracked connection within the existing MPD session
transaction, reads fresh status, stops only a playing or paused queue, and always
checks a final stopped status and stable connection epoch. It preserves the
existing queue during reconciliation. A new boot identifier, real catalog-backed
provider, service, and the existing endless timer are created only after that
check succeeds. The timer processes at most one service operation per tick.

The runtime supports LOCAL start, replacement, and stop. Its provider advertises
confirmed stop only. Pause, resume, seek, natural-end detection, queue progression,
and remote playback remain unsupported. `snapshot()` exposes safe lifecycle and
service diagnostics; service receipts are not public playback-state evidence.

Shutdown closes admission promptly. `finish_shutdown(deadline=..., release_owner=False)`
uses one monotonic deadline to drain the service, stop and join the timer, and
close the connection and catalog while retaining the owner lock. Once diagnostic
modules close and their threads join, `finish_shutdown(deadline=...,
release_owner=True)` releases ownership and marks the runtime CLOSED. An
unconfirmed stop, blocked work, cleanup failure, or expired deadline retains
ownership for a later explicit cleanup attempt. Successfully closed resources
are not closed again during retries. An explicit stop retry already authorized
before shutdown remains pending while shutdown closes service admission, and is
driven before the runtime can become quiescent.

## Daemon profile (opt-in)

The normal daemon profile remains selected unless the existing jukebox YAML
contains the exact boolean `local_playback.enabled: true`. The example
`resources/default-settings/jukebox.local-playback.example.yaml` shows the
required paths and the only accepted diagnostic module declarations. Copy or
merge these values into the configuration file passed to the daemon. The
restricted profile rejects malformed module declarations and every alias or
source outside the approved `publishing` and `misc` modules before importing
plugin, RPC, player, GPIO, RFID, timer, MQTT, speech, jingle, volume, or host
packages. Required import or initialization failures prevent startup.

Both daemon profiles use the same canonical owner file under
`/tmp/phoniebox-playback-<effective-uid>/audio-owner.lock`. The directory is
created with mode 0700 only when absent; an existing unsafe directory is a hard
failure. Neither profile accepts a lock-directory override. The legacy daemon
holds the same exclusive descriptor while its plugins and RPC server are active.

In the restricted profile, SIGINT/SIGTERM only records the first signal and a
single monotonic deadline ten seconds later. The main thread closes admission
and drains shutdown against that deadline. Exit status is nonzero unless the
runtime is CLOSED and quiescent with no live driver and no held owner descriptor.
This path does not invoke legacy player stop, jingle, or broad plugin shutdown.

The example MPD configuration at
`resources/default-settings/mpd.local-playback.example.conf` binds TCP to
loopback, grants unauthenticated clients read-only access, and gives write
permissions only to the password used by the owner credential file. Merge it
into the effective MPD configuration rather than assuming it replaces existing
settings. Audit every active TCP and Unix socket endpoint, host/local permission,
systemd socket unit, and included config on the target before activation. This
text example has not been validated against the installed MPD 0.24.x on the
Raspberry Pi; configuration acceptance and anonymous-write rejection remain
hardware deployment gates.

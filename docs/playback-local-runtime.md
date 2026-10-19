# Local playback runtime owner

`LocalPlaybackRuntime` is an inactive, daemon-owned composition boundary for one
LOCAL playback service. Constructing it only validates and copies configuration.
The caller must explicitly call `start(deadline=...)`; no daemon, HTTP, RPC, or UI
registration is included in this change.

The runtime accepts only absolute POSIX paths for its database, media root,
credential, and optional lock-directory override. MPD is restricted to
`127.0.0.1`. The private credential file must be a regular file owned by the
effective user, have no group or other permissions, and contain one nonempty
UTF-8 line of at most 4096 bytes. Its contents are never included in diagnostics.

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

Shutdown closes admission promptly. `finish_shutdown(deadline=...)` uses one
monotonic deadline to drain the service, stop and join the timer, close the
connection and catalog, and release the owner lock. An unconfirmed stop, blocked
work, cleanup failure, or expired deadline keeps the runtime nonquiescent and
retains ownership resources for a later explicit cleanup attempt.
An explicit stop retry already authorized before shutdown remains pending while
shutdown closes service admission, and is driven before the runtime can become
quiescent.

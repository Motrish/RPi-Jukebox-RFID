# Internal execution gate

This module is a prerequisite for a single playback controller. It is not registered in
the player runtime. The first increment supports LOCAL START, cancellation and STOP
only.

The controller reserves an opaque permit, obtains a lease for that permit, invokes the
corresponding provider method, then supplies that method's return value to completion.
Only one provider call may be outstanding. A queue selection is not evidence of
playback.

Cancellation advances the generation and revokes the START guard. It retains the
original owner so that cleanup STOP can still address the same execution. A malformed,
missing or unconfirmed receipt cannot free ownership. Only the current STOP permit's
correlated CONFIRMED/STOPPED receipt can free a previously started execution. A valid
START REJECTED may release a reservation because the provider guarantees it made no
mutating call.

An old permit cannot complete a newer attempt, including a STOP retry. Lease identities
and diagnostic snapshots are defensive copies. The gate never calls a provider, session,
resolver or callback while holding its state lock.

Guard checking and a later MPD write are not atomic. Cancellation therefore does not
prove that every transient late sound is impossible; a confirmed cleanup STOP is still
required before another START. A new in-memory gate also says nothing about the actual
MPD state after a crash.

This increment provides no process-wide instance lock, durable recovery, public playback
status, queue advancement, natural-end handling, Spotify integration or exclusion of
legacy RFID/GPIO/web writers. These are later controller tasks. Provider calls remain
externally orchestrated; there is no automatic cleanup worker or force-release method.

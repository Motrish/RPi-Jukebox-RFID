# Shared local MPD session

The local provider can use `components.local_provider.mpd_session.MpdSession` with the existing `PlayerMPD.mpd_client`. The player owns one `TrackedMPDClient`; its `shared_lock` is the same reentrant lock used by the legacy `MpdLock`. Constructing a session does not connect, create another player, clear the MPD queue or start a background worker.

This is an internal integration primitive. No provider is registered or activated automatically. A caller must supply an authorized local library resolver, the same trusted `time.monotonic` clock to the session and `LocalProvider`, and the existing execution lease/capability contract. Central playback serialization and exclusion of competing RFID, timer, web and other queue writers remain prerequisites for activation. Sharing a lock prevents overlapping protocol bytes; it does not prevent another writer from changing MPD between transactions.

## Deadline and connection lifetime

`transaction(deadline)` accepts an absolute finite monotonic deadline. It acquires the client's raw shared lock with the remaining duration and never uses the legacy lock's implicit reconnect. Connect, DNS resolution and MPD greeting happen outside the provider transaction; this adapter does not make legacy startup or legacy polling deadline-safe. A disconnected client is rejected without reconnect or command replay.

A transaction captures an owned duplicate of the current socket using public `fileno`, `dup` and `detach` APIs. A synchronized watchdog shuts down that exact connection when the absolute deadline expires. Protocol commands remain in the calling thread; there is no abandoned command worker. The captured socket cannot become a later connection merely because a descriptor number is reused. Disarming and owned-resource cleanup happen before the shared lock is released. The existing blocking client timeout and normal default socket timeout must remain `None`.

Network waits are interruptible, including a peer that sends an unfinished response byte by byte. This is not a hard real-time guarantee if the process is suspended or the operating system cannot schedule it. A failed or expired command may already have affected MPD. Shutdown does not roll back those effects, and an uncertain stop does not release playback ownership.

Connection replacement, disconnect and ambiguous transport failure invalidate the connection epoch. Old MPD song IDs must not be reused after a changed epoch. A later connection is explicit or belongs to legacy behavior; the session never reconnects inside a transaction. Retained contexts cannot issue commands after exit, although their epoch remains readable for the provider's final verification.

## Status and errors

The session exposes only the commands needed for a single local track. `status` reads one fresh MPD response and applies the existing strict raw-status converter; it does not combine cached player status with a separate song lookup. Malformed status becomes the provider's safe `PROVIDER_STATE_MISMATCH` error. An MPD ACK maps to `COMMAND_REJECTED`; unconfirmed transport outcomes invalidate the connection and are never retried automatically. Raw server text, paths and account details are not part of provider error messages.

The supported dependency for this adapter is pinned to `python-mpd2==3.1.1`. The implementation uses its public client APIs rather than replacing its protocol parser or accessing private socket/file fields. Tests use the real dependency with a local TCP protocol fixture. They do not replace a real-daemon/audio test on the Raspberry Pi.
Runtime support for interrupting both reads and writes is gated on Linux CI. Windows is not approved for deadline-bound blocking reads or writes: a duplicated-socket shutdown did not reliably interrupt an already waiting quiet read or blocked write on the development host. Windows still runs the lifecycle/error/lock assertions, but the two quiet-read latency assertions are excluded there and the blocked-write experiment is skipped. All latency assertions remain mandatory on Linux. The Linux write test runs the actual blocking operation in a child process with a separate safety timeout. The child must itself prove that the session interrupted I/O near the operation deadline; merely killing a hung child fails the test.

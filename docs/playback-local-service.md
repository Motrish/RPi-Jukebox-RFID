# Caller-driven local playback service

`LocalPlaybackService` is an inactive internal host for one injected LOCAL
provider. It adds no transport, worker, timer, queue mutation, persistence, or
public playback state. Callers submit desired starts or stops and advance the
service with `run_once(deadline=...)`.

Each request replaces the pending wish. A start with a different current owner
first invalidates that execution and performs one correlated provider STOP in a
step of its own. A later step may start the latest pending entry. This separation
lets a stop submitted between cleanup and successor dispatch suppress that start.
Only actual provider receipts can confirm start or cleanup; exceptions and
malformed receipts preserve gate ownership and require cleanup.

An unconfirmed STOP is latched. Ordinary `run_once` calls and START requests do
not retry it. A `request_stop` admitted after the failure has been published
authorizes one cleanup attempt. A STOP submitted while an attempt is in progress
does not rearm a later failure. Shutdown closes start admission and queues
cleanup; callers continue driving it, since shutdown does not join or cancel a
provider call.

The diagnostic snapshot contains the gate snapshot, a defensive pending-intent
copy, driver/closure/quiescence flags, and the last safe failure operation/code.
It reports this host's memory only. An empty initial gate is not evidence that
MPD is globally stopped, and a blocked resolver can outlast the supplied
deadline. The caller supplies a fresh absolute monotonic deadline per step.

The service assumes the injected provider is exclusively used by this host. It
does not establish process-wide ownership or disable legacy MPD writers. Do not
attach it to runtime until process ownership, startup reconciliation, and
exclusion or redirection of every legacy writer are handled together.

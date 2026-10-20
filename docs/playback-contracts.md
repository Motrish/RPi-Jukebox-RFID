# Playback admission contracts

This document defines the transport-free Python contract for version 1 playback admission. It validates frames only; it does not admit commands, inspect a store or report audio state.

`PLAYBACK_START` has exactly `contractVersion`, `commandId`, `action`, `queueId`, `expectedQueueRevision` and `entryId`. `PLAYBACK_STOP` has exactly `contractVersion`, `commandId` and `action`. Identifiers use the existing V1 ASCII token rule. Revisions and intent sequences are true JSON integers in `0..9007199254740991`; accepted sequences start at 1. Version must be the true integer 1. Python callers passing `1.0` are rejected as a float; after JSON parsing, JavaScript represents `1` and `1.0` as the same Number, so cross-language fixtures use distinguishable fractional values such as `1.5`.

`validate_playback_command_result` accepts only the closed `ACCEPTED` and `REJECTED` arms. Acceptance contains `intentId`, `intentSequence`, `acceptedAt` and `selection`; START selection contains the queue ID, resulting queue revision and full existing QueueEntry snapshot with LOCAL media, while STOP selection is exactly null. Rejection contains a `PlaybackAdmissionError`. `ACCEPTED` means a durable intent was committed; it says nothing about dispatch or playback.

`acceptedAt` uses exactly `YYYY-MM-DDTHH:mm:ss.SSSZ`, with a valid Gregorian date in years 0001 through 9999, UTC and no leap seconds. It is diagnostic and does not order intents. The dedicated error validator accepts the existing admission error subset through the unchanged V1 validator and adds `CAPABILITY_UNAVAILABLE` with `{capability: "SPOTIFY_PLAYBACK"}`. Admission errors use operation `PLAYBACK_ADMIT`; contract-validation errors retain `CONTRACT_VALIDATION`.

The shared JSON fixture pins normalized mappings and stable validation diagnostics for Python and the later JavaScript peer. Validation returns fresh nested JSON-shaped mappings. This contract slice makes no claims about storage, idempotency, sequencing persistence, selection mutation, availability or audio output.

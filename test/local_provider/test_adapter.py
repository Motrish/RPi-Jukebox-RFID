"""Behavioral tests for the synchronous, transport-free LOCAL provider."""

import copy
import json
import unittest
from contextlib import contextmanager
from pathlib import Path

from components.local_provider import LocalProvider, SessionFailure
from jukebox.contracts import ContractValidationError


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "v1.json"
RECEIPT_FIELDS = {
    "provider", "operation", "identity", "outcome", "epoch", "songid",
    "state", "positionMs", "durationMs", "observedAtMonotonic", "error",
}


class FakeClock:
    def __init__(self, value=10.0):
        self.value = value

    def __call__(self):
        return self.value


class FakeResolver:
    def __init__(self, result):
        self.result = result
        self.calls = []
        self.on_resolve = None

    def __call__(self, library_id):
        self.calls.append(library_id)
        if self.on_resolve is not None:
            return self.on_resolve(library_id)
        if isinstance(self.result, Exception):
            raise self.result
        return copy.deepcopy(self.result)


class FakeSession:
    def __init__(self, status=None):
        self.epoch = "epoch_01"
        self.current_status = copy.deepcopy(status)
        self.events = []
        self.clock = None
        self.deadline = None
        self.song_ids = 0
        self.stop_ack_without_stopping = False
        self.on_command = None
        self.fail_on_command = None

    @contextmanager
    def transaction(self, deadline):
        self.deadline = deadline
        self._record(("transaction", deadline))
        yield self

    def _record(self, event):
        if self.clock is not None and self.clock.value >= self.deadline:
            raise SessionFailure("TIMEOUT")
        self.events.append(event)

    def status(self):
        self._record(("status",))
        return copy.deepcopy(self.current_status)

    def repeat(self, enabled):
        self._option("repeat", enabled)

    def random(self, enabled):
        self._option("random", enabled)

    def single(self, enabled):
        self._option("single", enabled)

    def consume(self, enabled):
        self._option("consume", enabled)

    def _option(self, field, enabled):
        self._record((field, enabled))
        self.current_status[field] = enabled
        self._after_command(field)

    def clear(self):
        self._record(("clear",))
        self.current_status["playlistlength"] = 0
        self.current_status["songid"] = None
        self._after_command("clear")

    def addid(self, reference):
        self.song_ids += 1
        song_id = str(self.song_ids)
        self._record(("addid", reference, song_id))
        self.current_status["playlistlength"] += 1
        self._after_command("addid")
        return song_id

    def playid(self, song_id):
        self._record(("playid", song_id))
        self.current_status["songid"] = song_id
        self.current_status["state"] = "play"
        self.current_status["elapsed"] = 0.0
        self.current_status["duration"] = 120.0
        self._after_command("playid")

    def pause(self, value):
        self._record(("pause", value))
        self.current_status["state"] = "pause" if value else "play"
        self._after_command("pause")

    def seekid(self, song_id, position_seconds):
        self._record(("seekid", song_id, position_seconds))
        self.current_status["elapsed"] = position_seconds
        self._after_command("seekid")

    def stop(self):
        self._record(("stop",))
        if not self.stop_ack_without_stopping:
            self.current_status["state"] = "stop"
            self.current_status["songid"] = None
        self._after_command("stop")

    def _after_command(self, name):
        if self.on_command is not None:
            self.on_command(name)
        if self.fail_on_command == name:
            raise SessionFailure("TIMEOUT")


class LocalProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with FIXTURE_PATH.open(encoding="utf-8") as stream:
            cls.fixture = json.load(stream)

    def make_provider(self, *, guard=None, capabilities=None, resolver_result=None, clock=None):
        fixture = self.fixture
        self.clock = clock or FakeClock()
        self.session = FakeSession(fixture["initialStatus"])
        self.session.clock = self.clock
        self.resolver = FakeResolver(resolver_result or fixture["resolvedMedia"])
        self.guard_calls = []
        guard_fn = guard or self.allow_guard
        self.lease = {"identity": copy.deepcopy(fixture["identity"]), "guard": guard_fn}
        self.provider = LocalProvider(
            session=self.session,
            resolver=self.resolver,
            monotonic=self.clock,
            capabilities=capabilities or fixture["capabilities"],
        )
        return self.provider

    def allow_guard(self, operation, identity):
        self.guard_calls.append((operation, copy.deepcopy(identity)))
        return True

    def deadline(self):
        return self.clock.value + 5.0

    def start(self, provider=None, lease=None, media_ref=None, deadline=None):
        provider = provider or self.provider
        lease = lease or self.lease
        return provider.start(
            media_ref if media_ref is not None else self.fixture["mediaRef"],
            lease=lease,
            deadline=deadline if deadline is not None else self.deadline(),
        )

    def writes(self):
        return [
            event for event in self.session.events
            if event[0] not in {"transaction", "status"}
        ]

    def test_construction_is_inert_and_start_uses_confirmed_single_track_id(self):
        provider = self.make_provider()
        self.assertEqual([], self.session.events)
        self.assertEqual([], self.resolver.calls)

        receipt = self.start(provider)

        self.assertEqual(RECEIPT_FIELDS, set(receipt))
        self.assertEqual(("repeat", 0), self.writes()[0])
        self.assertEqual(("random", 0), self.writes()[1])
        self.assertEqual(("single", 1), self.writes()[2])
        self.assertEqual(("consume", 0), self.writes()[3])
        self.assertEqual(("clear",), self.writes()[4])
        self.assertEqual(("addid", "albums/demo/track-01.mp3", "1"), self.writes()[5])
        self.assertEqual(("playid", "1"), self.writes()[6])
        self.assertEqual("CONFIRMED", receipt["outcome"])
        self.assertEqual("PLAYING", receipt["state"])
        self.assertEqual("1", receipt["songid"])
        self.assertIsNone(receipt["error"])
        self.assertFalse(self.provider.capabilities["canIdentifyNaturalEnd"])

    def test_same_active_start_observes_without_restarting_track(self):
        provider = self.make_provider()
        first = self.start(provider)
        writes_after_first = list(self.writes())
        self.session.current_status["state"] = "pause"

        second = self.start(provider)

        self.assertEqual("CONFIRMED", first["outcome"])
        self.assertEqual("CONFIRMED", second["outcome"])
        self.assertEqual("PAUSED", second["state"])
        self.assertEqual(writes_after_first, self.writes())
        self.assertEqual(3, sum(event == ("status",) for event in self.session.events))
        self.assertEqual(1, sum(event[0] == "addid" for event in self.writes()))

    def test_initial_start_must_be_playing_even_if_the_track_is_already_paused(self):
        provider = self.make_provider()

        def pause_before_confirmation(command):
            if command == "playid":
                self.session.current_status["state"] = "pause"

        self.session.on_command = pause_before_confirmation
        receipt = self.start(provider)

        self.assertEqual("UNCONFIRMED", receipt["outcome"])
        self.assertEqual("PROVIDER_STATE_MISMATCH", receipt["error"]["code"])
        self.assertEqual("pause", self.session.current_status["state"])
        new_identity = copy.deepcopy(self.lease["identity"])
        new_identity.update(generation=8, executionId="execution_after_paused_start", entryId="entry_after_paused_start")
        next_start = self.start(
            provider,
            lease={"identity": new_identity, "guard": self.allow_guard},
        )
        self.assertEqual("EXECUTION_CONFLICT", next_start["error"]["code"])

    def test_observe_rejects_current_backend_error_status(self):
        provider = self.make_provider()
        self.start(provider)
        self.session.current_status["hasError"] = True
        before_writes = list(self.writes())

        receipt = provider.observe(lease=self.lease, deadline=self.deadline())

        self.assertEqual("REJECTED", receipt["outcome"])
        self.assertEqual("PROVIDER_STATE_MISMATCH", receipt["error"]["code"])
        self.assertEqual(before_writes, self.writes())

    def test_guard_change_after_addid_blocks_playid_and_keeps_old_identity_reserved(self):
        blocked = {"enabled": False}
        identity = copy.deepcopy(self.fixture["identity"])

        def guard(operation, received_identity):
            self.guard_calls.append((operation, copy.deepcopy(received_identity)))
            is_new_generation = received_identity["generation"] > identity["generation"]
            return operation == "STOP" or is_new_generation or not blocked["enabled"]

        provider = self.make_provider(guard=guard)

        def block_after_addid(command):
            if command == "addid":
                blocked["enabled"] = True

        self.session.on_command = block_after_addid
        receipt = self.start(provider)

        self.assertEqual("UNCONFIRMED", receipt["outcome"])
        self.assertEqual("STALE_EXECUTION", receipt["error"]["code"])
        self.assertNotIn(("playid", "1"), self.writes())
        new_lease = {
            "identity": {**identity, "generation": identity["generation"] + 1,
                         "executionId": "execution_new", "entryId": "entry_new"},
            "guard": guard,
        }
        blocked["enabled"] = True
        next_start = self.start(provider, lease=new_lease)
        self.assertEqual("EXECUTION_CONFLICT", next_start["error"]["code"])
        self.assertNotIn(("playid", "1"), self.writes())

        cleanup = provider.stop(lease=self.lease, deadline=self.deadline())
        self.assertEqual("CONFIRMED", cleanup["outcome"])
        self.assertNotIn(("playid", "1"), self.writes())

    def test_stop_ack_without_stopped_status_is_unconfirmed_and_blocks_next_start(self):
        provider = self.make_provider()
        self.start(provider)
        self.session.stop_ack_without_stopping = True

        stopped = provider.stop(lease=self.lease, deadline=self.deadline())

        self.assertEqual("UNCONFIRMED", stopped["outcome"])
        self.assertEqual("STOP_UNCONFIRMED", stopped["error"]["code"])
        next_identity = copy.deepcopy(self.lease["identity"])
        next_identity.update(generation=8, executionId="execution_next", entryId="entry_next")
        next_result = self.start(
            provider,
            lease={"identity": next_identity, "guard": self.allow_guard},
        )
        self.assertEqual("EXECUTION_CONFLICT", next_result["error"]["code"])

        self.session.stop_ack_without_stopping = False
        retry = provider.stop(lease=self.lease, deadline=self.deadline())
        self.assertEqual("CONFIRMED", retry["outcome"])
        self.assertEqual("STOPPED", retry["state"])

    def test_epoch_change_after_start_command_invalidates_observation_and_blocks_old_cleanup(self):
        provider = self.make_provider()

        def restart_session(command):
            if command == "playid":
                self.session.epoch = "epoch_02"

        self.session.on_command = restart_session
        receipt = self.start(provider)

        self.assertEqual("UNCONFIRMED", receipt["outcome"])
        self.assertEqual("SESSION_CHANGED", receipt["error"]["code"])
        self.assertEqual("UNKNOWN", receipt["state"])
        self.assertIsNone(receipt["epoch"])
        self.assertIsNone(receipt["songid"])
        before = list(self.session.events)

        cleanup = provider.stop(lease=self.lease, deadline=self.deadline())

        self.assertEqual("STOP_UNCONFIRMED", cleanup["error"]["code"])
        self.assertEqual(before, self.session.events[:-1])
        self.assertEqual(("transaction", self.deadline()), self.session.events[-1])

    def test_expiry_after_resolution_sends_no_session_command(self):
        clock = FakeClock()
        provider = self.make_provider(clock=clock)

        def expire_during_resolution(library_id):
            clock.value = 20.0
            return copy.deepcopy(self.fixture["resolvedMedia"])

        self.resolver.on_resolve = expire_during_resolution

        receipt = self.start(provider, deadline=15.0)

        self.assertEqual("REJECTED", receipt["outcome"])
        self.assertEqual("OPERATION_TIMEOUT", receipt["error"]["code"])
        self.assertEqual([], self.session.events)

    def test_guard_consuming_deadline_prevents_next_protocol_call(self):
        clock = FakeClock()
        calls = []

        def guard(operation, identity):
            calls.append((operation, copy.deepcopy(identity)))
            if len(calls) == 6:
                clock.value = 15.0
            return True

        provider = self.make_provider(clock=clock, guard=guard)
        receipt = self.start(provider, deadline=15.0)

        self.assertEqual("REJECTED", receipt["outcome"])
        self.assertEqual("OPERATION_TIMEOUT", receipt["error"]["code"])
        self.assertEqual([("transaction", 15.0)], self.session.events)

    def test_session_timeout_after_playid_keeps_execution_reserved_for_explicit_stop(self):
        provider = self.make_provider()
        self.session.fail_on_command = "playid"

        receipt = self.start(provider)

        self.assertEqual("UNCONFIRMED", receipt["outcome"])
        self.assertEqual("OPERATION_TIMEOUT", receipt["error"]["code"])
        next_identity = copy.deepcopy(self.lease["identity"])
        next_identity.update(generation=8, executionId="execution_after_timeout", entryId="entry_after_timeout")
        next_start = self.start(
            provider,
            lease={"identity": next_identity, "guard": self.allow_guard},
        )
        self.assertEqual("EXECUTION_CONFLICT", next_start["error"]["code"])

        self.session.fail_on_command = None
        stopped = provider.stop(lease=self.lease, deadline=self.deadline())
        self.assertEqual("CONFIRMED", stopped["outcome"])

    def test_malformed_deadline_is_contract_error_before_effect(self):
        provider = self.make_provider()

        with self.assertRaises(ContractValidationError):
            self.start(provider, deadline=True)

        self.assertEqual([], self.session.events)
        self.assertEqual([], self.resolver.calls)

    def test_nonlocal_media_and_unsafe_resolver_result_never_reach_session(self):
        provider = self.make_provider()
        spotify_ref = {"kind": "SPOTIFY", "uri": "spotify:track:0123456789012345678901"}

        nonlocal_receipt = self.start(provider, media_ref=spotify_ref)
        self.assertEqual("REJECTED", nonlocal_receipt["outcome"])
        self.assertEqual("CAPABILITY_UNAVAILABLE", nonlocal_receipt["error"]["code"])
        self.assertEqual([], self.session.events)

        provider = self.make_provider(resolver_result={
            "libraryId": "synthetic_track_01",
            "mpdReference": "../outside.mp3",
        })
        unsafe = self.start(provider)

        self.assertEqual("REJECTED", unsafe["outcome"])
        self.assertEqual("RESOLUTION_FAILED", unsafe["error"]["code"])
        self.assertEqual([], self.session.events)

    def test_pause_resume_and_seek_are_explicit_and_songid_bound(self):
        provider = self.make_provider()
        started = self.start(provider)
        song_id = started["songid"]

        paused = provider.pause(lease=self.lease, deadline=self.deadline())
        resumed = provider.resume(lease=self.lease, deadline=self.deadline())
        seeked = provider.seek(
            12500, lease=self.lease, deadline=self.deadline(),
        )

        self.assertEqual("CONFIRMED", paused["outcome"])
        self.assertEqual("PAUSED", paused["state"])
        self.assertEqual("CONFIRMED", resumed["outcome"])
        self.assertEqual("PLAYING", resumed["state"])
        self.assertEqual("CONFIRMED", seeked["outcome"])
        self.assertIn(("pause", 1), self.writes())
        self.assertIn(("pause", 0), self.writes())
        self.assertIn(("seekid", song_id, 12.5), self.writes())
        self.assertEqual(12500, seeked["positionMs"])

    def test_old_stop_cannot_stop_a_new_identity_after_confirmed_replacement(self):
        provider = self.make_provider()
        self.start(provider)
        stopped = provider.stop(lease=self.lease, deadline=self.deadline())
        self.assertEqual("CONFIRMED", stopped["outcome"])

        old_lease = self.lease
        next_identity = copy.deepcopy(old_lease["identity"])
        next_identity.update(generation=8, executionId="execution_next", entryId="entry_next")
        next_lease = {"identity": next_identity, "guard": self.allow_guard}
        next_start = self.start(provider, lease=next_lease)
        before_old_stop = list(self.session.events)

        old_stop = provider.stop(lease=old_lease, deadline=self.deadline())

        self.assertEqual("CONFIRMED", next_start["outcome"])
        self.assertEqual("REJECTED", old_stop["outcome"])
        self.assertEqual("EXECUTION_CONFLICT", old_stop["error"]["code"])
        self.assertEqual(before_old_stop, self.session.events)

    def test_observed_stop_is_not_inferred_as_natural_end_or_released_for_next_start(self):
        provider = self.make_provider()
        self.start(provider)
        self.session.current_status["state"] = "stop"
        self.session.current_status["songid"] = None
        before_writes = list(self.writes())

        observation = provider.observe(lease=self.lease, deadline=self.deadline())

        self.assertEqual("CONFIRMED", observation["outcome"])
        self.assertEqual("STOPPED", observation["state"])
        self.assertEqual(before_writes, self.writes())
        next_identity = copy.deepcopy(self.lease["identity"])
        next_identity.update(generation=8, executionId="execution_after_observe", entryId="entry_after_observe")
        next_start = self.start(
            provider,
            lease={"identity": next_identity, "guard": self.allow_guard},
        )
        self.assertEqual("EXECUTION_CONFLICT", next_start["error"]["code"])
        self.assertEqual(before_writes, self.writes())


if __name__ == "__main__":
    unittest.main()

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
        self.fail_on_entry = None
        self.on_exit = None
        self.fail_on_exit = None

    @contextmanager
    def transaction(self, deadline):
        self.deadline = deadline
        self._record(("transaction", deadline))
        if self.fail_on_entry is not None:
            raise SessionFailure(self.fail_on_entry)
        yield self
        if self.on_exit is not None:
            self.on_exit()
        if self.fail_on_exit is not None:
            raise SessionFailure(self.fail_on_exit)

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

    def test_initial_start_context_exit_timeout_keeps_new_identity_for_cleanup(self):
        provider = self.make_provider()
        self.session.fail_on_exit = "TIMEOUT"

        receipt = self.start(provider)

        self.assertEqual("UNCONFIRMED", receipt["outcome"])
        self.assertEqual("OPERATION_TIMEOUT", receipt["error"]["code"])
        self.assertEqual(self.lease["identity"], provider._identity)
        self.assertTrue(provider._uncertain)
        self.assertEqual("1", provider._songid)
        self.assertEqual("play", self.session.current_status["state"])

        self.session.fail_on_exit = None
        cleanup = provider.stop(lease=self.lease, deadline=self.deadline())
        self.assertEqual("CONFIRMED", cleanup["outcome"])
        self.assertIn(("stop",), self.writes())

    def test_replacement_start_exit_failure_does_not_restore_old_identity(self):
        provider = self.make_provider()
        self.assertEqual("CONFIRMED", self.start(provider)["outcome"])
        self.assertEqual("CONFIRMED", provider.stop(lease=self.lease, deadline=self.deadline())["outcome"])
        old_identity = copy.deepcopy(provider._identity)
        next_identity = copy.deepcopy(old_identity)
        next_identity.update(generation=8, executionId="execution_replacement", entryId="entry_replacement")
        next_lease = {"identity": next_identity, "guard": self.allow_guard}
        self.session.fail_on_exit = "UNAVAILABLE"

        receipt = self.start(provider, lease=next_lease)

        self.assertEqual("UNCONFIRMED", receipt["outcome"])
        self.assertEqual("PROVIDER_UNAVAILABLE", receipt["error"]["code"])
        self.assertEqual(next_identity, provider._identity)
        self.assertNotEqual(old_identity, provider._identity)
        self.assertTrue(provider._uncertain)
        self.assertEqual("2", provider._songid)

        self.session.fail_on_exit = None
        cleanup = provider.stop(lease=next_lease, deadline=self.deadline())
        self.assertEqual("CONFIRMED", cleanup["outcome"])

    def test_stop_context_exit_failures_keep_next_start_blocked(self):
        for failure in ("TIMEOUT", "UNAVAILABLE"):
            with self.subTest(failure=failure):
                provider = self.make_provider()
                self.assertEqual("CONFIRMED", self.start(provider)["outcome"])
                self.session.fail_on_exit = failure

                stopped = provider.stop(lease=self.lease, deadline=self.deadline())

                self.assertEqual("UNCONFIRMED", stopped["outcome"])
                self.assertEqual("STOP_UNCONFIRMED", stopped["error"]["code"])
                self.assertFalse(provider._confirmed_stopped)
                self.assertTrue(provider._uncertain)
                next_identity = copy.deepcopy(self.lease["identity"])
                next_identity.update(generation=8, executionId="execution_blocked", entryId="entry_blocked")
                next_result = self.start(
                    provider,
                    lease={"identity": next_identity, "guard": self.allow_guard},
                )
                self.assertEqual("EXECUTION_CONFLICT", next_result["error"]["code"])
                self.session.fail_on_exit = None

    def test_repeated_terminal_stop_exit_failure_revokes_old_release_until_reconfirmed(self):
        provider = self.make_provider()
        self.assertEqual("CONFIRMED", self.start(provider)["outcome"])
        first_stop = provider.stop(lease=self.lease, deadline=self.deadline())
        self.assertEqual("CONFIRMED", first_stop["outcome"])
        writes_after_first_stop = list(self.writes())
        self.session.fail_on_exit = "TIMEOUT"

        repeated_stop = provider.stop(lease=self.lease, deadline=self.deadline())

        self.assertEqual("UNCONFIRMED", repeated_stop["outcome"])
        self.assertEqual("STOP_UNCONFIRMED", repeated_stop["error"]["code"])
        self.assertEqual(writes_after_first_stop, self.writes())
        self.assertFalse(provider._confirmed_stopped)
        next_identity = copy.deepcopy(self.lease["identity"])
        next_identity.update(generation=8, executionId="execution_after_repeat_stop", entryId="entry_after_repeat_stop")
        next_lease = {"identity": next_identity, "guard": self.allow_guard}
        blocked = self.start(provider, lease=next_lease)
        self.assertEqual("EXECUTION_CONFLICT", blocked["error"]["code"])
        self.assertEqual(writes_after_first_stop, self.writes())

        self.session.fail_on_exit = None
        confirmed_again = provider.stop(lease=self.lease, deadline=self.deadline())
        self.assertEqual("CONFIRMED", confirmed_again["outcome"])
        released = self.start(provider, lease=next_lease)
        self.assertEqual("CONFIRMED", released["outcome"])

    def test_repeated_terminal_stop_entry_failures_revoke_old_release_until_reconfirmed(self):
        for failure in ("TIMEOUT", "UNAVAILABLE"):
            with self.subTest(failure=failure):
                provider = self.make_provider()
                self.assertEqual("CONFIRMED", self.start(provider)["outcome"])
                first_stop = provider.stop(lease=self.lease, deadline=self.deadline())
                self.assertEqual("CONFIRMED", first_stop["outcome"])
                prior_identity = copy.deepcopy(provider._identity)
                self.session.fail_on_entry = failure

                repeated_stop = provider.stop(lease=self.lease, deadline=self.deadline())

                self.assertEqual("UNCONFIRMED", repeated_stop["outcome"])
                self.assertEqual("STOP_UNCONFIRMED", repeated_stop["error"]["code"])
                self.assertEqual(prior_identity, provider._identity)
                self.assertFalse(provider._confirmed_stopped)
                self.assertEqual(("transaction", self.deadline()), self.session.events[-1])
                next_identity = copy.deepcopy(self.lease["identity"])
                next_identity.update(generation=8, executionId="execution_after_entry_failure",
                                     entryId="entry_after_entry_failure")
                next_lease = {"identity": next_identity, "guard": self.allow_guard}
                before_blocked_start = list(self.session.events)
                blocked = self.start(provider, lease=next_lease)
                self.assertEqual("EXECUTION_CONFLICT", blocked["error"]["code"])
                self.assertEqual(before_blocked_start, self.session.events)

                self.session.fail_on_entry = None
                confirmed_again = provider.stop(lease=self.lease, deadline=self.deadline())
                self.assertEqual("CONFIRMED", confirmed_again["outcome"])
                self.assertTrue(provider._confirmed_stopped)
                released = self.start(provider, lease=next_lease)
                self.assertEqual("CONFIRMED", released["outcome"])

    def test_repeated_terminal_stop_status_error_revokes_old_release_until_reconfirmed(self):
        provider = self.make_provider()
        self.assertEqual("CONFIRMED", self.start(provider)["outcome"])
        first_stop = provider.stop(lease=self.lease, deadline=self.deadline())
        self.assertEqual("CONFIRMED", first_stop["outcome"])
        self.session.current_status["hasError"] = True

        repeated_stop = provider.stop(lease=self.lease, deadline=self.deadline())

        self.assertEqual("UNCONFIRMED", repeated_stop["outcome"])
        self.assertEqual("STOP_UNCONFIRMED", repeated_stop["error"]["code"])
        self.assertIn(("status",), self.session.events[-1:])
        self.assertFalse(provider._confirmed_stopped)
        self.session.current_status["hasError"] = False
        next_identity = copy.deepcopy(self.lease["identity"])
        next_identity.update(generation=8, executionId="execution_after_status_error",
                             entryId="entry_after_status_error")
        next_lease = {"identity": next_identity, "guard": self.allow_guard}
        before_blocked_start = list(self.session.events)
        blocked = self.start(provider, lease=next_lease)
        self.assertEqual("EXECUTION_CONFLICT", blocked["error"]["code"])
        self.assertEqual(before_blocked_start, self.session.events)

        confirmed_again = provider.stop(lease=self.lease, deadline=self.deadline())
        self.assertEqual("CONFIRMED", confirmed_again["outcome"])
        released = self.start(provider, lease=next_lease)
        self.assertEqual("CONFIRMED", released["outcome"])

    def test_repeated_terminal_stop_expired_deadline_revokes_old_release_until_reconfirmed(self):
        provider = self.make_provider()
        self.assertEqual("CONFIRMED", self.start(provider)["outcome"])
        first_stop = provider.stop(lease=self.lease, deadline=self.deadline())
        self.assertEqual("CONFIRMED", first_stop["outcome"])
        before_expired_stop = list(self.session.events)

        repeated_stop = provider.stop(lease=self.lease, deadline=self.clock.value)

        self.assertEqual("UNCONFIRMED", repeated_stop["outcome"])
        self.assertEqual("STOP_UNCONFIRMED", repeated_stop["error"]["code"])
        self.assertEqual(before_expired_stop, self.session.events)
        self.assertFalse(provider._confirmed_stopped)
        next_identity = copy.deepcopy(self.lease["identity"])
        next_identity.update(generation=8, executionId="execution_after_expired_stop",
                             entryId="entry_after_expired_stop")
        next_lease = {"identity": next_identity, "guard": self.allow_guard}
        before_blocked_start = list(self.session.events)
        blocked = self.start(provider, lease=next_lease)
        self.assertEqual("EXECUTION_CONFLICT", blocked["error"]["code"])
        self.assertEqual(before_blocked_start, self.session.events)

        confirmed_again = provider.stop(lease=self.lease, deadline=self.deadline())
        self.assertEqual("CONFIRMED", confirmed_again["outcome"])
        released = self.start(provider, lease=next_lease)
        self.assertEqual("CONFIRMED", released["outcome"])

    def test_foreign_stop_and_invalid_input_preserve_confirmed_stop_release(self):
        provider = self.make_provider()
        self.assertEqual("CONFIRMED", self.start(provider)["outcome"])
        self.assertEqual("CONFIRMED", provider.stop(lease=self.lease, deadline=self.deadline())["outcome"])
        saved_state = (
            copy.deepcopy(provider._identity), provider._library_id, provider._epoch,
            provider._songid, provider._uncertain, provider._confirmed_stopped,
        )
        foreign_identity = copy.deepcopy(self.lease["identity"])
        foreign_identity.update(generation=8, executionId="execution_foreign_stop",
                                entryId="entry_foreign_stop")
        foreign = provider.stop(
            lease={"identity": foreign_identity, "guard": self.allow_guard},
            deadline=self.deadline(),
        )
        self.assertEqual("REJECTED", foreign["outcome"])
        self.assertEqual("EXECUTION_CONFLICT", foreign["error"]["code"])
        self.assertEqual(saved_state, (
            provider._identity, provider._library_id, provider._epoch,
            provider._songid, provider._uncertain, provider._confirmed_stopped,
        ))

        with self.assertRaises(ContractValidationError):
            provider.stop(lease=self.lease, deadline=True)
        self.assertEqual(saved_state, (
            provider._identity, provider._library_id, provider._epoch,
            provider._songid, provider._uncertain, provider._confirmed_stopped,
        ))
        next_identity = copy.deepcopy(self.lease["identity"])
        next_identity.update(generation=8, executionId="execution_after_rejected_stop",
                             entryId="entry_after_rejected_stop")
        released = self.start(provider, lease={"identity": next_identity, "guard": self.allow_guard})
        self.assertEqual("CONFIRMED", released["outcome"])

    def test_normal_context_exit_epoch_or_deadline_change_prevents_confirmation(self):
        for change in ("epoch", "deadline"):
            with self.subTest(change=change):
                clock = FakeClock()
                provider = self.make_provider(clock=clock)

                def change_during_exit():
                    if change == "epoch":
                        self.session.epoch = "epoch_after_exit"
                    else:
                        clock.value = 15.0

                self.session.on_exit = change_during_exit
                receipt = self.start(provider, deadline=15.0)

                self.assertEqual("UNCONFIRMED", receipt["outcome"])
                expected = "SESSION_CHANGED" if change == "epoch" else "OPERATION_TIMEOUT"
                self.assertEqual(expected, receipt["error"]["code"])
                self.assertEqual(self.lease["identity"], provider._identity)
                self.assertTrue(provider._uncertain)
                if change == "epoch":
                    self.assertIsNone(receipt["epoch"])
                    self.assertEqual("UNKNOWN", receipt["state"])
                self.session.on_exit = None

    def test_state_and_observation_receipts_wait_for_context_exit(self):
        for operation in ("pause", "resume", "seek", "observe"):
            with self.subTest(operation=operation):
                provider = self.make_provider()
                self.assertEqual("CONFIRMED", self.start(provider)["outcome"])
                if operation == "resume":
                    self.session.current_status["state"] = "pause"
                self.session.fail_on_exit = "TIMEOUT"

                if operation == "pause":
                    receipt = provider.pause(lease=self.lease, deadline=self.deadline())
                elif operation == "resume":
                    receipt = provider.resume(lease=self.lease, deadline=self.deadline())
                elif operation == "seek":
                    receipt = provider.seek(5000, lease=self.lease, deadline=self.deadline())
                else:
                    receipt = provider.observe(lease=self.lease, deadline=self.deadline())

                self.assertNotEqual("CONFIRMED", receipt["outcome"])
                self.assertIn("error", receipt)
                if operation == "observe":
                    self.assertEqual("REJECTED", receipt["outcome"])
                else:
                    self.assertEqual("UNCONFIRMED", receipt["outcome"])
                    self.assertTrue(provider._uncertain)
                self.session.fail_on_exit = None

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
        self.assertEqual(next_identity, provider._identity)
        self.assertFalse(provider._confirmed_stopped)

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

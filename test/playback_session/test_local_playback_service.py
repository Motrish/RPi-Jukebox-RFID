"""Unit coverage for caller-driven service admission and ownership."""

import unittest
import threading
from unittest.mock import patch

import components.playback_session.local_playback_service as service_module
from components.playback_session.local_playback_service import LocalPlaybackService
from components.playback_session.execution_gate import GateStateError
from jukebox.contracts import ContractValidationError


class Provider:
    def __init__(self):
        self.calls = []
        self.fail_next_stop = False
        self.on_stop = None

    def start(self, media_ref, *, lease, deadline):
        self.calls.append(("START", media_ref["libraryId"]))
        entered = getattr(self, "start_entered", None)
        if entered is not None:
            entered.set()
            if not self.start_release.wait(2.0):
                raise RuntimeError("test release timed out")
        ident = lease["identity"]
        if not lease["guard"]("START", ident):
            error = {"code": "STALE_EXECUTION", "message": "Lease is stale.",
                     "retryable": False, "operation": "START"}
            return receipt("START", ident, "REJECTED", "UNKNOWN", None, error=error)
        return receipt("START", ident, "CONFIRMED", "PLAYING", "9")

    def stop(self, *, lease, deadline):
        self.calls.append(("STOP", lease["identity"]["entryId"]))
        callback, self.on_stop = self.on_stop, None
        if callback is not None:
            callback()
        if self.fail_next_stop:
            self.fail_next_stop = False
            ident = lease["identity"]
            result = receipt("STOP", ident, "UNCONFIRMED", "UNKNOWN", None)
            result["error"] = {"code": "STOP_UNCONFIRMED", "message": "No confirmation.",
                               "retryable": False, "operation": "STOP"}
            return result
        return receipt("STOP", lease["identity"], "CONFIRMED", "STOPPED", None)


def receipt(operation, identity, outcome, state, songid, error=None):
    return {"provider": "LOCAL", "operation": operation, "identity": dict(identity),
            "outcome": outcome, "epoch": "epoch_01", "songid": songid,
            "state": state, "positionMs": None, "durationMs": None,
            "observedAtMonotonic": 11.0, "error": error}


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.provider = Provider()
        self.service = LocalPlaybackService(provider=self.provider, boot_id="boot_01", monotonic=lambda: 10.0)
        self.ref = {"kind": "LOCAL", "libraryId": "track_01"}

    def step(self):
        return self.service.run_once(deadline=20.0)

    def test_latest_start_only_and_copies_diagnostic_values(self):
        self.service.request_start("entry_a", self.ref)
        self.ref["libraryId"] = "changed"
        self.service.request_start("entry_b", {"kind": "LOCAL", "libraryId": "track_b"})
        pending = self.service.snapshot()["pending"]
        pending["mediaRef"]["libraryId"] = "mutated"
        self.step()
        self.assertEqual(self.provider.calls, [("START", "track_b")])
        self.assertIsNone(self.service.snapshot()["pending"])

    def test_stop_before_drain_suppresses_unstarted_start(self):
        self.service.request_start("entry_a", self.ref)
        self.service.request_stop()
        state = self.step()
        self.assertEqual(self.provider.calls, [])
        self.assertTrue(state["quiescent"])

    def test_cleanup_and_successor_are_separate_steps(self):
        self.service.request_start("entry_a", self.ref)
        self.step()
        self.service.request_start("entry_b", {"kind": "LOCAL", "libraryId": "track_b"})
        self.step()
        self.assertEqual([item[0] for item in self.provider.calls], ["START", "STOP"])
        self.service.request_stop()
        self.step()
        self.assertEqual([item[0] for item in self.provider.calls], ["START", "STOP"])

    def test_invalid_deadline_and_clock_preserve_pending(self):
        self.service.request_start("entry_a", self.ref)
        before = self.service.snapshot()
        with self.assertRaises(ContractValidationError):
            self.service.run_once(deadline=True)
        self.assertEqual(self.service.snapshot(), before)
        broken = LocalPlaybackService(provider=self.provider, boot_id="boot_02", monotonic=lambda: float("nan"))
        with self.assertRaises(GateStateError) as error:
            broken.run_once(deadline=20.0)
        self.assertEqual(error.exception.code, "CLOCK_UNAVAILABLE")
        self.assertEqual(self.provider.calls, [])

    def test_expired_deadline_and_invalid_media_have_no_effects(self):
        self.service.request_start("entry_a", self.ref)
        before = self.service.snapshot()
        with self.assertRaises(GateStateError) as error:
            self.service.run_once(deadline=10.0)
        self.assertEqual(error.exception.code, "DEADLINE_EXPIRED")
        self.assertEqual(self.service.snapshot(), before)
        with self.assertRaises(ContractValidationError):
            self.service.request_start("entry_b", {"kind": "SPOTIFY", "uri": "spotify:track:0000000000000000000000"})
        self.assertEqual(self.service.snapshot(), before)
        self.assertEqual(self.provider.calls, [])

    def test_clock_exception_is_unavailable_without_state_change(self):
        def broken_clock():
            raise RuntimeError("clock down")
        service = LocalPlaybackService(provider=self.provider, boot_id="boot_03", monotonic=broken_clock)
        before = service.snapshot()
        with self.assertRaises(GateStateError) as error:
            service.run_once(deadline=20.0)
        self.assertEqual(error.exception.code, "CLOCK_UNAVAILABLE")
        self.assertEqual(service.snapshot(), before)

    def test_shutdown_closes_start_admission_and_keeps_stop_pending(self):
        state = self.service.begin_shutdown()
        self.assertTrue(state["closed"])
        self.assertFalse(state["quiescent"])
        with self.assertRaises(GateStateError) as error:
            self.service.request_start("entry_a", self.ref)
        self.assertEqual(error.exception.code, "CLOSED")
        self.step()
        self.assertTrue(self.service.snapshot()["quiescent"])

    def test_failed_stop_latches_until_post_publication_explicit_stop(self):
        self.service.request_start("entry_a", self.ref)
        self.step()
        self.provider.fail_next_stop = True
        self.service.request_stop()
        failed = self.step()
        self.assertEqual(failed["lastFailure"], {"operation": "STOP", "code": "STOP_UNCONFIRMED"})
        self.service.request_start("entry_b", {"kind": "LOCAL", "libraryId": "track_b"})
        blocked = self.step()
        self.assertEqual(len(self.provider.calls), 2)
        self.assertEqual(blocked["gate"]["owner"]["entryId"], "entry_a")
        self.service.request_stop()
        self.step()
        self.assertEqual([call[0] for call in self.provider.calls], ["START", "STOP", "STOP"])
        self.assertEqual(self.service.snapshot()["gate"]["owner"], None)

    def test_blocked_superseded_start_cannot_consume_latest_intent(self):
        self.provider.start_entered = threading.Event()
        self.provider.start_release = threading.Event()
        errors = []

        def drive():
            try:
                self.step()
            except Exception as error:
                errors.append(error)

        self.service.request_start("entry_a", self.ref)
        thread = threading.Thread(target=drive)
        thread.start()
        try:
            self.assertTrue(self.provider.start_entered.wait(1.0))
            self.service.request_start("entry_b", {"kind": "LOCAL", "libraryId": "track_b"})
            with self.assertRaises(GateStateError) as error:
                self.step()
            self.assertEqual(error.exception.code, "BUSY")
        finally:
            self.provider.start_release.set()
            thread.join(2.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(self.service.snapshot()["pending"]["entryId"], "entry_b")
        self.step()  # cleanup only
        self.step()  # latest start only
        self.assertEqual([call[0] for call in self.provider.calls], ["START", "START"])
        self.assertEqual(self.service.snapshot()["gate"]["owner"]["entryId"], "entry_b")

    def test_stop_during_failed_stop_invocation_does_not_rearm_retry(self):
        self.service.request_start("entry_a", self.ref)
        self.step()
        self.provider.fail_next_stop = True
        self.provider.on_stop = self.service.request_stop
        self.service.request_stop()
        state = self.step()
        self.assertEqual(state["lastFailure"], {"operation": "STOP", "code": "STOP_UNCONFIRMED"})
        self.assertEqual(state["pending"]["operation"], "STOP")
        self.step()
        self.assertEqual([call[0] for call in self.provider.calls], ["START", "STOP"])
        self.service.request_stop()  # after failure publication: exactly one retry
        self.step()
        self.step()
        self.assertEqual([call[0] for call in self.provider.calls], ["START", "STOP", "STOP"])

    def test_stop_after_raw_return_before_failure_publication_does_not_rearm(self):
        self.service.request_start("entry_a", self.ref)
        self.step()
        self.provider.fail_next_stop = True
        self.service.request_stop()
        original_copy = service_module._plain_receipt

        def stop_after_return(receipt):
            safe = original_copy(receipt)
            self.service.request_stop()
            return safe

        with patch.object(service_module, "_plain_receipt", stop_after_return):
            state = self.step()
        self.assertEqual(state["lastFailure"], {"operation": "STOP", "code": "STOP_UNCONFIRMED"})
        self.step()
        self.assertEqual([call[0] for call in self.provider.calls], ["START", "STOP"])

    def test_start_uuid_generation_does_not_hold_service_arbitration_lock(self):
        entered, release = threading.Event(), threading.Event()
        reserve_thread = []
        request_thread = []

        def blocked_uuid():
            entered.set()
            if not release.wait(2.0):
                raise RuntimeError("uuid release timed out")
            return type("Token", (), {"hex": "execution_race"})()

        self.service.request_start("entry_a", self.ref)

        def drive():
            reserve_thread.append(self.step())

        def request_stop():
            self.service.request_stop()
            request_thread.append(True)

        fake_uuid_module = type("UuidModule", (), {"uuid4": staticmethod(blocked_uuid)})()
        with patch("components.playback_session.execution_gate.uuid", fake_uuid_module):
            driver = threading.Thread(target=drive)
            requester = threading.Thread(target=request_stop)
            driver.start()
            try:
                self.assertTrue(entered.wait(1.0))
                requester.start()
                requester.join(1.0)
                self.assertFalse(requester.is_alive())
                self.assertEqual(request_thread, [True])
            finally:
                release.set()
                driver.join(2.0)
                if requester.is_alive():
                    requester.join(2.0)
        self.assertFalse(driver.is_alive())
        self.assertEqual(len(reserve_thread), 1)
        self.assertEqual([call[0] for call in self.provider.calls], ["START"])
        self.assertIsNone(self.service.snapshot()["gate"]["owner"])

    def test_string_subclass_arguments_are_rejected_before_owner_invalidation(self):
        class Token(str):
            pass

        self.service.request_start("entry_live", self.ref)
        self.step()
        before = self.service.snapshot()
        for entry_id, ref in (
            (Token("entry_bad"), self.ref),
            ("entry_bad", {"kind": "LOCAL", "libraryId": Token("track_bad")}),
        ):
            with self.assertRaises(ContractValidationError):
                self.service.request_start(entry_id, ref)
            self.assertEqual(self.service.snapshot(), before)
        self.step()
        self.assertEqual([call[0] for call in self.provider.calls], ["START"])

    def test_invalid_provider_does_not_call_methods(self):
        class Bad:
            start = None
            stop = None
        with self.assertRaises(ContractValidationError) as error:
            LocalPlaybackService(provider=Bad(), boot_id="boot_01")
        self.assertEqual(error.exception.field, "provider")

    def test_base_exception_retires_permit_and_driver_then_propagates(self):
        class InterruptingProvider(Provider):
            def start(self, media_ref, *, lease, deadline):
                raise KeyboardInterrupt()

        service = LocalPlaybackService(provider=InterruptingProvider(), boot_id="boot_interrupt",
                                       monotonic=lambda: 10.0)
        service.request_start("entry_interrupt", self.ref)
        with self.assertRaises(KeyboardInterrupt):
            service.run_once(deadline=20.0)
        snapshot = service.snapshot()
        self.assertFalse(snapshot["driving"])
        self.assertIsNone(snapshot["gate"]["inFlight"])
        self.assertEqual(snapshot["gate"]["owner"]["entryId"], "entry_interrupt")
        self.assertTrue(snapshot["gate"]["cleanupRequired"])


if __name__ == "__main__":
    unittest.main()

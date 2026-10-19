import copy
import threading
import unittest
import importlib.util
import json
from pathlib import Path
from components.playback_session.execution_gate import ExecutionGate, GateStateError
import components.playback_session.execution_gate as gate_module
from jukebox.contracts import ContractValidationError


class ExecutionGateTests(unittest.TestCase):
    def start_receipt(self, identity, outcome="CONFIRMED", state="PLAYING", epoch="epoch_1"):
        return {"provider": "LOCAL", "operation": "START", "identity": copy.deepcopy(identity),
                "outcome": outcome, "epoch": epoch, "songid": "12" if state == "PLAYING" else None,
                "state": state, "positionMs": 0, "durationMs": 1000,
                "observedAtMonotonic": 1.0, "error": None}

    def start_failure_receipt(self, identity, outcome="UNCONFIRMED"):
        receipt = self.start_receipt(identity, outcome, "UNKNOWN", "epoch_1")
        receipt["songid"] = None
        receipt["error"] = {"code": "PROVIDER_UNAVAILABLE", "message": "failed",
                             "retryable": False, "operation": "START"}
        return receipt

    def stop_failure_receipt(self, identity, code="STOP_UNCONFIRMED"):
        receipt = self.stop_receipt(identity, epoch=None, outcome="UNCONFIRMED", state="UNKNOWN")
        receipt["observedAtMonotonic"] = None
        receipt["error"] = {"code": code, "message": "failed", "retryable": False,
                             "operation": "STOP"}
        return receipt

    def stop_receipt(self, identity, epoch="epoch_1", outcome="CONFIRMED", state="STOPPED"):
        return {"provider": "LOCAL", "operation": "STOP", "identity": copy.deepcopy(identity),
                "outcome": outcome, "epoch": epoch, "songid": None, "state": state,
                "positionMs": 0, "durationMs": 1000, "observedAtMonotonic": 2.0, "error": None}

    def started(self):
        gate = ExecutionGate(boot_id="boot_1")
        permit = gate.reserve_start("entry_1")
        lease = gate.lease(permit)
        identity = lease["identity"]
        gate.complete(permit, self.start_receipt(identity))
        return gate, identity

    def test_reservation_invalidation_and_defensive_copies(self):
        gate = ExecutionGate(boot_id="boot_1")
        permits = []
        barrier = threading.Barrier(3)
        barrier_released = False

        def reserve():
            barrier.wait(timeout=2)
            try:
                permits.append(gate.reserve_start("entry_1"))
            except GateStateError:
                pass

        threads = [threading.Thread(target=reserve) for _ in range(2)]
        try:
            for thread in threads:
                thread.start()
            barrier.wait(timeout=2)
            barrier_released = True
        finally:
            if not barrier_released:
                barrier.abort()
            for thread in threads:
                thread.join(2)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(1, len(permits))
        lease = gate.lease(permits[0])
        saved = copy.deepcopy(lease["identity"])
        lease["identity"]["entryId"] = "mutated"
        self.assertEqual(saved, gate.snapshot()["owner"])
        self.assertEqual(saved, gate.lease(permits[0])["identity"])
        snapshot = gate.snapshot()
        snapshot["owner"]["entryId"] = "snapshot_mutation"
        snapshot["generation"] = 0
        self.assertEqual(saved, gate.snapshot()["owner"])
        self.assertEqual(saved["generation"], gate.snapshot()["generation"])
        gate.invalidate()
        self.assertFalse(lease["guard"]("START", saved))
        self.assertTrue(gate.snapshot()["cleanupRequired"])

    def test_uncertain_start_requires_correlated_confirmed_stop(self):
        gate = ExecutionGate(boot_id="boot_1")
        start = gate.reserve_start("entry_1")
        ident = gate.lease(start)["identity"]
        gate.complete(start, self.start_failure_receipt(ident, "UNCONFIRMED"))
        self.assertEqual("PROVIDER_UNCONFIRMED", gate.snapshot()["error"])
        with self.assertRaises(GateStateError):
            gate.reserve_start("entry_2")
        gate.invalidate()
        stop = gate.reserve_stop()
        stop_lease = gate.lease(stop)
        self.assertTrue(stop_lease["guard"]("STOP", ident))
        bad = self.stop_receipt(ident, epoch="other_epoch")
        gate.complete(stop, bad)
        self.assertEqual("STOP_UNCONFIRMED", gate.snapshot()["error"])
        retry = gate.reserve_stop()
        gate.complete(retry, self.stop_receipt(ident))
        self.assertIsNone(gate.snapshot()["owner"])
        self.assertFalse(stop_lease["guard"]("STOP", ident))

    def test_rejected_start_releases_and_new_execution_is_fresh(self):
        gate = ExecutionGate(boot_id="boot_1")
        a = gate.reserve_start("entry_1")
        first = gate.lease(a)["identity"]
        rejected = self.start_receipt(first, "REJECTED", "UNKNOWN", None)
        rejected.update(songid=None, observedAtMonotonic=None)
        rejected["error"] = {"code": "RESOLUTION_FAILED", "message": "failed",
                             "retryable": False, "operation": "START"}
        gate.complete(a, rejected)
        b = gate.reserve_start("entry_1")
        self.assertNotEqual(first["executionId"], gate.lease(b)["identity"]["executionId"])
        self.assertGreater(gate.lease(b)["identity"]["generation"], first["generation"])

    def test_guard_rejects_malformed_identity_and_foreign_operation(self):
        gate = ExecutionGate(boot_id="boot_1")
        permit = gate.reserve_start("entry_1")
        lease = gate.lease(permit)
        identity = lease["identity"]
        self.assertFalse(lease["guard"]("STOP", identity))
        self.assertFalse(lease["guard"]("START", {**identity, "extra": 1}))
        self.assertFalse(lease["guard"]("START", {**identity, "generation": True}))
        self.assertFalse(lease["guard"]("START", {**identity, "bootId": "foreign"}))

    def test_local_provider_revocation_after_mutation_retains_owner_until_stop(self):
        adapter_path = Path(__file__).parents[1] / "local_provider" / "test_adapter.py"
        spec = importlib.util.spec_from_file_location("p04a_existing_adapter_tests", adapter_path)
        adapter_tests = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(adapter_tests)
        fixture_path = adapter_path.parent / "fixtures" / "v1.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        clock = adapter_tests.FakeClock()
        session = adapter_tests.FakeSession(fixture["initialStatus"])
        session.clock = clock
        resolver = adapter_tests.FakeResolver(fixture["resolvedMedia"])
        from components.local_provider import LocalProvider
        provider = LocalProvider(session=session, resolver=resolver, monotonic=clock,
                                 capabilities=fixture["capabilities"])
        gate = ExecutionGate(boot_id="boot_1")
        start = gate.reserve_start("entry_1")
        start_lease = gate.lease(start)

        def cancel_after_addid(command):
            if command == "addid":
                gate.invalidate()

        session.on_command = cancel_after_addid
        receipt = provider.start(fixture["mediaRef"], lease=start_lease, deadline=clock.value + 5)
        gate.complete(start, receipt)
        self.assertEqual("UNCONFIRMED", receipt["outcome"])
        self.assertNotIn("playid", [event[0] for event in session.events])
        self.assertIsNotNone(gate.snapshot()["owner"])
        with self.assertRaises(GateStateError):
            gate.reserve_start("entry_2")

        stop = gate.reserve_stop()
        stop_lease = gate.lease(stop)
        stopped = provider.stop(lease=stop_lease, deadline=clock.value + 5)
        gate.complete(stop, stopped)
        self.assertEqual("CONFIRMED", stopped["outcome"])
        self.assertIsNone(gate.snapshot()["owner"])

    def test_absent_null_foreign_and_duplicate_permits_never_complete(self):
        gate, identity = self.started()
        before = gate.snapshot()
        with self.assertRaises(GateStateError):
            gate.lease(None)
        self.assertEqual(before, gate.complete(None, None))
        self.assertEqual(before, gate.complete(None, self.stop_receipt(identity)))
        self.assertEqual(before, gate.complete(object(), self.stop_receipt(identity)))
        stop = gate.reserve_stop()
        live = gate.snapshot()
        self.assertEqual(live, gate.complete(object(), self.stop_receipt(identity)))
        gate.complete(stop, self.stop_receipt(identity))
        stopped = gate.snapshot()
        self.assertEqual(stopped, gate.complete(stop, self.stop_receipt(identity)))
        self.assertIsNone(stopped["owner"])

    def test_receipt_shape_errors_fail_closed_and_retire_current_permit(self):
        mutations = [
            lambda r: r.update(error={"code": "PROVIDER_UNAVAILABLE", "message": "bad",
                                     "retryable": False, "operation": "START"}),
            lambda r: r.update(outcome="UNCONFIRMED", error=None),
            lambda r: r.update(songid="not_digits"),
            lambda r: r.update(positionMs=10**100),
            lambda r: r.update(observedAtMonotonic=10**400),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                gate = ExecutionGate(boot_id="boot_1")
                permit = gate.reserve_start("entry_1")
                identity = gate.lease(permit)["identity"]
                receipt = self.start_receipt(identity)
                mutate(receipt)
                snapshot = gate.complete(permit, receipt)
                self.assertEqual("INVALID_RECEIPT", snapshot["error"])
                self.assertIsNotNone(snapshot["owner"])
                self.assertIsNone(snapshot["inFlight"])

    def test_invalid_rejection_does_not_release_reservation(self):
        gate = ExecutionGate(boot_id="boot_1")
        permit = gate.reserve_start("entry_1")
        ident = gate.lease(permit)["identity"]
        rejected = self.start_failure_receipt(ident, "REJECTED")
        rejected["error"].update(code="INVENTED_CODE", retryable=True)
        snapshot = gate.complete(permit, rejected)
        self.assertEqual("INVALID_RECEIPT", snapshot["error"])
        with self.assertRaises(GateStateError):
            gate.reserve_start("entry_2")

    def test_guard_identity_copy_and_stale_guards(self):
        gate = ExecutionGate(boot_id="boot_1")
        permit = gate.reserve_start("entry_1")
        lease = gate.lease(permit)
        identity = copy.deepcopy(lease["identity"])
        self.assertTrue(lease["guard"]("START", identity))
        lease["identity"]["entryId"] = "tampered"
        self.assertTrue(lease["guard"]("START", identity))
        gate.complete(permit, self.start_receipt(identity))
        self.assertFalse(lease["guard"]("START", identity))
        self.assertFalse(lease["guard"]("STOP", identity))

    def test_revoked_confirmed_start_keeps_owner_and_stop_survives_invalidation(self):
        gate = ExecutionGate(boot_id="boot_1")
        start = gate.reserve_start("entry_1")
        ident = gate.lease(start)["identity"]
        gate.invalidate()
        result = gate.complete(start, self.start_receipt(ident))
        self.assertEqual("STALE_EXECUTION", result["error"])
        self.assertEqual(ident, result["owner"])
        stop = gate.reserve_stop()
        lease = gate.lease(stop)
        gate.invalidate()
        self.assertTrue(lease["guard"]("STOP", ident))
        gate.complete(stop, self.stop_receipt(ident))
        self.assertIsNone(gate.snapshot()["owner"])

    def test_wrong_identity_operation_and_epoch_cannot_release_owner(self):
        gate, ident = self.started()
        stop = gate.reserve_stop()
        lease = gate.lease(stop)
        wrongs = [
            {**ident, "bootId": "other_boot"}, {**ident, "entryId": "other_entry"},
            {**ident, "executionId": "other_execution"},
        ]
        for wrong in wrongs:
            self.assertFalse(lease["guard"]("STOP", wrong))
        self.assertFalse(lease["guard"]("START", ident))
        before = gate.snapshot()
        bad = self.stop_receipt(ident, epoch="other_epoch")
        self.assertEqual("STOP_UNCONFIRMED", gate.complete(stop, bad)["error"])
        self.assertEqual(ident, gate.snapshot()["owner"])
        self.assertNotEqual(before, gate.snapshot())

    def test_old_stop_permit_cannot_override_retry_or_release_new_owner(self):
        gate, ident = self.started()
        old_stop = gate.reserve_stop()
        gate.complete(old_stop, self.stop_failure_receipt(ident))
        retry = gate.reserve_stop()
        pending = gate.snapshot()
        self.assertEqual(pending, gate.complete(old_stop, self.stop_receipt(ident)))
        gate.complete(retry, self.stop_failure_receipt(ident))
        failed = gate.snapshot()
        self.assertEqual(failed, gate.complete(old_stop, self.stop_receipt(ident)))
        retry2 = gate.reserve_stop()
        gate.complete(retry2, self.stop_receipt(ident))
        next_start = gate.reserve_start("entry_2")
        next_ident = gate.lease(next_start)["identity"]
        self.assertEqual(next_ident, gate.complete(old_stop, self.stop_receipt(ident))["owner"])

    def test_old_start_and_wrong_stop_receipts_cannot_change_later_owner(self):
        gate = ExecutionGate(boot_id="boot_1")
        old_start = gate.reserve_start("entry_1")
        old_ident = gate.lease(old_start)["identity"]
        rejected = self.start_failure_receipt(old_ident, "REJECTED")
        rejected["error"]["code"] = "RESOLUTION_FAILED"
        gate.complete(old_start, rejected)
        current_start = gate.reserve_start("entry_2")
        current_ident = gate.lease(current_start)["identity"]
        gate.complete(current_start, self.start_receipt(current_ident))
        before = gate.snapshot()
        self.assertEqual(before, gate.complete(old_start, self.start_receipt(old_ident)))

        stop = gate.reserve_stop()
        wrong_identity = self.stop_receipt({**current_ident, "entryId": "wrong_entry"})
        self.assertEqual("STOP_UNCONFIRMED", gate.complete(stop, wrong_identity)["error"])
        self.assertEqual(current_ident, gate.snapshot()["owner"])
        stop = gate.reserve_stop()
        wrong_operation = self.stop_receipt(current_ident)
        wrong_operation["operation"] = "START"
        gate.complete(stop, wrong_operation)
        self.assertEqual(current_ident, gate.snapshot()["owner"])
        with self.assertRaises(GateStateError):
            gate.lease(None)

    def test_public_and_guard_string_subclasses_are_rejected_before_state_changes(self):
        class HookText(str):
            def __eq__(self, other):
                raise AssertionError("caller equality executed")

        with self.assertRaises(ContractValidationError):
            ExecutionGate(boot_id=HookText("boot_1"))
        gate = ExecutionGate(boot_id="boot_1")
        before = gate.snapshot()
        with self.assertRaises(ContractValidationError):
            gate.reserve_start(HookText("entry_1"))
        self.assertEqual(before, gate.snapshot())
        permit = gate.reserve_start("entry_1")
        lease = gate.lease(permit)
        identity = copy.deepcopy(lease["identity"])
        identity["entryId"] = HookText("entry_1")
        self.assertFalse(lease["guard"]("START", identity))
        self.assertTrue(lease["guard"]("START", lease["identity"]))

        invalidated = self.start_receipt(lease["identity"])
        invalidated["outcome"] = HookText("CONFIRMED")
        completed = gate.complete(permit, invalidated)
        self.assertEqual("INVALID_RECEIPT", completed["error"])

    def test_invalid_arguments_and_counter_overflows_leave_state_unchanged(self):
        gate = ExecutionGate(boot_id="boot_1")
        before = gate.snapshot()
        for invalid in ("bad token", True, ""):
            with self.assertRaises(ContractValidationError):
                gate.reserve_start(invalid)
            self.assertEqual(before, gate.snapshot())
        gate._generation = 9007199254740991
        before = gate.snapshot()
        with self.assertRaises(GateStateError):
            gate.reserve_start("entry_1")
        self.assertEqual(before, gate.snapshot())
        with self.assertRaises(GateStateError):
            gate.invalidate()
        self.assertEqual(before, gate.snapshot())

    def test_none_and_malformed_receipts_retain_owner_and_allow_explicit_stop(self):
        for bad_receipt in (None, {"provider": "LOCAL"}):
            gate = ExecutionGate(boot_id="boot_1")
            permit = gate.reserve_start("entry_1")
            ident = gate.lease(permit)["identity"]
            snapshot = gate.complete(permit, bad_receipt)
            self.assertIsNotNone(snapshot["owner"])
            self.assertEqual("PROVIDER_UNCONFIRMED" if bad_receipt is None else "INVALID_RECEIPT",
                             snapshot["error"])
            stop = gate.reserve_stop()
            gate.complete(stop, self.stop_receipt(ident))
            self.assertIsNone(gate.snapshot()["owner"])

    def test_local_provider_blocked_resolver_allows_concurrent_invalidation(self):
        adapter_path = Path(__file__).parents[1] / "local_provider" / "test_adapter.py"
        spec = importlib.util.spec_from_file_location("p04a_blocked_adapter_tests", adapter_path)
        adapter_tests = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(adapter_tests)
        fixture = json.loads((adapter_path.parent / "fixtures" / "v1.json").read_text(encoding="utf-8"))
        from components.local_provider import LocalProvider
        clock = adapter_tests.FakeClock()
        session = adapter_tests.FakeSession(fixture["initialStatus"])
        session.clock = clock
        resolver = adapter_tests.FakeResolver(fixture["resolvedMedia"])
        entered, release = threading.Event(), threading.Event()
        invalidated = threading.Event()
        result = []

        def blocked_resolve(_library_id):
            entered.set()
            if not release.wait(2):
                raise RuntimeError("resolver barrier timed out")
            return fixture["resolvedMedia"]
        resolver.on_resolve = blocked_resolve
        provider = LocalProvider(session=session, resolver=resolver, monotonic=clock,
                                 capabilities=fixture["capabilities"])
        gate = ExecutionGate(boot_id="boot_1")
        permit = gate.reserve_start("entry_1")
        lease = gate.lease(permit)
        worker = threading.Thread(target=lambda: result.append(provider.start(
            fixture["mediaRef"], lease=lease, deadline=clock.value + 5)), daemon=True)
        canceller = threading.Thread(target=lambda: (gate.invalidate(), invalidated.set()), daemon=True)
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            canceller.start()
            self.assertTrue(invalidated.wait(2), "invalidation waited for the blocked provider call")
            release.set()
            worker.join(2)
            self.assertFalse(worker.is_alive())
            self.assertEqual([], session.events)
            gate.complete(permit, result[0])
        finally:
            release.set()
            worker.join(2)
            if canceller.ident is not None:
                canceller.join(2)
        self.assertFalse(worker.is_alive())
        self.assertFalse(canceller.is_alive())

    def test_provider_stop_failures_retain_owner_until_confirmed_retry(self):
        adapter_path = Path(__file__).parents[1] / "local_provider" / "test_adapter.py"
        spec = importlib.util.spec_from_file_location("p04a_stop_adapter_tests", adapter_path)
        adapter_tests = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(adapter_tests)
        fixture = json.loads((adapter_path.parent / "fixtures" / "v1.json").read_text(encoding="utf-8"))
        from components.local_provider import LocalProvider
        clock = adapter_tests.FakeClock()
        session = adapter_tests.FakeSession(fixture["initialStatus"])
        session.clock = clock
        resolver = adapter_tests.FakeResolver(fixture["resolvedMedia"])
        provider = LocalProvider(session=session, resolver=resolver, monotonic=clock,
                                 capabilities=fixture["capabilities"])
        gate = ExecutionGate(boot_id="boot_1")
        start = gate.reserve_start("entry_1")
        start_lease = gate.lease(start)
        gate.complete(start, provider.start(fixture["mediaRef"], lease=start_lease,
                                            deadline=clock.value + 5))
        ident = gate.snapshot()["owner"]

        session.stop_ack_without_stopping = True
        stop = gate.reserve_stop()
        failed = provider.stop(lease=gate.lease(stop), deadline=clock.value + 5)
        gate.complete(stop, failed)
        self.assertEqual("UNCONFIRMED", failed["outcome"])
        self.assertEqual(ident, gate.snapshot()["owner"])
        with self.assertRaises(GateStateError):
            gate.reserve_start("entry_2")

        session.stop_ack_without_stopping = False
        session.fail_on_exit = "TIMEOUT"
        stop = gate.reserve_stop()
        failed = provider.stop(lease=gate.lease(stop), deadline=clock.value + 5)
        gate.complete(stop, failed)
        self.assertEqual("UNCONFIRMED", failed["outcome"])
        self.assertEqual(ident, gate.snapshot()["owner"])

        session.fail_on_exit = None
        stop = gate.reserve_stop()
        confirmed = provider.stop(lease=gate.lease(stop), deadline=clock.value + 5)
        gate.complete(stop, confirmed)
        self.assertEqual("CONFIRMED", confirmed["outcome"])
        self.assertIsNone(gate.snapshot()["owner"])

    def test_string_subclass_receipts_are_rejected_without_lock_reentrancy(self):
        gate, ident = self.started()
        stop = gate.reserve_stop()
        receipt = self.stop_receipt(ident)
        finished = threading.Event()

        class ReentrantText(str):
            def __eq__(self, other):
                gate.snapshot()
                return super().__eq__(other)
        receipt["epoch"] = ReentrantText("epoch_1")
        worker = threading.Thread(target=lambda: (gate.complete(stop, receipt), finished.set()), daemon=True)
        worker.start()
        worker.join(1)
        self.assertTrue(finished.is_set(), "receipt equality hook deadlocked the gate lock")
        self.assertIsNotNone(gate.snapshot()["owner"])
        self.assertEqual("STOP_UNCONFIRMED", gate.snapshot()["error"])

    def test_receipt_mutation_after_validation_cannot_reach_locked_transition(self):
        gate, ident = self.started()
        stop = gate.reserve_stop()
        receipt = self.stop_receipt(ident)
        validated, release = threading.Event(), threading.Event()
        lock_checks, result = [], []
        original_validator = gate_module._valid_receipt_values

        def pause_after_real_validation(value, operation):
            valid = original_validator(value, operation)
            validated.set()
            if not release.wait(2):
                raise RuntimeError("receipt validation barrier timed out")
            return valid

        class LockCheckingText(str):
            def __eq__(self, other):
                lock_checks.append(gate._lock.locked())
                return super().__eq__(other)

        gate_module._valid_receipt_values = pause_after_real_validation
        worker = threading.Thread(target=lambda: result.append(gate.complete(stop, receipt)), daemon=True)
        worker.start()
        try:
            self.assertTrue(validated.wait(2))
            receipt["epoch"] = LockCheckingText("epoch_1")
            release.set()
            worker.join(2)
            self.assertFalse(worker.is_alive())
            self.assertEqual([], lock_checks)
            self.assertIsNone(result[0]["owner"])
        finally:
            release.set()
            worker.join(2)
            gate_module._valid_receipt_values = original_validator
        self.assertFalse(worker.is_alive())


if __name__ == "__main__":
    unittest.main()

"""Argument-surface tests for the durable dispatch bridge."""

import unittest

from components.playback_session.durable_dispatch import DurableDispatch
from components.playback_session.execution_gate import GateStateError
from jukebox.contracts import ContractValidationError
from jukebox.contracts.playback_v1 import validate_playback_command


def selection(kind="LOCAL"):
    media_ref = {"kind": "LOCAL", "libraryId": "m1"}
    if kind == "SPOTIFY":
        media_ref = {"kind": "SPOTIFY",
                     "uri": "spotify:track:" + "a" * 22}
    return {"queueId": "q1", "queueRevision": 1,
            "entry": {"entryId": "e1", "sourceEntryId": None,
                      "mediaRef": media_ref, "title": "Track", "position": 0}}


def accepted(action="PLAYBACK_START", kind="LOCAL"):
    body = None if action == "PLAYBACK_STOP" else selection(kind)
    return {"commandId": "c1", "action": action, "status": "ACCEPTED",
            "result": {"intentId": "i1", "intentSequence": 1,
                       "acceptedAt": "2026-10-21T00:00:00.000Z",
                       "selection": body}}


def receipt(operation, identity, outcome, state, songid, error=None):
    return {"provider": "LOCAL", "operation": operation,
            "identity": dict(identity), "outcome": outcome, "epoch": "ep1",
            "songid": songid, "state": state, "positionMs": None,
            "durationMs": None, "observedAtMonotonic": 10.0, "error": error}


class Provider:
    def __init__(self):
        self.calls = []
        self.fail_next_stop = False

    def start(self, media_ref, *, lease, deadline):
        self.calls.append("START")
        return receipt("START", lease["identity"], "CONFIRMED", "PLAYING", "1")

    def stop(self, *, lease, deadline):
        self.calls.append("STOP")
        identity = lease["identity"]
        if self.fail_next_stop:
            self.fail_next_stop = False
            error = {"code": "STOP_UNCONFIRMED",
                     "message": "No confirmation.", "retryable": False,
                     "operation": "STOP"}
            return receipt("STOP", identity, "UNCONFIRMED", "UNKNOWN", None,
                           error=error)
        return receipt("STOP", identity, "CONFIRMED", "STOPPED", None)


class Store:
    def __init__(self, result=None):
        self.result = result
        self.commands = []
        self.admitted = 0
        self.error = None

    def admit_playback(self, command):
        self.commands.append(command)
        if self.error is not None:
            raise self.error
        self.admitted += 1
        return self.result


class ValidatingStore:
    """Minimal store that applies the real command contract first."""

    def __init__(self, result):
        self.result = result
        self.commands = []
        self.admitted = 0

    def admit_playback(self, command):
        self.commands.append(command)
        validate_playback_command(command)
        self.admitted += 1
        return self.result


def command(command_id="c1"):
    return {"contractVersion": 1, "commandId": command_id,
            "action": "PLAYBACK_START", "queueId": "q1",
            "expectedQueueRevision": 1, "entryId": "e1"}


class InitArgumentTests(unittest.TestCase):
    def setUp(self):
        self.provider = Provider()

    def test_init_requires_store_keyword(self):
        with self.assertRaises(TypeError):
            DurableDispatch(provider=self.provider, boot_id="b1")

    def test_init_requires_provider_keyword(self):
        with self.assertRaises(TypeError):
            DurableDispatch(store=Store(), boot_id="b1")

    def test_init_rejects_positional_arguments(self):
        with self.assertRaises(TypeError):
            DurableDispatch(Store(), self.provider, "b1")

    def test_init_rejects_unknown_keyword(self):
        with self.assertRaises(TypeError):
            DurableDispatch(store=Store(), provider=self.provider,
                            boot_id="b1", service=object())

    def test_init_treats_none_monotonic_as_default_clock(self):
        bridge = DurableDispatch(store=Store(), provider=self.provider,
                                 boot_id="b1", monotonic=None)
        self.assertIsInstance(bridge, DurableDispatch)

    def test_init_rejects_provider_without_callable_operations(self):
        class Bad:
            start = None
            stop = None

        with self.assertRaises(ContractValidationError) as error:
            DurableDispatch(store=Store(), provider=Bad(), boot_id="b1")
        self.assertEqual(error.exception.field, "provider")

    def test_init_rejects_non_identifier_boot_ids(self):
        class Token(str):
            pass

        for boot_id in ("", 7, Token("b1"), None):
            with self.assertRaises(ContractValidationError) as error:
                DurableDispatch(store=Store(), provider=self.provider,
                                boot_id=boot_id)
            self.assertEqual(error.exception.field, "bootId")

    def test_init_rejects_non_callable_monotonic(self):
        for monotonic in ("clock", 1.5, object()):
            with self.assertRaises(ContractValidationError) as error:
                DurableDispatch(store=Store(), provider=self.provider,
                                boot_id="b1", monotonic=monotonic)
            self.assertEqual(error.exception.field, "monotonic")

    def test_init_accepts_duck_typed_store(self):
        store = Store(accepted("PLAYBACK_STOP"))
        bridge = DurableDispatch(store=store, provider=self.provider,
                                 boot_id="b1", monotonic=lambda: 1.0)
        result = bridge.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertEqual(result["admission"], store.result)


class DispatchArgumentTests(unittest.TestCase):
    def setUp(self):
        self.provider = Provider()
        self.store = Store(accepted())
        self.bridge = DurableDispatch(store=self.store,
                                      provider=self.provider, boot_id="b1",
                                      monotonic=lambda: 1.0)

    def test_command_object_is_forwarded_unchanged_to_store(self):
        self.store.result = accepted("PLAYBACK_STOP")
        value = {"commandId": 5, "surprise": True}
        self.bridge.dispatch(value, deadline=20.0)
        self.assertEqual(len(self.store.commands), 1)
        self.assertIs(self.store.commands[0], value)

    def test_store_validation_rejects_wrong_command_id_types(self):
        for command_id in (5, None, {"a": 1}, ["c1"]):
            store = ValidatingStore(accepted("PLAYBACK_STOP"))
            bridge = DurableDispatch(store=store, provider=self.provider,
                                     boot_id="b1", monotonic=lambda: 1.0)
            with self.assertRaises(ContractValidationError) as error:
                bridge.dispatch(command(command_id), deadline=20.0)
            self.assertEqual(error.exception.field, "command.commandId")
            self.assertEqual(len(store.commands), 1)
            self.assertEqual(self.provider.calls, [])

    def test_store_validation_error_propagates_unchanged(self):
        store = Store()
        marker = ContractValidationError("command.action", "unknown_action")
        store.error = marker
        bridge = DurableDispatch(store=store, provider=self.provider,
                                 boot_id="b1", monotonic=lambda: 1.0)
        with self.assertRaises(ContractValidationError) as error:
            bridge.dispatch(command(), deadline=20.0)
        self.assertIs(error.exception, marker)
        self.assertEqual(self.provider.calls, [])

    def test_rejected_admission_is_returned_unchanged(self):
        rejected = {"commandId": "c1", "action": "PLAYBACK_START",
                    "status": "REJECTED", "error": {}}
        self.store.result = rejected
        result = self.bridge.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertIs(result, rejected)
        self.assertEqual(self.provider.calls, [])

    def test_disallowed_status_is_returned_without_provider_call(self):
        for status in ("FAILED", "PENDING", 2, None):
            self.store.result = {"commandId": "c1", "action": "PLAYBACK_START",
                                 "status": status, "result": {}}
            result = self.bridge.dispatch({"commandId": "c1"}, deadline=20.0)
            self.assertEqual(result["status"], status)
        self.assertEqual(self.provider.calls, [])

    def test_unknown_action_is_returned_without_provider_call(self):
        self.store.result = {"commandId": "c1", "action": "PLAYBACK_SEEK",
                             "status": "ACCEPTED", "result": {}}
        result = self.bridge.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertEqual(result["action"], "PLAYBACK_SEEK")
        self.assertEqual(self.provider.calls, [])

    def test_non_mapping_admission_fails_without_provider_call(self):
        for admission in (None, [], "ACCEPTED", 4):
            self.store.result = admission
            with self.assertRaises(AttributeError):
                self.bridge.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertEqual(self.provider.calls, [])

    def test_accepted_admission_without_action_raises_key_error(self):
        self.store.result = {"status": "ACCEPTED"}
        with self.assertRaises(KeyError) as error:
            self.bridge.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertEqual(error.exception.args[0], "action")
        self.assertEqual(self.provider.calls, [])

    def test_start_admission_without_selection_raises_key_error(self):
        self.store.result = {"status": "ACCEPTED", "action": "PLAYBACK_START",
                             "result": {}}
        with self.assertRaises(KeyError) as error:
            self.bridge.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertEqual(error.exception.args[0], "selection")
        self.assertEqual(self.provider.calls, [])

    def test_entry_with_wrong_field_types_is_rejected(self):
        cases = (
            {"entryId": 5, "sourceEntryId": None,
             "mediaRef": {"kind": "LOCAL", "libraryId": "m1"},
             "title": "Track", "position": 0},
            {"entryId": "e1", "sourceEntryId": None,
             "mediaRef": {"kind": "LOCAL", "libraryId": 7},
             "title": "Track", "position": 0},
        )
        for entry in cases:
            admission = accepted()
            admission["result"]["selection"]["entry"] = entry
            self.store.result = admission
            with self.assertRaises(ContractValidationError):
                self.bridge.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertEqual(self.provider.calls, [])

    def test_non_local_media_ref_is_rejected(self):
        self.store.result = accepted(kind="SPOTIFY")
        with self.assertRaises(ContractValidationError) as error:
            self.bridge.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertEqual(error.exception.field, "mediaRef.kind")
        self.assertEqual(self.provider.calls, [])

    def test_malformed_dispatch_errors_leave_bridge_reusable(self):
        self.store.result = {"status": "ACCEPTED"}
        for _ in range(2):
            with self.assertRaises(KeyError):
                self.bridge.dispatch({"commandId": "c1"}, deadline=20.0)
        self.store.result = accepted("PLAYBACK_START")
        self.bridge.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertEqual(self.provider.calls, ["START"])
        self.assertEqual(self.store.admitted, 3)

    def test_dispatch_requires_deadline_keyword(self):
        with self.assertRaises(TypeError):
            self.bridge.dispatch({"commandId": "c1"})
        self.assertEqual(self.provider.calls, [])

    def test_invalid_deadline_type_is_rejected(self):
        for deadline in (True, "20.0", None, float("nan"), float("inf")):
            with self.assertRaises(ContractValidationError) as error:
                self.bridge.dispatch({"commandId": "c1"}, deadline=deadline)
            self.assertEqual(error.exception.field, "deadline")
        self.assertEqual(self.store.admitted, 0)
        self.assertEqual(self.store.commands, [])
        self.assertEqual(self.provider.calls, [])

    def test_invalid_deadline_is_not_admitted_to_store(self):
        store = ValidatingStore(accepted("PLAYBACK_STOP"))
        bridge = DurableDispatch(store=store, provider=self.provider,
                                 boot_id="b1", monotonic=lambda: 1.0)
        with self.assertRaises(ContractValidationError) as error:
            bridge.dispatch(command(), deadline=True)
        self.assertEqual(error.exception.field, "deadline")
        self.assertEqual(store.admitted, 0)
        self.assertEqual(store.commands, [])
        self.assertEqual(self.provider.calls, [])

    def test_expired_deadline_is_rejected_before_admission(self):
        store = ValidatingStore(accepted("PLAYBACK_STOP"))
        bridge = DurableDispatch(store=store, provider=self.provider,
                                 boot_id="b1", monotonic=lambda: 10.0)
        with self.assertRaises(GateStateError) as error:
            bridge.dispatch(command(), deadline=10.0)
        self.assertEqual(error.exception.code, "DEADLINE_EXPIRED")
        self.assertEqual(store.admitted, 0)
        self.assertEqual(self.provider.calls, [])

    def test_non_numeric_clock_raises_clock_unavailable(self):
        def broken():
            raise RuntimeError("clock down")

        for clock in (lambda: "later", lambda: None, broken):
            store = ValidatingStore(accepted("PLAYBACK_STOP"))
            bridge = DurableDispatch(store=store, provider=self.provider,
                                     boot_id="b1", monotonic=clock)
            with self.assertRaises(GateStateError) as error:
                bridge.dispatch(command(), deadline=20.0)
            self.assertEqual(error.exception.code, "CLOCK_UNAVAILABLE")
            self.assertEqual(store.admitted, 0)
        self.assertEqual(self.provider.calls, [])

    def test_admission_without_result_shape_fails_before_provider(self):
        self.store.result = {"status": "ACCEPTED", "action": "PLAYBACK_START"}
        with self.assertRaises(KeyError) as error:
            self.bridge.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertEqual(error.exception.args[0], "result")
        self.assertEqual(self.store.admitted, 1)
        self.assertEqual(self.provider.calls, [])
        self.store.result = accepted("PLAYBACK_START")
        self.bridge.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertEqual(self.provider.calls, ["START"])

    def test_changed_admission_for_known_command_id_is_not_memoized(self):
        # sol-Ruling: Memo nur bei kanonisch identischer frischer Admission.
        # Der FakeStore liefert fuer dieselbe commandId eine abweichende,
        # weiterhin ACCEPTED-Admission (STOP) -> kein Memo, normaler Fluss.
        first = self.bridge.dispatch({"commandId": "c1"}, deadline=20.0)
        self.store.result = accepted("PLAYBACK_STOP")
        result = self.bridge.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertIsNot(result, first)
        self.assertEqual(result["admission"], accepted("PLAYBACK_STOP"))
        self.assertEqual(self.store.admitted, 2)
        self.assertEqual(self.provider.calls, ["START", "STOP"])

    def test_rejected_admission_is_not_memoized(self):
        rejected = {"commandId": "c1", "action": "PLAYBACK_START",
                    "status": "REJECTED", "error": {}}
        self.store.result = rejected
        first = self.bridge.dispatch({"commandId": "c1"}, deadline=20.0)
        second = self.bridge.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertIs(first, rejected)
        self.assertIs(second, rejected)
        self.assertEqual(self.store.admitted, 2)
        self.assertEqual(self.provider.calls, [])

    def test_non_string_command_id_is_not_memoized(self):
        self.store.result = accepted("PLAYBACK_STOP")
        for _ in range(2):
            self.bridge.dispatch({"commandId": 5}, deadline=20.0)
        self.assertEqual(self.store.admitted, 2)
        self.assertEqual(self.provider.calls, [])

    def test_successful_result_exposes_gate_instead_of_receipt(self):
        result = self.bridge.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertEqual(set(result), {"admission", "playback", "gate"})
        self.assertNotIn("receipt", result)
        self.assertIs(result["gate"], result["playback"]["gate"])

    def test_failure_result_exposes_failure_instead_of_receipt(self):
        self.bridge.dispatch({"commandId": "c0"}, deadline=20.0)
        self.provider.fail_next_stop = True
        self.store.result = accepted("PLAYBACK_STOP")
        result = self.bridge.dispatch({"commandId": "c2"}, deadline=20.0)
        self.assertEqual(set(result), {"admission", "playback", "failure"})
        self.assertNotIn("receipt", result)
        self.assertNotIn("gate", result)

    def test_store_without_admit_playback_fails_before_provider(self):
        bridge = DurableDispatch(store=object(), provider=self.provider,
                                 boot_id="b1", monotonic=lambda: 1.0)
        with self.assertRaises(AttributeError):
            bridge.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertEqual(self.provider.calls, [])


if __name__ == "__main__":
    unittest.main()

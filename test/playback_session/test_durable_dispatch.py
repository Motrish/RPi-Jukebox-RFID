"""Durable command dispatch tests."""
import unittest
import threading
import json
from unittest.mock import patch

from components.playback_session.durable_dispatch import DurableDispatch
from components.playback_session.execution_gate import GateStateError
from jukebox.contracts import ContractValidationError


def accepted(action="PLAYBACK_START"):
    selection = None
    if action == "PLAYBACK_START":
        selection = {"queueId": "q1", "queueRevision": 1,
                     "entry": {"entryId": "e1", "sourceEntryId": None,
                               "mediaRef": {"kind": "LOCAL", "libraryId": "m1"},
                               "title": "Track", "position": 0}}
    return {"commandId": "c1", "action": action, "status": "ACCEPTED",
            "result": {"intentId": "i1", "intentSequence": 1,
                       "acceptedAt": "2026-10-21T00:00:00.000Z", "selection": selection}}


class Provider:
    def __init__(self):
        self.calls = []
        self.identities = []
        self.crash = False
        self.crash_error = RuntimeError("provider crash")
        self.start_result = None
        self.stop_unconfirmed = False

    def start(self, media_ref, *, lease, deadline):
        self.calls.append("START")
        if self.crash:
            raise self.crash_error
        i = lease["identity"]
        self.identities.append(dict(i))
        if self.start_result is not None:
            return self.start_result(i)
        return receipt("START", i, "CONFIRMED", "PLAYING", "1")

    def stop(self, *, lease, deadline):
        self.calls.append("STOP")
        i = lease["identity"]
        self.identities.append(dict(i))
        if self.stop_unconfirmed:
            return receipt("STOP", i, "UNCONFIRMED", "UNKNOWN", None,
                           {"code": "STOP_UNCONFIRMED", "message": "Not confirmed.",
                            "retryable": False, "operation": "STOP"})
        return receipt("STOP", i, "CONFIRMED", "STOPPED", None)


def receipt(op, ident, outcome, state, songid, error=None):
    return {"provider": "LOCAL", "operation": op, "identity": dict(ident),
            "outcome": outcome, "epoch": "ep1", "songid": songid,
            "state": state, "positionMs": None, "durationMs": None,
            "observedAtMonotonic": 10.0, "error": error}


class Store:
    def __init__(self, result):
        self.result = result
        self.writes = []
        self.admitted_result = None
        self.admissions = 0
        self.requests = {}

    def admit_playback(self, command):
        self.admissions += 1
        if type(command) is not dict or type(command.get("commandId")) is not str:
            raise ContractValidationError("command.commandId", "invalid_identifier")
        command_id = command["commandId"]
        if "action" in command and command["action"] not in {"PLAYBACK_START", "PLAYBACK_STOP"}:
            result = {"commandId": command_id, "action": command["action"],
                      "status": "REJECTED", "error": {"code": "VALIDATION_ERROR"}}
            self.admitted_result = result
            return result
        request = json.dumps(command, sort_keys=True)
        if command_id in self.requests and self.requests[command_id] != request:
            result = {"commandId": command_id, "action": command.get("action", "PLAYBACK_START"),
                      "status": "REJECTED",
                      "error": {"code": "COMMAND_ID_REUSED"}}
            self.admitted_result = result
            return result
        self.requests[command_id] = request
        self.admitted_result = self.result.copy()
        return self.result

    def _write_playback_result(self, conn, command_id, result):
        self.writes.append((command_id, result))


class DurableDispatchTests(unittest.TestCase):
    def setUp(self):
        self.provider = Provider()
        self.store = Store(accepted())
        self.dispatch = DurableDispatch(store=self.store, provider=self.provider,
                                        boot_id="b1", monotonic=lambda: 1.0)

    def test_accepted_start_is_forwarded_to_service(self):
        self.dispatch.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertEqual(self.provider.calls, ["START"])

    def test_rejected_command_does_not_start(self):
        self.store.result = {"commandId": "c1", "action": "PLAYBACK_START",
                             "status": "REJECTED", "error": {}}
        result = self.dispatch.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(result["admission"]["status"], "REJECTED")
        self.assertIsNone(result["playback"])

    def test_rejected_result_uses_unified_wrapper(self):
        self.store.result = {"commandId": "c1", "action": "PLAYBACK_START",
                             "status": "REJECTED", "error": {}}
        result = self.dispatch.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertEqual(result, {"admission": self.store.result, "playback": None,
                                  "operation": None, "gate": None, "failure": None,
                                  "intentId": None, "executionId": None})

    def test_rejected_result_carries_no_correlation_ids(self):
        self.store.result = {"commandId": "c1", "action": "PLAYBACK_START",
                             "status": "REJECTED", "error": {}}
        result = self.dispatch.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertIsNone(result["intentId"])
        self.assertIsNone(result["executionId"])

    def test_cleanup_stop_after_crash_reports_executed_operation(self):
        self.provider.crash = True
        with self.assertRaises(RuntimeError):
            self.dispatch.dispatch({"commandId": "c1"}, deadline=20.0)
        self.provider.crash = False
        result = self.dispatch.dispatch({"commandId": "c2"}, deadline=20.0)
        # Admission records requested START; the bridge reports cleanup STOP actually run.
        self.assertEqual(result["admission"]["action"], "PLAYBACK_START")
        self.assertEqual(result["operation"], "STOP")
        self.assertIsNotNone(result["gate"])
        self.assertIsNone(result["failure"])
        self.assertIs(result["gate"], result["playback"]["gate"])
        self.assertIsNone(result["gate"]["owner"])
        self.assertEqual(result["executionId"], self.provider.identities[-1]["executionId"])

    def test_successful_start_correlates_command_with_execution_and_intent(self):
        service = self.dispatch._service
        original = service.request_start
        issued = []

        def capture_intent(*args, **kwargs):
            intent_id = original(*args, **kwargs)
            issued.append(intent_id)
            return intent_id

        with patch.object(service, "request_start", side_effect=capture_intent):
            result = self.dispatch.dispatch({"commandId": "c1"}, deadline=20.0)
        owner = result["playback"]["gate"]["owner"]
        self.assertEqual(result["intentId"], issued[0])
        self.assertIsInstance(result["executionId"], str)
        self.assertEqual(result["executionId"], owner["executionId"])
        self.assertEqual(result["admission"]["commandId"], "c1")

    def test_successful_stop_correlates_with_released_identity(self):
        started = self.dispatch.dispatch({"commandId": "c0"}, deadline=20.0)
        old_execution_id = started["executionId"]
        service = self.dispatch._service
        original = service.request_stop
        issued = []

        def capture_intent(*args, **kwargs):
            intent_id = original(*args, **kwargs)
            issued.append(intent_id)
            return intent_id

        self.store.result = accepted("PLAYBACK_STOP")
        with patch.object(service, "request_stop", side_effect=capture_intent):
            result = self.dispatch.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertEqual(result["intentId"], issued[0])
        self.assertEqual(result["executionId"], old_execution_id)
        self.assertIsNone(result["playback"]["gate"]["owner"])

    def test_stale_failure_is_not_attributed_to_new_dispatch(self):
        self.dispatch.dispatch({"commandId": "c0"}, deadline=20.0)
        self.store.result = accepted("PLAYBACK_STOP")
        self.provider.stop = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("stop failed"))
        with self.assertRaises(RuntimeError):
            self.dispatch.dispatch({"commandId": "c1", "action": "PLAYBACK_STOP"},
                                   deadline=20.0)
        self.provider.stop = Provider.stop.__get__(self.provider)
        self.store.result = accepted("PLAYBACK_START")
        result = self.dispatch.dispatch({"commandId": "c2"}, deadline=20.0)
        self.assertIsNone(result["operation"])
        self.assertIsNone(result["failure"])
        self.assertEqual(result["playback"]["lastFailure"],
                         {"operation": "STOP", "code": "STOP_UNCONFIRMED"})

    def test_repeated_identical_failure_is_reported_fresh(self):
        self.provider.start_result = lambda identity: receipt(
            "START", identity, "REJECTED", "UNKNOWN", None,
            {"code": "PROVIDER_REJECTED", "message": "Rejected.",
             "retryable": False, "operation": "START"})
        first = self.dispatch.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertEqual(first["failure"],
                         {"operation": "START", "code": "START_REJECTED"})
        second = self.dispatch.dispatch({"commandId": "c2"}, deadline=20.0)
        self.assertEqual(self.provider.calls, ["START", "START"])
        self.assertEqual(second["operation"], "START")
        self.assertEqual(second["failure"], first["failure"])
        self.assertIsNone(second["gate"])

    def test_noop_stop_reports_no_operation(self):
        self.store.result = accepted("PLAYBACK_STOP")
        result = self.dispatch.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertIsNone(result["operation"])
        self.assertIsNone(result["failure"])
        self.assertIsNotNone(result["gate"])
        self.assertIsNone(result["playback"]["lastFailure"])

    def test_repeated_identical_stop_failure_is_reported_fresh(self):
        self.dispatch.dispatch({"commandId": "c0"}, deadline=20.0)
        self.store.result = accepted("PLAYBACK_STOP")
        self.provider.stop_unconfirmed = True
        first = self.dispatch.dispatch({"commandId": "c1", "action": "PLAYBACK_STOP"},
                                       deadline=20.0)
        second = self.dispatch.dispatch({"commandId": "c2", "action": "PLAYBACK_STOP"},
                                        deadline=20.0)
        self.assertEqual(self.provider.calls, ["START", "STOP", "STOP"])
        self.assertEqual(second["operation"], "STOP")
        self.assertEqual(second["failure"], first["failure"])
        self.assertEqual(second["failure"]["code"], "STOP_UNCONFIRMED")
        self.assertIsNone(second["gate"])

    def test_start_admission_reports_cleanup_stop_without_crash(self):
        self.dispatch.dispatch({"commandId": "c0"}, deadline=20.0)
        result = self.dispatch.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertEqual(result["admission"]["action"], "PLAYBACK_START")
        self.assertEqual(result["operation"], "STOP")

    def test_rejected_start_receipt_reports_operation_and_failure(self):
        self.provider.start_result = lambda identity: receipt(
            "START", identity, "REJECTED", "UNKNOWN", None,
            {"code": "PROVIDER_REJECTED", "message": "Rejected.",
             "retryable": False, "operation": "START"})
        result = self.dispatch.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertEqual(result["operation"], "START")
        self.assertEqual(result["failure"],
                         {"operation": "START", "code": "START_REJECTED"})
        self.assertIsNone(result["gate"])
        self.assertEqual(result["executionId"],
                         result["playback"]["lastExecution"]["executionId"])
        self.assertEqual(result["playback"]["lastExecution"]["intentId"], result["intentId"])

    def test_invalid_start_receipt_reports_invalid_receipt_failure(self):
        self.provider.start_result = lambda identity: receipt(
            "START", identity, "INVALID", "UNKNOWN", None)
        result = self.dispatch.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertEqual(result["operation"], "START")
        self.assertEqual(result["failure"]["code"], "INVALID_RECEIPT")
        self.assertIsNone(result["gate"])

    def test_stop_is_dispatched(self):
        self.dispatch.dispatch({"commandId": "c0"}, deadline=20.0)
        self.store.result = accepted("PLAYBACK_STOP")
        self.dispatch.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertEqual(self.provider.calls, ["START", "STOP"])

    def test_run_once_crash_propagates_without_store_write(self):
        self.provider.crash = True
        with self.assertRaises(RuntimeError) as raised:
            self.dispatch.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertIs(raised.exception, self.provider.crash_error)
        self.assertEqual(self.store.writes, [])
        self.assertEqual(self.store.admitted_result["status"], "ACCEPTED")
        self.assertNotIn("FAILED", [write[1].get("status") for write in self.store.writes])

    def test_provider_crash_replay_raises_memoized_exception_without_reexecution(self):
        self.provider.crash = True
        command = {"commandId": "c1"}
        with self.assertRaises(RuntimeError) as first:
            self.dispatch.dispatch(command, deadline=20.0)
        with self.assertRaises(RuntimeError) as replay:
            self.dispatch.dispatch(command, deadline=20.0)
        self.assertIs(first.exception, replay.exception)
        self.assertEqual(self.provider.calls, ["START"])

    def test_invalid_replayed_payload_is_rejected_by_store_contract(self):
        self.dispatch.dispatch({"commandId": "c1"}, deadline=20.0)
        calls = list(self.provider.calls)
        result = self.dispatch.dispatch(
            {"commandId": "c1", "action": "INVALID"}, deadline=20.0)
        self.assertEqual(result["admission"]["status"], "REJECTED")
        self.assertEqual(result["admission"]["error"]["code"], "VALIDATION_ERROR")
        self.assertEqual(self.provider.calls, calls)

    def test_modified_replayed_payload_gets_command_id_reused(self):
        self.dispatch.dispatch({"commandId": "c1"}, deadline=20.0)
        calls = list(self.provider.calls)
        result = self.dispatch.dispatch(
            {"commandId": "c1", "selection": "different"}, deadline=20.0)
        self.assertEqual(result["admission"]["status"], "REJECTED")
        self.assertEqual(result["admission"]["error"]["code"], "COMMAND_ID_REUSED")
        self.assertEqual(self.provider.calls, calls)

    def test_same_payload_replay_returns_memoized_result_without_new_start(self):
        command = {"commandId": "c1"}
        first = self.dispatch.dispatch(command, deadline=20.0)
        calls = list(self.provider.calls)
        replay = self.dispatch.dispatch(command, deadline=20.0)
        self.assertEqual(replay, first)
        self.assertEqual(replay["intentId"], first["intentId"])
        self.assertEqual(replay["executionId"], first["executionId"])
        self.assertEqual(self.provider.calls, calls)
        self.assertEqual(self.store.admissions, 1)

    def test_rejected_command_id_is_not_memoized(self):
        self.store.result = {"commandId": "c1", "action": "PLAYBACK_START",
                             "status": "REJECTED", "error": {}}
        self.dispatch.dispatch({"commandId": "c1"}, deadline=20.0)
        self.store.result = accepted()
        self.dispatch.dispatch({"commandId": "c1"}, deadline=20.0)
        self.assertEqual(self.provider.calls, ["START"])
        self.assertEqual(self.store.admissions, 2)

    def test_invalid_deadline_type_is_rejected_before_store_admission(self):
        with self.assertRaises(ContractValidationError):
            self.dispatch.dispatch({"commandId": "c1"}, deadline=True)
        self.assertEqual(self.store.admissions, 0)

    def test_past_deadline_rejected_before_store_admission(self):
        with self.assertRaises(GateStateError) as raised:
            self.dispatch.dispatch({"commandId": "c1"}, deadline=1.0)
        self.assertEqual(raised.exception.code, "DEADLINE_EXPIRED")
        self.assertEqual(self.store.admissions, 0)

    def test_stop_unconfirmed_can_be_retried_explicitly(self):
        self.dispatch.dispatch({"commandId": "c1"}, deadline=20.0)
        self.store.result = accepted("PLAYBACK_STOP")
        original_stop = self.provider.stop

        def failed_stop(**kwargs):
            self.provider.calls.append("STOP")
            raise RuntimeError("no stop")
        self.provider.stop = failed_stop
        with self.assertRaises(RuntimeError):
            self.dispatch.dispatch({"commandId": "c2", "action": "PLAYBACK_STOP"}, deadline=20.0)
        self.provider.stop = original_stop
        self.dispatch.dispatch({"commandId": "c3", "action": "PLAYBACK_STOP"}, deadline=20.0)
        self.assertEqual(self.provider.calls, ["START", "STOP", "STOP"])

    def test_simultaneous_dispatch_is_serialized(self):
        entered, release = threading.Event(), threading.Event()
        original = self.provider.start

        def blocked(*args, **kwargs):
            entered.set()
            release.wait(2)
            return original(*args, **kwargs)
        self.provider.start = blocked
        thread = threading.Thread(target=lambda: self.dispatch.dispatch({"commandId": "c1"}, deadline=20.0))
        thread.start()
        self.assertTrue(entered.wait(1))
        with self.assertRaises(GateStateError):
            self.dispatch.dispatch({"commandId": "c2"}, deadline=20.0)
        release.set()
        thread.join(2)
        self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()

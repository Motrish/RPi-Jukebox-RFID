import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "jukebox"))

from jukebox.contracts.playback_v1 import (  # noqa: E402
    __all__,
    validate_playback_admission_error, validate_playback_command,
    validate_playback_command_result,
)
from jukebox.contracts.v1 import ContractValidationError  # noqa: E402


VALIDATORS = {
    "validate_playback_command": validate_playback_command,
    "validate_playback_command_result": validate_playback_command_result,
    "validate_playback_admission_error": validate_playback_admission_error,
}


class PlaybackContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads((ROOT / "test/contracts/fixtures/playback_v1.json").read_text(encoding="utf-8"))

    def test_shared_fixture(self):
        self.assertEqual(set(self.fixture), {"fixtureVersion", "cases"})
        self.assertIs(type(self.fixture["fixtureVersion"]), int)
        self.assertEqual(self.fixture["fixtureVersion"], 1)
        self.assertIsInstance(self.fixture["cases"], list)
        self.assertTrue(self.fixture["cases"])
        names = set()
        for case in self.fixture["cases"]:
            self.assertIsInstance(case, dict)
            self.assertTrue(isinstance(case.get("name"), str) and case["name"])
            self.assertNotIn(case["name"], names)
            names.add(case["name"])
            self.assertIn(case.get("validator"), VALIDATORS)
            self.assertIn(set(case), ({"name", "validator", "input", "expected"},
                                      {"name", "validator", "input", "error"}))
        for case in self.fixture["cases"]:
            with self.subTest(case=case["name"]):
                validator = VALIDATORS[case["validator"]]
                if "expected" in case:
                    self.assertEqual(validator(case["input"]), case["expected"])
                else:
                    with self.assertRaises(ContractValidationError) as caught:
                        validator(case["input"])
                    self.assertEqual(caught.exception.error, case["error"])

    def test_command_numeric_and_closed_shape_boundaries(self):
        base = {"contractVersion": 1, "commandId": "c", "action": "PLAYBACK_START",
                "queueId": "q", "expectedQueueRevision": 9007199254740991, "entryId": "e"}
        self.assertEqual(validate_playback_command(base)["expectedQueueRevision"], 9007199254740991)
        for bad in (True, 1.0, "1", None, 9007199254740992, -1):
            with self.subTest(revision=bad), self.assertRaises(ContractValidationError):
                validate_playback_command({**base, "expectedQueueRevision": bad})
        for version in (True, 1.0, "1", None):
            with self.subTest(version=version), self.assertRaises(ContractValidationError) as caught:
                validate_playback_command({**base, "contractVersion": version})
            self.assertEqual(caught.exception.field, "document.contractVersion")
        with self.assertRaises(ContractValidationError) as caught:
            validate_playback_command({**base, "contractVersion": 2})
        self.assertEqual(caught.exception.code, "UNSUPPORTED_VERSION")

    def test_token_bounds_and_alphabet(self):
        base = {"contractVersion": 1, "commandId": "c", "action": "PLAYBACK_STOP"}
        self.assertEqual(validate_playback_command({**base, "commandId": "a" * 128})["commandId"], "a" * 128)
        for token in ("", "a" * 129, "bad space", "ümlaut"):
            with self.subTest(token=token), self.assertRaises(ContractValidationError):
                validate_playback_command({**base, "commandId": token})

    def test_defensive_nested_copies(self):
        case = next(c for c in self.fixture["cases"] if c["name"] == "accepted start")
        original = copy.deepcopy(case["input"])
        result = validate_playback_command_result(case["input"])
        result["result"]["selection"]["entry"]["mediaRef"]["libraryId"] = "changed"
        result["result"]["selection"]["entry"]["title"] = "changed"
        self.assertEqual(case["input"], original)

    def test_calendar_and_result_arm_validation(self):
        accepted = next(c["input"] for c in self.fixture["cases"] if c["name"] == "accepted start")
        for stamp in ("0000-01-01T00:00:00.000Z", "2024-02-30T00:00:00.000Z",
                      "2024-01-01T24:00:00.000Z", "2024-01-01T00:00:60.000Z",
                      "2024-01-01T00:00:00Z", "2024-01-01T00:00:00.00Z",
                      "2024-01-01T00:00:00.000+00:00"):
            with self.subTest(stamp=stamp), self.assertRaises(ContractValidationError):
                body = copy.deepcopy(accepted)
                body["result"]["acceptedAt"] = stamp
                validate_playback_command_result(body)
        rejected_with_result = {"contractVersion": 1, "commandId": "c", "action": "PLAYBACK_STOP",
                                "status": "REJECTED", "error": accepted["result"], "result": None}
        with self.assertRaises(ContractValidationError):
            validate_playback_command_result(rejected_with_result)

    def test_unhashable_enum_inputs_are_contract_errors(self):
        with self.assertRaises(ContractValidationError) as caught:
            validate_playback_admission_error({"code": [], "message": "x", "retryable": False,
                                               "operation": "PLAYBACK_ADMIT", "details": {}})
        self.assertEqual(caught.exception.field, "error.code")
        with self.assertRaises(ContractValidationError) as caught:
            validate_playback_command_result({"contractVersion": 1, "commandId": "c",
                                              "action": "PLAYBACK_STOP", "status": [], "error": {}})
        self.assertEqual(caught.exception.field, "commandResult.status")

    def test_declared_api_is_exact(self):
        self.assertEqual(__all__, ("validate_playback_command", "validate_playback_command_result",
                                   "validate_playback_admission_error"))

    def test_python_only_integer_cross_products(self):
        command = next(c["input"] for c in self.fixture["cases"] if c["name"] == "start command")
        accepted = next(c["input"] for c in self.fixture["cases"] if c["name"] == "accepted start")
        for value in (0, 9007199254740991):
            # Zero and the inclusive upper bound are valid at both numeric locations.
            validate_playback_command({**command, "expectedQueueRevision": value})
        for value in (-1, 1.0, "1", None, True, 9007199254740992):
            for field in ("expectedQueueRevision",):
                with self.subTest(field=field, value=value), self.assertRaises(ContractValidationError):
                    validate_playback_command({**command, field: value})
        for value in (1.0, "1", None, True, 9007199254740992):
            with self.subTest(queue_revision=value), self.assertRaises(ContractValidationError):
                body = copy.deepcopy(accepted)
                body["result"]["selection"]["queueRevision"] = value
                validate_playback_command_result(body)
        for value in (-1, 9007199254740992):
            with self.subTest(sequence=value), self.assertRaises(ContractValidationError):
                body = copy.deepcopy(accepted)
                body["result"]["intentSequence"] = value
                validate_playback_command_result(body)

    def test_command_keys_are_closed(self):
        command = next(c["input"] for c in self.fixture["cases"] if c["name"] == "start command")
        stop = next(c["input"] for c in self.fixture["cases"] if c["name"] == "stop command")
        for validator, mapping, label in ((validate_playback_command, command, "command"),
                                          (validate_playback_command, stop, "stop")):
            for key in mapping:
                altered = dict(mapping)
                altered.pop(key)
                with self.subTest(document=label, missing=key), self.assertRaises(ContractValidationError):
                    validator(altered)
            with self.subTest(document=label, extra=True), self.assertRaises(ContractValidationError):
                validator({**mapping, "unexpected": 1})

    def test_result_and_selection_keys_are_closed(self):
        accepted = next(c["input"] for c in self.fixture["cases"] if c["name"] == "accepted start")
        rejected = next(c["input"] for c in self.fixture["cases"] if c["name"] == "rejected stop")
        for key in accepted:
            altered = dict(accepted)
            altered.pop(key)
            with self.subTest(result_missing=key), self.assertRaises(ContractValidationError):
                validate_playback_command_result(altered)
        for key in rejected:
            altered = dict(rejected)
            altered.pop(key)
            with self.subTest(rejected_missing=key), self.assertRaises(ContractValidationError):
                validate_playback_command_result(altered)
        for mapping, label in ((accepted, "accepted-result"), (rejected, "rejected-result")):
            with self.subTest(result_extra=label), self.assertRaises(ContractValidationError):
                validate_playback_command_result({**mapping, "unexpected": 1})
        for key in accepted["result"]:
            altered = copy.deepcopy(accepted)
            altered["result"].pop(key)
            with self.subTest(body_missing=key), self.assertRaises(ContractValidationError):
                validate_playback_command_result(altered)
        for key in accepted["result"]["selection"]:
            altered = copy.deepcopy(accepted)
            altered["result"]["selection"].pop(key)
            with self.subTest(selection_missing=key), self.assertRaises(ContractValidationError):
                validate_playback_command_result(altered)
        for mapping, label in ((accepted["result"], "body"),
                               (accepted["result"]["selection"], "selection"),
                               (accepted["result"]["selection"]["entry"], "entry"),
                               (accepted["result"]["selection"]["entry"]["mediaRef"], "mediaRef")):
            altered = copy.deepcopy(accepted)
            target = altered["result"] if label == "body" else altered["result"]["selection"]
            if label in {"entry", "mediaRef"}:
                target = target["entry"] if label == "entry" else target["entry"]["mediaRef"]
            target["unexpected"] = 1
            with self.subTest(extra=label), self.assertRaises(ContractValidationError):
                validate_playback_command_result(altered)

    def test_admission_error_keys_and_capability_boundaries(self):
        capability = next(c["input"] for c in self.fixture["cases"] if c["name"] == "capability error")
        for key in capability:
            altered = dict(capability)
            altered.pop(key)
            with self.subTest(error_field_missing=key), self.assertRaises(ContractValidationError):
                validate_playback_admission_error(altered)
        with self.assertRaises(ContractValidationError):
            validate_playback_admission_error({**capability, "unexpected": 1})
        details = capability["details"]
        for key in details:
            with self.subTest(capability_detail_missing=key), self.assertRaises(ContractValidationError):
                validate_playback_admission_error({**capability, "details": {}})
        with self.assertRaises(ContractValidationError):
            validate_playback_admission_error({**capability, "details": {**details, "unexpected": 1}})
        for value in (None, [], "bad"):
            with self.subTest(details=value), self.assertRaises(ContractValidationError):
                validate_playback_admission_error({**capability, "details": value})
        for wrong in (True, None):
            with self.subTest(retryable=wrong), self.assertRaises(ContractValidationError):
                validate_playback_admission_error({**capability, "retryable": wrong})
        for code in ("COMMAND_NOT_FOUND", "POSITION_OUT_OF_RANGE", "ACTIVE_ENTRY_REQUIRES_CONTROLLER"):
            with self.subTest(excluded_code=code), self.assertRaises(ContractValidationError):
                validate_playback_admission_error({**capability, "code": code})

    def test_error_outputs_are_defensive_copies(self):
        conflict = {"code": "REVISION_CONFLICT", "message": "Conflict.", "retryable": False,
                    "operation": "PLAYBACK_ADMIT", "details": {"conflicts": [
                        {"objectType": "queue", "objectId": "q1", "expectedRevision": 0,
                         "actualRevision": 1}]}}
        original = copy.deepcopy(conflict)
        parsed = validate_playback_admission_error(conflict)
        parsed["details"]["conflicts"][0]["objectId"] = "mutated"
        self.assertEqual(conflict, original)
        capability = next(c["input"] for c in self.fixture["cases"] if c["name"] == "capability error")
        original = copy.deepcopy(capability)
        parsed = validate_playback_admission_error(capability)
        parsed["details"]["capability"] = "mutated"
        self.assertEqual(capability, original)

    def test_timestamp_python_boundary_cross_products(self):
        accepted = next(c["input"] for c in self.fixture["cases"] if c["name"] == "accepted start")
        for stamp in ("0000-01-01T00:00:00.000Z", "1900-02-29T00:00:00.000Z",
                      "2000-01-01T24:00:00.000Z", "2000-01-01T00:60:00.000Z",
                      "2000-01-01T00:00:60.000Z", "2000-01-01T00:00:00.00Z",
                      "2000-01-01T00:00:00.000z", "2000-01-01 00:00:00.000Z",
                      "2000-01-01T00:00:00.000+00:00", "2000-01-01T00:00:00.000Zx"):
            with self.subTest(stamp=stamp), self.assertRaises(ContractValidationError):
                body = copy.deepcopy(accepted)
                body["result"]["acceptedAt"] = stamp
                validate_playback_command_result(body)


if __name__ == "__main__":
    unittest.main()

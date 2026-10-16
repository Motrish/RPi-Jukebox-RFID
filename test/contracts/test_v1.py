import copy
import json
from pathlib import Path
import sys
import unittest

STAGE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STAGE_ROOT / "src" / "jukebox"))

from jukebox.contracts.v1 import (  # noqa: E402
    ContractValidationError,
    validate_command,
    validate_command_result,
    validate_error,
    validate_identifier,
    validate_media_ref,
    validate_playlist_entry,
    validate_playlist_snapshot,
    validate_queue_entry,
    validate_queue_snapshot,
)


FIXTURES = json.loads(
    (Path(__file__).parent / "fixtures" / "v1.json").read_text(encoding="utf-8-sig")
)
MIXED_ITEMS = [
    {"mediaRef": {"kind": "LOCAL", "libraryId": "lib_synthetic_001"}, "title": "Local story"},
    {"mediaRef": {"kind": "SPOTIFY", "uri": "spotify:track:0123456789ABCDEFGHIJKL"}, "title": "Spotify track"},
]


def command(action, **fields):
    return {"contractVersion": 1, "commandId": "cmd_synthetic_" + action.lower(), "action": action, **fields}


def valid_commands():
    return [
        command("PLAYLIST_CREATE", name="Mix", items=MIXED_ITEMS),
        command("PLAYLIST_RENAME", playlistId="pl_1", expectedRevision=0, name="Mix"),
        command("PLAYLIST_APPEND", playlistId="pl_1", expectedRevision=0, items=MIXED_ITEMS),
        command("PLAYLIST_REMOVE", playlistId="pl_1", expectedRevision=0, entryId="pe_1"),
        command("PLAYLIST_MOVE", playlistId="pl_1", expectedRevision=0, entryId="pe_1", toPosition=0),
        command("PLAYLIST_DELETE", playlistId="pl_1", expectedRevision=0),
        command("QUEUE_CREATE", items=MIXED_ITEMS),
        command("QUEUE_LOAD_PLAYLIST", queueId="q_1", expectedQueueRevision=0, playlistId="pl_1", expectedPlaylistRevision=0),
        command("QUEUE_APPEND", queueId="q_1", expectedRevision=0, items=MIXED_ITEMS),
        command("QUEUE_REMOVE", queueId="q_1", expectedRevision=0, entryId="qe_1"),
        command("QUEUE_MOVE", queueId="q_1", expectedRevision=0, entryId="qe_1", toPosition=0),
        command("QUEUE_SET_MODES", queueId="q_1", expectedRevision=0, repeatMode="ALL", shuffleMode="ON"),
        command("QUEUE_SET_CURRENT", queueId="q_1", expectedRevision=0, entryId=None),
        command("QUEUE_SAVE_NEW_PLAYLIST", queueId="q_1", expectedQueueRevision=0, name="Saved"),
        command("QUEUE_SAVE_PLAYLIST", queueId="q_1", expectedQueueRevision=0, playlistId="pl_1", expectedPlaylistRevision=0),
    ]


class ContractV1Tests(unittest.TestCase):
    def assert_contract_error(self, value, validator, *, code="VALIDATION_ERROR"):
        with self.assertRaises(ContractValidationError) as caught:
            validator(value)
        self.assertEqual(code, caught.exception.code)
        self.assertEqual(code, caught.exception.error["code"])
        self.assertIsInstance(caught.exception.error["details"], dict)

    def test_mixed_playlist_keeps_repeated_media_as_distinct_entries(self):
        original = copy.deepcopy(FIXTURES["valid_playlist"])
        value = validate_playlist_snapshot(original)

        self.assertIsInstance(value, dict)
        self.assertEqual(["LOCAL", "SPOTIFY", "LOCAL"], [e["mediaRef"]["kind"] for e in value["entries"]])
        self.assertEqual(3, len({e["entryId"] for e in value["entries"]}))
        self.assertEqual(value["entries"][0]["mediaRef"], value["entries"][2]["mediaRef"])
        self.assertNotEqual(value["entries"][0]["entryId"], value["entries"][2]["entryId"])
        self.assertEqual(original, FIXTURES["valid_playlist"])

    def test_mixed_queue_and_current_selection_validate(self):
        value = validate_queue_snapshot(FIXTURES["valid_queue"])

        self.assertEqual("qe_synthetic_002", value["currentEntryId"])
        self.assertEqual([0, 1, 2], [e["position"] for e in value["entries"]])
        self.assertEqual("pe_synthetic_003", value["entries"][2]["sourceEntryId"])

    def test_empty_unattributed_queue_accepts_explicit_nulls(self):
        value = validate_queue_snapshot(FIXTURES["valid_empty_queue"])

        self.assertEqual([], value["entries"])
        self.assertIsNone(value["sourcePlaylistId"])
        self.assertIsNone(value["sourcePlaylistRevision"])
        self.assertIsNone(value["currentEntryId"])

    def test_unknown_media_kind_is_rejected_with_stable_code(self):
        self.assert_contract_error({"kind": "M3U", "uri": "https://example.invalid/a"}, validate_media_ref)

    def test_media_ref_is_closed_and_requires_kind_specific_field(self):
        self.assert_contract_error({"kind": "LOCAL"}, validate_media_ref)
        self.assert_contract_error(
            {"kind": "LOCAL", "libraryId": "lib_1", "uri": "spotify:track:0123456789ABCDEFGHIJKL"},
            validate_media_ref,
        )

    def test_spotify_ref_requires_canonical_22_character_track_id(self):
        invalid_url = {"kind": "SPOTIFY", "uri": "https://open.spotify.com/track/0123456789ABCDEFGHIJKL"}
        invalid_uri = {"kind": "SPOTIFY", "uri": "spotify:track:short"}
        self.assert_contract_error(invalid_url, validate_media_ref)
        self.assert_contract_error(invalid_uri, validate_media_ref)

    def test_entry_validators_return_detached_json_copies(self):
        entry = {"entryId": "pe_1", "mediaRef": {"kind": "LOCAL", "libraryId": "lib_1"}, "title": "One", "position": 0}
        parsed = validate_playlist_entry(entry)
        queue_entry = {**entry, "sourceEntryId": None}
        parsed_queue = validate_queue_entry(queue_entry)
        entry["mediaRef"]["libraryId"] = "changed"
        self.assertEqual("lib_1", parsed["mediaRef"]["libraryId"])
        self.assertEqual("pe_1", parsed_queue["entryId"])

    def test_snapshot_rejects_missing_or_additional_fields(self):
        missing = copy.deepcopy(FIXTURES["valid_playlist"])
        del missing["name"]
        extra = copy.deepcopy(FIXTURES["valid_playlist"])
        extra["surprise"] = True

        self.assert_contract_error(missing, validate_playlist_snapshot)
        self.assert_contract_error(extra, validate_playlist_snapshot)

    def test_revision_requires_nonnegative_json_integer_not_bool_float_or_null(self):
        for invalid in (True, 1.0, -1, None, "3"):
            with self.subTest(revision=invalid):
                value = copy.deepcopy(FIXTURES["valid_playlist"])
                value["revision"] = invalid
                self.assert_contract_error(value, validate_playlist_snapshot)

    def test_unsupported_version_has_distinct_stable_code(self):
        value = copy.deepcopy(FIXTURES["valid_playlist"])
        value["contractVersion"] = 2
        self.assert_contract_error(value, validate_playlist_snapshot, code="UNSUPPORTED_VERSION")

    def test_wrong_version_types_are_validation_errors(self):
        for invalid in (True, 1.0, None, "1"):
            with self.subTest(version=invalid):
                value = copy.deepcopy(FIXTURES["valid_playlist"])
                value["contractVersion"] = invalid
                self.assert_contract_error(value, validate_playlist_snapshot)

    def test_entries_require_unique_ids_and_matching_contiguous_positions(self):
        duplicate = copy.deepcopy(FIXTURES["valid_playlist"])
        duplicate["entries"][1]["entryId"] = duplicate["entries"][0]["entryId"]
        gap = copy.deepcopy(FIXTURES["valid_playlist"])
        gap["entries"][1]["position"] = 5

        self.assert_contract_error(duplicate, validate_playlist_snapshot)
        self.assert_contract_error(gap, validate_playlist_snapshot)

    def test_queue_rejects_bad_selection_and_unpaired_source_revision(self):
        selection = copy.deepcopy(FIXTURES["valid_queue"])
        selection["currentEntryId"] = "qe_missing"
        source = copy.deepcopy(FIXTURES["valid_queue"])
        source["sourcePlaylistId"] = None

        self.assert_contract_error(selection, validate_queue_snapshot)
        self.assert_contract_error(source, validate_queue_snapshot)

    def test_queue_entry_requires_source_id_field_even_when_null(self):
        value = copy.deepcopy(FIXTURES["valid_queue"])
        del value["entries"][0]["sourceEntryId"]
        self.assert_contract_error(value, validate_queue_snapshot)

    def test_all_fifteen_write_command_shapes_are_accepted_and_copied(self):
        for source in valid_commands():
            with self.subTest(action=source["action"]):
                value = validate_command(source)
                self.assertEqual(source, value)
                self.assertIsNot(source, value)
                if "items" in source:
                    self.assertIsNot(source["items"], value["items"])

    def test_command_rejects_missing_unknown_fields_and_unknown_actions(self):
        valid = valid_commands()[0]
        missing = {key: value for key, value in valid.items() if key != "items"}
        extra = {**valid, "filePath": "unsafe"}
        unknown = {**valid, "action": "RAW_RPC"}

        self.assert_contract_error(missing, validate_command)
        self.assert_contract_error(extra, validate_command)
        self.assert_contract_error(unknown, validate_command)

    def test_command_rejects_boolean_and_float_revisions(self):
        for invalid in (True, 0.0):
            value = valid_commands()[1]
            value["expectedRevision"] = invalid
            self.assert_contract_error(value, validate_command)

    def test_command_result_has_exact_result_or_error_arm(self):
        result = {
            "contractVersion": 1,
            "commandId": "cmd_synthetic_playlist_create",
            "action": "PLAYLIST_CREATE",
            "status": "APPLIED",
            "result": {"playlist": FIXTURES["valid_playlist"]},
        }
        self.assertEqual(result, validate_command_result(result))
        bad = {**result, "error": {}}
        self.assert_contract_error(bad, validate_command_result)

    def test_error_validator_checks_stable_code_retryability_and_exact_fields(self):
        error = {
            "code": "VALIDATION_ERROR",
            "message": "Correct the playlist name.",
            "retryable": False,
            "operation": "PLAYLIST_CREATE",
            "details": {"field": "name", "reason": "invalid_name"},
        }
        self.assertEqual(error, validate_error(error))
        wrong_retry = {**error, "retryable": True}
        extra = {**error, "traceback": "private"}
        self.assert_contract_error(wrong_retry, validate_error)
        self.assert_contract_error(extra, validate_error)

    def test_limit_error_details_are_valid_error_details(self):
        oversized = [{"mediaRef": MIXED_ITEMS[0]["mediaRef"], "title": "Synthetic"}] * 10001
        with self.assertRaises(ContractValidationError) as caught:
            validate_command(command("PLAYLIST_CREATE", name="Large", items=oversized))
        error = caught.exception.error
        self.assertEqual("LIMIT_EXCEEDED", error["code"])
        self.assertEqual({"field": "command.items", "limit": 10000}, error["details"])
        self.assertEqual(error, validate_error(error))

    def test_result_rejects_unhashable_status_values_as_contract_errors(self):
        base = {
            "contractVersion": 1,
            "commandId": "cmd_synthetic_playlist_create",
            "action": "PLAYLIST_CREATE",
            "status": "APPLIED",
            "result": {"playlist": FIXTURES["valid_playlist"]},
        }
        for status in ([], {}):
            with self.subTest(status=status):
                self.assert_contract_error({**base, "status": status}, validate_command_result)

    def test_public_identifier_validator_uses_the_contract_token_rule(self):
        self.assertEqual("library_01", validate_identifier("library_01"))
        for invalid in ("", "a/b", "ümlaut", "x" * 129):
            with self.subTest(identifier=invalid):
                self.assert_contract_error(invalid, validate_identifier)


if __name__ == "__main__":
    unittest.main()

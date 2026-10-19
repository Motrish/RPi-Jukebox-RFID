"""Focused contract tests for raw MPD status normalization."""

import copy
import unittest

from components.local_provider.adapter import _normalise_mpd_status
from jukebox.contracts import ContractValidationError


def raw_status(**overrides):
    value = {
        "state": "play",
        "playlistlength": "1",
        "repeat": "0",
        "random": "0",
        "single": "0",
        "consume": "0",
    }
    value.update(overrides)
    return value


class TestMPDStatusNormalization(unittest.TestCase):
    def test_converts_protocol_strings_to_closed_status(self):
        raw = raw_status(
            songid="0012", elapsed="1.25", duration="3.5",
            volume="80", audio="44100:16:2",
        )

        result = _normalise_mpd_status(raw)

        self.assertEqual(result, {
            "state": "play", "songid": "0012", "playlistlength": 1,
            "repeat": 0, "random": 0, "single": 0, "consume": 0,
            "elapsed": 1.25, "duration": 3.5, "hasError": False,
        })

    def test_missing_optional_fields_become_none_or_false(self):
        result = _normalise_mpd_status(raw_status())

        self.assertIsNone(result["songid"])
        self.assertIsNone(result["elapsed"])
        self.assertIsNone(result["duration"])
        self.assertIs(result["hasError"], False)

    def test_present_none_optional_fields_are_invalid(self):
        for field in ("songid", "elapsed", "duration", "error"):
            with self.subTest(field=field):
                with self.assertRaises(ContractValidationError):
                    _normalise_mpd_status(raw_status(**{field: None}))

    def test_song_id_remains_a_string(self):
        result = _normalise_mpd_status(raw_status(songid="0007"))
        self.assertEqual(result["songid"], "0007")
        self.assertIsInstance(result["songid"], str)

    def test_error_is_reduced_to_boolean_without_exposing_text(self):
        secret = "private decoder detail"
        result = _normalise_mpd_status(raw_status(error=secret))

        self.assertIs(result["hasError"], True)
        self.assertNotIn("error", result)
        self.assertNotIn(secret, repr(result))

    def test_empty_error_means_no_error(self):
        self.assertIs(
            _normalise_mpd_status(raw_status(error=""))["hasError"], False,
        )

    def test_non_string_error_is_invalid(self):
        for value in (0, False, [], {}):
            with self.subTest(value=value):
                with self.assertRaises(ContractValidationError):
                    _normalise_mpd_status(raw_status(error=value))

    def test_oneshot_is_preserved_for_single_and_consume(self):
        result = _normalise_mpd_status(raw_status(
            single="oneshot", consume="oneshot",
        ))
        self.assertEqual(result["single"], "oneshot")
        self.assertEqual(result["consume"], "oneshot")

    def test_missing_required_fields_are_invalid(self):
        for field in (
            "state", "playlistlength", "repeat", "random", "single", "consume",
        ):
            with self.subTest(field=field):
                raw = raw_status()
                del raw[field]
                with self.assertRaises(ContractValidationError):
                    _normalise_mpd_status(raw)

    def test_required_fields_must_be_strings(self):
        for field in (
            "state", "playlistlength", "repeat", "random", "single", "consume",
        ):
            with self.subTest(field=field):
                with self.assertRaises(ContractValidationError):
                    _normalise_mpd_status(raw_status(**{field: 1}))

    def test_invalid_state_and_option_values_are_rejected(self):
        cases = (
            {"state": "idle"}, {"repeat": "2"}, {"random": "-1"},
            {"single": "2"}, {"consume": "2"},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                with self.assertRaises(ContractValidationError):
                    _normalise_mpd_status(raw_status(**overrides))

    def test_integer_fields_use_strict_ascii_decimal_grammar(self):
        for field in ("playlistlength", "repeat", "random", "single", "consume"):
            for value in ("+1", "-1", " 1", "1 ", "1.0", "Ã¯Â¼â€˜", "\n1", "1\n"):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ContractValidationError):
                        _normalise_mpd_status(raw_status(**{field: value}))

    def test_times_use_strict_decimal_seconds_and_valid_range(self):
        for field in ("elapsed", "duration"):
            for value in ("+1", "-1", ".5", "1.", "1e2", " 1", "Ã¯Â¼â€˜", "inf", "\n1", "1\n"):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ContractValidationError):
                        _normalise_mpd_status(raw_status(**{field: value}))
        with self.assertRaises(ContractValidationError):
            _normalise_mpd_status(raw_status(duration="999999999999999999999999999999"))

    def test_unknown_keys_are_ignored_and_time_is_not_elapsed_fallback(self):
        result = _normalise_mpd_status(raw_status(
            time="9.5", future_field="ignored",
        ))
        self.assertIsNone(result["elapsed"])
        self.assertEqual(
            set(result),
            {
                "state", "songid", "playlistlength", "repeat", "random",
                "single", "consume", "elapsed", "duration", "hasError",
            },
        )

    def test_input_mapping_is_not_mutated(self):
        raw = raw_status(elapsed="2.75", error="decoder error")
        before = copy.deepcopy(raw)

        _normalise_mpd_status(raw)

        self.assertEqual(raw, before)

    def test_non_mapping_inputs_are_rejected_as_contract_errors(self):
        for raw in (None, [], "state", 1, True):
            with self.subTest(raw_type=type(raw).__name__):
                with self.assertRaises(ContractValidationError):
                    _normalise_mpd_status(raw)

    def test_required_fields_reject_none_and_boolean_values(self):
        for field in ("state", "playlistlength", "repeat", "random", "single", "consume"):
            for value in (None, True):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ContractValidationError):
                        _normalise_mpd_status(raw_status(**{field: value}))

    def test_present_optional_fields_require_protocol_strings(self):
        for field in ("songid", "elapsed", "duration"):
            with self.subTest(field=field):
                with self.assertRaises(ContractValidationError):
                    _normalise_mpd_status(raw_status(**{field: 1}))

    def test_song_id_rejects_non_ascii_digits_and_other_text(self):
        for value in ("abc123", "Ã¯Â¼â€˜Ã¯Â¼â€™Ã¯Â¼â€œ", "12\n"):
            with self.subTest(value=value):
                with self.assertRaises(ContractValidationError):
                    _normalise_mpd_status(raw_status(songid=value))

    def test_playlist_length_accepts_leading_zero_decimal(self):
        result = _normalise_mpd_status(raw_status(playlistlength="0001"))
        self.assertEqual(result["playlistlength"], 1)

    def test_option_fields_require_exact_zero_or_one_spellings(self):
        for field in ("repeat", "random", "single", "consume"):
            for value in ("00", "01"):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ContractValidationError):
                        _normalise_mpd_status(raw_status(**{field: value}))

    def test_unhashable_option_values_are_contract_errors(self):
        for field in ("repeat", "random", "single", "consume"):
            for value in ([], {}):
                with self.subTest(field=field, value_type=type(value).__name__):
                    with self.assertRaises(ContractValidationError):
                        _normalise_mpd_status(raw_status(**{field: value}))

    def test_error_whitespace_is_true_and_invalid_state_text_is_not_exposed(self):
        self.assertIs(
            _normalise_mpd_status(raw_status(error=" \t"))["hasError"], True,
        )
        marker = "private-state-marker"
        with self.assertRaises(ContractValidationError) as raised:
            _normalise_mpd_status(raw_status(state=marker))
        self.assertNotIn(marker, str(raised.exception))

    def test_long_decimal_time_that_overflows_float_is_rejected(self):
        with self.assertRaises(ContractValidationError):
            _normalise_mpd_status(raw_status(elapsed="9" * 400))


if __name__ == "__main__":
    unittest.main()

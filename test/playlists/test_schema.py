import json
from pathlib import Path

import pytest

from components.playlists.schema import get_all_schemas, get_schema, validate_playlist, validate_queue
from jukebox.contracts.v1 import ContractValidationError


FIXTURES = json.loads(
    (Path(__file__).parents[1] / "contracts" / "fixtures" / "v1.json").read_text(encoding="utf-8-sig")
)


def test_get_schema_resolves_openapi_component():
    assert get_schema("Playlist") == get_all_schemas()["Playlist"]


def test_get_all_schemas_returns_independent_mapping():
    schemas = get_all_schemas()
    schemas["Playlist"]["properties"].clear()
    assert get_all_schemas()["Playlist"]["properties"]


def test_get_schema_returns_nested_copy():
    schema = get_schema("Playlist")
    schema["properties"].clear()
    assert get_schema("Playlist")["properties"]


@pytest.mark.parametrize("fixture", ["valid_playlist"])
def test_validate_playlist_delegates_to_v1_contract(fixture):
    assert validate_playlist(FIXTURES[fixture]) is None


@pytest.mark.parametrize("fixture", ["valid_queue", "valid_empty_queue"])
def test_validate_queue_delegates_to_v1_contract(fixture):
    assert validate_queue(FIXTURES[fixture]) is None


def test_validate_playlist_propagates_contract_error():
    with pytest.raises(ContractValidationError):
        validate_playlist({})


def test_validate_queue_propagates_contract_error():
    with pytest.raises(ContractValidationError):
        validate_queue({})

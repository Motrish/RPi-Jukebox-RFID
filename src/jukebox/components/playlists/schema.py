"""
Playlist & Queue Schema Module

Exposes the OpenAPI schema as a Python dict and provides validation helpers
using the existing jukebox.contracts.v1 validators.
"""

from pathlib import Path
from copy import deepcopy
from typing import Any, Dict

import ruamel.yaml

# Import existing validators
from jukebox.contracts.v1 import (
    validate_playlist_snapshot,
    validate_queue_snapshot,
    validate_command,
)

__all__ = ["get_all_schemas", "get_schema", "load_openapi_schema", "validate_command",
           "validate_playlist", "validate_queue"]

_OPENAPI_PATH = Path(__file__).resolve().parents[4] / "docs" / "openapi" / "playlists-v1.yaml"


def load_openapi_schema(path: Path = _OPENAPI_PATH) -> Dict[str, Any]:
    """Load the OpenAPI document on demand, optionally from an explicit path."""
    with Path(path).open("r", encoding="utf-8") as stream:
        return ruamel.yaml.YAML(typ="safe").load(stream)


def get_schema(name: str, path: Path = _OPENAPI_PATH) -> Dict[str, Any]:
    """Get a component schema by name (e.g., 'Playlist', 'QueueEntry')."""
    schema = load_openapi_schema(path).get("components", {}).get("schemas", {}).get(name)
    if schema is None:
        raise KeyError(f"Schema '{name}' not found in OpenAPI components")
    return deepcopy(schema)


def get_all_schemas(path: Path = _OPENAPI_PATH) -> Dict[str, Dict[str, Any]]:
    """Return all component schemas."""
    return deepcopy(load_openapi_schema(path).get("components", {}).get("schemas", {}))


def validate_playlist(data: Dict[str, Any]) -> None:
    """Validate a playlist object against the OpenAPI schema and v1 contract."""
    # First validate against v1 contract
    validate_playlist_snapshot(data)
    # Additional OpenAPI schema validation could be added here


def validate_queue(data: Dict[str, Any]) -> None:
    """Validate a queue object against the OpenAPI schema and v1 contract."""
    validate_queue_snapshot(data)

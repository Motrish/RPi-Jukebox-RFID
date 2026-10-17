"""Authenticated, read-only HTTP access to the local media catalog."""

from .server import make_read_authorizer, make_server

__all__ = ["make_read_authorizer", "make_server"]

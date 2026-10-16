"""Transport-free local playback provider primitives."""

from .adapter import LocalProvider, SessionFailure

__all__ = ["LocalProvider", "SessionFailure"]

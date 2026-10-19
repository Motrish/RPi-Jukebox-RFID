"""Internal playback-session coordination primitives."""
from .execution_gate import ExecutionGate, GateStateError

__all__ = ["ExecutionGate", "GateStateError"]

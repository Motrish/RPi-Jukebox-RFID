"""Internal bridge from durable playlist commands to local playback."""

import math
import json
import threading
import time

from jukebox.contracts import ContractValidationError

from .execution_gate import GateStateError
from .local_playback_service import LocalPlaybackService


class DurableDispatch:
    """Admit one command and advance its local service synchronously."""

    def __init__(self, *, store, provider, boot_id, monotonic=None):
        self._store = store
        self._clock = time.monotonic if monotonic is None else monotonic
        options = {"provider": provider, "boot_id": boot_id}
        if monotonic is not None:
            options["monotonic"] = monotonic
        self._service = LocalPlaybackService(**options)
        self._lock = threading.Lock()
        self._completed = {}

    def dispatch(self, command, *, deadline):
        self._validate_deadline(deadline)
        if not self._lock.acquire(blocking=False):
            raise GateStateError("BUSY")
        try:
            admitted = self._store.admit_playback(command)
            command_id = command.get("commandId") if type(command) is dict else None
            if type(command_id) is str and command_id in self._completed:
                previous_admission, previous_result = self._completed[command_id]
                if _canonical(admitted) == _canonical(previous_admission):
                    return previous_result
            if admitted.get("status") != "ACCEPTED":
                return admitted
            action = admitted["action"]
            if action == "PLAYBACK_START":
                entry = admitted["result"]["selection"]["entry"]
                # commandId→executionId correlation is deferred to C4b.
                self._service.request_start(entry["entryId"], entry["mediaRef"])
            elif action == "PLAYBACK_STOP":
                self._service.request_stop()
            else:
                return admitted
            # Propagates provider failure verbatim; C4b will publish a contract-shaped result.
            state = self._service.run_once(deadline=deadline)
            if state.get("lastFailure") is not None:
                result = {"admission": admitted, "playback": state,
                          "failure": state["lastFailure"]}
            else:
                result = {"admission": admitted, "playback": state,
                          "gate": state["gate"]}
            if type(command_id) is str:
                self._completed[command_id] = (admitted, result)
            return result
        finally:
            self._lock.release()

    def _validate_deadline(self, deadline):
        if type(deadline) not in {int, float} or not _finite(deadline):
            raise ContractValidationError("deadline", "invalid_deadline")
        try:
            now = self._clock()
        except Exception:
            raise GateStateError("CLOCK_UNAVAILABLE") from None
        if type(now) not in {int, float} or not _finite(now):
            raise GateStateError("CLOCK_UNAVAILABLE")
        if float(deadline) <= float(now):
            raise GateStateError("DEADLINE_EXPIRED")


def _finite(value):
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

"""Internal bridge from durable playlist commands to local playback."""

import math
import json
import threading
import time

from jukebox.contracts import ContractValidationError

from .execution_gate import GateStateError
from .local_playback_service import LocalPlaybackService


class DurableDispatch:
    """Admit a command and advance playback once.

    ``admission.action`` is the requested command; ``operation`` is what ran.
    They can differ after a provider crash, when the step performs cleanup STOP.
    A successful ``operation=None`` means this step did no work because it was
    already satisfied. For executed steps exactly one of ``gate``/``failure`` is
    set; rejected or unknown admissions set neither.
    ``executionId`` identifies the gate owner (lease/generation), persists until
    release, and is reused by STOP receipt matching; STOP creates no new ID.
    """

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
                return _wrapper(admitted)
            action = admitted["action"]
            before = self._service.snapshot()
            if action == "PLAYBACK_START":
                entry = admitted["result"]["selection"]["entry"]
                # Receipt-level correlation (commandId inside receipt identity) belongs to the HTTP layer.
                intent_id = self._service.request_start(entry["entryId"], entry["mediaRef"])
            elif action == "PLAYBACK_STOP":
                intent_id = self._service.request_stop()
            else:
                return _wrapper(admitted)
            pre_run = self._service.snapshot()
            # Propagates provider failure verbatim; C4b will publish a contract-shaped result.
            state = self._service.run_once(deadline=deadline)
            operation, work_ran = _execution_outcome(before, pre_run, state, intent_id)
            failure = state.get("lastFailure") if work_ran else None
            if failure is not None:
                result = _wrapper(admitted, state, operation, failure=failure,
                                  intent_id=intent_id,
                                  execution_id=_execution_id(pre_run, state))
            else:
                result = _wrapper(admitted, state, operation, gate=state["gate"],
                                  intent_id=intent_id,
                                  execution_id=_execution_id(pre_run, state))
            if type(command_id) is str:
                self._completed[command_id] = (dict(admitted), result)
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


def _wrapper(admission, playback=None, operation=None, *, gate=None, failure=None,
             intent_id=None, execution_id=None):
    return {"admission": admission, "playback": playback, "operation": operation,
            "gate": gate, "failure": failure, "intentId": intent_id,
            "executionId": execution_id}


def _execution_id(pre_run, after):
    owner = after["gate"]["owner"] or pre_run["gate"]["owner"]
    return None if owner is None else owner["executionId"]


def _execution_outcome(before, pre_run, after, intent_id):
    owner = pre_run["gate"]["owner"]
    after_owner = after["gate"]["owner"]
    owner_trip = None
    if before["gate"]["owner"] == owner:
        owner_trip = ("START" if owner is None and after_owner is not None else
                      "STOP" if owner is not None and after_owner is None else None)
    pending = pre_run.get("pending")
    pending_matches = (pending is not None and pending.get("intentId") == intent_id)
    start_pending_consumed = (pending_matches and pending.get("operation") == "START"
                              and after.get("pending") is None)
    start_work = owner_trip == "START" or start_pending_consumed
    stop_work = (
        owner is not None
        and (pre_run["gate"]["cleanupRequired"]
             or (pending_matches and pending.get("operation") == "STOP"))
    )
    # request_start disables retry after STOP_UNCONFIRMED; the service's earlier
    # failed-stop latch then returns without attempting cleanup, despite owner state.
    pre_failure = pre_run.get("lastFailure")
    latched_start = (pending_matches and pending.get("operation") == "START"
                     and pre_failure is not None
                     and pre_failure.get("operation") == "STOP"
                     and pre_failure.get("code") == "STOP_UNCONFIRMED")
    if latched_start:
        stop_work = False
    work_ran = bool(start_work or stop_work)
    operation = owner_trip
    if operation is None and work_ran:
        failure = after.get("lastFailure")
        if failure is not None:
            operation = failure.get("operation")
    return operation, work_ran

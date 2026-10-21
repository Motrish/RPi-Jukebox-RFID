"""Run one short, private LocalProvider playback probe against MPD."""

import json
import time
import uuid
from pathlib import Path

from components.local_provider.adapter import LocalProvider
from components.local_provider.mpd_session import MpdSession, TrackedMPDClient


HOST = "127.0.0.1"
PORT = 6601
MUSIC_ROOT = Path.home() / "phoniebox-hardwaretest" / "mpd-p01" / "music"
LIBRARY_ID = "hardware_probe_lokal"
MEDIA_REF = {"kind": "LOCAL", "libraryId": LIBRARY_ID}
CAPABILITIES = {
    "canPause": True,
    "canResume": True,
    "canSeek": True,
    "canConfirmStop": True,
    "canIdentifyNaturalEnd": False,
}
OPERATIONS = {"START", "PAUSE", "RESUME", "SEEK", "STOP"}


def _resolve_track(music_root):
    root = Path(music_root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Authorized music root is not a directory.")
    track = root / "lokal.mp3"
    resolved = track.resolve(strict=True)
    if resolved.parent != root or not resolved.is_file():
        raise ValueError("Authorized track must be a regular file directly inside the music root.")
    return root


def _identity():
    return {
        "bootId": "probe_" + uuid.uuid4().hex,
        "generation": 0,
        "executionId": "probe_" + uuid.uuid4().hex,
        "entryId": "probe_" + uuid.uuid4().hex,
    }


def _safe_error(operation, error):
    return {
        "provider": "LOCAL",
        "operation": operation,
        "outcome": "FAILED",
        "error": {"type": type(error).__name__},
    }


def _resolver(library_id):
    if library_id != LIBRARY_ID:
        return None
    return {"libraryId": library_id, "mpdReference": "lokal.mp3"}


def _actions(provider, lease):
    return (("START", 2), ("PAUSE", 1), ("RESUME", 2), ("SEEK", 1), ("STOP", None))


def _perform(provider, lease, operation, deadline):
    if operation == "START":
        return provider.start(MEDIA_REF, lease=lease, deadline=deadline)
    if operation == "PAUSE":
        return provider.pause(lease=lease, deadline=deadline)
    if operation == "RESUME":
        return provider.resume(lease=lease, deadline=deadline)
    if operation == "SEEK":
        return provider.seek(0, lease=lease, deadline=deadline)
    return provider.stop(lease=lease, deadline=deadline)


def _run_actions(provider, lease, clock, wait, publish, state):
    for operation, delay in _actions(provider, lease):
        if operation == "START":
            state["started"] = True
        receipt = _perform(provider, lease, operation, clock() + 5.0)
        publish(receipt)
        if receipt.get("outcome") != "CONFIRMED":
            return
        if operation == "STOP":
            state["stopped"] = True
        elif delay is not None:
            wait(delay)


def _safe_publish(publish, receipt):
    try:
        publish(receipt)
    except BaseException:
        pass


def run_probe(*, music_root=MUSIC_ROOT, port=PORT, wait=time.sleep, emit=None,
              monotonic=time.monotonic):
    """Run one bounded private probe; injection points are for isolated tests."""
    _resolve_track(music_root)
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Invalid private MPD port.")
    if not callable(wait) or not callable(monotonic):
        raise ValueError("Clock and wait hooks must be callable.")
    if emit is None:

        def emit(receipt):
            print(json.dumps(receipt, sort_keys=True), flush=True)

    identity = _identity()
    lease = {
        "identity": identity,
        "guard": lambda operation, current: current == identity and operation in OPERATIONS,
    }
    client = TrackedMPDClient()
    receipts = []
    state = {"started": False, "stopped": False}
    primary_error = None

    def publish(receipt):
        receipts.append(receipt)
        emit(receipt)

    try:
        client.timeout = 2
        client.idletimeout = None
        client.connect(HOST, port)
        client.timeout = None
        session = MpdSession(client, monotonic=monotonic)
        with session.transaction(monotonic() + 5.0) as context:
            status = context.status()
        if status["state"] != "stop" or status["hasError"]:
            raise RuntimeError("Private MPD preflight requires stopped state and no error.")

        provider = LocalProvider(
            session=session,
            resolver=_resolver,
            monotonic=monotonic,
            capabilities=CAPABILITIES,
        )
        _run_actions(provider, lease, monotonic, wait, publish, state)
    except BaseException as error:
        primary_error = error
    finally:
        try:
            if state["started"] and not state["stopped"] and "provider" in locals():
                try:
                    cleanup = provider.stop(lease=lease, deadline=monotonic() + 5.0)
                    _safe_publish(publish, cleanup)
                except BaseException as error:
                    _safe_publish(publish, _safe_error("CLEANUP_STOP", error))
        finally:
            try:
                client.disconnect()
            except BaseException as error:
                _safe_publish(publish, _safe_error("DISCONNECT", error))
    if primary_error is not None:
        raise primary_error
    return receipts


def main():
    receipts = run_probe()
    expected = ["START", "PAUSE", "RESUME", "SEEK", "STOP"]
    successful = [item.get("operation") for item in receipts] == expected
    successful = successful and all(item.get("outcome") == "CONFIRMED" for item in receipts)
    return 0 if successful else 1


if __name__ == "__main__":
    raise SystemExit(main())

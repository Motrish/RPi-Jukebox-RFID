"""Argument- und Konfigurationsvertragschecks fuer den neuen runtime.dispatch."""

import importlib.util
import json
import math
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from components.local_provider import LocalProvider
from components.playback_session.durable_dispatch import DurableDispatch
from components.playback_session.execution_gate import GateStateError
from components.playback_session.local_playback_service import LocalPlaybackService
from components.playback_session.runtime import LocalPlaybackRuntime
from components.playlists.store import PlaylistStore
from jukebox.contracts import ContractValidationError

_STAGE = Path(__file__).resolve().parents[2]
_ADAPTER_FILE = _STAGE / "test" / "local_provider" / "test_adapter.py"
_ADAPTER_SPEC = importlib.util.spec_from_file_location("dispatch_args_adapter_support", _ADAPTER_FILE)
_ADAPTER_MODULE = importlib.util.module_from_spec(_ADAPTER_SPEC)
_ADAPTER_SPEC.loader.exec_module(_ADAPTER_MODULE)
with (_STAGE / "test" / "local_provider" / "fixtures" / "v1.json").open(encoding="utf-8") as _fixture_stream:
    _PROVIDER_FIXTURE = json.load(_fixture_stream)

_LOCAL_MEDIA = {"kind": "LOCAL", "libraryId": "synthetic_track_01"}


class _ManualTimer:
    """Deterministischer Ersatz fuer den Timer-Thread (kein Hintergrundlauf)."""

    def __init__(self):
        self.triggers = 0
        self.timer_thread = None
        self.running = True

    def is_alive(self):
        return self.running

    def trigger(self):
        self.triggers += 1

    def cancel(self):
        self.running = False


class RuntimeDispatchArgumentTests(unittest.TestCase):
    """Public dispatch-Vertrage ohne Rennen: Argumente, Phasen, Store-Nachweis."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store_path = Path(self.temp.name) / "dispatch-args.sqlite3"

    def ready_runtime(self, *, configured):
        """READY-Runtime mit echtem Service/Provider; Bootstrap analog Unit-Tests gefakt."""
        clock = _ADAPTER_MODULE.FakeClock()
        session = _ADAPTER_MODULE.FakeSession(_PROVIDER_FIXTURE["initialStatus"])
        session.clock = clock
        provider = LocalProvider(session=session,
                                 resolver=lambda _library_id: _PROVIDER_FIXTURE["resolvedMedia"],
                                 monotonic=clock,
                                 capabilities=_PROVIDER_FIXTURE["capabilities"])
        service = LocalPlaybackService(provider=provider, boot_id="args_boot", monotonic=clock)
        runtime = LocalPlaybackRuntime(database_path="/tmp/library.sqlite",
                                       library_root="/srv/audio",
                                       credential_path="/etc/mpd.secret",
                                       monotonic=clock,
                                       playlist_database_path=(
                                           "/tmp/args-playlists.sqlite3" if configured else None))
        runtime._phase = "READY"
        runtime._ready = True
        runtime._boot_id = "args_boot"
        runtime._service = service
        runtime._timer = _ManualTimer()
        if configured:
            # Der deklarierte Pfad wird erst im echten Bootstrap geoeffnet; der
            # hier verdrahtete Store liegt auf echtem Temp-SQLite.
            store = PlaylistStore(str(self.store_path))
            runtime._durable_dispatch = DurableDispatch(
                store=store, service=service, boot_id="args_boot", monotonic=clock,
                before_execute=runtime._dispatch_may_execute,
                publish_intent=runtime._publish_dispatch_intent)
        return runtime, session, clock

    def command_log_count(self):
        with closing(sqlite3.connect(str(self.store_path))) as conn:
            return conn.execute("SELECT COUNT(*) FROM command_log").fetchone()[0]

    def stop_command(self, command_id):
        return {"contractVersion": 1, "commandId": command_id, "action": "PLAYBACK_STOP"}

    def test_default_runtime_without_store_path_is_not_configured(self):
        runtime, session, _clock = self.ready_runtime(configured=False)
        with self.assertRaises(GateStateError) as raised:
            runtime.dispatch(self.stop_command("args_default_stop"), deadline=20.0)
        self.assertEqual("NOT_CONFIGURED", raised.exception.code)
        self.assertEqual([], session.events)

    def test_playlist_database_path_requires_absolute_posix_form(self):
        with self.assertRaises(ContractValidationError) as raised:
            LocalPlaybackRuntime(database_path="/tmp/library.sqlite", library_root="/srv/audio",
                                 credential_path="/etc/mpd.secret",
                                 playlist_database_path="relative.sqlite")
        self.assertEqual("playlist_database_path", raised.exception.field)
        self.assertEqual("invalid_path", raised.exception.reason)

    def test_invalid_deadline_types_are_rejected_before_store_admission(self):
        runtime, session, _clock = self.ready_runtime(configured=True)
        for deadline in (True, math.inf, math.nan, "later", None):
            with self.subTest(deadline=deadline):
                with self.assertRaises(ContractValidationError) as raised:
                    runtime.dispatch(self.stop_command("args_bad_deadline"), deadline=deadline)
                self.assertEqual(("deadline", "invalid_deadline"),
                                 (raised.exception.field, raised.exception.reason))
        self.assertEqual(0, self.command_log_count())
        self.assertEqual([], session.events)

    def test_expired_deadline_is_rejected_and_dispatch_stays_available(self):
        runtime, session, clock = self.ready_runtime(configured=True)
        with self.assertRaises(GateStateError) as raised:
            runtime.dispatch(self.stop_command("args_expired_stop"), deadline=clock.value)
        self.assertEqual("DEADLINE_EXPIRED", raised.exception.code)
        self.assertEqual(0, self.command_log_count())
        self.assertEqual([], session.events)
        # Der abgewiesene Aufruf darf den Driver nicht kleben: Folge-STOP laeuft durch.
        result = runtime.dispatch(self.stop_command("args_after_expired"), deadline=clock.value + 5.0)
        self.assertEqual("ACCEPTED", result["admission"]["status"])
        self.assertEqual(1, self.command_log_count())

    def test_malformed_commands_are_rejected_without_provider_effects(self):
        runtime, session, _clock = self.ready_runtime(configured=True)
        malformed = (None, "stop", {}, {"commandId": 123},
                     {"contractVersion": 1, "commandId": "args_c1", "action": "PAUSE"},
                     {"contractVersion": 1, "commandId": "args_c2", "action": "PLAYBACK_START"})
        for command in malformed:
            with self.subTest(command=command):
                with self.assertRaises(ContractValidationError):
                    runtime.dispatch(command, deadline=20.0)
        self.assertEqual(0, self.command_log_count())
        self.assertEqual([], session.events)

    def test_valid_stop_command_is_admitted_without_provider_effects(self):
        runtime, session, _clock = self.ready_runtime(configured=True)
        result = runtime.dispatch(self.stop_command("args_stop_ok"), deadline=20.0)
        self.assertEqual("ACCEPTED", result["admission"]["status"])
        self.assertEqual("PLAYBACK_STOP", result["admission"]["action"])
        self.assertIsNone(result["operation"])
        self.assertIsNotNone(result["gate"])
        # Verbindliche BASE-Korrelation: intentId ist der publizierte
        # Request-Intent, auch wenn kein Schritt ausgefuehrt wurde.
        # (executionId bleibt None ohne ausgefuehrten Schritt.)
        self.assertIsNotNone(result["intentId"])
        self.assertEqual([], session.events)
        with closing(sqlite3.connect(str(self.store_path))) as conn:
            row = conn.execute(
                "SELECT result_json FROM command_log WHERE command_id = ?",
                ("args_stop_ok",)).fetchone()
        self.assertIsNotNone(row)
        self.assertIn('"status":"ACCEPTED"', row[0].replace(" ", ""))

    def test_valid_start_command_executes_exactly_one_provider_start(self):
        runtime, session, clock = self.ready_runtime(configured=True)
        store = runtime._durable_dispatch._store
        queue = store.execute({"contractVersion": 1, "commandId": "args_make_queue",
                               "action": "QUEUE_CREATE",
                               "items": [{"mediaRef": _LOCAL_MEDIA, "title": "A"}]})
        queue_snapshot = queue["result"]["queue"]
        command = {"contractVersion": 1, "commandId": "args_start_ok", "action": "PLAYBACK_START",
                   "queueId": queue_snapshot["queueId"],
                   "expectedQueueRevision": queue_snapshot["revision"],
                   "entryId": queue_snapshot["entries"][0]["entryId"]}
        result = runtime.dispatch(command, deadline=clock.value + 10.0)
        self.assertEqual("ACCEPTED", result["admission"]["status"])
        self.assertEqual("START", result["operation"])
        self.assertIsNone(result["failure"])
        self.assertEqual(command["entryId"], result["gate"]["owner"]["entryId"])
        self.assertEqual(result["executionId"], result["gate"]["owner"]["executionId"])
        self.assertEqual(1, sum(event[0] == "playid" for event in session.events))
        self.assertEqual(0, sum(event[0] == "stop" for event in session.events))


if __name__ == "__main__":
    unittest.main()

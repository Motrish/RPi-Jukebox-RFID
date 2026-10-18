"""Single-step worker tests using only temporary journals and trusted fakes."""

import os
import copy
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import unittest
from unittest.mock import patch

STAGE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STAGE_ROOT))

from installation.websetup.jobs import JobError, JobStore  # noqa: E402
from installation.websetup import worker  # noqa: E402


CONFIG = {
    "audioOutput": "SYSTEM_DEFAULT",
    "rfidEnabled": True,
    "pisugarEnabled": False,
}
STEPS = ("CHECK_SYSTEM", "CONFIGURE_AUDIO", "VERIFY_INSTALLATION")


class FakeHandler:
    def __init__(self, observation="APPLIED", apply_error=None, mutate=False):
        self.observation = observation
        self.apply_error = apply_error
        self.mutate = mutate
        self.applied = []
        self.observed = []
        self.received_configs = []

    def apply(self, config):
        self.received_configs.append(config)
        self.applied.append(copy.deepcopy(config))
        if self.mutate:
            config["audioOutput"] = "changed"
        if self.apply_error:
            raise self.apply_error

    def observe(self, config):
        self.received_configs.append(config)
        self.observed.append(copy.deepcopy(config))
        if self.mutate:
            config["rfidEnabled"] = False
        return self.observation


def handlers_for(handler):
    return {step: handler for step in STEPS}


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary.name) / "jobs.sqlite3"
        self.store = JobStore(self.database)

    def tearDown(self):
        self.temporary.cleanup()

    def assert_worker_error(self, code, callback):
        with self.assertRaises(worker.WorkerError) as raised:
            callback()
        self.assertEqual(raised.exception.code, code)
        self.assertNotIn(str(self.database), str(raised.exception))
        self.assertNotIn(str(self.database), repr(raised.exception))

    def make_worker(self, handler):
        return worker.Worker(self.database, handlers_for(handler))

    def test_constructor_is_inert_and_rejects_bad_arguments_and_handler_mapping(self):
        handler = FakeHandler()
        source = handlers_for(handler)
        instance = worker.Worker(self.database, source)
        source.clear()
        self.assertTrue(self.database.exists())
        self.assertFalse(Path(str(self.database) + ".worker.lock").exists())
        self.assertIsNone(self.store.active())
        self.assert_worker_error("INVALID_REQUEST", lambda: worker.Worker(":memory:", handlers_for(handler)))
        self.assert_worker_error("INVALID_REQUEST", lambda: worker.Worker(
            Path(":memory:"), handlers_for(handler)))
        self.assert_worker_error("INVALID_REQUEST", lambda: worker.Worker(b"db", handlers_for(handler)))
        self.assert_worker_error("WORKER_UNAVAILABLE", lambda: worker.Worker(
            self.database.parent / "missing.sqlite3", handlers_for(handler)))
        self.assert_worker_error("INVALID_REQUEST", lambda: worker.Worker(self.database, {}))
        self.assert_worker_error("INVALID_REQUEST", lambda: worker.Worker(
            self.database, dict(handlers_for(handler), EXTRA=handler)))
        hardlink = Path(self.temporary.name) / "jobs-hardlink.sqlite3"
        try:
            os.link(str(self.database), str(hardlink))
        except (OSError, NotImplementedError):
            pass
        else:
            self.assert_worker_error("WORKER_UNAVAILABLE", lambda: worker.Worker(
                hardlink, handlers_for(handler)))
        symlink = Path(self.temporary.name) / "jobs-symlink.sqlite3"
        try:
            os.symlink(str(self.database), str(symlink))
        except (OSError, NotImplementedError):
            pass
        else:
            self.assert_worker_error("WORKER_UNAVAILABLE", lambda: worker.Worker(
                symlink, handlers_for(handler)))
        self.assertIsInstance(instance, worker.Worker)

    @unittest.skipUnless(os.name == "posix", "worker execution and flock are validated in Linux CI")
    def test_worker_does_not_bootstrap_empty_or_unrelated_database_files(self):
        handler = FakeHandler()
        empty_file = Path(self.temporary.name) / "empty.sqlite3"
        empty_file.write_bytes(b"")
        before = empty_file.read_bytes()
        with self.assertRaises(worker.WorkerError) as raised:
            worker.Worker(empty_file, handlers_for(handler)).run_once()
        self.assertEqual(raised.exception.code, "WORKER_UNAVAILABLE")
        self.assertEqual(empty_file.read_bytes(), before)

        unrelated = Path(self.temporary.name) / "unrelated.sqlite3"
        connection = sqlite3.connect(str(unrelated))
        connection.execute("CREATE TABLE unrelated(value TEXT)")
        connection.execute("INSERT INTO unrelated VALUES ('preserve')")
        connection.commit()
        connection.close()
        before = unrelated.read_bytes()
        with self.assertRaises(worker.WorkerError) as raised:
            worker.Worker(unrelated, handlers_for(handler)).run_once()
        self.assertEqual(raised.exception.code, "WORKER_UNAVAILABLE")
        self.assertEqual(unrelated.read_bytes(), before)
        self.assertEqual(handler.applied, [])

    @unittest.skipUnless(os.name == "posix", "worker execution and flock are validated in Linux CI")
    def test_same_worker_instance_is_not_reentrant_and_lease_file_is_persistent(self):
        self.store.submit("same-process-lease", CONFIG)
        entered = threading.Event()
        release = threading.Event()
        errors = []

        class BlockingHandler(FakeHandler):
            def apply(self, config):
                self.applied.append(config)
                entered.set()
                if not release.wait(10):
                    raise RuntimeError("test timeout")

        handler = BlockingHandler()
        instance = self.make_worker(handler)

        def run():
            try:
                instance.run_once()
            except Exception as error:
                errors.append(error)

        thread = threading.Thread(target=run)
        thread.start()
        try:
            self.assertTrue(entered.wait(10), "worker did not reach apply")
            running = self.store.active()
            self.assertEqual(running["status"], "RUNNING")
            self.assert_worker_error("WORKER_BUSY", instance.run_once)
            self.assertEqual(self.store.get(running["jobId"]), running)
        finally:
            release.set()
            thread.join(timeout=15)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertTrue(Path(str(self.database) + ".worker.lock").is_file())
        self.assertEqual(len(handler.applied), 1)

    @unittest.skipUnless(os.name == "posix", "worker execution and flock are validated in Linux CI")
    def test_kill_after_intent_before_effect_fails_from_observation_without_reapply(self):
        queued = self.store.submit("intent-before-effect", CONFIG)
        entered = Path(self.temporary.name) / "entered.marker"
        effect = Path(self.temporary.name) / "effect.count"
        child_code = r'''import pathlib, sys, time
sys.path.insert(0, sys.argv[1])
from installation.websetup.worker import Worker
from installation.websetup.jobs import JobStore
steps = ("CHECK_SYSTEM", "CONFIGURE_AUDIO", "VERIFY_INSTALLATION")
db, entered, effect = sys.argv[2:]
class Handler:
    def apply(self, config):
        current = JobStore(db).active()
        assert current["status"] == "RUNNING" and current["stepId"] == steps[0]
        pathlib.Path(entered).write_text("ready", encoding="utf-8")
        while True: time.sleep(0.02)
    def observe(self, config):
        path = pathlib.Path(effect)
        return "APPLIED" if path.exists() and path.read_text(encoding="utf-8") == "1" else "NOT_APPLIED"
h = Handler()
Worker(db, {step:h for step in steps}).run_once()
'''
        process = subprocess.Popen(
            [sys.executable, "-B", "-c", child_code, str(STAGE_ROOT), str(self.database),
             str(entered), str(effect)],
            cwd=str(STAGE_ROOT), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            deadline = time.monotonic() + 10
            running = None
            while time.monotonic() < deadline:
                running = self.store.active()
                if running is not None and running["status"] == "RUNNING":
                    break
                if process.poll() is not None:
                    self.fail("lease child exited before intent was persisted")
                time.sleep(0.02)
            self.assertIsNotNone(running)
            self.assertEqual(running["status"], "RUNNING")
            deadline = time.monotonic() + 10
            while not entered.exists() and time.monotonic() < deadline:
                if process.poll() is not None:
                    self.fail("lease child exited before effect boundary")
                time.sleep(0.02)
            self.assertTrue(entered.exists(), "child did not verify persisted intent")
            process.kill()
            process.wait(timeout=5)

            class MarkerObserver(FakeHandler):
                def observe(self, config):
                    self.received_configs.append(config)
                    self.observed.append(copy.deepcopy(config))
                    exists = effect.exists() and effect.read_text(encoding="utf-8") == "1"
                    return "APPLIED" if exists else "NOT_APPLIED"

                def apply(self, config):
                    self.received_configs.append(config)
                    count = int(effect.read_text(encoding="utf-8")) if effect.exists() else 0
                    effect.write_text(str(count + 1), encoding="utf-8")
                    self.applied.append(copy.deepcopy(config))

            observer = MarkerObserver()
            failed = self.make_worker(observer).run_once()
            self.assertEqual(failed["status"], "FAILED")
            self.assertEqual(failed["error"], {"code": "OBSERVATION_FAILED"})
            self.assertEqual(observer.applied, [])
            self.assertEqual(observer.observed, [CONFIG])
            self.assertFalse(effect.exists())
            self.assertEqual(self.store.get(queued["jobId"]), failed)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            process.communicate(timeout=5)

    @unittest.skipUnless(os.name == "posix", "worker execution and flock are validated in Linux CI")
    def test_corrupt_snapshot_never_reaches_handler(self):
        queued = self.store.submit("corrupt-active", CONFIG)
        connection = sqlite3.connect(str(self.database))
        try:
            connection.execute("UPDATE jobs SET config_json = '{}' WHERE job_id = ?",
                               (queued["jobId"],))
            connection.commit()
        finally:
            connection.close()
        handler = FakeHandler()
        self.assert_worker_error("WORKER_UNAVAILABLE", lambda: self.make_worker(handler).run_once())
        self.assertEqual(handler.applied, [])
        self.assertEqual(handler.observed, [])

    @unittest.skipUnless(os.name == "posix", "worker execution and flock are validated in Linux CI")
    def test_handler_joberror_is_observed_but_store_joberror_propagates(self):
        self.store.submit("handler-joberror", CONFIG)
        handler = FakeHandler()

        def joberror_apply(config):
            raise JobError("STORE_UNAVAILABLE")

        handler.apply = joberror_apply
        confirmed = self.make_worker(handler).run_once()
        self.assertEqual(confirmed["appliedSteps"], [{"stepId": STEPS[0], "diagnostic": "CONFIRMED"}])
        self.assertEqual(handler.observed, [CONFIG])

        with tempfile.TemporaryDirectory() as second_temporary:
            database = Path(second_temporary) / "store-error.sqlite3"
            JobStore(database).submit("store-joberror", CONFIG)
            handler = FakeHandler()
            original_store = worker.JobStore

            def store_then_add_failure(path):
                store = original_store(path)
                connection = sqlite3.connect(str(path))
                try:
                    connection.execute(
                        "CREATE TRIGGER reject_worker_update BEFORE UPDATE ON jobs "
                        "BEGIN SELECT RAISE(FAIL, 'private store detail'); END"
                    )
                    connection.commit()
                finally:
                    connection.close()
                return store

            instance = worker.Worker(database, handlers_for(handler))
            with patch.object(worker, "JobStore", side_effect=store_then_add_failure):
                try:
                    instance.run_once()
                except JobError as error:
                    caught = error
                    formatted = "".join(traceback.format_exception(
                        type(error), error, error.__traceback__))
                else:
                    self.fail("genuine journal write failure was not propagated")
            self.assertEqual(caught.code, "STORE_UNAVAILABLE")
            self.assertNotIn("private store detail", formatted)
            self.assertTrue(caught.__suppress_context__)
            self.assertEqual(handler.applied, [])

            cleanup = sqlite3.connect(str(database))
            try:
                cleanup.execute("DROP TRIGGER reject_worker_update")
                cleanup.commit()
            finally:
                cleanup.close()
            self.assertEqual(instance.run_once()["status"], "QUEUED")
            self.assertEqual(handler.applied, [CONFIG])

    @unittest.skipUnless(os.name == "posix", "worker execution and flock are validated in Linux CI")
    def test_lease_fstat_failure_is_redacted_closes_fd_and_releases_lease(self):
        self.store.submit("lease-fstat-failure", CONFIG)
        handler = FakeHandler()
        instance = self.make_worker(handler)
        original_fstat = os.fstat
        opened = []

        def fail_lease_fstat(descriptor):
            if not opened:
                opened.append(descriptor)
                raise OSError("private fstat detail")
            return original_fstat(descriptor)

        with patch.object(worker.os, "fstat", side_effect=fail_lease_fstat):
            try:
                instance.run_once()
            except worker.WorkerError as error:
                caught = error
                formatted = "".join(traceback.format_exception(
                    type(error), error, error.__traceback__))
            else:
                self.fail("lease fstat failure was not translated")
        self.assertEqual(caught.code, "WORKER_UNAVAILABLE")
        self.assertNotIn("private fstat detail", formatted)
        self.assertEqual(len(opened), 1)
        with self.assertRaises(OSError):
            os.fstat(opened[0])
        self.assertEqual(self.store.active()["status"], "QUEUED")
        self.assertEqual(instance.run_once()["status"], "QUEUED")
        self.assertEqual(handler.applied, [CONFIG])

    @unittest.skipUnless(os.name == "posix", "worker execution and flock are validated in Linux CI")
    def test_baseexception_keeps_intent_and_releases_lease(self):
        self.store.submit("baseexception", CONFIG)

        class InterruptingHandler(FakeHandler):
            def apply(self, config):
                self.applied.append(config)
                raise KeyboardInterrupt()

        handler = InterruptingHandler(observation="APPLIED")
        instance = self.make_worker(handler)
        with self.assertRaises(KeyboardInterrupt):
            instance.run_once()
        running = self.store.active()
        self.assertEqual(running["status"], "RUNNING")
        recovered = instance.run_once()
        self.assertEqual(recovered["status"], "QUEUED")
        self.assertEqual(handler.applied, [CONFIG])
        self.assertEqual(handler.observed, [CONFIG])
        current = recovered
        for step in STEPS[1:]:
            current = self.store.begin_step(current["jobId"], current["revision"], step)
            current = self.store.confirm_step(current["jobId"], current["revision"], step)

        self.store.submit("baseexception-during-acquire", CONFIG)
        ordinary = FakeHandler()
        instance = self.make_worker(ordinary)
        with patch.object(worker.fcntl, "flock", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                instance.run_once()
        self.assertEqual(self.store.active()["status"], "QUEUED")
        self.assertEqual(instance.run_once()["status"], "QUEUED")
        self.assertEqual(len(ordinary.applied), 1)

    @unittest.skipUnless(os.name == "posix", "worker execution and flock are validated in Linux CI")
    def test_database_or_lease_path_rebinding_stops_before_observation(self):
        for target in ("database", "lease"):
            with self.subTest(target=target):
                with tempfile.TemporaryDirectory() as case_directory:
                    database = Path(case_directory) / "jobs.sqlite3"
                    store = JobStore(database)
                    queued = store.submit("rebind-" + target, CONFIG)
                    handler = FakeHandler()

                    def replace_path(config):
                        handler.applied.append(copy.deepcopy(config))
                        path = (database if target == "database"
                                else Path(str(database) + ".worker.lock"))
                        moved = Path(str(path) + ".moved")
                        os.replace(str(path), str(moved))
                        path.write_bytes(b"replacement")

                    handler.apply = replace_path
                    instance = worker.Worker(database, handlers_for(handler))
                    self.assert_worker_error("WORKER_UNAVAILABLE", instance.run_once)
                    self.assertEqual(handler.observed, [])
                    persisted_database = (Path(str(database) + ".moved")
                                          if target == "database" else database)
                    interrupted = JobStore(persisted_database).active()
                    self.assertEqual((interrupted["status"], interrupted["stepId"]),
                                     ("RUNNING", STEPS[0]))
                    if target == "database":
                        database.unlink()
                        Path(str(database) + ".moved").replace(database)
                    else:
                        lock_path = Path(str(database) + ".worker.lock")
                        moved_lock = Path(str(lock_path) + ".moved")
                        lock_path.unlink()
                        moved_lock.replace(lock_path)
                    recovery_handler = FakeHandler(observation="UNKNOWN")
                    recovered = worker.Worker(
                        database, handlers_for(recovery_handler)).run_once()
                    self.assertEqual(recovered["status"], "WAITING_USER")
                    self.assertEqual(recovered["stepId"], STEPS[0])
                    self.assertEqual(handler.applied, [CONFIG])
                    self.assertEqual(handler.observed, [])
                    self.assertEqual(recovery_handler.applied, [])
                    self.assertEqual(len(recovery_handler.observed), 1)
                    self.assertEqual(store.get(queued["jobId"])["status"], "WAITING_USER")

    @unittest.skipUnless(os.name == "posix", "worker execution and flock are validated in Linux CI")
    def test_single_step_apply_then_independent_observation_confirms_once(self):
        queued = self.store.submit("single-step", CONFIG)
        handler = FakeHandler(mutate=True)
        instance = self.make_worker(handler)
        first = instance.run_once()
        self.assertEqual(first["status"], "QUEUED")
        self.assertEqual(first["revision"], 2)
        self.assertEqual(first["appliedSteps"], [{"stepId": STEPS[0], "diagnostic": "CONFIRMED"}])
        self.assertEqual(handler.applied, [CONFIG])
        self.assertEqual(handler.observed, [CONFIG])
        self.assertEqual(self.store.get(queued["jobId"]), first)
        self.assertEqual(instance.run_once()["stepId"], None)
        self.assertEqual(self.store.get(queued["jobId"])["revision"], 4)
        self.assertEqual(len(handler.applied), 2)

    @unittest.skipUnless(os.name == "posix", "worker execution and flock are validated in Linux CI")
    def test_unknown_and_observation_errors_wait_without_blind_retry(self):
        self.store.submit("unknown-result", CONFIG)
        handler = FakeHandler(observation="MAYBE")
        instance = self.make_worker(handler)
        waiting = instance.run_once()
        self.assertEqual(waiting["status"], "WAITING_USER")
        self.assertEqual(waiting["nextAction"], {"kind": "INSPECT_SYSTEM"})
        self.assertEqual(instance.run_once(), waiting)
        self.assertEqual(handler.applied, [CONFIG])
        self.assertEqual(len(handler.observed), 2)
        handler.observation = "APPLIED"
        confirmed = instance.run_once()
        self.assertEqual(confirmed["status"], "QUEUED")
        self.assertEqual(len(handler.applied), 1)
        while confirmed["status"] == "QUEUED":
            confirmed = instance.run_once()
        self.assertEqual(confirmed["status"], "SUCCEEDED")

        self.store.submit("observe-error", CONFIG)
        failing = FakeHandler()

        def fail_observation(config):
            raise RuntimeError("secret handler detail")

        failing.observe = fail_observation
        waiting = self.make_worker(failing).run_once()
        self.assertEqual(waiting["status"], "WAITING_USER")
        self.assertNotIn("secret handler detail", repr(waiting))

    @unittest.skipUnless(os.name == "posix", "worker execution and flock are validated in Linux CI")
    def test_not_applied_fails_and_apply_error_still_observes(self):
        self.store.submit("not-applied", CONFIG)
        handler = FakeHandler(observation="NOT_APPLIED", apply_error=ValueError("private"))
        failed = self.make_worker(handler).run_once()
        self.assertEqual(failed["status"], "FAILED")
        self.assertEqual(failed["error"], {"code": "STEP_FAILED"})
        self.assertEqual(len(handler.observed), 1)

    @unittest.skipUnless(os.name == "posix", "worker execution and flock are validated in Linux CI")
    def test_apply_return_is_ignored_and_waiting_never_applies(self):
        self.store.submit("apply-unknown", CONFIG)
        handler = FakeHandler(observation="UNKNOWN")
        handler.apply = lambda config: "APPLIED"
        waiting = self.make_worker(handler).run_once()
        self.assertEqual(waiting["status"], "WAITING_USER")
        self.assertEqual(self.make_worker(handler).run_once(), waiting)

    @unittest.skipUnless(os.name == "posix", "worker execution and flock are validated in Linux CI")
    def test_handler_mapping_and_configs_are_defensively_copied(self):
        self.store.submit("defensive-copy", CONFIG)
        handler = FakeHandler(mutate=True)
        mapping = handlers_for(handler)
        instance = worker.Worker(self.database, mapping)
        mapping[STEPS[0]] = object()
        result = instance.run_once()
        self.assertEqual(result["desiredConfigSummary"], CONFIG)
        self.assertEqual(handler.applied, [CONFIG])
        self.assertEqual(handler.observed, [CONFIG])
        self.assertIsNot(handler.received_configs[0], handler.received_configs[1])
        persisted_config = self.store.get(result["jobId"])["desiredConfigSummary"]
        self.assertEqual(persisted_config, CONFIG)
        self.assertIsNot(handler.received_configs[0], persisted_config)
        self.assertIsNot(handler.received_configs[1], persisted_config)

    @unittest.skipUnless(os.name == "posix", "worker execution and flock are validated in Linux CI")
    def test_queued_without_job_returns_none_and_store_errors_remain_redacted(self):
        self.assertIsNone(self.make_worker(FakeHandler()).run_once())
        self.assertIsNone(self.make_worker(FakeHandler()).run_once())

    @unittest.skipUnless(os.name == "posix", "actual flock lease proof runs in Linux CI")
    def test_process_lease_excludes_second_process_and_recovers_killed_intent(self):
        self.store.submit("lease-and-crash", CONFIG)
        marker = Path(self.temporary.name) / "effect.count"
        release = Path(self.temporary.name) / "release.marker"
        child_code = r'''import pathlib, sys, time
sys.path.insert(0, sys.argv[1])
from installation.websetup.worker import Worker
from installation.websetup.jobs import JobStore
db, marker, release = sys.argv[2:]
steps = ("CHECK_SYSTEM", "CONFIGURE_AUDIO", "VERIFY_INSTALLATION")
class Handler:
    def apply(self, value):
        current = JobStore(db).active()
        assert current["status"] == "RUNNING" and current["stepId"] == steps[0]
        path = pathlib.Path(marker)
        count = int(path.read_text(encoding="utf-8")) if path.exists() else 0
        path.write_text(str(count + 1), encoding="utf-8")
        while not pathlib.Path(release).exists(): time.sleep(0.02)
    def observe(self, value):
        path = pathlib.Path(marker)
        return "APPLIED" if path.exists() and path.read_text(encoding="utf-8") == "1" else "NOT_APPLIED"
h = Handler()
Worker(db, {step:h for step in steps}).run_once()
'''
        process = subprocess.Popen(
            [sys.executable, "-B", "-c", child_code, str(STAGE_ROOT), str(self.database),
             str(marker), str(release)],
            cwd=str(STAGE_ROOT), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline and (not marker.exists() or marker.read_text(encoding='utf-8') != '1'):
                if process.poll() is not None:
                    self.fail("lease child exited before handler marker: {}".format(process.stderr.read()))
                time.sleep(0.02)
            self.assertTrue(marker.exists(), "lease child did not record effect")
            self.assertEqual(marker.read_text(encoding="utf-8"), "1")
            before = self.store.active()
            self.assertEqual((before["status"], before["stepId"]), ("RUNNING", STEPS[0]))
            self.assert_worker_error("WORKER_BUSY", lambda: self.make_worker(FakeHandler()).run_once())
            self.assertEqual(self.store.get(before["jobId"]), before)
            process.kill()
            process.wait(timeout=5)

            class MarkerObserver(FakeHandler):
                def observe(self, config):
                    self.received_configs.append(config)
                    self.observed.append(copy.deepcopy(config))
                    return ("APPLIED" if marker.exists()
                            and marker.read_text(encoding="utf-8") == "1" else "NOT_APPLIED")

                def apply(self, config):
                    self.received_configs.append(config)
                    count = int(marker.read_text(encoding="utf-8")) if marker.exists() else 0
                    marker.write_text(str(count + 1), encoding="utf-8")
                    self.applied.append(copy.deepcopy(config))

            observer = MarkerObserver()
            recovered = self.make_worker(observer).run_once()
            self.assertEqual(recovered["status"], "QUEUED")
            self.assertEqual(recovered["appliedSteps"], [{"stepId": STEPS[0], "diagnostic": "CONFIRMED"}])
            self.assertEqual(observer.applied, [])
            self.assertEqual(observer.observed, [CONFIG])
            self.assertEqual(marker.read_text(encoding="utf-8"), "1")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()

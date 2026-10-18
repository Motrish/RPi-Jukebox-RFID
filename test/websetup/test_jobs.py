"""Durable setup-job journal tests; all work stays in temporary databases."""

import json
from pathlib import Path
import sqlite3
import sys
import subprocess
import tempfile
import threading
import unittest

STAGE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STAGE_ROOT))

from installation.websetup import jobs  # noqa: E402


CONFIG = {
    "audioOutput": "SYSTEM_DEFAULT",
    "rfidEnabled": True,
    "pisugarEnabled": False,
}
STEPS = ("CHECK_SYSTEM", "CONFIGURE_AUDIO", "VERIFY_INSTALLATION")
SNAPSHOT_FIELDS = {
    "contractVersion", "jobId", "commandId", "status", "stepId",
    "desiredConfigSummary", "appliedSteps", "revision", "createdAt",
    "updatedAt", "nextAction", "error",
}


class JobStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database = str(Path(self.temporary.name) / "jobs.sqlite3")
        self.store = jobs.JobStore(self.database)

    def tearDown(self):
        self.temporary.cleanup()

    def assert_error(self, code, callback):
        with self.assertRaises(jobs.JobError) as raised:
            callback()
        self.assertEqual(raised.exception.code, code)
        self.assertNotIn(self.database, str(raised.exception))

    def assert_snapshot(self, snapshot):
        self.assertEqual(set(snapshot), SNAPSHOT_FIELDS)
        self.assertEqual(snapshot["contractVersion"], "websetup.job.v1")
        self.assertTrue(snapshot["createdAt"].endswith("Z"))
        self.assertTrue(snapshot["updatedAt"].endswith("Z"))
        self.assertEqual(snapshot["desiredConfigSummary"], CONFIG)
        self.assertEqual(json.loads(json.dumps(snapshot)), snapshot)

    def finish_job(self, snapshot):
        current = snapshot
        for step in STEPS:
            current = self.store.begin_step(current["jobId"], current["revision"], step)
            self.assertEqual(current["status"], "RUNNING")
            self.assertEqual(current["stepId"], step)
            current = self.store.confirm_step(current["jobId"], current["revision"], step)
        return current

    def test_submit_creates_closed_json_snapshot_and_active_reads(self):
        snapshot = self.store.submit("first-command", CONFIG)
        self.assert_snapshot(snapshot)
        self.assertEqual(snapshot["status"], "QUEUED")
        self.assertIsNone(snapshot["stepId"])
        self.assertEqual(snapshot["appliedSteps"], [])
        self.assertEqual(snapshot["revision"], 0)
        self.assertEqual(snapshot["createdAt"], snapshot["updatedAt"])
        self.assertIsNone(snapshot["nextAction"])
        self.assertIsNone(snapshot["error"])
        self.assertEqual(self.store.get(snapshot["jobId"]), snapshot)
        self.assertEqual(self.store.active(), snapshot)

    def test_submit_is_idempotent_by_validated_content_and_returns_current_snapshot(self):
        snapshot = self.store.submit("same-command", CONFIG)
        progressed = self.store.begin_step(snapshot["jobId"], 0, STEPS[0])
        reordered = {
            "pisugarEnabled": False,
            "rfidEnabled": True,
            "audioOutput": "SYSTEM_DEFAULT",
        }
        replay = self.store.submit("same-command", reordered)
        self.assertEqual(replay, progressed)
        self.assertEqual(replay["revision"], 1)
        self.assert_error(
            "COMMAND_ID_REUSED",
            lambda: self.store.submit("same-command", dict(CONFIG, rfidEnabled=False)),
        )

    def test_active_job_conflict_does_not_consume_new_command_id(self):
        self.store.submit("first-command", CONFIG)
        other = dict(CONFIG, rfidEnabled=False)
        self.assert_error("JOB_CONFLICT", lambda: self.store.submit("later-command", other))
        current = self.finish_job(self.store.get(self.store.active()["jobId"]))
        self.assertEqual(current["status"], "SUCCEEDED")
        accepted = self.store.submit("later-command", other)
        self.assertEqual(accepted["status"], "QUEUED")
        self.assertEqual(accepted["revision"], 0)

    def test_begin_confirm_preserves_intent_then_records_only_observed_steps(self):
        created = self.store.submit("run-command", CONFIG)
        begun = self.store.begin_step(created["jobId"], 0, STEPS[0])
        self.assertEqual((begun["status"], begun["stepId"], begun["revision"]),
                         ("RUNNING", STEPS[0], 1))
        self.assertEqual(begun["appliedSteps"], [])
        first = self.store.confirm_step(created["jobId"], 1, STEPS[0])
        self.assertEqual(first["status"], "QUEUED")
        self.assertIsNone(first["stepId"])
        self.assertEqual(first["revision"], 2)
        self.assertEqual(first["appliedSteps"], [{"stepId": STEPS[0], "diagnostic": "CONFIRMED"}])
        second = self.store.begin_step(created["jobId"], 2, STEPS[1])
        self.assertEqual(second["stepId"], STEPS[1])
        self.assertEqual(second["revision"], 3)

    def test_stale_revision_and_invalid_transitions_do_not_mutate(self):
        queued = self.store.submit("transition-command", CONFIG)
        begun = self.store.begin_step(queued["jobId"], 0, STEPS[0])
        self.assert_error("REVISION_CONFLICT", lambda: self.store.confirm_step(
            queued["jobId"], 0, STEPS[0]))
        self.assert_error("INVALID_TRANSITION", lambda: self.store.begin_step(
            queued["jobId"], 1, STEPS[1]))
        self.assert_error("INVALID_TRANSITION", lambda: self.store.begin_step(
            queued["jobId"], 1, STEPS[0]))
        self.assertEqual(self.store.get(queued["jobId"]), begun)

    def test_fail_preserves_current_intent_and_previous_confirmations_then_releases_lock(self):
        queued = self.store.submit("failed-command", CONFIG)
        begun = self.store.begin_step(queued["jobId"], 0, STEPS[0])
        first = self.store.confirm_step(queued["jobId"], begun["revision"], STEPS[0])
        active = self.store.begin_step(first["jobId"], first["revision"], STEPS[1])
        failed = self.store.fail_step(active["jobId"], active["revision"], STEPS[1], "STEP_FAILED")
        self.assertEqual(failed["status"], "FAILED")
        self.assertEqual(failed["stepId"], STEPS[1])
        self.assertEqual(failed["appliedSteps"], first["appliedSteps"])
        self.assertEqual(failed["error"], {"code": "STEP_FAILED"})
        self.assertIsNone(failed["nextAction"])
        accepted = self.store.submit("next-command", dict(CONFIG, rfidEnabled=False))
        self.assertEqual(accepted["status"], "QUEUED")
        self.assertEqual(self.store.submit("failed-command", CONFIG), failed)

    def test_fail_requires_a_fixed_error_code_before_any_state_change(self):
        queued = self.store.submit("missing-error-command", CONFIG)
        running = self.store.begin_step(queued["jobId"], 0, STEPS[0])
        self.assert_error("INVALID_REQUEST", lambda: self.store.fail_step(
            running["jobId"], running["revision"], STEPS[0], None))
        self.assertEqual(self.store.get(running["jobId"]), running)

    def test_reconcile_interrupted_requires_explicit_call_and_never_restarts_intent(self):
        queued = self.store.submit("recover-command", CONFIG)
        begun = self.store.begin_step(queued["jobId"], 0, STEPS[0])
        reopened = jobs.JobStore(self.database)
        self.assertEqual(reopened.get(queued["jobId"]), begun)
        recovered = reopened.reconcile_interrupted()
        self.assertEqual(len(recovered), 1)
        waiting = recovered[0]
        self.assertEqual(waiting["status"], "WAITING_USER")
        self.assertEqual(waiting["stepId"], STEPS[0])
        self.assertEqual(waiting["appliedSteps"], [])
        self.assertEqual(waiting["revision"], 2)
        self.assertEqual(waiting["nextAction"], {"kind": "INSPECT_SYSTEM"})
        self.assertEqual(reopened.reconcile_interrupted(), [])
        self.assertEqual(reopened.get(queued["jobId"]), waiting)
        self.assert_error("INVALID_TRANSITION", lambda: reopened.begin_step(
            waiting["jobId"], waiting["revision"], STEPS[0]))
        confirmed = reopened.confirm_step(waiting["jobId"], waiting["revision"], STEPS[0])
        self.assertEqual(confirmed["status"], "QUEUED")
        self.assertEqual(confirmed["appliedSteps"], [{"stepId": STEPS[0], "diagnostic": "CONFIRMED"}])

    def test_wait_for_inspection_persists_only_current_running_intent(self):
        queued = self.store.submit("inspect-command", CONFIG)
        running = self.store.begin_step(queued["jobId"], 0, STEPS[0])
        waiting = self.store.wait_for_inspection(running["jobId"], running["revision"], STEPS[0])
        self.assertEqual(waiting["status"], "WAITING_USER")
        self.assertEqual(waiting["stepId"], STEPS[0])
        self.assertEqual(waiting["appliedSteps"], [])
        self.assertEqual(waiting["revision"], running["revision"] + 1)
        self.assertEqual(waiting["nextAction"], {"kind": "INSPECT_SYSTEM"})
        self.assertIsNone(waiting["error"])
        self.assert_error("INVALID_TRANSITION", lambda: self.store.wait_for_inspection(
            waiting["jobId"], waiting["revision"], STEPS[0]))
        self.assert_error("REVISION_CONFLICT", lambda: self.store.wait_for_inspection(
            running["jobId"], running["revision"], STEPS[0]))
        self.assertEqual(self.store.get(waiting["jobId"]), waiting)

    def test_wait_for_inspection_rejects_wrong_step_invalid_inputs_and_overflow_atomically(self):
        queued = self.store.submit("inspect-validation-command", CONFIG)
        running = self.store.begin_step(queued["jobId"], 0, STEPS[0])
        self.assert_error("INVALID_TRANSITION", lambda: self.store.wait_for_inspection(
            running["jobId"], running["revision"], STEPS[1]))
        self.assert_error("INVALID_REQUEST", lambda: self.store.wait_for_inspection(
            running["jobId"], True, STEPS[0]))
        self.assertEqual(self.store.get(running["jobId"]), running)
        connection = sqlite3.connect(self.database)
        try:
            connection.execute("UPDATE jobs SET revision = ? WHERE job_id = ?",
                               ((1 << 63) - 1, running["jobId"]))
            connection.commit()
        finally:
            connection.close()
        before = self.store.get(running["jobId"])
        self.assert_error("STORE_UNAVAILABLE", lambda: self.store.wait_for_inspection(
            before["jobId"], before["revision"], STEPS[0]))
        self.assertEqual(self.store.get(before["jobId"]), before)

    def test_terminal_jobs_survive_reopen_and_active_slot_is_released(self):
        queued = self.store.submit("complete-command", CONFIG)
        complete = self.finish_job(queued)
        self.assertEqual(complete["status"], "SUCCEEDED")
        self.assertEqual(complete["revision"], 6)
        self.assertEqual(len(complete["appliedSteps"]), 3)
        reopened = jobs.JobStore(self.database)
        self.assertEqual(reopened.get(complete["jobId"]), complete)
        self.assertIsNone(reopened.active())
        self.assertEqual(reopened.submit("complete-command", CONFIG), complete)

    def test_returned_snapshots_are_independent_copies(self):
        snapshot = self.store.submit("copy-command", CONFIG)
        snapshot["desiredConfigSummary"]["audioOutput"] = "tampered"
        snapshot["appliedSteps"].append({"stepId": "x", "diagnostic": "CONFIRMED"})
        current = self.store.get(snapshot["jobId"])
        self.assertEqual(current["desiredConfigSummary"], CONFIG)
        self.assertEqual(current["appliedSteps"], [])

    def test_public_inputs_are_validated_before_database_changes(self):
        invalid_configs = (
            None, {}, dict(CONFIG, extra="value"), dict(CONFIG, audioOutput="/tmp/file"),
            dict(CONFIG, rfidEnabled=1), dict(CONFIG, pisugarEnabled=None),
        )
        for config in invalid_configs:
            with self.subTest(config=config):
                self.assert_error("INVALID_REQUEST", lambda: self.store.submit("valid-id", config))
        for command_id in ("", "a" * 65, "contains space", "é"):
            with self.subTest(command_id=command_id):
                self.assert_error("INVALID_REQUEST", lambda: self.store.submit(command_id, CONFIG))
        self.assertIsNone(self.store.active())
        valid = self.store.submit("valid-id", CONFIG)
        for revision in (True, -1, "0", 1.5):
            with self.subTest(revision=revision):
                self.assert_error("INVALID_REQUEST", lambda: self.store.begin_step(
                    valid["jobId"], revision, STEPS[0]))
        self.assertEqual(self.store.get(valid["jobId"])["revision"], 0)

    def test_fixed_step_and_error_allowlists_and_missing_job_codes(self):
        self.assert_error("JOB_NOT_FOUND", lambda: self.store.get("missing-job"))
        self.assert_error("INVALID_REQUEST", lambda: self.store.get(""))
        queued = self.store.submit("allowlist-command", CONFIG)
        self.assert_error("INVALID_REQUEST", lambda: self.store.begin_step(
            queued["jobId"], 0, "RUN_ARBITRARY_COMMAND"))
        self.assert_error("INVALID_REQUEST", lambda: self.store.fail_step(
            queued["jobId"], 0, STEPS[0], "SECRET_VALUE"))
        self.assertEqual(self.store.get(queued["jobId"]), queued)

    def test_concurrent_same_command_id_creates_one_job(self):
        barrier = threading.Barrier(8)
        results = []
        errors = []

        def submit():
            try:
                local = jobs.JobStore(self.database)
                barrier.wait(timeout=5)
                results.append(local.submit("thread-command", CONFIG))
            except Exception as error:  # collected to fail in the main test thread
                errors.append(error)

        threads = [threading.Thread(target=submit) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 8)
        self.assertEqual(len({item["jobId"] for item in results}), 1)
        self.assertEqual(len({item["revision"] for item in results}), 1)

    def test_two_processes_serialize_submission_in_sqlite(self):
        child_code = (
            "import json, sys; "
            "sys.path.insert(0, sys.argv[1]); "
            "from installation.websetup import jobs; "
            "result = {'kind': 'ok', 'snapshot': jobs.JobStore(sys.argv[2]).submit("
            "sys.argv[3], json.loads(sys.argv[4]))}; "
            "sys.stdout.write(json.dumps(result, separators=(',', ':')))"
        )
        command = [
            sys.executable, "-B", "-c", child_code, str(STAGE_ROOT), self.database,
            "process-command", json.dumps(CONFIG, separators=(",", ":")),
        ]
        processes = []
        results = []
        try:
            for _index in range(2):
                processes.append(subprocess.Popen(
                    command, cwd=str(STAGE_ROOT), stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                ))
            for process in processes:
                stdout, stderr = process.communicate(timeout=15)
                self.assertEqual(process.returncode, 0, stderr)
                results.append(json.loads(stdout))
        finally:
            for process in processes:
                if process.poll() is None:
                    process.terminate()
            for process in processes:
                if process.poll() is None:
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate(timeout=5)
        self.assertEqual([result["kind"] for result in results], ["ok", "ok"])
        self.assertEqual(len({result["snapshot"]["jobId"] for result in results}), 1)
        self.assertEqual(self.store.active()["jobId"], results[0]["snapshot"]["jobId"])

    def test_different_concurrent_commands_have_one_winner_and_release_loser_id(self):
        barrier = threading.Barrier(2)
        results = []

        def submit(command_id, config):
            local = jobs.JobStore(self.database)
            barrier.wait(timeout=5)
            try:
                results.append((command_id, "ok", local.submit(command_id, config)))
            except jobs.JobError as error:
                results.append((command_id, error.code, None))

        threads = [
            threading.Thread(target=submit, args=("first-racer", CONFIG)),
            threading.Thread(target=submit, args=("second-racer", dict(CONFIG, rfidEnabled=False))),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertEqual(sorted(result[1] for result in results), ["JOB_CONFLICT", "ok"])
        loser_id = next(command_id for command_id, status, _value in results if status == "JOB_CONFLICT")
        current = self.store.active()
        self.finish_job(current)
        accepted = self.store.submit(loser_id, dict(CONFIG, rfidEnabled=False))
        self.assertEqual(accepted["status"], "QUEUED")

    def test_concurrent_same_revision_transition_has_one_winner(self):
        queued = self.store.submit("revision-race-command", CONFIG)
        barrier = threading.Barrier(2)
        results = []

        def begin():
            local = jobs.JobStore(self.database)
            barrier.wait(timeout=5)
            try:
                results.append(("ok", local.begin_step(queued["jobId"], 0, STEPS[0])))
            except jobs.JobError as error:
                results.append((error.code, None))

        threads = [threading.Thread(target=begin) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(sorted(kind for kind, _value in results), ["REVISION_CONFLICT", "ok"])
        self.assertEqual(self.store.get(queued["jobId"])["revision"], 1)

    def test_sqlite_failure_rolls_back_transition_and_is_redacted(self):
        queued = self.store.submit("rollback-command", CONFIG)
        probe = sqlite3.connect(self.database)
        try:
            tables = [row[0] for row in probe.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
        finally:
            probe.close()
        self.assertTrue(tables)
        table = "jobs"
        connection = sqlite3.connect(self.database)
        try:
            table = table.replace('"', '""')
            connection.execute(
                'CREATE TRIGGER block_job_write AFTER UPDATE ON "{}" '
                'BEGIN SELECT RAISE(FAIL, "private sqlite detail"); END'.format(table)
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(jobs.JobError) as raised:
            self.store.begin_step(queued["jobId"], 0, STEPS[0])
        self.assertEqual(raised.exception.code, "STORE_UNAVAILABLE")
        self.assertNotIn("private sqlite detail", str(raised.exception))
        self.assertNotIn(self.database, repr(raised.exception))
        cleanup = sqlite3.connect(self.database)
        try:
            cleanup.execute("DROP TRIGGER block_job_write")
            cleanup.commit()
        finally:
            cleanup.close()
        reopened = jobs.JobStore(self.database)
        self.assertEqual(reopened.get(queued["jobId"]), queued)

    def test_revision_overflow_is_controlled_and_does_not_partially_transition(self):
        queued = self.store.submit("overflow-command", CONFIG)
        connection = sqlite3.connect(self.database)
        try:
            connection.execute(
                "UPDATE jobs SET revision = ? WHERE job_id = ?",
                ((1 << 63) - 1, queued["jobId"]),
            )
            connection.commit()
        finally:
            connection.close()
        before = self.store.get(queued["jobId"])
        self.assert_error("STORE_UNAVAILABLE", lambda: self.store.begin_step(
            queued["jobId"], before["revision"], STEPS[0]))
        self.assertEqual(self.store.get(queued["jobId"]), before)

    def test_unrecognized_database_is_rejected_without_replacing_it(self):
        bad_database = Path(self.temporary.name) / "foreign.sqlite3"
        connection = sqlite3.connect(str(bad_database))
        connection.execute("CREATE TABLE unrelated(value TEXT)")
        connection.execute("INSERT INTO unrelated VALUES ('preserve')")
        connection.commit()
        connection.close()
        before = bad_database.read_bytes()
        with self.assertRaises(jobs.JobError) as raised:
            jobs.JobStore(str(bad_database))
        self.assertEqual(raised.exception.code, "STORE_UNAVAILABLE")
        self.assertEqual(bad_database.read_bytes(), before)

    def test_wrong_declared_schema_is_rejected_before_any_job_write(self):
        bad_database = Path(self.temporary.name) / "wrong-types.sqlite3"
        connection = sqlite3.connect(str(bad_database))
        try:
            connection.execute("CREATE TABLE journal_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            connection.execute(
                "CREATE TABLE jobs (job_id TEXT PRIMARY KEY, command_id TEXT NOT NULL UNIQUE, "
                "config_json TEXT NOT NULL, status TEXT NOT NULL, step_id TEXT, "
                "applied_steps_json TEXT NOT NULL, revision TEXT NOT NULL, "
                "created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
                "next_action_json TEXT, error_json TEXT)"
            )
            connection.execute(
                "CREATE UNIQUE INDEX one_active_job ON jobs ((1)) "
                "WHERE status IN ('QUEUED', 'RUNNING', 'WAITING_USER')"
            )
            connection.execute(
                "INSERT INTO journal_meta (key, value) VALUES ('schema_version', '1')"
            )
            connection.commit()
        finally:
            connection.close()
        before = bad_database.read_bytes()
        with self.assertRaises(jobs.JobError) as raised:
            jobs.JobStore(str(bad_database))
        self.assertEqual(raised.exception.code, "STORE_UNAVAILABLE")
        self.assertEqual(bad_database.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

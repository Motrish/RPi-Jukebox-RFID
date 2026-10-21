import unittest
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from installation.websetup.jobs import JobStore, JobError  # noqa: E402
from installation.websetup.worker import Worker, WorkerError  # noqa: E402


class FakeHandler:
    def apply(self, config):
        return None

    def observe(self, config):
        return 'UNKNOWN'


def valid_handlers():
    return {
        'CHECK_SYSTEM': FakeHandler(),
        'CONFIGURE_AUDIO': FakeHandler(),
        'VERIFY_INSTALLATION': FakeHandler()
    }


class TestJobStoreAndWorker(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.db = Path(self.tempdir.name) / 'jobs.sqlite3'
        self.store = JobStore(self.db)
        self.config = {
            'audioOutput': 'SYSTEM_DEFAULT',
            'rfidEnabled': False,
            'pisugarEnabled': True
        }

    def test_wait_for_inspection(self):
        snapshot = self.store.submit('inspect', self.config)
        job_id = snapshot['jobId']
        self.store.begin_step(job_id, 0, 'CHECK_SYSTEM')
        wait_result = self.store.wait_for_inspection(job_id, 1, 'CHECK_SYSTEM')
        persisted = self.store.get(job_id)

        self.assertEqual(persisted['status'], 'WAITING_USER')
        self.assertEqual(persisted['revision'], 2)
        self.assertEqual(persisted['stepId'], 'CHECK_SYSTEM')
        self.assertEqual(persisted['appliedSteps'], [])
        self.assertEqual(persisted['nextAction']['kind'], 'INSPECT_SYSTEM')
        self.assertIsNone(persisted['error'])
        self.assertEqual(persisted, wait_result)

        with self.assertRaises(JobError) as context:
            self.store.wait_for_inspection(job_id, 2, 'CHECK_SYSTEM')
        self.assertEqual(context.exception.code, 'INVALID_TRANSITION')
        self.assertEqual(self.store.get(job_id), persisted)

    def test_bad_handler_mapping(self):
        bad_mappings = [
            None,
            {},
            [],
            {'CHECK_SYSTEM': None},
            {'CHECK_SYSTEM': FakeHandler(), 'EXTRA_KEY': 'extra_value'},
            {'CHECK_SYSTEM': object(), 'EXTRA_KEY': 'extra_value'},
            {'CHECK_SYSTEM': FakeHandler(), 'EXTRA_KEY': 'extra_value', 'ANOTHER_KEY': 'another_value'},
            {'CHECK_SYSTEM': object(), 'EXTRA_KEY': 'extra_value', 'ANOTHER_KEY': 'another_value'}
        ]

        original_db_bytes = self.db.read_bytes() if self.db.exists() else b''

        for mapping in bad_mappings:
            with self.subTest(mapping=mapping):
                with self.assertRaises(WorkerError) as context:
                    Worker(self.db, mapping)
                self.assertEqual(context.exception.code, 'INVALID_REQUEST')
                self.assertEqual(self.db.read_bytes(), original_db_bytes)
                self.assertFalse((Path(str(self.db) + '.worker.lock')).exists())

    def test_bad_database_arguments(self):
        bad_paths = [None, True, 1, b'bytes', '', ':memory:']
        valid_mapping = valid_handlers()
        original_db_bytes = self.db.read_bytes() if self.db.exists() else b''

        for path in bad_paths:
            with self.subTest(path=path):
                with self.assertRaises(WorkerError) as context:
                    Worker(path, valid_mapping)
                self.assertEqual(context.exception.code, 'INVALID_REQUEST')
                self.assertEqual(self.db.read_bytes(), original_db_bytes)
                self.assertFalse((Path(str(self.db) + '.worker.lock')).exists())


if __name__ == '__main__':
    unittest.main()

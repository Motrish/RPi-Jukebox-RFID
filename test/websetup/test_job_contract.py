import unittest
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from installation.websetup.jobs import JobStore, JobError  # noqa: E402


class TestJobStore(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.store = JobStore(Path(self.tempdir.name) / 'jobs.sqlite3')
        self.config = {
            'audioOutput': 'HIFIBERRY_MINIAMP',
            'rfidEnabled': False,
            'pisugarEnabled': True
        }

    def test_initial_shape(self):
        self.assertIsNone(self.store.active())
        initial = self.store.submit('initial', self.config)
        self.assertEqual(initial['contractVersion'], 'websetup.job.v1')
        self.assertNotEqual(initial['jobId'], 'initial')
        self.assertEqual(initial['commandId'], 'initial')
        self.assertEqual(initial['status'], 'QUEUED')
        self.assertEqual(initial['revision'], 0)
        self.assertIsNone(initial['stepId'])
        self.assertIsNone(initial['nextAction'])
        self.assertIsNone(initial['error'])
        self.assertEqual(initial['appliedSteps'], [])
        self.assertEqual(initial['desiredConfigSummary'], self.config)
        self.assertEqual(initial['createdAt'], initial['updatedAt'])
        self.assertTrue(initial['createdAt'].endswith('Z'))
        self.assertEqual(self.store.get(initial['jobId']), initial)

    def test_bad_command_ids(self):
        invalid_ids = ['', None, True, 1, 'a' * 65, 'ä', 'space here', 'secret-marker!', 'has/slash', 'line\n']
        for command_id in invalid_ids:
            with self.subTest(command_id=command_id):
                with self.assertRaises(JobError) as context:
                    self.store.submit(command_id, self.config)
                self.assertIn('INVALID_REQUEST', str(context.exception))
                self.assertIsNone(self.store.active())
                self.assertNotIn('secret-marker', str(context.exception))

    def test_bad_configs(self):
        invalid_configs = [
            None, [], {},
            {'rfidEnabled': None}, {'pisugarEnabled': None},
            {'secret-marker': 'value'}, {'audioOutput': None}, {'audioOutput': []}
        ]
        for key in ['rfidEnabled', 'pisugarEnabled']:
            for value in [0, 1, 'true', None, []]:
                bad_config = self.config.copy()
                bad_config[key] = value
                invalid_configs.append(bad_config)

        for bad_config in invalid_configs:
            with self.subTest(config=bad_config):
                with self.assertRaises(JobError) as context:
                    self.store.submit('valid', bad_config)
                self.assertIn('INVALID_REQUEST', str(context.exception))
                self.assertIsNone(self.store.active())

    def test_copy_isolation(self):
        original = self.store.submit('secret-marker', self.config)
        jobId = original['jobId']

        self.config['audioOutput'] = 'SYSTEM_DEFAULT'
        original['desiredConfigSummary']['pisugarEnabled'] = False
        original['appliedSteps'].append('fake_object')
        original['status'] = 'FAILED'

        persisted = self.store.get(jobId)
        self.assertEqual(persisted['desiredConfigSummary']['audioOutput'], 'HIFIBERRY_MINIAMP')
        self.assertTrue(persisted['desiredConfigSummary']['pisugarEnabled'])
        self.assertEqual(persisted['appliedSteps'], [])
        self.assertEqual(persisted['status'], 'QUEUED')


if __name__ == '__main__':
    unittest.main()

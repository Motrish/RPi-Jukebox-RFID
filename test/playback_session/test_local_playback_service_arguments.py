import unittest

from components.playback_session.local_playback_service import LocalPlaybackService
from jukebox.contracts import ContractValidationError


class NeverCalledProvider:
    def start(self, *args, **kwargs):
        raise AssertionError()

    def stop(self, *args, **kwargs):
        raise AssertionError()


class TestLocalPlaybackService(unittest.TestCase):
    def test_invalid_run_once_deadline_preserves_state(self):
        service = LocalPlaybackService(
            provider=NeverCalledProvider(),
            boot_id='boot_one',
            monotonic=lambda: 10
        )
        service.request_start(
            entry_id='entry_one',
            media_ref={'kind': 'LOCAL', 'libraryId': 'library_one'}
        )

        before = service.snapshot()

        deadlines = [None, True, 'x', float('nan'), float('inf'), 10**400]

        for deadline in deadlines:
            with self.subTest(deadline=repr(deadline)):
                with self.assertRaises(ContractValidationError):
                    service.run_once(deadline=deadline)
                self.assertEqual(service.snapshot(), before)


if __name__ == '__main__':
    unittest.main()

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "jukebox"))

from jukebox.contracts.v1 import validate_command_result  # noqa: E402
from components.library_api.playlist_api import execute  # noqa: E402


class PlaylistErrorProjectionTests(unittest.TestCase):
    def test_rejected_result_does_not_expose_untrusted_error_text(self):
        command = {"contractVersion": 1, "commandId": "cmd_safe",
                   "action": "PLAYLIST_CREATE", "name": "Mix", "items": []}
        secret = "sqlite /srv/private/playlists.sqlite SELECT secret FROM credentials"
        source = {"contractVersion": 1, "commandId": "cmd_safe",
                  "action": "PLAYLIST_CREATE", "status": "REJECTED",
                  "error": {"code": "STORE_UNAVAILABLE", "message": secret,
                            "retryable": True, "operation": "STORE_WRITE",
                            "details": {"operation": "STORE_WRITE"}}}

        result = execute(command, lambda _: source)

        self.assertNotIn(secret, repr(result))
        self.assertEqual("cmd_safe", result["commandId"])
        self.assertEqual("PLAYLIST_CREATE", result["action"])
        self.assertEqual("REJECTED", result["status"])
        self.assertTrue(result["error"]["retryable"])
        self.assertEqual(source["error"]["message"], secret)
        self.assertEqual(result, validate_command_result(result))


if __name__ == "__main__":
    unittest.main()

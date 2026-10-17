import json
import http.client
import tempfile
import threading
import unittest
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

STAGE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STAGE_ROOT))

from installation.websetup import preflight, server  # noqa: E402


class PreflightTests(unittest.TestCase):
    def test_os_release_is_data_only_allowlisted_and_bounded(self):
        parsed = preflight.parse_os_release(
            'NAME="Raspberry Pi OS"\nVERSION_ID=12\nID=raspbian\n'
            'ID_LIKE="debian"\nSECRET=do-not-return\nNAME=last\n'
        )
        self.assertEqual(parsed, {"NAME": "Raspberry Pi OS", "VERSION_ID": "12", "ID": "raspbian", "ID_LIKE": "debian"})
        self.assertNotIn("SECRET", parsed)

    def test_unreadable_os_release_is_unknown_without_exception_details(self):
        report = preflight.build_report(
            root=Path("."),
            os_release_reader=lambda: (_ for _ in ()).throw(PermissionError("secret-path")),
            system_probe=lambda: {}, file_reader=lambda _p, _l: "",
            marker_probe=lambda _p: False, disk_probe=lambda _p: 100,
        )
        self.assertEqual(report["facts"]["os_name"]["status"], "unknown")
        self.assertIn("nicht gelesen", report["facts"]["os_name"]["reason"])
        self.assertNotIn("secret-path", json.dumps(report))

    def test_unreadable_markers_are_unknown_instead_of_absent(self):
        def marker_probe(path):
            if path.name in ("install-jukebox.sh", "jukebox.yaml"):
                raise PermissionError("private marker")
            raise OSError("private marker")

        report = preflight.build_report(
            root=Path("."), marker_probe=marker_probe,
            os_release_reader=lambda: "", system_probe=lambda: {},
            file_reader=lambda _path, _limit: "", disk_probe=lambda _path: 1,
        )
        facts = report["facts"]
        self.assertEqual(facts["repository"]["status"], "unknown")
        self.assertEqual(facts["bundle"]["status"], "unknown")
        settings = facts["installation"]["settings"]["markers"]
        self.assertEqual(settings["jukebox_config"]["status"], "unknown")
        self.assertEqual(settings["logger_config"]["status"], "unknown")
        self.assertNotIn("private marker", json.dumps(report))

    def test_settings_gitkeep_does_not_mean_installed_configuration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = root / "shared" / "settings"
            settings.mkdir(parents=True)
            (settings / ".gitkeep").touch()
            report = preflight.build_report(
                root=root, os_release_reader=lambda: "NAME=Test\nID=test\nVERSION_ID=1\n",
                system_probe=lambda: {"machine": "armv6l", "pointer_bits": 32, "python": "3.11"},
                file_reader=lambda _p, _l: "MemTotal: 512000 kB\n",
                marker_probe=lambda path: Path(path).is_file(),
                disk_probe=lambda _p: 1024 * 1024 * 1024,
            )
            result = report["facts"]["installation"]["settings"]
            self.assertEqual(result["status"], "observed")
            self.assertFalse(result["value"]["jukebox_config"])
            self.assertFalse(result["value"]["logger_config"])
            self.assertNotIn(str(root), json.dumps(report))

    def test_missing_probe_values_remain_unknown_with_reason(self):
        report = preflight.build_report(
            root=Path("."), os_release_reader=lambda: "", system_probe=lambda: {},
            file_reader=lambda _p, _l: "", marker_probe=lambda _p: False,
            disk_probe=lambda _p: None,
        )
        self.assertEqual(report["facts"]["architecture"]["status"], "unknown")
        self.assertTrue(report["facts"]["architecture"]["reason"])
        self.assertEqual(report["facts"]["memory"]["status"], "unknown")
        self.assertEqual(report["facts"]["free_disk"]["status"], "unknown")
        self.assertEqual(report["facts"]["os_name"]["status"], "unknown")
        self.assertIn("Betriebssystemfeld NAME", report["facts"]["os_name"]["reason"])
        self.assertEqual(report["facts"]["repository"]["value"], False)
        self.assertEqual(report["facts"]["bundle"]["value"], False)
        settings = report["facts"]["installation"]["settings"]["value"]
        self.assertFalse(settings["jukebox_config"])
        self.assertFalse(settings["logger_config"])


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        (root / "installation" / "websetup").mkdir(parents=True)
        (root / "installation" / "websetup" / "index.html").write_text("<h1>fixed status page</h1>")
        (root / "private.txt").write_text("must not be served")
        cls.before = sorted(
            (path.relative_to(root).as_posix(), path.read_bytes())
            for path in root.rglob("*") if path.is_file()
        )
        report = {"schema": "websetup.preflight.v1", "facts": {}}
        cls.httpd = server.make_server(root=root, port=0, report_factory=lambda: report)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:%d" % cls.httpd.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=2)
        cls.temp.cleanup()

    def test_only_fixed_page_and_redacted_json_are_served(self):
        with urlopen(self.base + "/", timeout=2) as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b"fixed status page", response.read())
        with urlopen(self.base + "/api/preflight", timeout=2) as response:
            payload = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(payload["schema"], "websetup.preflight.v1")

    def test_unknown_paths_queries_methods_and_file_paths_are_rejected(self):
        requests = ((self.base + "/secret", 404), (self.base + "/?file=secret", 400), (self.base + "/etc/passwd", 404))
        for url, expected_status in requests:
            with self.assertRaises(HTTPError) as caught:
                urlopen(url, timeout=2)
            self.assertEqual(caught.exception.code, expected_status)
        for method in ("POST", "PUT", "HEAD"):
            request = Request(self.base + "/", method=method)
            with self.assertRaises(HTTPError) as caught:
                urlopen(request, timeout=2)
            self.assertEqual(caught.exception.code, 405)
        request = Request(self.base + "/private.txt", method="TRACE")
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=2)
        self.assertEqual(caught.exception.code, 501)
        self.assertNotIn(b"private.txt", caught.exception.read())

    def test_requests_do_not_change_fixture_files(self):
        with urlopen(self.base + "/api/preflight", timeout=2) as response:
            response.read()
        with urlopen(self.base + "/", timeout=2) as response:
            response.read()
        root = Path(self.temp.name)
        after = sorted(
            (path.relative_to(root).as_posix(), path.read_bytes())
            for path in root.rglob("*") if path.is_file()
        )
        self.assertEqual(after, self.before)

    def test_server_is_bound_to_loopback(self):
        self.assertIn(self.httpd.server_address[0], ("127.0.0.1", "::1"))

    def test_host_origin_and_absolute_targets_are_rejected_before_probe(self):
        calls = []
        httpd = server.make_server(
            root=Path(self.temp.name), port=0,
            report_factory=lambda: calls.append(True) or {"schema": "websetup.preflight.v1"},
        )
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            port = httpd.server_address[1]
            bad_requests = [
                ("/api/preflight", [("Host", "attacker.example")]),
                ("/api/preflight", [("Host", "127.0.0.1"), ("Origin", "http://attacker.example")]),
                ("http://127.0.0.1:%d/api/preflight" % port, [("Host", "127.0.0.1:%d" % port)]),
                ("/api/preflight", [("Host", "user@localhost")]),
                ("/api/preflight", [("Host", "localhost"), ("Host", "127.0.0.1")]),
            ]
            for target, headers in bad_requests:
                status, _body = self._raw_request(port, target, headers)
                self.assertGreaterEqual(status, 400)
                self.assertLess(status, 500)
            self.assertEqual(calls, [])
            authority = "127.0.0.1:%d" % port
            status, _body = self._raw_request(
                port, "/api/preflight",
                [("Host", authority), ("Origin", "http://" + authority)],
            )
            self.assertEqual(status, 200)
            self.assertEqual(calls, [True])
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=2)

    @staticmethod
    def _raw_request(port, target, headers):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        connection.putrequest("GET", target, skip_host=True)
        for name, value in headers:
            connection.putheader(name, value)
        connection.endheaders()
        response = connection.getresponse()
        result = response.status, response.read()
        connection.close()
        return result


if __name__ == "__main__":
    unittest.main()

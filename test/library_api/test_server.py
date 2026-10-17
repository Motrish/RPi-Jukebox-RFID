"""Black-box tests for the bounded, authenticated library read API."""

import http.client
import importlib
import io
import json
import os
import runpy
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import textwrap
import unittest
from pathlib import Path
from unittest import mock


_STAGE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_STAGE_ROOT / "src" / "jukebox"))

_server_module = importlib.import_module("components.library_api.server")
_cli_module = importlib.import_module("components.library_api.__main__")
make_read_authorizer = _server_module.make_read_authorizer
make_server = _server_module.make_server

_TOKEN = "A" * 43
_TOKEN_PATTERN = (
    r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])"
)
_ITEMS = [
    {
        "libraryId": "lib_alpha",
        "displayName": "same-name.mp3",
        "availability": "AVAILABLE",
    },
    {
        "libraryId": "lib_beta",
        "displayName": "same-name.mp3",
        "availability": "MISSING",
    },
]


class FakeCatalog:
    """Count only the two permitted catalog reads."""

    def __init__(self):
        self.calls = []
        self.list_result = {"items": _ITEMS, "nextCursor": None}
        self.get_result = _ITEMS[0]
        self.failure = None
        self.closed = False

    def list_media(self, limit=50, cursor=None):
        self.calls.append(("list_media", limit, cursor))
        if self.failure is not None:
            raise self.failure
        return self.list_result

    def get_media(self, library_id):
        self.calls.append(("get_media", library_id))
        if self.failure is not None:
            raise self.failure
        return self.get_result

    def close(self):
        self.closed = True


class RunningServer:
    def __init__(self, catalog, authorizer=None):
        self.catalog = catalog
        self.auth_calls = []
        if authorizer is None:
            def authorizer(credential):
                return credential == _TOKEN
        self.authorizer = authorizer
        self.server = make_server(
            catalog=catalog,
            read_authorizer=self._authorize,
            port=0,
            origin_host="127.0.0.1",
        )
        address, port = self.server.server_address[:2]
        self.authority = "127.0.0.1:{}".format(port)
        self.origin = "http://{}".format(self.authority)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()

    def _authorize(self, credential):
        self.auth_calls.append(credential)
        return self.authorizer(credential)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        if self.thread.is_alive():
            raise AssertionError("server thread did not stop")

    def request(self, method="GET", target="/api/library/media", headers=None,
                body=None, raw_headers=None):
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_address[1], timeout=2
        )
        try:
            connection.putrequest(method, target, skip_host=True)
            if headers is None:
                headers = {}
            for key, value in headers.items():
                connection.putheader(key, value)
            if raw_headers:
                for key, value in raw_headers:
                    connection.putheader(key, value)
            connection.endheaders(body)
            response = connection.getresponse()
            payload = response.read()
            return response.status, response.getheaders(), payload
        finally:
            connection.close()

    def valid_headers(self):
        return {
            "Host": self.authority,
            "Authorization": "Bearer {}".format(_TOKEN),
        }


class LibraryApiHttpTests(unittest.TestCase):
    def setUp(self):
        self.catalog = FakeCatalog()
        self.app = RunningServer(self.catalog)

    def tearDown(self):
        self.app.close()

    @staticmethod
    def body_json(payload):
        return json.loads(payload.decode("utf-8"))

    def test_list_and_get_are_real_http_reads_with_closed_fields(self):
        headers = self.app.valid_headers()
        headers["Origin"] = self.app.origin
        status, response_headers, payload = self.app.request(headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(
            self.body_json(payload), {"items": _ITEMS, "nextCursor": None}
        )
        self.assertEqual(
            self.catalog.calls,
            [("list_media", 50, None)],
        )
        self.assertEqual(self.app.auth_calls, [_TOKEN, _TOKEN])
        self.assert_json_headers(response_headers, payload)
        self.assertNotIn(b"mpdReference", payload)

        self.catalog.calls.clear()
        status, _, payload = self.app.request(
            target="/api/library/media/lib_alpha",
            headers=self.app.valid_headers(),
        )
        self.assertEqual(status, 200)
        self.assertEqual(self.body_json(payload), _ITEMS[0])
        self.assertEqual(self.catalog.calls, [("get_media", "lib_alpha")])

    def test_paging_uses_only_canonical_limit_and_cursor(self):
        status, _, payload = self.app.request(
            target="/api/library/media?limit=2&cursor=lib_alpha",
            headers=self.app.valid_headers(),
        )
        self.assertEqual(status, 200)
        self.assertEqual(self.catalog.calls, [("list_media", 2, "lib_alpha")])
        self.assertEqual(self.body_json(payload)["items"], _ITEMS)

        bad_targets = (
            "/api/library/media?limit=01",
            "/api/library/media?limit=+1",
            "/api/library/media?limit=201",
            "/api/library/media?limit=1&limit=2",
            "/api/library/media?cursor=",
            "/api/library/media?unexpected=x",
            "/api/library/media?limit=1%26cursor=lib_alpha",
            "/api/library/media/lib_alpha?limit=1",
        )
        for target in bad_targets:
            with self.subTest(target=target):
                status, _, payload = self.app.request(
                    target=target, headers=self.app.valid_headers()
                )
                self.assertEqual(status, 400)
                self.assertEqual(
                    self.body_json(payload)["error"]["code"], "INVALID_REQUEST"
                )
        self.assertEqual(len(self.catalog.calls), 1)

    def test_untrusted_requests_never_reach_catalog(self):
        cases = [
            (401, {"Host": self.app.authority}, None),
            (
                401,
                {"Host": self.app.authority, "Authorization": "Bearer wrong"},
                None,
            ),
            (
                400,
                {
                    "Host": "example.invalid",
                    "Authorization": "Bearer " + _TOKEN,
                },
                None,
            ),
            (400, {**self.app.valid_headers(), "Origin": "null"}, None),
            (
                400,
                {**self.app.valid_headers(), "Origin": "http://localhost"},
                None,
            ),
            (
                400,
                {**self.app.valid_headers(), "Origin": self.app.origin},
                [("Host", self.app.authority)],
            ),
            (
                400,
                {**self.app.valid_headers(), "Origin": self.app.origin},
                [("Origin", self.app.origin)],
            ),
            (
                401,
                {**self.app.valid_headers(), "Origin": self.app.origin},
                [("Authorization", "Bearer " + _TOKEN)],
            ),
        ]
        for expected, headers, duplicates in cases:
            with self.subTest(headers=headers, duplicates=duplicates):
                status, _, payload = self.app.request(
                    headers=headers, raw_headers=duplicates
                )
                self.assertEqual(status, expected)
                if payload:
                    self.assertTrue(payload.startswith(b"{"))
        self.assertEqual(self.catalog.calls, [])

    def test_authorizer_must_return_exact_true_and_must_pass_twice(self):
        for result in (False, None, 1, "yes"):
            with self.subTest(result=result):
                self.app.authorizer = lambda credential, value=result: value
                self.app.auth_calls.clear()
                status, _, _ = self.app.request(
                    headers=self.app.valid_headers()
                )
                self.assertEqual(status, 401)
                self.assertEqual(self.catalog.calls, [])

        self.app.auth_calls.clear()
        self.catalog.calls.clear()
        self.app.authorizer = lambda credential: len(self.app.auth_calls) == 1
        status, _, payload = self.app.request(headers=self.app.valid_headers())
        self.assertEqual(status, 401)
        self.assertNotIn(b"same-name", payload)
        self.assertEqual(self.catalog.calls, [("list_media", 50, None)])

    def test_ttl_gate_is_monotonic_and_expires_at_900_seconds(self):
        now = [100.0]
        authorizer = make_read_authorizer(_TOKEN, clock=lambda: now[0])
        self.assertIs(authorizer(_TOKEN), True)
        now[0] = 999.999
        self.assertIs(authorizer(_TOKEN), True)
        now[0] = 1000.0
        self.assertIs(authorizer(_TOKEN), False)
        self.assertIs(authorizer("B" * 43), False)

    def test_expiry_before_catalog_and_during_read_prevents_data_output(self):
        now = [0.0]
        self.app.authorizer = make_read_authorizer(
            _TOKEN, clock=lambda: now[0]
        )
        now[0] = 900.0
        status, _, payload = self.app.request(headers=self.app.valid_headers())
        self.assertEqual(status, 401)
        self.assertNotIn(b"same-name", payload)
        self.assertEqual(self.catalog.calls, [])

        now[0] = 0.0
        original_list = self.catalog.list_media

        def expire_while_reading(limit=50, cursor=None):
            result = original_list(limit, cursor)
            now[0] = 900.0
            return result

        self.catalog.list_media = expire_while_reading
        status, _, payload = self.app.request(headers=self.app.valid_headers())
        self.assertEqual(status, 401)
        self.assertNotIn(b"same-name", payload)
        self.assertEqual(len(self.catalog.calls), 1)
        self.catalog.list_media = original_list

    def test_authorizer_errors_fail_closed_without_catalog_access(self):
        self.app.authorizer = lambda credential: (_ for _ in ()).throw(
            RuntimeError("secret diagnostic")
        )
        status, _, payload = self.app.request(headers=self.app.valid_headers())
        self.assertEqual(status, 401)
        self.assertNotIn(b"secret diagnostic", payload)
        self.assertEqual(self.catalog.calls, [])

    def test_backend_errors_and_invalid_records_are_safe_503(self):
        self.catalog.failure = RuntimeError("/private/path/token=" + _TOKEN)
        status, _, payload = self.app.request(headers=self.app.valid_headers())
        self.assertEqual(status, 503)
        self.assertEqual(
            self.body_json(payload),
            {"error": {
                "code": "SERVICE_UNAVAILABLE",
                "message": "The library service is unavailable.",
            }},
        )
        self.assertNotIn(_TOKEN.encode("ascii"), payload)
        self.assertNotIn(b"/private/path", payload)

        self.catalog.failure = None
        self.catalog.list_result = {
            "items": [{**_ITEMS[0], "path": "/secret"}],
            "nextCursor": None,
        }
        status, _, payload = self.app.request(headers=self.app.valid_headers())
        self.assertEqual(status, 503)
        self.assertNotIn(b"/secret", payload)

    def test_unknown_id_is_404_without_backend_field_reflection(self):
        self.catalog.get_result = None
        status, _, payload = self.app.request(
            target="/api/library/media/lib_missing",
            headers=self.app.valid_headers(),
        )
        self.assertEqual(status, 404)
        self.assertEqual(
            self.body_json(payload)["error"]["code"], "NOT_FOUND"
        )

    def test_routes_methods_bodies_and_origins_are_closed(self):
        headers = self.app.valid_headers()
        for method, target, expected in (
            ("POST", "/api/library/media", 405),
            ("PUT", "/api/library/media", 405),
            ("DELETE", "/api/library/media", 405),
            ("OPTIONS", "/api/library/media", 405),
            ("HEAD", "/api/library/media", 405),
            ("BREW", "/api/library/media", 405),
            ("GET", "/", 404),
            ("GET", "/health", 404),
            ("GET", "/assets/app.js", 404),
            ("GET", "/api/library/resolve", 404),
            ("GET", "/api/library/media/../etc/passwd", 400),
            ("GET", "/api/library/media/lib_alpha%2fsecret", 400),
            ("GET", "/api/library/media/lib_alpha\\secret", 400),
            ("GET", "//example.invalid/api/library/media", 400),
            ("GET", "http://example.invalid/api/library/media", 400),
            ("GET", "/api/library/media#fragment", 400),
        ):
            with self.subTest(method=method, target=target):
                status, _, payload = self.app.request(
                    method=method, target=target, headers=headers
                )
                self.assertEqual(status, expected)
                if method == "HEAD":
                    self.assertEqual(payload, b"")
                else:
                    self.assertTrue(payload.startswith(b"{"))
        status, _, _ = self.app.request(
            headers={**headers, "Origin": "https://127.0.0.1"}
        )
        self.assertEqual(status, 400)
        self.assertEqual(self.catalog.calls, [])

    def test_get_bodies_and_transfer_headers_are_rejected_before_read(self):
        cases = [
            ("GET", b"x", [("Content-Length", "1")]),
            ("GET", None, [("Content-Length", "-1")]),
            ("GET", None, [("Content-Length", "0"), ("Content-Length", "0")]),
            ("GET", None, [("Transfer-Encoding", "chunked")]),
            ("GET", None, [("Expect", "100-continue")]),
        ]
        for method, body, headers in cases:
            with self.subTest(body=body, headers=headers):
                status, _, payload = self.app.request(
                    method=method,
                    headers=self.app.valid_headers(),
                    raw_headers=headers,
                    body=body,
                )
                self.assertIn(status, (400, 417))
                if payload:
                    self.assertTrue(payload.startswith(b"{"))
        self.assertEqual(self.catalog.calls, [])

    def test_target_and_header_limits_do_not_reach_catalog(self):
        long_target = "/" + "a" * 2048
        status, _, _ = self.app.request(
            target=long_target, headers=self.app.valid_headers()
        )
        self.assertIn(status, (400, 414))

        oversized = self.app.valid_headers()
        oversized["X-Fill"] = "x" * 8200
        status, _, payload = self.app.request(headers=oversized)
        self.assertIn(status, (400, 431))
        if payload:
            self.assertTrue(payload.startswith(b"{"))

        too_many = self.app.valid_headers()
        too_many.update({"X-{:02d}".format(index): "x" for index in range(34)})
        status, _, payload = self.app.request(headers=too_many)
        self.assertIn(status, (400, 431))
        if payload:
            self.assertTrue(payload.startswith(b"{"))
        self.assertEqual(self.catalog.calls, [])

    def test_response_size_is_bounded_and_never_partially_succeeds(self):
        self.catalog.list_result = {
            "items": [{
                "libraryId": "lib_oversize",
                "displayName": "x" * (256 * 1024),
                "availability": "AVAILABLE",
            }],
            "nextCursor": None,
        }
        status, _, payload = self.app.request(
            headers=self.app.valid_headers()
        )
        self.assertEqual(status, 503)
        self.assertEqual(
            self.body_json(payload)["error"]["code"], "SERVICE_UNAVAILABLE"
        )
        self.assertLess(len(payload), 1024)

    def test_safe_json_headers_have_fixed_length_no_store_and_nosniff(self):
        status, headers, payload = self.app.request(
            headers=self.app.valid_headers()
        )
        self.assertEqual(status, 200)
        self.assert_json_headers(headers, payload)
        self.assertEqual(self.catalog.closed, False)
        self.assertEqual(
            {name.lower(): value for name, value in headers}.get("connection"),
            "close",
        )

    def assert_json_headers(self, headers, payload):
        normalized = {name.lower(): value for name, value in headers}
        self.assertEqual(
            normalized.get("content-type"), "application/json;charset=utf-8"
        )
        self.assertEqual(normalized.get("cache-control"), "no-store")
        self.assertEqual(normalized.get("x-content-type-options"), "nosniff")
        self.assertEqual(int(normalized["content-length"]), len(payload))
        self.assertNotIn("access-control-allow-origin", normalized)


class LibraryApiFactoryTests(unittest.TestCase):
    def test_loopback_factory_does_not_own_injected_catalog(self):
        catalog = FakeCatalog()
        server = make_server(
            catalog=catalog,
            read_authorizer=lambda credential: True,
            port=0,
            origin_host="localhost",
        )
        try:
            self.assertEqual(server.server_address[0], "127.0.0.1")
            self.assertFalse(catalog.closed)
        finally:
            server.server_close()
        self.assertFalse(catalog.closed)

    def test_factory_rejects_unapproved_origin_hosts(self):
        hosts = ("0.0.0.0", "192.168.1.5", "example.local", "localhost:80")
        for host in hosts:
            with self.subTest(host=host):
                with self.assertRaises((ValueError, OSError)):
                    make_server(
                        catalog=FakeCatalog(),
                        read_authorizer=lambda credential: True,
                        port=0,
                        origin_host=host,
                    )


class CliAndImportTests(unittest.TestCase):
    def setUp(self):
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = str(_STAGE_ROOT / "src" / "jukebox")

    @staticmethod
    def free_port():
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.bind(("127.0.0.1", 0))
            return listener.getsockname()[1]
        finally:
            listener.close()

    def test_imports_do_not_create_catalog_secret_or_listener(self):
        script = textwrap.dedent(
            """
            import secrets
            import socket
            import sqlite3
            import sys
            sys.path.insert(0, {source!r})

            def forbidden(*args, **kwargs):
                raise AssertionError("import caused a side effect")

            socket.socket.bind = forbidden
            socket.socket.listen = forbidden
            secrets.token_bytes = forbidden
            secrets.token_urlsafe = forbidden
            sqlite3.connect = forbidden

            import components.library_api
            import components.library_api.server
            import components.library_api.__main__
            """.format(source=str(_STAGE_ROOT / "src" / "jukebox"))
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(_STAGE_ROOT),
            env=self.env,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_non_tty_cli_refuses_without_creating_database_or_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "library"
            root.mkdir()
            database = Path(directory) / "missing.sqlite3"
            port = self.free_port()
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "components.library_api",
                    "--database",
                    str(database),
                    "--library-root",
                    str(root),
                    "--port",
                    str(port),
                ],
                cwd=str(_STAGE_ROOT),
                env=self.env,
                input="",
                capture_output=True,
                text=True,
                timeout=5,
            )
            output = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(database.exists())
            self.assertNotRegex(output, _TOKEN_PATTERN)
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                self.assertNotEqual(
                    listener.connect_ex(("127.0.0.1", port)), 0
                )
            finally:
                listener.close()

    def test_cli_rejects_uninitialized_database_before_listener(self):
        class Tty(io.StringIO):
            def isatty(self):
                return True

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "library"
            root.mkdir()
            database = Path(directory) / "uninitialized.sqlite3"
            connection = sqlite3.connect(str(database))
            connection.execute("PRAGMA user_version = 0")
            connection.close()
            port = self.free_port()
            arguments = [
                "library-api",
                "--database",
                str(database),
                "--library-root",
                str(root),
                "--port",
                str(port),
            ]
            output = Tty()
            error = Tty()
            with mock.patch.object(sys, "argv", arguments):
                with mock.patch("sys.stdin", Tty()):
                    with mock.patch("sys.stdout", output):
                        with mock.patch("sys.stderr", error):
                            with mock.patch.object(
                                socket.socket,
                                "bind",
                                side_effect=AssertionError(
                                    "listener opened before schema check"
                                ),
                            ) as bind:
                                with self.assertRaises(SystemExit) as raised:
                                    runpy.run_module(
                                        "components.library_api",
                                        run_name="__main__",
                                    )
            self.assertNotEqual(raised.exception.code, 0)
            bind.assert_not_called()
            connection = sqlite3.connect(str(database))
            try:
                self.assertEqual(
                    connection.execute("PRAGMA user_version").fetchone()[0], 0
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT name FROM sqlite_master "
                        "WHERE type = 'table'"
                    ).fetchall(),
                    [],
                )
            finally:
                connection.close()
            self.assertEqual(output.getvalue(), "")
            self.assertNotRegex(
                error.getvalue(),
                _TOKEN_PATTERN,
            )

    def test_cli_closes_owned_server_and_catalog_on_every_exit_path(self):
        class Tty(io.StringIO):
            def isatty(self):
                return True

        class OwnedCatalog:
            def __init__(self, database, library_root):
                self.close_calls = 0

            def close(self):
                self.close_calls += 1

        class OwnedServer:
            def __init__(self, behavior):
                self.behavior = behavior
                self.server_close_calls = 0

            def serve_forever(self, poll_interval):
                if isinstance(self.behavior, BaseException):
                    raise self.behavior

            def server_close(self):
                self.server_close_calls += 1

        behaviors = (
            (None, 0),
            (KeyboardInterrupt(), 0),
            (RuntimeError("synthetic server failure"), 1),
        )
        for behavior, expected_status in behaviors:
            with self.subTest(behavior=type(behavior).__name__):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory) / "library"
                    root.mkdir()
                    database = Path(directory) / "catalog.sqlite3"
                    connection = sqlite3.connect(str(database))
                    connection.execute("PRAGMA user_version = 1")
                    connection.close()
                    catalog = OwnedCatalog(str(database), str(root))
                    server = OwnedServer(behavior)
                    output = Tty()
                    error = Tty()
                    args = [
                        "--database",
                        str(database),
                        "--library-root",
                        str(root),
                        "--port",
                        "48762",
                    ]
                    with mock.patch("sys.stdin", Tty()):
                        with mock.patch("sys.stdout", output):
                            with mock.patch("sys.stderr", error):
                                with mock.patch.object(
                                    _cli_module,
                                    "LibraryCatalog",
                                    return_value=catalog,
                                ):
                                    with mock.patch.object(
                                        _cli_module,
                                        "make_server",
                                        return_value=server,
                                    ):
                                        with mock.patch.object(
                                            _cli_module,
                                            "make_read_authorizer",
                                            return_value=lambda credential: True,
                                        ):
                                            with mock.patch.object(
                                                _cli_module.secrets,
                                                "token_urlsafe",
                                                return_value=_TOKEN,
                                            ):
                                                status = _cli_module.main(args)
                    self.assertEqual(status, expected_status)
                    self.assertEqual(server.server_close_calls, 1)
                    self.assertEqual(catalog.close_calls, 1)
                    self.assertEqual(output.getvalue().count(_TOKEN), 1)
                    self.assertNotIn(_TOKEN, error.getvalue())


@unittest.skipUnless(
    sys.platform.startswith("linux"),
    "the real catalog uses Linux descriptor-relative filesystem access",
)
class RealCatalogHttpInteropTests(unittest.TestCase):
    def test_registered_regular_file_is_read_over_loopback_http(self):
        catalog_module = importlib.import_module("components.library_catalog")
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "library"
            root.mkdir()
            (root / "track.mp3").write_bytes(b"registered fixture")
            catalog = catalog_module.LibraryCatalog(
                base / "catalog.sqlite3", root
            )
            try:
                registered = catalog.register_file("track.mp3")
                app = RunningServer(catalog)
                try:
                    status, _, payload = app.request(
                        headers=app.valid_headers()
                    )
                    self.assertEqual(status, 200)
                    self.assertEqual(
                        json.loads(payload.decode("utf-8")),
                        {"items": [registered], "nextCursor": None},
                    )
                    status, _, payload = app.request(
                        target="/api/library/media/" + registered["libraryId"],
                        headers=app.valid_headers(),
                    )
                    self.assertEqual(status, 200)
                    self.assertEqual(
                        json.loads(payload.decode("utf-8")), registered
                    )
                finally:
                    app.close()
            finally:
                catalog.close()


if __name__ == "__main__":
    unittest.main()

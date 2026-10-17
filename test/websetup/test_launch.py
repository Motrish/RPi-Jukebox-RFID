"""Tests for the local bundle-backed developer launcher.

The real-browser acceptance path is intentionally explicit; normal unittest
discovery stays stdlib-only and quick.
"""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import importlib
import json
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest import mock
from urllib.parse import urlsplit

STAGE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STAGE_ROOT))

# Keep this import unconditional: publishing the phase-one tests must expose a
# missing launcher as a real collection error, never as a skip or fallback.
launch = importlib.import_module("installation.websetup.launch")  # noqa: E402,F401

# Narrow product-test seam: launch.run(argv, *, make_server_factory,
# popen_factory) returns an exit status. Every listener/process creation must
# pass through those factories; bundle.staged_bundle remains real and unpatched.


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def run_cli(arguments, timeout=8, cwd=None, env=None):
    command = [sys.executable, str(STAGE_ROOT / "installation/websetup/launch.py")]
    return subprocess.run(command + arguments, cwd=cwd, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=timeout, check=False)


class LauncherCliTests(unittest.TestCase):
    def make_bundle(self, temporary):
        root = Path(temporary)
        build = root / "build"
        (build / "static" / "js").mkdir(parents=True)
        (build / "index.html").write_text(
            "<!doctype html><html><body><div id='root'></div></body></html>", encoding="utf-8")
        (build / "static" / "js" / "app.js").write_text("window.app = true;", encoding="utf-8")
        (build / "asset-manifest.json").write_text('{"files":{}}', encoding="utf-8")
        output = root / "bundle"
        result = subprocess.run(
            [sys.executable, str(STAGE_ROOT / "tools/web_bundle.py"), "package",
             "--build-dir", str(build), "--output-dir", str(output),
             "--repository", "Motrish/RPi-Jukebox-RFID", "--commit", "a" * 40],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=False)
        if result.returncode:
            raise AssertionError("real bundle producer failed: " + result.stderr)
        return output / "webapp-build.tar.gz", output / "manifest.json"

    def base_args(self, temporary, port=None):
        archive, manifest = self.make_bundle(temporary)
        args = ["--archive", str(archive), "--manifest", str(manifest),
                "--repository", "Motrish/RPi-Jukebox-RFID", "--commit", "a" * 40]
        if port is not None:
            args.extend(["--port", str(port)])
        return args

    def test_rejects_unknown_options_and_invalid_ports(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = self.base_args(temporary)
            for extra in (["--document-root", temporary], ["--upstream", "127.0.0.1:1"],
                          ["--port", "80"], ["--port", "65536"], ["--port", "no"]):
                result = run_cli(base + extra)
                self.assertNotEqual(result.returncode, 0, extra)
                self.assertNotIn("Traceback", result.stderr)

    def test_invalid_bundle_fails_before_requested_listener(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive, manifest = self.make_bundle(temporary)
            archive.write_bytes(archive.read_bytes()[:-1] + bytes([archive.read_bytes()[-1] ^ 1]))
            port = free_port()
            arguments = ["--archive", str(archive), "--manifest", str(manifest),
                         "--repository", "Motrish/RPi-Jukebox-RFID", "--commit", "a" * 40,
                         "--port", str(port)]
            calls = []

            def forbidden_listener(*_args, **_kwargs):
                calls.append(True)
                raise AssertionError("listener/process factory called before invalid bundle rejection")

            from installation.websetup import bundle
            captured_stdout = StringIO()
            captured_stderr = StringIO()
            with mock.patch.object(bundle, "staged_bundle", wraps=bundle.staged_bundle) as intake:
                with redirect_stdout(captured_stdout), redirect_stderr(captured_stderr):
                    result = launch.run(arguments, make_server_factory=forbidden_listener,
                                        popen_factory=forbidden_listener)
            self.assertNotEqual(result, 0)
            self.assertEqual(intake.call_count, 1)
            self.assertEqual(calls, [])
            self.assertNotIn("Traceback", captured_stdout.getvalue() + captured_stderr.getvalue())
            self.assertNotIn(str(archive), captured_stdout.getvalue() + captured_stderr.getvalue())
            with socket.socket() as probe:
                self.assertNotEqual(probe.connect_ex(("127.0.0.1", port)), 0)

    def test_active_foreign_http_200_is_never_probed_or_announced(self):
        requests = []

        class ForeignHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                body = b"foreign listener"
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format, *_args):
                return

        foreign = ThreadingHTTPServer(("127.0.0.1", 0), ForeignHandler)
        foreign_thread = threading.Thread(target=foreign.serve_forever, daemon=True)
        foreign_thread.start()
        try:
            with tempfile.TemporaryDirectory() as temporary:
                arguments = self.base_args(temporary, foreign.server_address[1])
                arguments.extend(["--nginx-binary", sys.executable])

                class CompletedConfig:
                    returncode = 0

                    def communicate(self, timeout=None):
                        return "", ""

                class DelayedExit:
                    returncode = None
                    polls = 0

                    def poll(self):
                        self.polls += 1
                        return None if self.polls == 1 else 1

                    def wait(self, timeout=None):
                        self.returncode = 1
                        return self.returncode

                    def terminate(self):
                        self.returncode = -15

                    def kill(self):
                        self.returncode = -9

                child = DelayedExit()
                process_calls = []

                def popen_factory(command, **_kwargs):
                    process_calls.append(list(command))
                    return CompletedConfig() if "-t" in command else child

                output = StringIO()
                errors = StringIO()
                with redirect_stdout(output), redirect_stderr(errors):
                    result = launch.run(arguments, popen_factory=popen_factory)
                self.assertNotEqual(result, 0)
                self.assertNotIn("http://127.0.0.1:{}/setup/".format(foreign.server_address[1]),
                                 output.getvalue())
                self.assertNotIn("/#/design-preview", output.getvalue())
                self.assertEqual(requests, [])
                self.assertEqual(process_calls, [])
                self.assertNotIn("Traceback", output.getvalue() + errors.getvalue())
                self.assertEqual(raw_http(foreign.server_address[1], "/setup/")[0], 200)
                self.assertEqual(requests, ["/setup/"])
        finally:
            foreign.shutdown()
            foreign.server_close()
            foreign_thread.join(timeout=2)

    def test_dollar_private_temp_path_rejects_before_listener_factories(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary) / "$server_port"
            parent.mkdir()
            arguments = self.base_args(temporary)
            arguments.extend(["--nginx-binary", sys.executable])
            listener_factory = mock.Mock(side_effect=AssertionError("listener created"))
            process_factory = mock.Mock(side_effect=AssertionError("process created"))
            output = StringIO()
            errors = StringIO()
            with mock.patch.object(launch.tempfile, "tempdir", str(parent)):
                with redirect_stdout(output), redirect_stderr(errors):
                    result = launch.run(arguments, make_server_factory=listener_factory,
                                        popen_factory=process_factory)
            self.assertNotEqual(result, 0)
            self.assertEqual(listener_factory.call_count, 0)
            self.assertEqual(process_factory.call_count, 0)
            self.assertNotIn(str(parent), output.getvalue() + errors.getvalue())
            self.assertEqual(list(parent.iterdir()), [])

    def test_missing_nginx_is_diagnosed_without_install_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = self.base_args(temporary)
            args.extend(["--nginx-binary", str(Path(temporary) / "no-nginx")])
            result = run_cli(args)
            self.assertNotEqual(result.returncode, 0)
            combined = result.stdout + result.stderr
            self.assertNotIn("Traceback", combined)
            self.assertNotIn("apt", combined.lower())

    def test_raw_filesystem_exception_is_replaced_with_fixed_diagnostic(self):
        raw_error = "/tmp/i01b-bootstrap-test/nginx-prefix/logs: private-payload-7d31"
        arguments = ["--archive", "unused", "--manifest", "unused",
                     "--repository", "Motrish/RPi-Jukebox-RFID", "--commit", "a" * 40,
                     "--nginx-binary", sys.executable]
        output = StringIO()
        errors = StringIO()
        with mock.patch.object(launch.tempfile, "TemporaryDirectory", side_effect=OSError(raw_error)):
            with redirect_stdout(output), redirect_stderr(errors):
                result = launch.run(arguments)
        combined = output.getvalue() + errors.getvalue()
        self.assertNotEqual(result, 0)
        self.assertNotIn(raw_error, combined)
        self.assertNotIn("private-payload-7d31", combined)
        self.assertNotIn("Traceback", combined)

    @unittest.skipUnless(os.name == "posix", "nginx process failure check runs on Linux CI")
    def test_nginx_config_test_failure_leaves_no_listener_or_private_stage(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive, manifest = self.make_bundle(temporary)
            fake_nginx = Path(temporary) / "nginx-test-failure"
            fake_nginx.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
            fake_nginx.chmod(0o700)
            private_parent = Path(temporary) / "private"
            private_parent.mkdir(mode=0o700)
            port = free_port()
            args = ["--archive", str(archive), "--manifest", str(manifest),
                    "--repository", "Motrish/RPi-Jukebox-RFID", "--commit", "a" * 40,
                    "--port", str(port), "--nginx-binary", str(fake_nginx)]
            child_env = os.environ.copy()
            child_env["TMPDIR"] = str(private_parent)
            result = run_cli(args, env=child_env)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Traceback", result.stdout + result.stderr)
            self.assertEqual(list(private_parent.iterdir()), [])
            with socket.socket() as probe:
                self.assertNotEqual(probe.connect_ex(("127.0.0.1", port)), 0)

    @unittest.skipUnless(os.name == "posix", "POSIX shell/process checks run on Linux CI")
    def test_shell_entry_works_from_unrelated_directory_and_keeps_arguments(self):
        shell = STAGE_ROOT / "installation/bootstrap-web.sh"
        with tempfile.TemporaryDirectory(prefix="launcher cwd with spaces ") as elsewhere:
            result = subprocess.run(["/bin/sh", str(shell), "--invalid-option"], cwd=elsewhere,
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    timeout=5, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)

    @unittest.skipUnless(os.name == "posix", "signal checks run on Linux CI")
    def test_port_collision_does_not_adopt_or_close_existing_listener(self):
        with tempfile.TemporaryDirectory() as temporary, socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            result = run_cli(self.base_args(temporary, port), timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(listener.getsockname()[1], port)
            probe = socket.create_connection(("127.0.0.1", port), timeout=1)
            probe.close()


def raw_http(port, target, headers=(), method="GET"):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    connection.putrequest(method, target, skip_host=True)
    if not any(name.lower() == "host" for name, _value in headers):
        connection.putheader("Host", "127.0.0.1:{}".format(port))
    for name, value in headers:
        connection.putheader(name, value)
    connection.endheaders()
    response = connection.getresponse()
    result = response.status, response.getheaders(), response.read()
    connection.close()
    return result


def wait_for_ready(process, port, deadline):
    output = []
    expected_urls = ("http://127.0.0.1:{}/setup/".format(port), "/#/design-preview")
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError("launcher exited before readiness")
        readable, _writable, _exceptional = select.select([process.stdout], [], [], 0.05)
        if readable:
            chunk = os.read(process.stdout.fileno(), 4096).decode("utf-8", errors="replace")
            if chunk:
                output.append(chunk)
        if all(value in "".join(output) for value in expected_urls):
            status, _headers, _body = raw_http(port, "/setup/", [("Host", "127.0.0.1:{}".format(port))])
            if status == 200:
                return "".join(output)
    raise AssertionError("launcher did not publish both ready URLs and serve setup before deadline")


def verify_http_matrix(port):
    good = "127.0.0.1:{}".format(port)
    cases = [
        ("/setup/", [("Host", good)], "GET", (200,)),
        ("/api/preflight", [("Host", good)], "GET", (200,)),
        ("/api/preflight", [("Host", good), ("Origin", "http://" + good)], "GET", (200,)),
        ("/setup/", [("Host", "attacker.invalid")], "GET", (400, 403)),
        ("/setup/", [("Host", "localhost:{}".format(port))], "GET", (400, 403)),
        ("/setup/", [("Host", good), ("Host", good)], "GET", (400, 403)),
        ("/api/preflight", [("Host", good), ("Origin", "http://attacker.invalid")], "GET", (400, 403)),
        ("/api/preflight", [("Host", good), ("Origin", "")], "GET", (400, 403)),
        ("/api/preflight", [("Host", good), ("Origin", " ")], "GET", (400, 403)),
        ("/api/preflight", [("Host", good), ("Origin", "http://" + good),
                            ("Origin", "http://" + good)], "GET", (400, 403)),
        ("/api/preflight?probe=1", [("Host", good)], "GET", (400, 404)),
        ("/unknown-api", [("Host", good)], "GET", (400, 404)),
        ("/api/unknown", [("Host", good)], "GET", (400, 404)),
        ("/admin", [("Host", good)], "GET", (400, 404)),
        ("/rpc", [("Host", good)], "GET", (400, 404)),
        ("/ws", [("Host", good)], "GET", (400, 404)),
        ("/logs", [("Host", good)], "GET", (400, 404)),
        ("/setup", [("Host", good)], "GET", (400, 404)),
        ("/setup/unknown", [("Host", good)], "GET", (400, 404)),
        ("http://{}:{}/api/preflight".format("127.0.0.1", port), [("Host", good)], "GET", (400, 404)),
        ("/setup/", [("Host", good)], "POST", (405,)),
        ("/../etc/passwd", [("Host", good)], "GET", (400, 404)),
        ("/%2e%2e/etc/passwd", [("Host", good)], "GET", (400, 404)),
    ]
    for target, headers, method, accepted in cases:
        status, _response_headers, body = raw_http(port, target, headers, method)
        if status not in accepted:
            raise AssertionError("unexpected HTTP status for {}: {}".format(target, status))
        reject_spa = target.startswith(("/unknown", "/api/unknown", "/admin", "/rpc", "/ws", "/logs", "/setup"))
        reject_spa = reject_spa or target.startswith("http://")
        if reject_spa and status >= 400:
            if status < 400:
                raise AssertionError("forbidden route returned a success response: {}".format(target))
            if b"<html" in body.lower():
                raise AssertionError("forbidden route returned SPA HTML: {}".format(target))
        if target == "/api/preflight" and status == 200:
            payload = json.loads(body)
            if payload.get("schema") != "websetup.preflight.v1" or "facts" not in payload:
                raise AssertionError("preflight response did not contain I01a facts")


def browser_route(route, origin, observed, blocked):
    parsed = urlsplit(route.request.url)
    same_origin = "{}://{}".format(parsed.scheme, parsed.netloc) == origin
    allowed_paths = {
        "/setup/", "/api/preflight", "/", "/index.html", "/favicon.ico",
        "/logo192.png", "/manifest.json", "/locales/de/translation.json",
        "/locales/en/translation.json",
    }
    allowed = same_origin and route.request.method == "GET" and not parsed.query and (
        parsed.path in allowed_paths or parsed.path.startswith("/static/"))
    if allowed:
        observed.append(parsed.path)
        route.continue_()
    else:
        blocked.append(parsed.scheme + "://" + parsed.netloc + parsed.path[:100])
        route.abort()


def observe_preflight(response, args, output, api_reports):
    if urlsplit(response.url).path != "/api/preflight":
        return
    payload = response.json()
    if response.status != 200 or payload.get("schema") != "websetup.preflight.v1":
        raise AssertionError("browser received an invalid I01a response")
    if not isinstance(payload.get("facts"), dict) or not payload["facts"]:
        raise AssertionError("browser received no redacted I01a facts")
    serialized = json.dumps(payload, sort_keys=True)
    private_values = (str(Path(args.archive).resolve()), str(Path(args.manifest).resolve()),
                      str(output.resolve()), "foreign-sentinel.txt")
    if any(value in serialized for value in private_values):
        raise AssertionError("I01a response exposed private test data")
    api_reports.append(payload)


def verify_browser(args, port, output):
    from playwright.sync_api import sync_playwright

    observed, blocked, page_errors, static_mimes, api_reports = [], [], [], [], []
    origin = "http://127.0.0.1:{}".format(port)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_init_script("Object.defineProperty(navigator, 'language', {get: () => 'de'});"
                                "Object.defineProperty(navigator, 'languages', {get: () => ['de','en']});")
        context.route("**/*", lambda route: browser_route(route, origin, observed, blocked))
        page = context.new_page()
        page.on("pageerror", lambda error: page_errors.append(type(error).__name__))
        page.on("response", lambda response: static_mimes.append(
            (urlsplit(response.url).path, response.headers.get("content-type", ""))
        ) if "/static/" in urlsplit(response.url).path else None)
        page.on("response", lambda response: observe_preflight(response, args, output, api_reports))
        verify_browser_routes(page, origin, output, observed, blocked, page_errors, static_mimes, api_reports)
        browser.close()
    return len(observed)


def verify_browser_routes(page, origin, output, observed, blocked, page_errors, static_mimes, api_reports):
    page.goto(origin + "/setup/", wait_until="networkidle", timeout=10000)
    if page.locator("body").inner_text().strip() == "":
        raise AssertionError("I01a setup page rendered no content")
    loaded_state = "Systemdaten wurden schreibgeschützt geladen."
    page.locator("#state").get_by_text(loaded_state, exact=True).wait_for(timeout=5000)
    if page.locator(".fact").count() < 1 or not api_reports:
        raise AssertionError("browser did not render the successfully fetched I01a facts")
    page.goto(origin + "/#/design-preview", wait_until="networkidle", timeout=10000)
    if page.locator("#root").evaluate("element => element.children.length") < 1:
        raise AssertionError("React design-preview route rendered an empty root")
    if blocked or page_errors:
        raise AssertionError("browser blocked requests or errors: {} {}".format(blocked, page_errors))
    if "/api/preflight" not in observed or not any(path.startswith("/static/") for path in observed):
        raise AssertionError("browser did not fetch setup facts and same-origin React assets")
    has_javascript_mime = any(path.endswith(".js") and "javascript" in mime for path, mime in static_mimes)
    if not has_javascript_mime:
        raise AssertionError("React JavaScript asset had no JavaScript MIME type")
    page.screenshot(path=str(output / "bootstrap-browser.png"), full_page=True)


def launcher_command(args, port):
    return ["/bin/sh", str(STAGE_ROOT / "installation/bootstrap-web.sh"),
            "--archive", str(Path(args.archive).resolve()),
            "--manifest", str(Path(args.manifest).resolve()),
            "--repository", args.repository, "--commit", args.commit,
            "--port", str(port), "--nginx-binary", str(Path(args.nginx_binary).resolve())]


def process_descendants(pid):
    result = subprocess.run(["ps", "-eo", "pid=,ppid="], text=True, capture_output=True,
                            timeout=3, check=True)
    parents = {}
    for line in result.stdout.splitlines():
        child, parent = map(int, line.split())
        parents.setdefault(parent, []).append(child)
    found = []
    pending = [pid]
    while pending:
        parent = pending.pop()
        children = parents.get(parent, [])
        found.extend(children)
        pending.extend(children)
    return found


def owned_process_ids(process):
    return [process.pid] + process_descendants(process.pid)


def process_group_members(group_id):
    result = subprocess.run(["ps", "-eo", "pid=,pgid="], text=True, capture_output=True,
                            timeout=3, check=True)
    return [int(pid) for pid, pgid in (line.split() for line in result.stdout.splitlines())
            if int(pgid) == group_id]


def loopback_listeners_for(process):
    owners = {}
    for pid in owned_process_ids(process):
        try:
            descriptors = Path("/proc/{}/fd".format(pid)).iterdir()
            for descriptor in descriptors:
                try:
                    target = os.readlink(descriptor)
                except OSError:
                    continue
                if target.startswith("socket:[") and target.endswith("]"):
                    owners.setdefault(target[8:-1], set()).add(pid)
        except OSError:
            continue
    result = set()
    with open("/proc/net/tcp", encoding="ascii") as table:
        next(table)
        for line in table:
            fields = line.split()
            local_address, state, inode = fields[1], fields[3], fields[9]
            if state != "0A" or inode not in owners:
                continue
            address_hex, port_hex = local_address.split(":")
            address = socket.inet_ntoa(bytes.fromhex(address_hex)[::-1])
            if address.startswith("127."):
                for pid in owners[inode]:
                    result.add((pid, address, int(port_hex, 16), inode))
    return result


def all_tcp_listener_inodes():
    inodes = set()
    for table_name in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(table_name, encoding="ascii") as table:
                next(table)
                for line in table:
                    fields = line.split()
                    if fields[3] == "0A":
                        inodes.add(fields[9])
        except OSError:
            continue
    return inodes


def pid_is_running(pid):
    try:
        stat = Path("/proc/{}/stat".format(pid)).read_text(encoding="ascii")
    except OSError:
        return False
    return stat.rsplit(")", 1)[-1].strip().split()[0] != "Z"


def signal_process(process, signum, whole_group):
    try:
        if whole_group:
            os.killpg(process.pid, signum)
        else:
            process.send_signal(signum)
    except ProcessLookupError:
        pass


def communicate_with_escalation(process):
    try:
        return process.communicate(timeout=6)
    except subprocess.TimeoutExpired:
        signal_process(process, signal.SIGTERM, whole_group=True)
    try:
        return process.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        signal_process(process, signal.SIGKILL, whole_group=True)
        return process.communicate(timeout=2)


def wait_for_pids(known_pids, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end and any(pid_is_running(pid) for pid in known_pids):
        time.sleep(0.05)
    return [pid for pid in known_pids if pid_is_running(pid)]


def finish_owned_process(process, known_pids, signum=None, whole_group=False):
    group_members = process_group_members(process.pid)
    known_pids = sorted(set(known_pids).union(group_members))
    if whole_group:
        signal_process(process, signum or signal.SIGTERM, whole_group=True)
    elif process.poll() is None:
        signal_process(process, signum or signal.SIGTERM, whole_group)
    stdout, stderr = communicate_with_escalation(process)
    survivors = wait_for_pids(known_pids, 2)
    if survivors:
        signal_process(process, signal.SIGKILL, whole_group=True)
        wait_for_pids(survivors, 2)
    return stdout or "", stderr or "", survivors


def assert_listeners_gone(snapshot):
    expected = {item[3] for item in snapshot}
    if expected.intersection(all_tcp_listener_inodes()):
        raise AssertionError("an owned loopback listener remained after launcher exit")


def verify_signal_cleanup(args, output, private_parent, signum):
    port = free_port()
    process = subprocess.Popen(launcher_command(args, port), cwd=output,
                               env=dict(os.environ, TMPDIR=str(private_parent)),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    known_pids = [process.pid]
    listeners = set()
    try:
        wait_for_ready(process, port, time.monotonic() + 15)
        known_pids = owned_process_ids(process)
        listeners = loopback_listeners_for(process)
        if not any(item[2] == port for item in listeners) or not any(item[2] != port for item in listeners):
            raise AssertionError("launcher did not own both nginx and preflight loopback listeners")
        _stdout, _stderr, survivors = finish_owned_process(
            process, known_pids, signum=signum, whole_group=(signum == signal.SIGINT))
        if process.returncode != 0 or survivors:
            raise AssertionError("launcher did not stop cleanly for signal {}".format(signum))
        if list(private_parent.iterdir()):
            raise AssertionError("signal shutdown leaked private files")
        assert_listeners_gone(listeners)
    finally:
        _stdout, _stderr, _survivors = finish_owned_process(process, known_pids, whole_group=True)


def verify_nginx_child_exit(args, output, private_parent):
    port = free_port()
    process = subprocess.Popen(launcher_command(args, port), cwd=output,
                               env=dict(os.environ, TMPDIR=str(private_parent)),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    known_pids = [process.pid]
    listeners = set()
    try:
        wait_for_ready(process, port, time.monotonic() + 15)
        known_pids = owned_process_ids(process)
        listeners = loopback_listeners_for(process)
        nginx_pids = [item[0] for item in listeners if item[2] == port and item[0] != process.pid]
        if not nginx_pids:
            raise AssertionError("could not identify the owned nginx listener process")
        os.kill(nginx_pids[0], signal.SIGKILL)
        deadline = time.monotonic() + 8
        while process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        if process.poll() is None:
            raise AssertionError("launcher did not notice its nginx child exit before deadline")
        _stdout, _stderr, survivors = finish_owned_process(process, known_pids)
        if process.returncode == 0 or survivors:
            raise AssertionError("launcher did not stop after unexpected nginx exit")
        if list(private_parent.iterdir()):
            raise AssertionError("nginx child exit leaked private files")
        assert_listeners_gone(listeners)
    finally:
        _stdout, _stderr, _survivors = finish_owned_process(process, known_pids, whole_group=True)


def verify_real_nginx_port_collision(args, output, private_parent):
    requests = []

    class ForeignHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            body = b"foreign listener"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            return

    foreign = ThreadingHTTPServer(("127.0.0.1", 0), ForeignHandler)
    foreign_thread = threading.Thread(target=foreign.serve_forever, daemon=True)
    foreign_thread.start()
    port = foreign.server_address[1]
    try:
        result = subprocess.run(
            launcher_command(args, port), cwd=output,
            env=dict(os.environ, TMPDIR=str(private_parent)),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            timeout=12, check=False,
        )
        if result.returncode == 0:
            raise AssertionError("real nginx launcher adopted an occupied loopback port")
        if "Traceback" in result.stdout + result.stderr:
            raise AssertionError("real nginx port collision printed a traceback")
        if "/setup/" in result.stdout or "/#/design-preview" in result.stdout:
            raise AssertionError("launcher announced readiness for a foreign HTTP server")
        if requests:
            raise AssertionError("launcher sent a readiness probe to the pre-existing listener")
        status, _headers, body = raw_http(port, "/setup/")
        if status != 200 or body != b"foreign listener":
            raise AssertionError("launcher changed the active foreign HTTP service")
        if requests != ["/setup/"]:
            raise AssertionError("foreign HTTP service did not remain independently usable")
    finally:
        foreign.shutdown()
        foreign.server_close()
        foreign_thread.join(timeout=2)
    if list(private_parent.iterdir()):
        raise AssertionError("real nginx port collision leaked private files")


def verify_dollar_temp_path(args, output):
    private_parent = output / "private-$server_port"
    private_parent.mkdir(mode=0o700)
    port = free_port()
    process = subprocess.Popen(launcher_command(args, port), cwd=output,
                               env=dict(os.environ, TMPDIR=str(private_parent)),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        _stdout, _stderr, _survivors = finish_owned_process(process, [process.pid], whole_group=True)
        raise AssertionError("dollar-path launch exceeded its rejection deadline") from None
    combined = stdout + stderr
    if process.returncode == 0 or "Traceback" in combined:
        raise AssertionError("dollar-bearing nginx root path was not rejected safely")
    if str(private_parent) in combined or "/setup/" in stdout or "/#/design-preview" in stdout:
        raise AssertionError("dollar-path rejection leaked a path or announced readiness")
    if list(private_parent.iterdir()):
        raise AssertionError("dollar-path rejection leaked private files")
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise AssertionError("dollar-path rejection left an outer listener")


def verify_quoted_temp_path(args, output):
    private_parent = output / "private ' path with spaces"
    private_parent.mkdir(mode=0o700)
    port = free_port()
    process = subprocess.Popen(launcher_command(args, port), cwd=output,
                               env=dict(os.environ, TMPDIR=str(private_parent)),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    known_pids = [process.pid]
    listeners = set()
    ready_output = ""
    try:
        try:
            ready_output = wait_for_ready(process, port, time.monotonic() + 15)
            ready = True
        except AssertionError:
            ready = False
        known_pids = owned_process_ids(process)
        listeners = loopback_listeners_for(process)
        if ready:
            _stdout, _stderr, survivors = finish_owned_process(
                process, known_pids, signum=signal.SIGTERM)
            if process.returncode != 0 or survivors:
                raise AssertionError("quoted private path did not shut down cleanly")
        else:
            if process.poll() is None or process.returncode == 0:
                raise AssertionError("quoted path was neither served nor rejected promptly")
            if listeners:
                raise AssertionError("quoted path was rejected after opening a listener")
        if list(private_parent.iterdir()):
            raise AssertionError("quoted-path launch leaked private files")
        assert_listeners_gone(listeners)
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                raise AssertionError("quoted-path launch left its outer listener behind")
    finally:
        stdout, stderr, _survivors = finish_owned_process(process, known_pids, whole_group=True)
        if str(private_parent) in ready_output + stdout + stderr:
            raise AssertionError("quoted-path launch exposed its private path")


def run_primary_acceptance(args, output, process, port, checks):
    ready_output = wait_for_ready(process, port, time.monotonic() + 15)
    checks.append("flushed setup and React URLs precede successful setup response")
    listeners = loopback_listeners_for(process)
    if not any(item[2] == port for item in listeners):
        raise AssertionError("actual nginx listener is not owned by the launcher process tree")
    if not any(item[2] != port for item in listeners):
        raise AssertionError("I01a upstream listener is not owned by the launcher process tree")
    checks.append("owned nginx and in-process I01a listeners observed")
    verify_http_matrix(port)
    checks.append("strict Host/Origin, method, traversal and unknown-route HTTP matrix")
    browser_requests = verify_browser(args, port, output)
    checks.append("Chromium setup facts, React preview, same-origin requests, no page errors")
    return ready_output, listeners, browser_requests


def verify_primary_shutdown(args, output, private_parent, archive_bytes, manifest_bytes,
                            sentinel, process, known_pids, listeners, ready_output, port):
    stdout, stderr, survivors = finish_owned_process(
        process, known_pids, signum=signal.SIGTERM)
    if process.returncode != 0 or survivors:
        raise AssertionError("launcher did not stop its owned processes cleanly on SIGTERM")
    expected_setup = "http://127.0.0.1:{}/setup/".format(port)
    if expected_setup not in ready_output or "/#/design-preview" not in ready_output:
        raise AssertionError("launcher did not publish both ready URLs before readiness")
    combined_output = ready_output + stdout + stderr
    private_paths = (str(Path(args.archive).resolve()), str(Path(args.manifest).resolve()), str(output))
    if any(path in combined_output for path in private_paths):
        raise AssertionError("launcher printed a private filesystem path")
    if sentinel.read_bytes() != b"leave this file alone":
        raise AssertionError("launcher changed a foreign sentinel")
    if list(private_parent.iterdir()):
        raise AssertionError("launcher left private stage or nginx files behind")
    if Path(args.archive).read_bytes() != archive_bytes or Path(args.manifest).read_bytes() != manifest_bytes:
        raise AssertionError("launcher changed caller bundle inputs")
    assert_listeners_gone(listeners)
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise AssertionError("launcher listener remained after shutdown")


def run_lifecycle_acceptance(args, output, private_parent, checks):
    verify_real_nginx_port_collision(args, output, private_parent)
    checks.append("real nginx rejected an occupied port without affecting its owner")
    verify_dollar_temp_path(args, output)
    checks.append("real nginx launch rejected a variable-bearing private path before listeners")
    verify_signal_cleanup(args, output, private_parent, signal.SIGINT)
    checks.append("Ctrl-C stopped owned process and both listeners")
    verify_signal_cleanup(args, output, private_parent, signal.SIGTERM)
    checks.append("SIGTERM stopped owned process and both listeners")
    verify_nginx_child_exit(args, output, private_parent)
    checks.append("unexpected nginx exit stopped launcher and I01a listener")
    verify_quoted_temp_path(args, output)
    checks.append("quoted private path safely served or failed before opening listeners")


def integration(args):
    """Run actual bundle, nginx, HTTP and Chromium checks used by the workflow."""
    required = (args.archive, args.manifest, args.repository, args.commit,
                args.nginx_binary, args.output_dir)
    if any(value is None for value in required):
        raise SystemExit("integration mode requires archive, manifest, identity, nginx and output")
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    sentinel = output / "foreign-sentinel.txt"
    sentinel.write_bytes(b"leave this file alone")
    private_parent = output / "private-parent"
    private_parent.mkdir()
    private_parent.chmod(0o700)
    archive_bytes = Path(args.archive).read_bytes()
    manifest_bytes = Path(args.manifest).read_bytes()
    port = free_port()
    child_env = dict(os.environ, TMPDIR=str(private_parent))
    try:
        process = subprocess.Popen(launcher_command(args, port), cwd=output, env=child_env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, start_new_session=True)
    except Exception as error:
        failure = {"status": "FAIL", "checks": [], "failure_type": type(error).__name__,
                   "failure_summary": "bootstrap acceptance could not start"}
        (output / "report.json").write_text(json.dumps(failure, indent=2), encoding="utf-8")
        raise
    checks = []
    known_pids = [process.pid]
    main_finished = False
    try:
        ready_output, listeners, browser_requests = run_primary_acceptance(
            args, output, process, port, checks)
        known_pids = owned_process_ids(process)
        verify_primary_shutdown(args, output, private_parent, archive_bytes, manifest_bytes,
                                sentinel, process, known_pids, listeners, ready_output, port)
        main_finished = True
        checks.append("SIGTERM stopped both owned listeners and preserved inputs/sentinel")
        run_lifecycle_acceptance(args, output, private_parent, checks)
        report = {"status": "PASS", "checks": checks, "browser_requests": browser_requests}
        (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    except Exception as error:
        failure = {"status": "FAIL", "checks": checks,
                   "failure_type": type(error).__name__, "failure_summary": "bootstrap acceptance failed"}
        (output / "report.json").write_text(json.dumps(failure, indent=2), encoding="utf-8")
        raise
    finally:
        if not main_finished:
            _stdout, _stderr, _survivors = finish_owned_process(process, known_pids, whole_group=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--integration", action="store_true")
    parser.add_argument("--archive")
    parser.add_argument("--manifest")
    parser.add_argument("--repository")
    parser.add_argument("--commit")
    parser.add_argument("--nginx-binary")
    parser.add_argument("--output-dir")
    args, unittest_args = parser.parse_known_args()
    if args.integration:
        integration(args)
    else:
        unittest.main(argv=[sys.argv[0]] + unittest_args)


if __name__ == "__main__":
    main()

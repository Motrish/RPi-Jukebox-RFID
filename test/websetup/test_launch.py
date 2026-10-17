"""Tests for the local bundle-backed developer launcher.

The real-browser acceptance path is intentionally explicit; normal unittest
discovery stays stdlib-only and quick.
"""

import argparse
import http.client
import importlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.parse import urlsplit

STAGE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STAGE_ROOT))

# Keep this import unconditional: publishing the phase-one tests must expose a
# missing launcher as a real collection error, never as a skip or fallback.
launch = importlib.import_module("installation.websetup.launch")  # noqa: E402,F401


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
            for extra in (["--document-root", temporary], ["--upstream", "127.0.0.1:1"],
                          ["--port", "80"], ["--port", "65536"], ["--port", "no"]):
                result = run_cli(self.base_args(temporary) + extra)
                self.assertNotEqual(result.returncode, 0, extra)
                self.assertNotIn("Traceback", result.stderr)

    def test_invalid_bundle_fails_before_requested_listener(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "bad.tar.gz"
            manifest = Path(temporary) / "bad.json"
            archive.write_bytes(b"not a bundle")
            manifest.write_text("{}", encoding="utf-8")
            port = free_port()
            result = run_cli(["--archive", str(archive), "--manifest", str(manifest),
                              "--repository", "Motrish/RPi-Jukebox-RFID",
                              "--commit", "a" * 40, "--port", str(port)])
            self.assertNotEqual(result.returncode, 0)
            combined = result.stdout + result.stderr
            self.assertNotIn("Traceback", combined)
            self.assertNotIn(str(archive), combined)
            self.assertNotIn("not a bundle", combined)
            with socket.socket() as probe:
                self.assertNotEqual(probe.connect_ex(("127.0.0.1", port)), 0)

    def test_missing_nginx_is_diagnosed_without_install_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = self.base_args(temporary)
            args.extend(["--nginx-binary", str(Path(temporary) / "no-nginx")])
            result = run_cli(args)
            self.assertNotEqual(result.returncode, 0)
            combined = result.stdout + result.stderr
            self.assertNotIn("Traceback", combined)
            self.assertNotIn("apt", combined.lower())

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
    for name, value in headers:
        connection.putheader(name, value)
    connection.endheaders()
    response = connection.getresponse()
    result = response.status, response.getheaders(), response.read()
    connection.close()
    return result


def wait_for_ready(process, port, deadline):
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError("launcher exited before readiness")
        try:
            status, _headers, _body = raw_http(port, "/")
            if status < 500:
                return
        except OSError:
            pass
        time.sleep(0.05)
    raise AssertionError("launcher did not become ready before deadline")


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
        ("/admin", [("Host", good)], "GET", (400, 404)),
        ("/rpc", [("Host", good)], "GET", (400, 404)),
        ("/ws", [("Host", good)], "GET", (400, 404)),
        ("/logs", [("Host", good)], "GET", (400, 404)),
        ("/setup/", [("Host", good)], "POST", (405,)),
        ("/../etc/passwd", [("Host", good)], "GET", (400, 404)),
        ("/%2e%2e/etc/passwd", [("Host", good)], "GET", (400, 404)),
    ]
    for target, headers, method, accepted in cases:
        status, _response_headers, body = raw_http(port, target, headers, method)
        if status not in accepted:
            raise AssertionError("unexpected HTTP status for {}: {}".format(target, status))
        if target.startswith(("/unknown", "/admin")) and b"<html" in body.lower():
            raise AssertionError("unknown route returned SPA HTML")
        if target == "/api/preflight" and status == 200:
            payload = json.loads(body)
            if payload.get("schema") != "websetup.preflight.v1" or "facts" not in payload:
                raise AssertionError("preflight response did not contain I01a facts")


def verify_browser(port, output):
    from playwright.sync_api import sync_playwright

    observed = []
    blocked = []
    page_errors = []
    static_mimes = []
    origin = "http://127.0.0.1:{}".format(port)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_init_script("Object.defineProperty(navigator, 'language', {get: () => 'de'});"
                                "Object.defineProperty(navigator, 'languages', {get: () => ['de','en']});")

        def route_request(route):
            parsed = urlsplit(route.request.url)
            same = "{}://{}".format(parsed.scheme, parsed.netloc) == origin
            allowed = same and route.request.method == "GET" and not parsed.query and (
                parsed.path in ("/", "/index.html", "/favicon.ico", "/logo192.png", "/manifest.json",
                                "/locales/de/translation.json", "/locales/en/translation.json")
                or same and route.request.method == "GET" and parsed.path.startswith("/static/"))
            if allowed:
                observed.append(parsed.path)
                route.continue_()
            else:
                blocked.append(parsed.scheme + "://" + parsed.netloc + parsed.path[:100])
                route.abort()

        context.route("**/*", route_request)
        page = context.new_page()
        page.on("pageerror", lambda error: page_errors.append(type(error).__name__))
        page.on("response", lambda response: static_mimes.append(
            (urlsplit(response.url).path, response.headers.get("content-type", ""))
        ) if "/static/" in urlsplit(response.url).path else None)
        page.goto(origin + "/setup/", wait_until="networkidle", timeout=10000)
        if page.locator("body").inner_text().strip() == "":
            raise AssertionError("I01a setup page rendered no content")
        page.get_by_text("Systemdaten", exact=False).wait_for(timeout=5000)
        page.goto(origin + "/#/design-preview", wait_until="networkidle", timeout=10000)
        if page.locator("#root").evaluate("element => element.children.length") < 1:
            raise AssertionError("React design-preview route rendered an empty root")
        if blocked or page_errors:
            raise AssertionError("browser blocked requests or errors: {} {}".format(blocked, page_errors))
        if not observed:
            raise AssertionError("browser did not load same-origin bundle assets")
        if "/api/preflight" not in observed:
            raise AssertionError("browser did not fetch the redacted I01a report")
        if not any(path.endswith(".js") and "javascript" in mime for path, mime in static_mimes):
            raise AssertionError("React JavaScript asset had no JavaScript MIME type")
        page.screenshot(path=str(output / "bootstrap-browser.png"), full_page=True)
        browser.close()
    return len(observed)


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


def verify_signal_cleanup(args, output, private_parent, signum):
    port = free_port()
    process = subprocess.Popen(launcher_command(args, port), cwd=output,
                               env=dict(os.environ, TMPDIR=str(private_parent)),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    wait_for_ready(process, port, time.monotonic() + 15)
    if signum == signal.SIGINT:
        os.killpg(process.pid, signum)
    else:
        process.send_signal(signum)
    process.communicate(timeout=8)
    if process.returncode != 0:
        raise AssertionError("launcher did not stop cleanly for signal {}".format(signum))
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise AssertionError("launcher listener remained after signal shutdown")
    if list(private_parent.iterdir()):
        raise AssertionError("signal shutdown leaked private files")


def verify_nginx_child_exit(args, output, private_parent):
    port = free_port()
    process = subprocess.Popen(launcher_command(args, port), cwd=output,
                               env=dict(os.environ, TMPDIR=str(private_parent)),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    wait_for_ready(process, port, time.monotonic() + 15)
    children = process_descendants(process.pid)
    if not children:
        raise AssertionError("launcher had no owned nginx child to stop in the fixture")
    os.kill(children[-1], signal.SIGKILL)
    process.communicate(timeout=8)
    if process.returncode == 0:
        raise AssertionError("launcher did not report unexpected nginx exit")
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise AssertionError("preflight listener remained after nginx exit")
    if list(private_parent.iterdir()):
        raise AssertionError("nginx child exit leaked private files")


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
    process = subprocess.Popen(launcher_command(args, port), cwd=output, env=child_env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    checks = []
    captured = ""
    captured_stderr = ""
    try:
        wait_for_ready(process, port, time.monotonic() + 15)
        checks.append("own launcher readiness")
        verify_http_matrix(port)
        checks.append("strict Host/Origin, method, traversal and unknown-route HTTP matrix")
        browser_requests = verify_browser(port, output)
        checks.append("Chromium setup facts, React preview, same-origin requests, no page errors")
        report = {"status": "PASS", "checks": checks, "browser_requests": browser_requests}
        (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            try:
                captured, captured_stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                captured, captured_stderr = process.communicate(timeout=2)
    if process.returncode != 0:
        raise AssertionError("launcher did not stop cleanly on SIGTERM")
    if "http://127.0.0.1:{}/setup/".format(port) not in captured or "/#/design-preview" not in captured:
        raise AssertionError("launcher did not print both ready URLs")
    combined_output = captured + captured_stderr
    for private_path in (str(Path(args.archive).resolve()), str(Path(args.manifest).resolve()), str(output)):
        if private_path in combined_output:
            raise AssertionError("launcher printed a private filesystem path")
    if sentinel.read_bytes() != b"leave this file alone":
        raise AssertionError("launcher changed a foreign sentinel")
    if list(private_parent.iterdir()):
        raise AssertionError("launcher left private stage or nginx files behind")
    if Path(args.archive).read_bytes() != archive_bytes or Path(args.manifest).read_bytes() != manifest_bytes:
        raise AssertionError("launcher changed caller bundle inputs")
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise AssertionError("launcher listener remained after shutdown")
    verify_signal_cleanup(args, output, private_parent, signal.SIGINT)
    verify_signal_cleanup(args, output, private_parent, signal.SIGTERM)
    verify_nginx_child_exit(args, output, private_parent)


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

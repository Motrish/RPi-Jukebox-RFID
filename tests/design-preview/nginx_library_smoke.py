#!/usr/bin/env python3
"""Exercise the built library through an isolated, real nginx process."""

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright


CODE = "x01-nginx-test-0123456789012345678901234567"
ASSET_ROOT = {
    "/", "/index.html", "/favicon.ico", "/logo192.png", "/manifest.json",
    "/locales/de/translation.json", "/locales/en/translation.json",
}
TEMPLATE_TOKENS = {
    "@@X01_LISTEN_PORT@@", "@@X01_BUILD_ROOT@@", "@@X01_BACKEND_PORT@@",
}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def nginx_quote(value):
    return '"{}"'.format(value.replace("\\", "\\\\").replace('"', '\\"'))


def fixture_catalog(temp_path):
    source_root = Path(__file__).resolve().parents[2] / "src" / "jukebox"
    sys.path.insert(0, str(source_root))
    from components.library_catalog import LibraryCatalog
    from components.library_catalog import catalog as catalog_module
    from components.library_api import make_read_authorizer, make_server

    root = temp_path / "audio"
    root.mkdir()
    store = temp_path / "catalog.sqlite3"
    paths = ["same-a/same.mp3", "same-b/same.mp3"]
    paths.extend("album-{0:02d}/track-{0:02d}.mp3".format(index) for index in range(19))
    paths.extend(["long/" + "é" * 90 + ".mp3", "removed.mp3"])
    catalog = LibraryCatalog(store, root)
    ids = {}
    fixture_ids = [SimpleNamespace(hex="{:032x}".format(index))
                   for index in range(1, len(paths) + 1)]
    with patch.object(catalog_module.uuid, "uuid4", side_effect=fixture_ids):
        for relative in paths:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"synthetic audio fixture")
            ids[relative] = catalog.register_file(relative)["libraryId"]
    (root / "removed.mp3").unlink()

    counters = {"arrivals": 0, "authorization": 0, "list": 0, "detail": 0}
    switches = {"clock": 0, "fail_list": False}
    original_list = catalog.list_media
    original_detail = catalog.get_media

    def counted_list(*args, **kwargs):
        counters["list"] += 1
        if switches["fail_list"]:
            raise RuntimeError("synthetic catalog failure")
        return original_list(*args, **kwargs)

    def counted_detail(*args, **kwargs):
        counters["detail"] += 1
        return original_detail(*args, **kwargs)

    catalog.list_media = counted_list
    catalog.get_media = counted_detail
    authorizer = make_read_authorizer(CODE, clock=lambda: switches["clock"])

    def counted_authorizer(credential):
        counters["authorization"] += 1
        return authorizer(credential)

    backend = make_server(catalog, counted_authorizer, 0)
    base_handler = backend.RequestHandlerClass

    class ObservedHandler(base_handler):
        def handle_one_request(self):
            counters["arrivals"] += 1
            super().handle_one_request()

    backend.RequestHandlerClass = ObservedHandler
    thread = threading.Thread(target=backend.serve_forever, daemon=True)
    thread.start()
    expected = catalog.list_media(limit=50)["items"]
    require(len(expected) == len(paths), "catalog fixture setup failed")
    return catalog, backend, thread, counters, switches, expected, ids


def reserve_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def render_template(template, build_root, outer_port, backend_port, destination):
    source = template.read_text(encoding="utf-8")
    require(all(source.count(token) == 1 for token in TEMPLATE_TOKENS),
            "nginx template must contain each named X01 parameter exactly once")
    rendered = source
    values = {
        "@@X01_LISTEN_PORT@@": str(outer_port),
        "@@X01_BUILD_ROOT@@": nginx_quote(str(build_root)),
        "@@X01_BACKEND_PORT@@": str(backend_port),
    }
    for token, value in values.items():
        rendered = rendered.replace(token, value)
    require(not any(token in rendered for token in TEMPLATE_TOKENS),
            "nginx template contains an unrendered X01 parameter")
    destination.write_text(rendered, encoding="utf-8")


def wait_for_nginx(process, port, log_file):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError("nginx exited during startup; see the test output artifact")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    log_file.flush()
    raise AssertionError("nginx did not accept loopback connections within 5 seconds")


class NginxProcess:
    def __init__(self, executable, template, build_root, backend_port, work):
        self.executable = executable
        self.template = template
        self.build_root = build_root
        self.backend_port = backend_port
        self.work = work
        self.port = reserve_port()
        self.prefix = work / "nginx-prefix"
        self.prefix.mkdir()
        (self.prefix / "logs").mkdir()
        self.config = work / "nginx.conf"
        render_template(template, build_root, self.port, backend_port, self.config)
        self.output = open(work / "nginx-output.log", "w", encoding="utf-8")
        self.process = None
        self.url = "http://127.0.0.1:{}/".format(self.port)

    def __enter__(self):
        checked = subprocess.run(
            [self.executable, "-t", "-p", str(self.prefix) + "/", "-c", str(self.config)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=8,
            check=False,
        )
        if checked.returncode != 0:
            self.output.close()
            raise AssertionError(
                "nginx -t rejected the exact rendered config: {}".format(
                    checked.stdout[-2000:]
                )
            )
        version = subprocess.run(
            [self.executable, "-v"], stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, timeout=3, check=False,
        )
        require(version.returncode == 0, "nginx -v failed")
        self.version = version.stdout.strip()
        self.process = subprocess.Popen(
            [self.executable, "-p", str(self.prefix) + "/", "-c", str(self.config),
             "-g", "daemon off;"],
            stdin=subprocess.DEVNULL, stdout=self.output, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            wait_for_nginx(self.process, self.port, self.output)
        except Exception:
            self.stop()
            self.output.close()
            raise
        return self

    def __exit__(self, _type, _value, _traceback):
        self.stop()
        self.output.close()

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        self.output.close()


def raw_request(port, method, target, headers=(), http_version="1.1", timeout=4):
    lines = ["{} {} HTTP/{}".format(method, target, http_version)]
    lines.extend("{}: {}".format(name, value) for name, value in headers)
    request = ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as connection:
        connection.settimeout(timeout)
        connection.sendall(request)
        chunks = []
        while True:
            try:
                chunk = connection.recv(65536)
            except socket.timeout:
                raise AssertionError("HTTP response stalled beyond socket timeout") from None
            if not chunk:
                break
            chunks.append(chunk)
    response = b"".join(chunks)
    head, separator, body = response.partition(b"\r\n\r\n")
    require(separator, "nginx returned an incomplete HTTP response")
    first, *header_lines = head.decode("latin-1").split("\r\n")
    match = re.match(r"HTTP/\d(?:\.\d)? ([0-9]{3})", first)
    require(match is not None, "nginx returned an invalid status line")
    parsed_headers = {}
    for line in header_lines:
        if ":" in line:
            key, value = line.split(":", 1)
            parsed_headers[key.lower()] = value.strip()
    return int(match.group(1)), parsed_headers, body


def headers_for(outer, code=CODE, origin=None):
    result = [("Host", outer)]
    if origin is not None:
        result.append(("Origin", origin))
    if code is not None:
        result.append(("Authorization", "Bearer " + code))
    return result


def assert_not_success(response, label):
    require(response[0] >= 400,
            "{} unexpectedly returned HTTP {}".format(label, response[0]))


def verify_http_surface(nginx, backend, counters, switches, ids):
    outer = urlparse(nginx.url).netloc
    origin = "http://" + outer
    before = dict(counters)
    status, response_headers, body = raw_request(
        nginx.port, "GET", "/api/library/media?limit=20",
        headers_for(outer, origin=origin),
    )
    require(status == 200 and "no-store" in response_headers.get("cache-control", ""),
            "valid list request did not return a no-store 200")
    first_page = json.loads(body)
    require(len(first_page["items"]) == 20, "nginx list response lost page-size semantics")
    require(counters["arrivals"] == before["arrivals"] + 1,
            "valid request did not reach the real API exactly once")
    require(counters["list"] == before["list"] + 1,
            "valid request did not reach the real catalog")

    detail_id = ids["same-a/same.mp3"]
    status, _, detail = raw_request(
        nginx.port, "GET", "/api/library/media/" + detail_id,
        headers_for(outer, origin=origin),
    )
    require(status == 200 and json.loads(detail)["libraryId"] == detail_id,
            "nginx detail request did not preserve the strict API route")

    status, _, absent_origin = raw_request(
        nginx.port, "GET", "/api/library/media?limit=20",
        headers_for(outer, origin=None),
    )
    require(status == 200 and json.loads(absent_origin)["items"],
            "absent Origin did not remain absent through nginx")

    before = dict(counters)
    long_target = "/api/library/media?limit=20&cursor=" + ("a" * 2100)
    assert_not_success(raw_request(nginx.port, "GET", long_target,
                                   headers_for(outer, origin=origin)),
                       "oversized request target")
    require(counters["authorization"] == before["authorization"]
            and counters["list"] == before["list"]
            and counters["detail"] == before["detail"],
            "oversized request target reached authorization or the catalog")
    before = dict(counters)
    huge_headers = headers_for(outer, origin=origin)
    huge_headers.append(("X-X01-Padding", "a" * 9000))
    assert_not_success(raw_request(nginx.port, "GET", "/api/library/media?limit=20",
                                   huge_headers), "oversized request header")
    require(counters["authorization"] == before["authorization"]
            and counters["list"] == before["list"]
            and counters["detail"] == before["detail"],
            "oversized request header reached authorization or the catalog")
    before = dict(counters)
    many_headers = headers_for(outer, origin=origin)
    many_headers.extend(("X-X01-Extra-{}".format(index), "x") for index in range(40))
    assert_not_success(raw_request(nginx.port, "GET", "/api/library/media?limit=20",
                                   many_headers), "too many request headers")
    require(counters["authorization"] == before["authorization"]
            and counters["list"] == before["list"]
            and counters["detail"] == before["detail"],
            "over-limit header count reached authorization or the catalog")

    before = dict(counters)
    for target, label in (
        ("/api/library/media%2Fanything?limit=20", "encoded slash"),
        ("/api/library/media?limit=20&bad=%", "invalid percent escape"),
        ("/api/library/media/%2e%2e/media?limit=20", "encoded dot segment"),
        ("/api/library/media/../media?limit=20", "dot segment"),
        ("/api//library/media?limit=20", "duplicate slash"),
        ("/api/library/media\\?limit=20", "backslash"),
        ("/api/library/media?limit=20&bad=%2F", "encoded query"),
        ("/api/library/media?limit=0", "out-of-range query"),
        ("/api/library/media?limit=20&limit=20", "duplicate query field"),
        ("/api/library/media/{}?limit=20".format(ids["same-a/same.mp3"]),
         "detail query"),
        ("http://127.0.0.1:{}/api/library/media?limit=20".format(nginx.port),
         "absolute-form target"),
        ("/api/unknown", "unknown API path"),
    ):
        response = raw_request(nginx.port, "GET", target,
                               headers_for(outer, origin=origin))
        assert_not_success(response, label)
    require(counters["arrivals"] == before["arrivals"]
            and counters["authorization"] == before["authorization"]
            and counters["list"] == before["list"]
            and counters["detail"] == before["detail"],
            "an invalid URI reached the backend, authorizer, or catalog")

    before = dict(counters)
    for method in ("HEAD", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"):
        response = raw_request(nginx.port, method, "/api/library/media?limit=20",
                               headers_for(outer, origin=origin))
        assert_not_success(response, method + " API method")
    require(counters["arrivals"] == before["arrivals"],
            "a non-GET request reached the API")

    for headers, version, label in (
        ([("Host", "elsewhere.invalid:{}".format(nginx.port)),
          ("Origin", origin), ("Authorization", "Bearer " + CODE)], "1.1", "foreign Host"),
        ([("Host", outer), ("Host", outer), ("Origin", origin),
          ("Authorization", "Bearer " + CODE)], "1.1", "duplicate Host"),
        ([("Host", ""), ("Origin", origin),
          ("Authorization", "Bearer " + CODE)], "1.1", "empty Host"),
        ([("Host", outer), ("Origin", "http://elsewhere.invalid"),
          ("Authorization", "Bearer " + CODE)], "1.1", "foreign Origin"),
        ([("Host", outer), ("Origin", origin), ("Origin", origin),
          ("Authorization", "Bearer " + CODE)], "1.1", "duplicate Origin"),
        ([("Host", outer), ("Origin", "HTTP://" + outer),
          ("Authorization", "Bearer " + CODE)], "1.1", "case-changed Origin"),
    ):
        before_arrivals = counters["arrivals"]
        response = raw_request(nginx.port, "GET", "/api/library/media?limit=20",
                               headers, http_version=version)
        assert_not_success(response, label)
        require(counters["arrivals"] == before_arrivals,
                label + " reached the backend before rejection")

    before_arrivals = counters["arrivals"]
    assert_not_success(raw_request(nginx.port, "GET", "/api/library/media?limit=20",
                                   [("Authorization", "Bearer " + CODE)],
                                   http_version="1.0"), "missing HTTP/1.0 Host")
    require(counters["arrivals"] == before_arrivals,
            "missing HTTP/1.0 Host reached the backend")

    for origins, label in (
        ([""], "empty Origin"), (["  "], "whitespace Origin"),
        (["", ""], "duplicate empty Origin"), (["", origin], "mixed Origin values"),
        ([origin, ""], "mixed reverse Origin values"),
    ):
        before = dict(counters)
        request_headers = [("Host", outer)]
        request_headers.extend(("Origin", value) for value in origins)
        request_headers.append(("Authorization", "Bearer " + CODE))
        response = raw_request(nginx.port, "GET", "/api/library/media?limit=20",
                               request_headers)
        assert_not_success(response, label)
        require(counters["authorization"] == before["authorization"]
                and counters["list"] == before["list"]
                and counters["detail"] == before["detail"],
                label + " reached authorization or the catalog")
        if origins == [""] or origins == ["  "]:
            require(counters["arrivals"] == before["arrivals"] + 1,
                    label + " was not relayed unchanged to the real API")
        else:
            require(counters["arrivals"] == before["arrivals"],
                    label + " reached the backend despite being distinguishable")

    for code, expected_status, label in ((None, 401, "missing bearer"),
                                         ("invalid", 401, "invalid bearer")):
        response = raw_request(nginx.port, "GET", "/api/library/media?limit=20",
                               headers_for(outer, code=code, origin=origin))
        require(response[0] == expected_status, label + " did not retain API status")
    switches["clock"] = 900
    response = raw_request(nginx.port, "GET", "/api/library/media?limit=20",
                           headers_for(outer, origin=origin))
    require(response[0] == 401, "nginx path bypassed the real API token TTL")
    switches["clock"] = 0

    switches["fail_list"] = True
    response = raw_request(nginx.port, "GET", "/api/library/media?limit=20",
                           headers_for(outer, origin=origin))
    switches["fail_list"] = False
    require(response[0] == 503 and "application/json" in response[1].get("content-type", "")
            and "no-store" in response[1].get("cache-control", ""),
            "API failure lost its JSON 503/no-store contract through nginx")

    for path in ("/logs", "/rawRPC", "/api/", "/api/admin"):
        response = raw_request(nginx.port, "GET", path, [("Host", outer)])
        assert_not_success(response, path)
        require(b"<html" not in response[2].lower(), path + " returned SPA HTML")
    traversal = raw_request(nginx.port, "GET", "/%2e%2e/outside-build-secret.txt",
                            [("Host", outer)])
    assert_not_success(traversal, "build-root traversal")
    require(b"must-not-be-served" not in traversal[2],
            "static server exposed a file outside the fixed build root")

    direct = "127.0.0.1:{}".format(backend.server_address[1])
    before = counters["authorization"]
    response = raw_request(backend.server_address[1], "GET", "/api/library/media?limit=20",
                           [("Host", outer), ("Origin", origin),
                            ("Authorization", "Bearer " + CODE)])
    require(response[0] == 400 and counters["authorization"] == before,
            "direct API request accepted the frontend authority")
    response = raw_request(backend.server_address[1], "GET", "/api/library/media?limit=20",
                           [("Host", direct), ("Origin", origin),
                            ("Authorization", "Bearer " + CODE)])
    require(response[0] == 400 and counters["authorization"] == before,
            "direct API request accepted the frontend Origin")
    response = raw_request(backend.server_address[1], "GET", "/api/library/media?limit=20",
                           [("Host", direct), ("Authorization", "Bearer " + CODE)])
    require(response[0] == 200, "direct API strict backend authority check changed")
    require(not (nginx.prefix / "logs" / "access.log").exists(),
            "nginx wrote an access log for the local library site")


def install_browser_guards(context, origin, observed, blocked, sockets):
    def guard(route):
        request = route.request
        parsed = urlparse(request.url)
        same_origin = "{}://{}".format(parsed.scheme, parsed.netloc) == origin
        api = (request.method == "GET" and parsed.path == "/api/library/media"
               and set(dict(part.split("=", 1) for part in parsed.query.split("&") if "=" in part))
               <= {"limit", "cursor"})
        asset = request.method == "GET" and not parsed.query and (
            parsed.path in ASSET_ROOT or parsed.path.startswith("/static/"))
        if same_origin and (api or asset):
            if api:
                observed.append(parsed.path + "?" + parsed.query)
            route.continue_()
        else:
            blocked.append("{} {}".format(request.method, parsed.path[:160]))
            route.abort()

    context.route("**/*", guard)

    def reject_socket(ws):
        sockets.append(urlparse(ws.url).path[:160])
        ws.close(code=1000, reason="Forbidden")

    context.route_web_socket("**/*", reject_socket)


def verify_browser(nginx, output, expected, ids, backend, api_thread, counters):
    origin = nginx.url.rstrip("/")
    network = []
    blocked = []
    sockets = []
    page_errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 960})
        context.add_init_script(
            "Object.defineProperty(navigator, 'language', {get: () => 'de'});"
            "Object.defineProperty(navigator, 'languages', {get: () => ['de', 'en']});"
        )
        install_browser_guards(context, origin, network, blocked, sockets)
        page = context.new_page()
        page.set_default_timeout(10000)
        page.set_default_navigation_timeout(10000)
        page.on("pageerror", lambda error: page_errors.append(type(error).__name__))
        page.goto(origin + "/index.html#/design-preview/library", wait_until="networkidle")
        page.get_by_role("heading", name="Bibliothek").wait_for()
        code = page.get_by_label(re.compile("zugangscode", re.I))
        code.fill(CODE)
        code.press("Enter")
        first, second = expected[:20], expected[20:]
        expected_ids = [item["libraryId"] for item in first]
        expect(page.get_by_text(re.compile(r"^lib_[A-Za-z0-9_-]+$"), exact=True)).to_have_text(expected_ids)
        same_ids = {ids["same-a/same.mp3"], ids["same-b/same.mp3"]}
        require(page.get_by_text("same.mp3", exact=True).count()
                == sum(item["libraryId"] in same_ids for item in first),
                "browser lost deterministic duplicate-title catalog rows")
        page.get_by_role("button", name=re.compile("weiter", re.I)).click()
        expect(page.get_by_text(re.compile(r"^lib_[A-Za-z0-9_-]+$"), exact=True)).to_have_text(
            [item["libraryId"] for item in second]
        )
        missing_id = ids["removed.mp3"]
        require(page.locator(".library-row").filter(
            has=page.get_by_text(missing_id, exact=True)
        ).get_by_text("Fehlt", exact=True).count() == 1,
                "browser did not show the real MISSING catalog state")
        require(len(network) >= 2 and all(path.startswith("/api/library/media?") for path in network),
                "browser paging did not use the real same-origin nginx API route")
        require(not page_errors, "browser page errors: {}".format(page_errors))
        require(not blocked and not sockets,
                "browser attempted blocked HTTP/WebSocket traffic: {} {}".format(blocked, sockets))
        image = output / "nginx-library.png"
        page.screenshot(path=str(image), full_page=True)

        backend.shutdown()
        backend.server_close()
        api_thread.join(timeout=5)
        page.get_by_role("button", name="Aktualisieren").click()
        page.get_by_text("Die Bibliothek konnte nicht geladen werden. Bitte erneut versuchen.").wait_for()
        require(page.get_by_text(CODE, exact=True).count() == 0,
                "backend failure displayed the access code")
        require(not page_errors, "browser page errors after upstream failure: {}".format(page_errors))
        require(not blocked and not sockets,
                "browser attempted blocked HTTP/WebSocket traffic after upstream failure: {} {}"
                .format(blocked, sockets))
        page.close()
        context.close()
        browser.close()
    return len(network)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve-directory", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--nginx-template", default="resources/default-settings/nginx.library-loopback.conf")
    parser.add_argument("--nginx-binary")
    parser.add_argument("--emit-library-png-base64", action="store_true")
    args = parser.parse_args()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    template = Path(args.nginx_template).resolve()
    require(template.is_file(), "missing required nginx template: {}".format(template))
    executable = (str(Path(args.nginx_binary).resolve()) if args.nginx_binary
                  else shutil.which("nginx"))
    require(executable is not None, "nginx executable is required for the real-proxy smoke test")
    require(Path(executable).is_file() and os.access(executable, os.X_OK),
            "--nginx-binary must identify an executable nginx binary")
    build_root = Path(args.serve_directory).resolve(strict=True)
    require(build_root.is_dir() and (build_root / "index.html").is_file(),
            "--serve-directory must be a completed React build")

    with tempfile.TemporaryDirectory(prefix="x01-nginx-") as temporary:
        temp_path = Path(temporary)
        (temp_path / "outside-build-secret.txt").write_text("must-not-be-served", encoding="utf-8")
        catalog, backend, api_thread, counters, switches, expected, ids = fixture_catalog(temp_path)
        try:
            with NginxProcess(executable, template, build_root,
                              backend.server_address[1], temp_path) as nginx:
                verify_http_surface(nginx, backend, counters, switches, ids)
                browser_requests = verify_browser(
                    nginx, output, expected, ids, backend, api_thread, counters
                )
                report = {
                    "status": "PASS",
                    "nginx_version": nginx.version,
                    "checks": ["nginx -t exact rendered template", "strict proxy/header/URI rejection",
                               "same-origin browser catalog paging through real nginx",
                               "bounded stopped-upstream browser error"],
                    "browser_requests": browser_requests,
                    "api_observed_arrivals": counters["arrivals"],
                }
                (output / "report.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )
                print("PASS: real nginx library smoke; {}".format(nginx.version), flush=True)
        finally:
            if backend.fileno() != -1:
                backend.shutdown()
                backend.server_close()
            api_thread.join(timeout=5)
            catalog.close()


if __name__ == "__main__":
    main()

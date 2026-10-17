#!/usr/bin/env python3
"""Exercise the built library route against the real Linux catalog and API."""

import argparse
import base64
import json
import mimetypes
import re
import sys
import tempfile
import threading
from types import SimpleNamespace
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from playwright.sync_api import expect, sync_playwright


MARKER = "U03A2_LIBRARY_PNG_BASE64_BEGIN"
CODE = "u03-library-test-01234567890123456789012345"
ALLOWED_ROOT = {
    "/", "/index.html", "/favicon.ico", "/logo192.png", "/manifest.json",
    "/locales/de/translation.json", "/locales/en/translation.json",
}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def catalog_fixture(root, store):
    source_root = Path(__file__).resolve().parents[2] / "src" / "jukebox"
    sys.path.insert(0, str(source_root))
    from components.library_catalog import LibraryCatalog
    from components.library_catalog import catalog as catalog_module
    from components.library_api import make_read_authorizer, make_server

    root.mkdir()
    paths = ["same-a/same.mp3", "same-b/same.mp3"]
    paths.extend(f"album-{index:02d}/track-{index:02d}.mp3" for index in range(19))
    paths.extend(["\u9577\u3044\u540d\u524d/" + "\u00e9" * 90 + ".mp3", "z-removed.mp3"])
    catalog = LibraryCatalog(store, root)
    path_ids = {}
    fixture_uuids = [SimpleNamespace(hex=f"{index:032x}") for index in range(1, len(paths) + 1)]
    with patch.object(catalog_module.uuid, "uuid4", side_effect=fixture_uuids):
        for relative in paths:
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"test audio metadata only")
            path_ids[relative] = catalog.register_file(relative)["libraryId"]
    (root / "z-removed.mp3").unlink()
    expected_items = catalog.list_media(limit=50)["items"]
    expected_ids = [f"lib_{index:032x}" for index in range(1, len(paths) + 1)]
    require([record["libraryId"] for record in expected_items] == expected_ids,
            "catalog fixture IDs or sort order changed")
    backend = make_server(catalog, make_read_authorizer(CODE), 0)
    thread = threading.Thread(target=backend.serve_forever, daemon=True)
    thread.start()
    return catalog, backend, thread, expected_items, path_ids


def build_assets(directory):
    root = Path(directory).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("build directory is not a directory")
    assets = {}
    for path in root.rglob("*"):
        if path.is_file():
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(root):
                raise ValueError("build contains an asset outside its root")
            relative = "/" + resolved.relative_to(root).as_posix()
            if relative.startswith("/static/") or relative in ALLOWED_ROOT:
                assets[relative] = resolved
    if "/index.html" not in assets:
        raise ValueError("build index.html is missing")
    return assets


class LibraryProxyHandler(BaseHTTPRequestHandler):
    """Handle the single catalog endpoint and fixed build asset list."""

    def log_message(self, _format, *_args):
        return

    def do_GET(self):
        owner = self.server.owner
        outer = f"127.0.0.1:{owner.server.server_address[1]}"
        if not valid_outer_headers(self, outer):
            self.send_error(400)
        elif is_api_request(self.path):
            self.forward_api()
        else:
            self.serve_asset()

    def serve_asset(self):
        asset = self.server.owner.assets.get(self.path)
        if asset is None:
            self.send_error(404)
            return
        body = asset.read_bytes()
        self.send_response(200)
        content_type = mimetypes.guess_type(str(asset))[0]
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def forward_api(self):
        owner = self.server.owner
        authorizations = self.headers.get_all("Authorization", [])
        if authorizations != [f"Bearer {CODE}"]:
            self.send_error(400)
            return
        owner.proxy_requests.append(self.path)
        target = owner.backend + self.path
        # Relay the exact browser-supplied value after restricting the fixture credential.
        headers = {"Host": owner.backend_authority, "Authorization": authorizations[0]}
        if self.headers.get("Origin"):
            headers["Origin"] = owner.backend
        try:
            with urlopen(Request(target, headers=headers), timeout=8) as response:
                body = response.read(300000)
                status = response.status
                content_type = response.headers.get("Content-Type", "application/json")
        except HTTPError as error:
            with error:
                body = error.read(300000)
                status = error.code
                content_type = error.headers.get("Content-Type", "application/json")
        except Exception:
            self.send_error(502)
            return
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class LocalServers:
    """Serve allowlisted assets and one fixed, same-origin API proxy route."""

    def __init__(self, build, backend):
        self.assets = build_assets(build)
        self.backend = f"http://127.0.0.1:{backend.server_address[1]}"
        self.backend_authority = urlparse(self.backend).netloc
        self.proxy_requests = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), LibraryProxyHandler)
        self.server.owner = self
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/index.html"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, _type, _value, _traceback):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def valid_outer_headers(handler, outer):
    hosts = handler.headers.get_all("Host", [])
    origins = handler.headers.get_all("Origin", [])
    return hosts == [outer] and len(origins) <= 1 and (
        not origins or origins == [f"http://{outer}"]
    )


def is_api_request(path):
    pattern = r"/api/library/media\?limit=20(?:&cursor=[A-Za-z0-9_-]{1,128})?"
    return re.fullmatch(pattern, path) is not None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve-directory", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--emit-library-png-base64", action="store_true")
    args = parser.parse_args()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="u03a2-library-") as temp:
        temp_path = Path(temp)
        catalog, backend, api_thread, expected_items, path_ids = catalog_fixture(
            temp_path / "audio", temp_path / "catalog.sqlite3"
        )
        try:
            with LocalServers(args.serve_directory, backend) as servers:
                run_browser(
                    servers, output, args.emit_library_png_base64, expected_items, path_ids
                )
                require(len(servers.proxy_requests) >= 2,
                        "successful browser paging did not reach the real API twice")
        finally:
            backend.shutdown()
            backend.server_close()
            api_thread.join(timeout=5)
            catalog.close()


def verify_no_secret_persistence_source():
    component_dir = Path(__file__).resolve().parents[2] / "src/webapp/src/components/DesignPreview"
    forbidden = re.compile(r"\b(?:localStorage|sessionStorage)\b|document\s*\.\s*cookie")
    for name in ("LibraryPage.js", "libraryClient.js"):
        source = (component_dir / name).read_text(encoding="utf-8")
        require(forbidden.search(source) is None,
                f"secret-persistence API appears in {name}")


CONTROLLED_FETCH = r"""
(() => {
  window.__u03Case = "normal";
  window.__u03Calls = 0;
  const json = (status, value) => new Response(JSON.stringify(value), {
    status, headers: { "Content-Type": "application/json" }
  });
  const success = (id, title) => json(200, {
    items: [{ libraryId: id, displayName: title, availability: "AVAILABLE" }],
    nextCursor: null
  });
  const originalFetch = window.fetch.bind(window);
  window.fetch = (input, init) => {
    const requestUrl = input instanceof Request ? input.url : String(input);
    const url = new URL(requestUrl, location.href);
    if (url.pathname !== "/api/library/media") return originalFetch(input, init);
    const mode = window.__u03Case;
    const call = ++window.__u03Calls;
    if (mode === "loading") {
      return new Promise(resolve => setTimeout(
        () => resolve(success("lib_load", "Geladener Testtitel.mp3")), 700
      ));
    }
    if (mode === "empty") return json(200, { items: [], nextCursor: null });
    if (mode === "unauthorized") return json(401, { error: { secret: "never display" } });
    if (mode === "not-found") return json(404, { error: { secret: "never display" } });
    if (mode === "unavailable") return json(503, { error: { secret: "never display" } });
    if (mode === "malformed") return new Response("not-json", {
      status: 200, headers: { "Content-Type": "application/json" }
    });
    if (mode === "first-then-unauthorized") {
      return call === 1
        ? success("lib_before_401", "Zugriff vor 401.mp3")
        : json(401, { error: { secret: "never display" } });
    }
    if (mode === "late-after-forget") {
      if (call === 1) return success("lib_initial", "Startzustand.mp3");
      if (call === 2) return new Promise(resolve => setTimeout(
        () => resolve(success("lib_late", "Verspätete alte Antwort.mp3")), 700
      ));
      return success("lib_fresh", "Neue Freigabe.mp3");
    }
    return originalFetch(input, init);
  };
})();
"""


def install_network_guards(context, servers, blocked, sockets):
    origin = f"http://127.0.0.1:{servers.server.server_address[1]}"

    def network_guard(route):
        request = route.request
        parsed = urlparse(request.url)
        local = f"{parsed.scheme}://{parsed.netloc}" == origin
        api = (
            request.method == "GET"
            and is_api_request(parsed.path + ("?" + parsed.query if parsed.query else ""))
        )
        asset = request.method == "GET" and not parsed.query and parsed.path in servers.assets
        if local and (api or asset):
            route.continue_()
        else:
            blocked.append(f"{request.method} {parsed.netloc}{parsed.path}")
            route.abort()

    def reject_socket(route):
        parsed = urlparse(route.url)
        sockets.append(f"{parsed.netloc}{parsed.path}")
        route.close(code=1000, reason="Unexpected WebSocket in library preview")

    context.route("**/*", network_guard)
    context.route_web_socket("**/*", reject_socket)


def watch_page(page, page_errors, protocol_errors):
    page.set_default_timeout(10000)
    page.set_default_navigation_timeout(10000)
    page.on("pageerror", lambda error: page_errors.append(type(error).__name__))
    page.on(
        "console",
        lambda message: protocol_errors.append("console-error")
        if message.type == "error" else None,
    )
    page.on(
        "requestfailed",
        lambda request: protocol_errors.append(f"request-failed:{request.method}"),
    )


def verify_catalog_page(page, expected):
    ids = page.get_by_text(re.compile(r"^lib_[A-Za-z0-9_-]+$"), exact=True)
    expected_ids = [record["libraryId"] for record in expected]
    expect(ids).to_have_text(expected_ids, timeout=10000)
    labels = {"AVAILABLE": "Vorhanden", "MISSING": "Fehlt", "UNKNOWN": "Unbekannt"}
    for availability, label in labels.items():
        expected_count = sum(record["availability"] == availability for record in expected)
        require(page.get_by_text(label, exact=True).count() == expected_count,
                f"unexpected {availability} status count")
    for record in expected:
        require(page.get_by_text(record["displayName"], exact=True).count() >= 1,
                f"catalog title missing for {record['libraryId']}")


def run_real_catalog_check(context, servers, output, emit_png, report, expected_items, path_ids):
    page = context.new_page()
    try:
        requests_before_route = len(servers.proxy_requests)
        page.goto(f"{servers.url}#/design-preview/library", wait_until="networkidle")
        page.get_by_role("heading", name="Bibliothek").wait_for()
        require(len(servers.proxy_requests) == requests_before_route,
                "library API was requested before code submission")
        page.screenshot(path=str(output / "library-code-empty-desktop.png"), full_page=True)
        code_input = page.get_by_label(re.compile("zugangscode", re.I))
        code_input.fill(CODE)
        code_input.press("Enter")

        first, second = expected_items[:20], expected_items[20:]
        verify_catalog_page(page, first)
        same_ids = {path_ids["same-a/same.mp3"], path_ids["same-b/same.mp3"]}
        missing_id = path_ids["z-removed.mp3"]
        missing = next(record for record in expected_items if record["libraryId"] == missing_id)
        require(len(first) == 20 and missing["availability"] == "MISSING",
                "fixture does not contain 20 items and one registered missing file")
        first_same = sum(item["libraryId"] in same_ids for item in first)
        require(page.get_by_text("same.mp3", exact=True).count() == first_same,
                "first-page duplicate titles did not match their catalog IDs")

        page.get_by_role("button", name=re.compile("weiter", re.I)).click()
        verify_catalog_page(page, second)
        second_same = sum(item["libraryId"] in same_ids for item in second)
        require(page.get_by_text("same.mp3", exact=True).count() == second_same,
                "second-page duplicate titles did not match their catalog IDs")
        require(first_same + second_same == 2, "both same-named catalog files were not rendered")
        page.get_by_role("button", name=re.compile("zurück", re.I)).click()
        verify_catalog_page(page, first)
        report["checks"].append(
            "real entered code, browser/API/catalog paging, deterministic IDs, duplicate titles, MISSING"
        )

        for width in (1440, 1024, 768, 390, 320):
            page.set_viewport_size({"width": width, "height": 960})
            metrics = page.evaluate(
                "({width: document.documentElement.clientWidth, "
                "scroll: document.documentElement.scrollWidth})"
            )
            require(metrics["scroll"] <= metrics["width"], f"horizontal overflow at {width}px")
            if width in (1440, 390):
                shot = output / f"library-{width}.png"
                page.screenshot(path=str(shot), full_page=True)
                report["screenshots"].append(str(shot))
                if width == 1440 and emit_png:
                    encoded = base64.b64encode(shot.read_bytes()).decode("ascii")
                    require(len(encoded) <= 1_400_000, "review PNG exceeds log limit")
                    print(f"{MARKER} {encoded}", flush=True)

        page.set_viewport_size({"width": 390, "height": 844})
        page.get_by_role("button", name=re.compile("menü öffnen", re.I)).click()
        page.keyboard.press("Escape")
        require(page.locator(".menu-toggle").get_attribute("aria-expanded") == "false",
                "Escape did not close the mobile menu")
        page.get_by_role("button", name=re.compile("menü öffnen", re.I)).click()
        page.get_by_role("link", name="Musik", exact=True).click()
        page.get_by_role("heading", name="Musik").wait_for()
        page.get_by_role("button", name=re.compile("menü öffnen", re.I)).click()
        page.get_by_role("link", name="Bibliothek", exact=True).click()
        require(page.get_by_label(re.compile("zugangscode", re.I)).input_value() == "",
                "access code survived route unmount")
        require(page.get_by_text("same.mp3", exact=True).count() == 0,
                "catalog data survived route unmount")
        page.reload(wait_until="networkidle")
        require(page.get_by_label(re.compile("zugangscode", re.I)).input_value() == "",
                "access code survived reload")
        report["checks"].append("mobile keyboard close, route unmount, and reload cleanup")
    finally:
        page.close()


def open_controlled_page(context, servers, mode):
    page = context.new_page()
    page.add_init_script(CONTROLLED_FETCH)
    page.goto(f"{servers.url}#/design-preview/library", wait_until="networkidle")
    page.evaluate("caseName => { window.__u03Case = caseName; window.__u03Calls = 0; }", mode)
    page.get_by_label(re.compile("zugangscode", re.I)).fill(CODE)
    page.get_by_label(re.compile("zugangscode", re.I)).press("Enter")
    return page


def run_controlled_browser_cases(context, servers, report):
    page = open_controlled_page(context, servers, "loading")
    try:
        expect(page.get_by_role("status")).to_be_visible()
        expect(page.get_by_text("Geladener Testtitel.mp3", exact=True)).to_be_visible()
        report["controlled_checks"].append("Fetch-controlled loading then success")
    finally:
        page.close()

    page = open_controlled_page(context, servers, "empty")
    try:
        expect(page.get_by_text(re.compile("keine titel", re.I))).to_be_visible()
        report["controlled_checks"].append("Fetch-controlled empty catalog")
    finally:
        page.close()

    for mode in ("unauthorized", "not-found", "unavailable", "malformed"):
        page = open_controlled_page(context, servers, mode)
        try:
            expect(page.get_by_role("alert")).to_be_visible()
            require(page.get_by_text("never display", exact=True).count() == 0,
                    f"{mode} response leaked its body")
            report["controlled_checks"].append(f"Fetch-controlled {mode} error")
        finally:
            page.close()

    page = open_controlled_page(context, servers, "first-then-unauthorized")
    try:
        expect(page.get_by_text("Zugriff vor 401.mp3", exact=True)).to_be_visible()
        page.get_by_role("button", name=re.compile("aktualisieren", re.I)).click()
        expect(page.get_by_role("alert")).to_be_visible()
        require(page.get_by_text("Zugriff vor 401.mp3", exact=True).count() == 0,
                "401 left previously visible catalog data")
        require(page.get_by_label(re.compile("zugangscode", re.I)).input_value() == "",
                "401 left the access code in the form")
        report["controlled_checks"].append("Fetch-controlled 401 removes prior data and code")
    finally:
        page.close()

    page = open_controlled_page(context, servers, "late-after-forget")
    try:
        expect(page.get_by_text("Startzustand.mp3", exact=True)).to_be_visible()
        page.get_by_role("button", name=re.compile("aktualisieren", re.I)).click()
        page.get_by_role("button", name=re.compile("zugang vergessen", re.I)).click()
        code_input = page.get_by_label(re.compile("zugangscode", re.I))
        code_input.fill(CODE)
        code_input.press("Enter")
        expect(page.get_by_text("Neue Freigabe.mp3", exact=True)).to_be_visible()
        page.wait_for_timeout(850)
        require(page.get_by_text("Verspätete alte Antwort.mp3", exact=True).count() == 0,
                "late response restored data after forget and new code")
        expect(page.get_by_text("Neue Freigabe.mp3", exact=True)).to_be_visible()
        report["controlled_checks"].append(
            "Fetch-controlled late response cannot restore data after forget and new code"
        )
    finally:
        page.close()


def run_browser(servers, output, emit_png, expected_items, path_ids):
    report = {
        "status": "running", "checks": [], "controlled_checks": [],
        "screenshots": [], "api_paths": [],
    }
    blocked = []
    sockets = []
    page_errors = []
    protocol_errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = None
        try:
            context = browser.new_context(viewport={"width": 1440, "height": 960})
            install_network_guards(context, servers, blocked, sockets)
            context.on("page", lambda page: watch_page(page, page_errors, protocol_errors))
            verify_no_secret_persistence_source()
            report["checks"].append("product source has no browser storage or cookie API")
            run_real_catalog_check(
                context, servers, output, emit_png, report, expected_items, path_ids
            )
            run_controlled_browser_cases(context, servers, report)
            require(not blocked, "browser attempted a forbidden HTTP request")
            require(not sockets, "browser attempted a WebSocket")
            require(not page_errors, "browser raised an unexpected JavaScript exception")
            require(not protocol_errors, "browser emitted an unexpected protocol or console error")
            report["api_paths"] = servers.proxy_requests
            report["status"] = "passed"
        except Exception:
            report["status"] = "failed"
            (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            raise
        finally:
            if context is not None:
                try:
                    context.close()
                finally:
                    browser.close()
            else:
                browser.close()
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

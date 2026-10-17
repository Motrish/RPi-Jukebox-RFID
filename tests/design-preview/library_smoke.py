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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright


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
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "jukebox"))
    from jukebox.components.library_catalog import LibraryCatalog
    from jukebox.components.library_api import make_read_authorizer, make_server

    root.mkdir()
    paths = ["same-a/same.mp3", "same-b/same.mp3"]
    paths.extend(f"album-{index:02d}/track-{index:02d}.mp3" for index in range(19))
    paths.extend(["長い名前/" + "é" * 90 + ".mp3", "z-removed.mp3"])
    catalog = LibraryCatalog(store, root)
    for relative in paths:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"test audio metadata only")
        catalog.register_file(relative)
    (root / "z-removed.mp3").unlink()
    backend = make_server(catalog, make_read_authorizer(CODE), 0)
    thread = threading.Thread(target=backend.serve_forever, daemon=True)
    thread.start()
    return catalog, backend, thread


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
    pattern = r"/api/library/media\?limit=20(?:&cursor=[A-Za-z0-9_-]+)?"
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
        catalog, backend, api_thread = catalog_fixture(temp_path / "audio", temp_path / "catalog.sqlite3")
        try:
            with LocalServers(args.serve_directory, backend) as servers:
                run_browser(servers, output, args.emit_library_png_base64)
                require(len(servers.proxy_requests) >= 2,
                        "successful browser paging did not reach the real API twice")
        finally:
            backend.shutdown()
            backend.server_close()
            api_thread.join(timeout=5)
            catalog.close()


def run_browser(servers, output, emit_png):
    report = {"status": "running", "checks": [], "screenshots": [], "api_paths": []}
    origin = f"http://127.0.0.1:{servers.server.server_address[1]}"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 960})
        page = context.new_page()
        page.set_default_timeout(10000)
        page.set_default_navigation_timeout(10000)
        page_errors = []
        blocked = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))

        def network_guard(route):
            request = route.request
            parsed = urlparse(request.url)
            local = f"{parsed.scheme}://{parsed.netloc}" == origin
            api = parsed.path == "/api/library/media" and request.method == "GET"
            asset = parsed.path.startswith("/static/") or parsed.path in ALLOWED_ROOT
            if local and (api or asset):
                route.continue_()
            else:
                blocked.append(request.url)
                route.abort()

        page.route("**/*", network_guard)
        page.goto(f"{servers.url}#/design-preview/library", wait_until="networkidle")
        page.get_by_role("heading", name="Bibliothek").wait_for()
        page.screenshot(path=str(output / "library-code-empty-desktop.png"), full_page=True)
        code_input = page.get_by_label(re.compile("zugangscode", re.I))
        code_input.fill(CODE)
        code_input.press("Enter")
        page.get_by_text("Vorhanden", exact=True).wait_for()
        require(page.get_by_text(re.compile(r"^lib_[A-Za-z0-9_-]+$")).count() >= 20,
                "first page did not render at least 20 catalog entries")
        same_titles = page.get_by_text("same.mp3", exact=True).count()
        missing_statuses = page.get_by_text("Fehlt", exact=True).count()
        page.get_by_role("button", name=re.compile("weiter", re.I)).click()
        page.get_by_text("Seite 2", exact=False).wait_for()
        same_titles += page.get_by_text("same.mp3", exact=True).count()
        missing_statuses += page.get_by_text("Fehlt", exact=True).count()
        require(same_titles == 2, "same-named files were not both rendered over the two pages")
        require(missing_statuses == 1, "registered then removed file was not shown as missing")
        page.get_by_role("button", name=re.compile("zurück", re.I)).click()
        page.get_by_text("same.mp3", exact=True).wait_for()
        report["checks"].append(
            "entered code, real files/catalog/API, duplicate titles, missing status and paging"
        )

        for width in (1440, 768, 390, 320):
            page.set_viewport_size({"width": width, "height": 960})
            metrics = page.evaluate(
                "({width: document.documentElement.clientWidth, "
                "scroll: document.documentElement.scrollWidth})"
            )
            require(metrics["scroll"] <= metrics["width"], f"horizontal overflow at {width}px: {metrics}")
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
        page.get_by_role("link", name="Musik", exact=True).click()
        page.get_by_role("heading", name="Musik").wait_for()
        page.get_by_role("button", name=re.compile("menü öffnen", re.I)).click()
        page.get_by_role("link", name="Bibliothek", exact=True).click()
        code_input = page.get_by_label(re.compile("zugangscode", re.I))
        require(code_input.input_value() == "", "access code survived route unmount")
        require(page.get_by_text("same.mp3", exact=True).count() == 0,
                "catalog data survived route unmount")

        page.reload(wait_until="networkidle")
        require(page.get_by_label(re.compile("zugangscode", re.I)).input_value() == "",
                "access code survived reload")
        require(page.get_by_text("same.mp3", exact=True).count() == 0,
                "catalog data survived reload")
        require(not blocked, f"unexpected browser network requests: {blocked}")
        require(not page_errors, f"browser runtime errors: {page_errors}")
        report["checks"].append(
            "mobile route-change cleanup, empty form, no persistence, and same-origin GET-only network"
        )
        report["api_paths"] = servers.proxy_requests
        report["status"] = "passed"
        (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        context.close()
        browser.close()


if __name__ == "__main__":
    main()

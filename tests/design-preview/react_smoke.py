#!/usr/bin/env python3
"""Browser smoke checks for the built React design-preview route."""

import argparse
import base64
import json
import re
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright


ALLOWED_ROOT_PATHS = {
    "/",
    "/index.html",
    "/favicon.ico",
    "/logo192.png",
    "/manifest.json",
    "/locales/de/translation.json",
    "/locales/en/translation.json",
}
PNG_LOG_MARKER = "U02B_REACT_PREVIEW_PNG_BASE64_BEGIN"


class QuietHandler(SimpleHTTPRequestHandler):
    """Serve only the provided build directory without request logging."""

    def log_message(self, _format, *_args):
        pass


class LocalBuildServer:
    def __init__(self, directory):
        self.directory = Path(directory).resolve(strict=True)
        if not self.directory.is_dir():
            raise ValueError("--serve-directory must point to a directory")
        handler = lambda *args, **kwargs: QuietHandler(  # noqa: E731
            *args, directory=str(self.directory), **kwargs
        )
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/index.html"

    def __enter__(self):
        self.thread.start()
        return self.url

    def __exit__(self, _type, _value, _traceback):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the built React design preview in Chromium."
    )
    parser.add_argument("--url", help="Existing built-app URL; use with an external server.")
    parser.add_argument(
        "--serve-directory",
        help="Serve a CRA build directory on an ephemeral 127.0.0.1 port for this run.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/design-preview-react",
        help="Directory for screenshots and the JSON test report.",
    )
    parser.add_argument(
        "--emit-preview-png-base64",
        action="store_true",
        help="Emit one <=1 MB 1440px PNG as a marked Base64 log line for visual review.",
    )
    args = parser.parse_args()
    if bool(args.url) == bool(args.serve_directory):
        parser.error("provide exactly one of --url or --serve-directory")
    return args


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def preview_network_guard(page, base_url, report, block_websockets=True):
    origin = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"

    def inspect_request(route):
        parsed = urlparse(route.request.url)
        local = f"{parsed.scheme}://{parsed.netloc}" == origin
        known_asset = parsed.path.startswith("/static/") or parsed.path in ALLOWED_ROOT_PATHS
        if local and known_asset:
            report["http_requests"].append(route.request.url)
            route.continue_()
        else:
            report["blocked_requests"].append(route.request.url)
            route.abort()

    page.route("**/*", inspect_request)

    def reject_websocket(socket):
        report["websockets"].append(socket.url)
        socket.close(code=1000, reason="Preview transport is forbidden")

    if block_websockets:
        page.route_web_socket("**/*", reject_websocket)


def attach_browser_errors(page, report):
    page.on("pageerror", lambda error: report["page_errors"].append(str(error)))
    page.on(
        "console",
        lambda message: report["console_errors"].append(message.text)
        if message.type == "error"
        else None,
    )


def pin_test_locale(page):
    page.add_init_script(
        "Object.defineProperty(navigator, 'language', {get: () => 'de'});"
        "Object.defineProperty(navigator, 'languages', {get: () => ['de', 'en']});"
    )


def player_title(page):
    return page.locator(".player-copy strong").inner_text().strip()


def first_upcoming(page):
    return page.locator("#preview-queue li").first.inner_text().strip()


def assert_no_overflow(page):
    sizes = page.evaluate(
        "({width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth})"
    )
    require(sizes["scroll"] <= sizes["width"], f"Horizontal overflow: {sizes}")


def wait_for_focus(page, selector):
    try:
        page.wait_for_function(
            "selector => { const target = document.querySelector(selector); "
            "return Boolean(target) && document.activeElement === target; }",
            arg=selector,
            timeout=5000,
        )
    except PlaywrightTimeoutError as error:
        state = page.evaluate(
            "selector => ({active: document.activeElement?.outerHTML, "
            "target: document.querySelector(selector)?.outerHTML, "
            "sidebarClass: document.querySelector('#preview-sidebar')?.className, "
            "sidebarVisibility: getComputedStyle(document.querySelector('#preview-sidebar')).visibility, "
            "expanded: document.querySelector('.menu-toggle')?.getAttribute('aria-expanded')})",
            selector,
        )
        raise AssertionError(f"Focus did not reach {selector}; browser state: {state}") from error


def wait_for_menu_closed(page):
    page.wait_for_function(
        "document.querySelector('.menu-toggle')?.getAttribute('aria-expanded') === 'false'"
    )
    page.locator("#preview-sidebar").wait_for(state="hidden")


def wait_for_menu_open(page):
    page.wait_for_function(
        "document.querySelector('.menu-toggle')?.getAttribute('aria-expanded') === 'true'"
    )


def assert_preview_clean(report):
    require(not report["websockets"], f"Preview opened WebSockets: {report['websockets']}")
    require(not report["blocked_requests"],
            f"Preview attempted non-allowlisted HTTP requests: {report['blocked_requests']}")
    require(not report["console_errors"], f"Preview console errors: {report['console_errors']}")
    require(not report["page_errors"], f"Preview page errors: {report['page_errors']}")


def test_final_guard_detects_late_request(context, base_url):
    report = {
        "http_requests": [],
        "blocked_requests": [],
        "websockets": [],
        "console_errors": [],
        "page_errors": [],
    }
    page = context.new_page()
    pin_test_locale(page)
    attach_browser_errors(page, report)
    preview_network_guard(page, base_url, report)
    page.goto(f"{base_url}#/design-preview/start", wait_until="networkidle")
    page.locator(".design-preview").wait_for()
    parsed_base = urlparse(base_url)
    probe_url = f"{parsed_base.scheme}://{parsed_base.netloc}/api/__u02_late_guard_probe"
    result = page.evaluate(
        "url => fetch(url).then(() => 'unexpected').catch(() => 'blocked')",
        probe_url,
    )
    require(result == "blocked", "Late-guard probe was not blocked by the browser route")
    require(any("/__u02_late_guard_probe" in url for url in report["blocked_requests"]),
            "Late-guard probe was not recorded by the request guard")
    try:
        assert_preview_clean(report)
    except AssertionError as error:
        require("non-allowlisted HTTP requests" in str(error),
                f"Late-guard probe failed for an unrelated reason: {error}")
    else:
        raise AssertionError("Final preview guard accepted a forbidden late request")
    page.close()


def test_routes_brand_and_player(page, base_url):
    page.goto(f"{base_url}#/design-preview", wait_until="networkidle")
    page.locator(".design-preview").wait_for()
    require(
        page.get_by_role("note").filter(has_text="Designvorschau · Beispieldaten").count() == 1,
        "Preview banner is missing",
    )
    require(page.locator("#routes").count() == 0, "Legacy router mounted in preview boot")

    for label, heading in (
        ("Start", "Abend"),
        ("Musik", "Musik"),
        ("Spotify", "Spotify"),
        ("Playlists", "Playlists"),
        ("RFID", "RFID"),
        ("Akku & PiSugar", "Akku & PiSugar"),
        ("Einstellungen", "Einstellungen"),
    ):
        page.get_by_role("link", name=label, exact=True).click()
        page.get_by_role("heading", name=re.compile(re.escape(heading))).wait_for()

    page.get_by_role("link", name="Musik", exact=True).click()
    page.get_by_role("button", name=re.compile("Leise Wellen")).first.click()
    require(player_title(page) == "Leise Wellen", "Track selection did not update the preview player")

    for section in ("RFID", "Einstellungen"):
        page.get_by_role("link", name=section, exact=True).click()
        brand = page.get_by_role("link", name="Phoniebox Start")
        brand.focus()
        page.keyboard.press("Enter")
        page.get_by_role("heading", name="Abend").wait_for()
        require(page.get_by_role("link", name="Start", exact=True).get_attribute("aria-current") == "page",
                f"Brand keyboard navigation did not activate Start from {section}")
        require(player_title(page) == "Leise Wellen", "Player selection changed during Brand navigation")

    page.goto(f"{base_url}#/design-preview/unexpected/nested", wait_until="networkidle")
    page.locator(".design-preview").wait_for()
    page.get_by_role("heading", name="Abend").wait_for()


def test_queue_and_mix(page, base_url):
    page.goto(f"{base_url}#/design-preview/start", wait_until="networkidle")
    page.get_by_role("button", name=re.compile("Leise Wellen")).first.click()
    page.get_by_role("button", name="Warteschlange anzeigen").click()
    next_title = first_upcoming(page).split(" · ", 1)[0]
    require(next_title == "Kleiner Komet", f"Unexpected next queue title after selection: {next_title}")
    page.get_by_role("button", name="Nächster Titel").click()
    require(player_title(page) == next_title, "Next action disagreed with the visible queue")

    page.get_by_role("button", name="Vorheriger Titel").click()
    require(player_title(page) == "Leise Wellen", "Previous action failed to restore the selected title")
    require(first_upcoming(page).split(" · ", 1)[0] == "Kleiner Komet",
            "Queue did not follow previous-track action")

    page.get_by_role("link", name="Musik", exact=True).click()
    page.get_by_role("heading", name="Musik").wait_for()
    page.get_by_role("link", name="Start", exact=True).click()
    page.get_by_role("heading", name="Abend").wait_for()
    require(player_title(page) == "Leise Wellen", "Player selection changed across Start navigation")
    require(page.get_by_role("button", name="Warteschlange anzeigen").get_attribute("aria-expanded") == "false",
            "Route navigation did not close the queue panel")
    page.get_by_role("button", name="Mix starten").click()
    require(player_title(page) == "Morgens im Garten", "Mix action did not select its first example track")
    page.get_by_role("button", name="Warteschlange anzeigen").click()
    mix_next = first_upcoming(page).split(" · ", 1)[0]
    require(mix_next == "Leise Wellen", f"Unexpected first queue title after mix start: {mix_next}")
    page.get_by_role("button", name="Nächster Titel").click()
    require(player_title(page) == mix_next, "Next action disagreed with the mix queue")


def test_search_and_battery(page, base_url):
    page.goto(f"{base_url}#/design-preview/start", wait_until="networkidle")
    search = page.get_by_role("searchbox", name="Titel, Album oder Quelle suchen")
    search.fill("kein beispiel passt dazu")
    page.get_by_role("heading", name="Nichts gefunden").wait_for()
    page.get_by_role("button", name="Suche zurücksetzen").click()
    require(search.input_value() == "", "Search reset did not clear the input")

    page.get_by_role("link", name="Akku & PiSugar", exact=True).click()
    page.get_by_text("82%", exact=True).wait_for()
    require("scaleY(0.82)" in page.locator(".battery-large > span").get_attribute("style"),
            "Battery illustration does not use the displayed example percentage")

    page.get_by_label("Aktiv · nicht erreichbar").check()
    page.get_by_text("Akku nicht erreichbar").wait_for()
    require(page.get_by_text("82%", exact=True).count() == 0,
            "Unreachable battery state retained an old percentage")
    require(page.get_by_role("link", name="PiSugar-Akku unbekannt").count() == 1,
            "Unknown battery header indicator is missing")

    page.get_by_label("PiSugar deaktiviert").check()
    page.get_by_role("heading", name="PiSugar deaktiviert", exact=True).wait_for()
    require(page.locator(".battery-pill").count() == 0, "Disabled PiSugar still shows a header indicator")


def test_mobile_menu(page, base_url):
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{base_url}#/design-preview/start", wait_until="networkidle")
    toggle = page.locator(".menu-toggle")
    start_link = page.locator('#preview-sidebar .nav-item[aria-current="page"]')
    toggle.focus()
    page.keyboard.press("Enter")
    wait_for_menu_open(page)
    require(start_link.is_visible(), "Enter did not open the mobile navigation")
    wait_for_focus(page, '#preview-sidebar .nav-item[aria-current="page"]')
    page.keyboard.press("Escape")
    wait_for_menu_closed(page)
    wait_for_focus(page, ".menu-toggle")
    page.keyboard.press("Space")
    wait_for_menu_open(page)
    wait_for_focus(page, '#preview-sidebar .nav-item[aria-current="page"]')
    require(page.locator('#preview-sidebar .nav-item[aria-current="page"]').is_visible(),
            "Space opened the menu without exposing the active route")
    rfid_link = page.get_by_role("link", name="RFID", exact=True)
    for _ in range(4):
        page.keyboard.press("Tab")
    require(rfid_link.evaluate("el => document.activeElement === el"),
            "Tab from the active item did not reach the next visible sidebar link")
    page.keyboard.press("Enter")
    page.get_by_role("heading", name="RFID").wait_for()
    wait_for_menu_closed(page)
    wait_for_focus(page, ".menu-toggle")
    page.keyboard.press("Enter")
    wait_for_menu_open(page)
    wait_for_focus(page, '#preview-sidebar .nav-item[aria-current="page"]')
    require(page.locator('#preview-sidebar .nav-item[aria-current="page"]').is_visible(),
            "Reopened menu did not expose the active route")
    page.keyboard.press("Escape")
    wait_for_menu_closed(page)
    wait_for_focus(page, ".menu-toggle")
    page.keyboard.press("Tab")
    require(page.locator("#preview-sidebar").evaluate("el => !el.contains(document.activeElement)"),
            "Closed mobile navigation still receives keyboard focus")
    assert_no_overflow(page)


def run(args):
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "status": "running",
        "checks": [],
        "screenshots": [],
        "http_requests": [],
        "blocked_requests": [],
        "websockets": [],
        "legacy_mocked_websockets": [],
        "console_errors": [],
        "page_errors": [],
    }

    def run_at(base_url):
        report["base_url"] = base_url
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 960})
            page = context.new_page()
            pin_test_locale(page)
            attach_browser_errors(page, report)
            preview_network_guard(page, base_url, report)
            test_routes_brand_and_player(page, base_url)
            report["checks"].append("direct preview boot, seven routes, unknown path and keyboard Brand return")
            test_queue_and_mix(page, base_url)
            report["checks"].append("queue order matches selection, next, previous and mix actions")
            test_search_and_battery(page, base_url)
            report["checks"].append("search empty/reset and all three PiSugar preview states")
            test_mobile_menu(page, base_url)
            report["checks"].append("mobile menu, Escape focus return, Tab exclusion and 320px overflow")
            require(not report["websockets"], f"Preview opened WebSockets: {report['websockets']}")
            require(not report["blocked_requests"],
                    f"Preview attempted non-allowlisted HTTP requests: {report['blocked_requests']}")
            require(not report["console_errors"], f"Preview console errors: {report['console_errors']}")
            require(not report["page_errors"], f"Preview page errors: {report['page_errors']}")

            page.get_by_role("button", name="Menü öffnen").click()
            page.get_by_role("link", name="Akku & PiSugar", exact=True).click()
            page.get_by_label("Aktiv · Prozent bekannt").check()
            for width in (390, 768, 1440):
                page.set_viewport_size({"width": width, "height": 960})
                page.goto(f"{base_url}#/design-preview/start", wait_until="networkidle")
                page.locator(".design-preview").wait_for()
                assert_no_overflow(page)
                shot = output_dir / f"react-preview-{width}.png"
                page.screenshot(path=str(shot), full_page=True)
                report["screenshots"].append(str(shot))
                if width == 1440 and args.emit_preview_png_base64:
                    image = shot.read_bytes()
                    encoded = base64.b64encode(image).decode("ascii")
                    line = f"{PNG_LOG_MARKER}:{encoded}"
                    require(len(line) <= 1_000_000, "Marked Base64 screenshot line exceeds the 1 MB log limit")
                    print(line)
            page.set_viewport_size({"width": 320, "height": 800})
            assert_no_overflow(page)
            test_final_guard_detects_late_request(context, base_url)
            report["checks"].append("final guard rejects a late forbidden HTTP request")
            assert_preview_clean(report)
            context.close()

            legacy_report = {
                "http_requests": [],
                "blocked_requests": [],
                "websockets": [],
                "legacy_mocked_websockets": [],
                "console_errors": [],
                "page_errors": [],
            }
            legacy_context = browser.new_context(viewport={"width": 1280, "height": 900})
            legacy_page = legacy_context.new_page()
            pin_test_locale(legacy_page)
            attach_browser_errors(legacy_page, legacy_report)
            preview_network_guard(legacy_page, base_url, legacy_report, block_websockets=False)

            def mock_legacy_socket(socket):
                legacy_report["legacy_mocked_websockets"].append(socket.url)
                socket.close(code=1000, reason="Mock legacy test transport")

            legacy_page.route_web_socket("**/*", mock_legacy_socket)
            legacy_page.goto(f"{base_url}#/", wait_until="networkidle")
            legacy_page.locator("#routes").wait_for()
            legacy_page.locator(".MuiBottomNavigation-root").wait_for()
            require(legacy_page.locator(".design-preview").count() == 0,
                    "Legacy boot rendered the preview")
            require(legacy_page.get_by_role("link", name=re.compile("Start")).count() > 0,
                    "Existing legacy navigation is missing")
            require(bool(legacy_report["legacy_mocked_websockets"]),
                    "Legacy boot did not reach its mocked transport")
            require(not legacy_report["blocked_requests"],
                    f"Legacy boot attempted non-allowlisted HTTP requests: {legacy_report['blocked_requests']}")
            require(not legacy_report["page_errors"],
                    f"Legacy boot raised page errors: {legacy_report['page_errors']}")
            report["legacy_mocked_websockets"] = legacy_report["legacy_mocked_websockets"]
            report["legacy_http_requests"] = legacy_report["http_requests"]
            report["legacy_blocked_requests"] = legacy_report["blocked_requests"]
            report["legacy_page_errors"] = legacy_report["page_errors"]
            report["legacy_console_errors"] = legacy_report["console_errors"]
            report["checks"].append("legacy router and navigation load with mocked WebSocket transport")
            legacy_context.close()
            browser.close()

    if args.serve_directory:
        with LocalBuildServer(args.serve_directory) as base_url:
            run_at(base_url)
    else:
        run_at(args.url)

    report["status"] = "PASS"
    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PASS: {len(report['checks'])} browser checks; report: {report_path}")


def main():
    args = parse_args()
    try:
        run(args)
    except Exception as error:  # Keep a machine-readable failure report alongside screenshots.
        output_dir = Path(args.output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        failure = {"status": "FAIL", "error": f"{type(error).__name__}: {error}"}
        (output_dir / "report.json").write_text(
            json.dumps(failure, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        raise


if __name__ == "__main__":
    main()

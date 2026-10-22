"""Local-only Playwright smoke test for the built Modern UI."""

import json
import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "src" / "webapp" / "build"
ARTIFACTS = Path(os.environ.get("C9_SMOKE_ARTIFACTS", Path(__file__).parent / "artifacts"))
READ_TOKEN = "r" * 43
WRITE_TOKEN = "w" * 43


class QuietHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BUILD), **kwargs)

    def log_message(self, *_args):
        pass


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                viewports = (
                    ("desktop", {"width": 1280, "height": 900}),
                    ("mobile", {"width": 390, "height": 844}),
                )
                for label, viewport in viewports:
                    context = browser.new_context(viewport=viewport)
                    page = context.new_page()
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    requests = []
                    sockets = []
                    page.on("request", lambda request: requests.append(request))
                    page.on("websocket", lambda socket: sockets.append(socket.url))
                    page.goto(
                        f"http://127.0.0.1:{server.server_port}/#/modern-ui",
                        wait_until="networkidle",
                    )
                    page.get_by_role("heading", name="Phoniebox – Playlist-Pilot").wait_for()
                    assert not [r for r in requests if "/api/" in r.url], (
                        f"unexpected initial API requests: {requests}"
                    )
                    assert not sockets, f"unexpected initial WebSockets: {sockets}"

                    if label == "desktop":
                        def api_mock(route):
                            if route.request.method == "GET" and route.request.url.endswith("/api/playlists?limit=50"):
                                authorization = route.request.header_value("authorization")
                                assert authorization == f"Bearer {READ_TOKEN}", (
                                    f"GET authorization header: {authorization!r}"
                                )
                                route.fulfill(status=200, content_type="application/json", body=json.dumps({
                                    "contractVersion": 1, "nextCursor": None,
                                    "playlists": [{"playlistId": "pl_smoke", "name": "Smoke Playlist", "revision": 3}],
                                }))
                            elif route.request.method == "POST" and route.request.url.endswith("/api/playlist-commands"):
                                authorization = route.request.header_value("authorization")
                                assert authorization == f"Bearer {WRITE_TOKEN}", (
                                    f"POST authorization header: {authorization!r}"
                                )
                                body = route.request.post_data_json
                                assert body == {
                                    "contractVersion": 1,
                                    "commandId": "smoke-command",
                                    "action": "QUEUE_CREATE",
                                    "items": [],
                                }
                                route.fulfill(status=200, content_type="application/json", body=json.dumps({
                                    "contractVersion": 1,
                                    "commandId": body["commandId"],
                                    "action": body["action"],
                                    "status": "REJECTED",
                                    "error": {
                                        "code": "VALIDATION_ERROR",
                                        "message": "A safe synthetic diagnostic.",
                                        "retryable": False,
                                        "operation": body["action"],
                                        "details": {"field": "command", "reason": "synthetic_rejection"},
                                    },
                                }))
                            else:
                                route.abort()

                        page.route("**/api/**", api_mock)
                        page.get_by_label("Lese-Zugangscode").fill(READ_TOKEN)
                        page.get_by_role("button", name="Playlists laden").click()
                        page.get_by_role("button", name="Smoke Playlist · Revision 3").wait_for()
                        page.get_by_label("Schreib-Zugangscode (optional, getrennt)").fill(WRITE_TOKEN)
                        command = '{"contractVersion":1,"commandId":"smoke-command","action":"QUEUE_CREATE","items":[]}'
                        page.get_by_label("Erweitertes V1-Kommando (JSON)").fill(command)
                        page.get_by_role("button", name="Kommando senden").click()
                        page.get_by_text(
                            "Kommando abgelehnt: Die gewünschte Änderung wurde nicht ausgeführt."
                        ).wait_for()
                        assert page.get_by_label("Erweitertes V1-Kommando (JSON)").input_value() == command
                        assert page.get_by_label("Lese-Zugangscode").input_value() == READ_TOKEN
                        assert page.get_by_label("Schreib-Zugangscode (optional, getrennt)").input_value() == WRITE_TOKEN
                        all_requests = requests + []
                        assert all(
                            READ_TOKEN not in request.url and WRITE_TOKEN not in request.url
                            for request in all_requests
                        )
                        assert all(
                            READ_TOKEN not in (request.post_data or "")
                            and WRITE_TOKEN not in (request.post_data or "")
                            for request in all_requests
                        )
                        stored = page.evaluate(
                            "JSON.stringify([localStorage, sessionStorage].map(storage => Object.entries(storage)))"
                        )
                        assert READ_TOKEN not in stored and WRITE_TOKEN not in stored, (
                            f"credential persisted in browser storage: {stored}"
                        )
                        page.locator("details > summary").filter(
                            has_text="Lokaler Konfigurationsentwurf"
                        ).click()
                        page.get_by_text(
                            "Nur in dieser Ansicht, nicht im Daemon gespeichert.",
                            exact=True
                        ).wait_for()
                        requests.clear()

                    page.screenshot(path=str(ARTIFACTS / f"modern-ui-{label}.png"), full_page=True)
                    page.locator("button, input, textarea, a").first.focus()
                    page.keyboard.press("Tab")
                    focused = page.evaluate("document.activeElement?.tagName")
                    assert focused in {"INPUT", "BUTTON", "TEXTAREA", "A"}, f"tab focus missing: {focused}"
                    if label == "mobile":
                        overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
                        assert not overflow, "horizontal overflow at 390px viewport"
                    assert not errors, f"browser errors: {errors}"
                    context.close()
                browser.close()
            finally:
                if not browser.is_connected():
                    pass
        print(f"PASS: desktop and 390px mobile; local mocked API only; no initial API/WebSocket traffic; errors={errors}")
        print(f"Screenshots: {ARTIFACTS / 'modern-ui-desktop.png'}, {ARTIFACTS / 'modern-ui-mobile.png'}")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()

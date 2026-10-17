#!/usr/bin/env python3
"""Browser acceptance checks for the static Phoniebox design preview."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

FAILURES: list[str] = []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check the static preview in Chromium. Serve its directory separately, "
            "for example with python -m http.server 8000 --bind 127.0.0.1."
        )
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000/index.html",
        help="Preview URL (default: %(default)s)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts"),
        help="Directory for viewport screenshots (default: %(default)s)",
    )
    return parser.parse_args()


def require(condition: bool, message: str) -> None:
    if not condition:
        FAILURES.append(message)


def main() -> int:
    FAILURES.clear()
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []
    page_errors: list[str] = []
    external_requests: list[str] = []
    preview_origin = urlparse(args.url).netloc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on(
            "request",
            lambda request: external_requests.append(request.url)
            if urlparse(request.url).netloc and urlparse(request.url).netloc != preview_origin
            else None,
        )
        page.goto(args.url, wait_until="networkidle")
        page.get_by_role("heading", name="Lieblingsmusik").wait_for()
        require(page.get_by_text("Designvorschau · Beispieldaten").is_visible(), "Permanent preview label is missing")
        require(page.get_by_text("Spotify", exact=True).count() >= 2, "Spotify source badges are missing")

        page.locator('.album-card[data-track="Leise Wellen"]').click()
        require(page.locator("#player-title").inner_text() == "Leise Wellen", "Selecting a cover did not update the player")
        require("Spotify" in page.locator("#player-artist").inner_text(), "Player does not show the selected source")
        page.get_by_role("button", name="Vorschau pausieren").click()
        paused = page.get_by_role("button", name="Vorschau fortsetzen")
        require(paused.get_attribute("aria-pressed") == "false", "Pause state did not change")
        page.get_by_role("button", name="Warteschlange anzeigen").click()
        require(page.locator("#queue-panel").is_visible(), "Queue did not open")
        page.keyboard.press("Escape")
        require(page.locator("#queue-panel").is_hidden(), "Escape did not close the queue")
        page.get_by_role("button", name="Spotify", exact=True).click()
        require(page.locator("#breadcrumb-current").inner_text() == "Spotify", "Spotify navigation did not update the view")
        require(page.locator("#player-title").inner_text() == "Leise Wellen", "Player state did not persist across navigation")
        require(page.locator("#placeholder-panel").is_hidden(), "Spotify should keep the shared music preview visible")
        for view, label in (("music", "Musik"), ("playlists", "Playlists"), ("start", "Start")):
            page.locator(f'.nav-item[data-view="{view}"]').click()
            require(
                page.locator("#breadcrumb-current").inner_text() == label,
                f"{label} navigation did not update the view",
            )
            require(
                page.locator("#album-grid").is_visible(),
                f"{label} should keep the shared music preview visible",
            )

        def return_home_with_keyboard(view: str, shift_tabs: int) -> None:
            page.locator(f'.nav-item[data-view="{view}"]').click()
            for _ in range(shift_tabs):
                page.keyboard.press("Shift+Tab")
            brand = page.locator(".brand")
            brand_has_focus = brand.evaluate("element => document.activeElement === element")
            require(brand_has_focus, f"Brand link was not keyboard-reachable from {view}")
            page.keyboard.press("Enter")
            breadcrumb = page.locator("#breadcrumb-current").inner_text()
            require(breadcrumb == "Start", f"Brand link did not return from {view}")
            active_view = page.locator('.nav-item[data-view="start"]').get_attribute("aria-current")
            require(active_view == "page", "Brand link did not activate Start navigation")
            require(page.locator("#hero-title").is_visible(), "Brand link did not show the Start view")
            require(page.locator("#placeholder-panel").is_hidden(), "Brand link left a placeholder visible")
            require(page.locator("#player-title").inner_text() == "Leise Wellen", "Brand link changed the player selection")
            page.locator('.nav-item[data-view="start"]').click()

        return_home_with_keyboard("rfid", 5)
        return_home_with_keyboard("settings", 7)

        page.locator('.album-card[data-track="Leise Wellen"]').click()
        page.locator(".queue-button").click()
        queued_title = page.locator("#queue-panel span").nth(0).inner_text().split(" · ")[0]
        require(queued_title == "Kleiner Komet", "Queue after Leise Wellen should start with Kleiner Komet")
        page.locator('[data-action="next"]').click()
        require(
            page.locator("#player-title").inner_text() == queued_title,
            "Next did not select the title shown first in the queue",
        )
        page.locator('[data-action="previous"]').click()
        require(page.locator("#player-title").inner_text() == "Leise Wellen", "Previous did not restore Leise Wellen")
        queued_title = page.locator("#queue-panel span").nth(0).inner_text().split(" · ")[0]
        require(queued_title == "Kleiner Komet", "Queue order after Previous is incorrect")
        page.locator('[data-action="next"]').click()
        require(
            page.locator("#player-title").inner_text() == queued_title,
            "Next after Previous did not match the visible queue",
        )
        page.locator('[data-action="play-mix"]').click()
        require(page.locator("#player-title").inner_text() == "Morgens im Garten", "Mix start did not select its first track")
        queued_title = page.locator("#queue-panel span").nth(0).inner_text().split(" · ")[0]
        require(queued_title == "Leise Wellen", "Queue after mix start should start with Leise Wellen")
        page.locator('[data-action="next"]').click()
        require(
            page.locator("#player-title").inner_text() == queued_title,
            "Next after mix start did not match the visible queue",
        )

        search = page.locator("#music-search")
        search.fill("keine passende beispieldatei")
        require(page.get_by_role("heading", name="Nichts gefunden").is_visible(), "Empty search state is missing")
        page.get_by_role("button", name="Suche zurücksetzen").click()
        require(page.locator("#empty-state").is_hidden(), "Search reset did not restore results")
        require(search.input_value() == "", "Search reset did not clear the search")
        page.keyboard.press("/")
        require(page.evaluate("document.activeElement.id") == "music-search", "Slash keyboard shortcut did not focus search")
        page.locator("#volume").evaluate(
            "element => { element.value = '31'; element.dispatchEvent(new Event('input', { bubbles: true })); }"
        )
        require(page.locator("#volume-value").inner_text() == "31", "Volume preview did not update")

        page.locator('.nav-item[data-view="energy"]').click()
        require(page.locator("#energy-state-title").inner_text() == "Akku verbunden", "Known PiSugar state is missing")
        require(page.locator("#battery-status").is_visible(), "Known PiSugar state should show the header indicator")
        require(page.locator("#energy-percent").inner_text() == "82%", "Known battery percentage is missing")
        require(
            page.locator("#battery-fill").evaluate("element => element.style.transform") == "scaleY(0.82)",
            "Battery fill must use the same sample percentage in its inner fill area",
        )
        page.locator('input[name="battery-mode"][value="unreachable"]').check()
        require(
            page.locator("#battery-label").inner_text() == "PiSugar · unbekannt",
            "Unavailable battery must read as unknown",
        )
        require(page.locator("#energy-reading").is_hidden(), "Unavailable battery must not show a stale percentage")
        page.locator('input[name="battery-mode"][value="off"]').check()
        require(page.locator("#battery-status").is_hidden(), "Disabled PiSugar should hide the header indicator")
        require(page.locator("#energy-state-title").inner_text() == "PiSugar deaktiviert", "Disabled PiSugar state is missing")
        page.locator('input[name="battery-mode"][value="active"]').check()
        require(page.locator("#energy-percent").inner_text() == "82%", "Known battery preview value did not return")

        for width in (390, 768, 1440):
            page.set_viewport_size({"width": width, "height": 1000 if width == 1440 else 900})
            page.goto(args.url, wait_until="networkidle")
            page.screenshot(path=str(args.output_dir / f"preview-{width}.png"))
            overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
            require(not overflow, f"Horizontal page overflow at {width}px")

        page.set_viewport_size({"width": 390, "height": 844})
        page.reload(wait_until="networkidle")
        menu = page.locator(".menu-toggle")
        menu.click()
        require(menu.get_attribute("aria-expanded") == "true", "Mobile menu did not open")
        page.keyboard.press("Escape")
        menu_open = page.locator("body").evaluate("element => element.classList.contains('menu-open')")
        require(menu_open is False, "Escape did not close the mobile menu")
        has_focus = menu.evaluate("element => document.activeElement === element")
        require(has_focus, "Escape did not return focus to the menu toggle")
        page.keyboard.press("Tab")
        sidebar_has_focus = page.locator("#sidebar").evaluate(
            "element => element.contains(document.activeElement)"
        )
        require(sidebar_has_focus is False, "Closed mobile sidebar must not receive keyboard focus")
        menu.click()
        page.locator('.nav-item[data-view="rfid"]').click()
        require(
            page.locator("#placeholder-title").inner_text() == "RFID",
            "RFID navigation did not show its honest placeholder",
        )
        menu_open = page.locator("body").evaluate("element => element.classList.contains('menu-open')")
        require(menu_open is False, "Selecting a mobile destination did not close the menu")
        menu.click()
        page.locator('.nav-item[data-view="settings"]').click()
        require(
            page.locator("#placeholder-title").inner_text() == "Einstellungen",
            "Settings navigation did not show its honest placeholder",
        )

        page.set_viewport_size({"width": 320, "height": 800})
        page.goto(args.url, wait_until="networkidle")
        overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
        require(not overflow, "Horizontal page overflow at 320px")
        page.screenshot(path=str(args.output_dir / "preview-320.png"))

        browser.close()

    require(not console_errors, f"Browser console errors: {console_errors}")
    require(not page_errors, f"Unhandled browser errors: {page_errors}")
    require(not external_requests, f"Unexpected external requests: {external_requests}")
    if FAILURES:
        for failure in FAILURES:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print(
        "PASS: navigation, mobile menu/Escape, keyboard search, player/queue, source labels, search reset, PiSugar states, "
        "no overflow, no console errors or external requests"
    )
    print(f"Screenshots: {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # Keep assertion detail visible and return a useful CLI status.
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

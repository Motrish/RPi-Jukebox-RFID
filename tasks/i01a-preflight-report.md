# I01a Preflight slice review record

Stand: 17.10.2026. The four approved product/test files are frozen in this staged tree. No package, installer, CI, configuration, or service files changed.

## Review fixes

- Marker checks now use one injectable `stat` probe. Missing paths and non-directories produce observed `false`; permission and other OS/probe errors produce `unknown` with a German reason. The result keeps independent status for both settings files. A `.gitkeep` alone still reports both actual YAML files absent.
- The server accepts only one literal loopback `Host` authority (`127.0.0.1`, `localhost`, optional valid port; `[::1]` is accepted as an authority although the listener itself remains IPv4). If `Origin` is present, it must be one HTTP origin whose authority matches `Host`. Duplicate or malformed headers, foreign authorities, query/fragment targets, absolute-form targets, and unrecognized paths are rejected before invoking the report probe. No CORS permission is emitted.
- User-facing page text and probe reasons are German. Unknown values remain explicit, the page says „Noch keine Konfiguration“, and DOM values use `textContent`.

## RED/GREEN evidence

After adding the marker and HTTP regressions, the first focused full run failed as expected: marker injection was not accepted (`TypeError`), and a request with a foreign Host returned 200 before the test expected rejection. After the implementation, all 10 tests pass, including both regression cases and the existing `.gitkeep` distinction.

Commands from this directory:

```powershell
$env:PYTHONPATH='G:/Entwicklung/phoniebox-tools/python'
python -B -m unittest discover -s test\websetup -v
python -m flake8 --max-line-length=127 --max-complexity=12 --ignore=E126,E127,E128,W503,F824 --per-file-ignores=__init__.py:F401 installation/websetup test/websetup
```

Both commands completed successfully. The standalone namespace-package invocation also works with `python -B -m installation.websetup.server --help`.

## Isolated pytest console collection correction

The isolated pytest 9.1.1 console entry initially reproduced a collection failure with `--import-mode=importlib --collect-only`: `ModuleNotFoundError: No module named 'installation'`, with 0 tests collected. The test now inserts its staged root into `sys.path` before importing the namespace package, following the existing contract-test pattern; no CI or package path configuration was changed.

From the staged root, the isolated console entry passed collection (10 collected) and execution (10 passed). `PYTHONPATH` below contains only the isolated pytest tool directory, not the project root:

```powershell
$env:PYTHONPATH='G:\Entwicklung\phoniebox-tools\pytest-check'
G:\Entwicklung\phoniebox-tools\pytest-check\bin\pytest.exe --import-mode=importlib --collect-only test\websetup\test_preflight.py
G:\Entwicklung\phoniebox-tools\pytest-check\bin\pytest.exe --import-mode=importlib test\websetup\test_preflight.py -q
```

## Browser evidence

Chromium via the installed Python Playwright package loaded the page from an ephemeral loopback server. The page rendered 11 cards, displayed the no-configuration notice, had zero page errors, and had a 390-pixel document width at the 390-pixel viewport. The screenshots are local development-host evidence only; they do not describe the target Pi. The development host correctly showed OS and memory as unknown.

Artifacts:

- `artifacts/desktop.png`
- `artifacts/390.png`

Exact PowerShell command used to produce both screenshots (run from this staged root):

```powershell
@'
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright
from installation.websetup.server import make_server

root = Path.cwd()
artifacts = root / "artifacts"
httpd = make_server(root=root, port=0)
thread = threading.Thread(target=httpd.serve_forever, daemon=True)
thread.start()
try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://127.0.0.1:%d/" % httpd.server_address[1], wait_until="networkidle", timeout=8000)
        page.screenshot(path=str(artifacts / "desktop.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(artifacts / "390.png"), full_page=True)
        print("page_title=" + page.title())
        print("page_state=" + page.locator("#state").inner_text())
        print("fact_cards=" + str(page.locator(".fact").count()))
        print("mobile_document_width=" + str(page.locator("body").evaluate("element => element.scrollWidth")))
        print("mobile_viewport_width=390")
        print("page_errors=" + str(errors))
        print("notice_count=" + str(page.get_by_text("Noch keine Konfiguration").count()))
        browser.close()
finally:
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=2)
'@ | python -B -
```

No target-device, LAN, installation, or persistent-service claim is made by these checks.

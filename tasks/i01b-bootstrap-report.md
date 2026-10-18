# I01b Phase 1 report

Stage: `G:/Entwicklung/phoniebox-staging/i01b-bootstrap`
Base: integrated `2002cc2c2de3daa8f0b2b06e6f9513cd71c92886`, tree `3dd4b2240cca9ebf729050a919cd3207074fd5b2`.

## Frozen publish candidates

Only these two new publishable paths were authored in Phase 1:

- `test/websetup/test_launch.py`
- `.github/workflows/test_build_webapp_v3.yml`

The three product paths remain absent: `installation/bootstrap-web.sh`, `installation/websetup/launch.py`, and `resources/default-settings/nginx.bootstrap-loopback.conf`. No other existing source or workflow was modified. Local `__pycache__` files are generated test output and are not publish candidates.

The test has an unconditional import of `installation.websetup.launch` using `importlib.import_module`; collection cannot skip or fall back. Standard unittest coverage checks CLI flag/port rejection, invalid-bundle-before-listener behavior, missing nginx diagnostics, real producer-created bundles, POSIX shell invocation from a different working directory, port collision ownership, and an nginx configuration-test failure with cleanup. Explicit `--integration` mode accepts the actual archive, manifest, expected repository/commit, nginx executable, and output directory. It exercises the shell entry and actual extracted nginx, Host/Origin (including duplicate/empty/whitespace) and route/method/path rejection, redacted I01a response, Chromium setup and React routes, same-origin request enforcement, JavaScript MIME, safe startup or pre-listener rejection with a private temp path containing spaces and a quote, SIGINT/SIGTERM, owned nginx child exit, private temp cleanup, foreign sentinel and input preservation. Finite deadlines are used throughout.

The workflow extends both existing path filters without changing branch selection. It adds normal unittest discovery for all `test/websetup/test_*.py` regressions, then runs explicit bootstrap acceptance on the exact verified bundle before artifact upload and includes the report directory in always-uploaded evidence. Existing React/Jest, browser, nginx, package, upload, download, and exact-artifact verification steps remain. The job deadline is 16 minutes: the previous 10-minute limit plus the two new bounded 3-minute steps.

## Immutable dependency copies

The required I01a, R01b, and R01a dependency copies were made with byte-preserving `Copy-Item`; SHA-256 comparisons against their source stages all matched. The copied files are context only, not publish candidates:

- I01a: `installation/websetup/server.py`, `preflight.py`, `index.html`, `test/websetup/test_preflight.py`.
- R01b: `installation/websetup/bundle.py`, `test/websetup/test_bundle.py`.
- R01a: `tools/web_bundle.py`, `test/web_bundle/test_web_bundle.py`, and the original workflow before the authorized Phase 1 workflow edit.

X01 nginx configuration and `tests/design-preview/nginx_library_smoke.py` were inspected as read-only patterns; no copies or edits were made there.

## Commands and results

- `python -m py_compile test/websetup/test_launch.py` ? passed.
- V3 flake8 on the new test and copied Python tests with max line length 127, max complexity 12, ignores `E126,E127,E128,W503,F824`, and `__init__.py:F401` ? passed.
- `python -m unittest discover -s test/websetup -p test_launch.py -v` ? expected RED, one collection error: `ModuleNotFoundError: No module named 'installation.websetup.launch'`. No product code exists in the stage.
- Existing I01a suite ? 10 passed.
- Existing R01b suite ? 39 total, 2 skipped on Windows (POSIX mode/FIFO cases).
- Existing R01a suite ? 15 total, 2 skipped on Windows (invalid filename/FIFO cases).
- SHA-256 checks for all eight immutable Python dependencies ? matched their source stages.

The integration command was not run locally because this host is Windows and the harness intentionally invokes POSIX `/bin/sh`, Linux process signals, actual nginx, and Chromium. CI is the specified place for that actual integration proof. A local YAML parser was unavailable (`PyYAML` is not installed); the workflow was reviewed in place, and CI will parse and execute it.

No device, account, service, LAN, GitHub, package-installation, or remote mutation was performed. Phase 1 is frozen for Root's exact-path publication and actual Linux Missingmodule RED; Phase 2 remains unstarted.

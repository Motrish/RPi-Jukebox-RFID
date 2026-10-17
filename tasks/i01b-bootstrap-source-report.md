# I01b Phase 2 source report

Phase 2 is implemented in the three authorized product paths. The shell entry resolves the checkout from its own location, checks for Python 3.9+, and forwards arguments directly. The Python launcher validates the actual R01a/R01b bundle before opening a listener, keeps `bundle.staged_bundle` active for the complete serving lifetime, starts the unchanged I01a `make_server(root=checkout_root, port=0)` on a managed thread, and owns only its foreground nginx child. Nginx is rendered from the fixed template into a private prefix with all five HTTP temporary directories there. Startup and configuration checks have deadlines; shutdown closes the owned child and preflight listener and removes only the private temporary tree.

The template binds only to `127.0.0.1`, permits the exact outer authority and GET routes, proxies `/setup/` to I01a `/` and `/api/preflight` to the fixed I01a route, and limits static requests to the CRA root files, locale files, and `/static/`. Query/path variants, unsupported routes, absolute-form targets, and non-GET requests do not reach the SPA or upstream. It uses X01's empty-versus-valid Origin routing: the empty route forwards the original header unchanged, allowing I01a to accept a missing Origin and reject an explicitly empty one; a valid outer Origin is rewritten to the fixed upstream authority. The nginx `$http_origin` comma check and X01 behavior are retained for duplicate values.

The approved test file received one narrow addition after Root identified that the existing default-nginx port-collision test could pass when nginx was absent from PATH. The Linux integration now exercises collision using the explicit nginx binary that has already passed the real bundle/browser acceptance setup, and checks that the foreign listener remains usable and no private files leak. Tests and workflow remain the only other whitelist paths; workflow contents are unchanged.

## Validation

- `python -m unittest discover -s test/websetup -p 'test_*.py'` — 55 total, 5 skipped on Windows (50 executed). The skipped checks require POSIX process/signal behavior or POSIX file modes; platform-independent launcher, preflight, and intake checks ran.
- `python -m unittest discover -s test/web_bundle -p 'test_*.py'` — 15 total, 2 skipped on Windows (13 executed) for POSIX-only filename/FIFO fixtures.
- `python -m py_compile installation\websetup\launch.py test\websetup\test_launch.py` — passed.
- `$env:PYTHONPATH='G:\Entwicklung\phoniebox-tools\python'; python -m flake8 installation\websetup\launch.py test\websetup\test_launch.py --max-line-length=127 --max-complexity=12 --ignore=E126,E127,E128,W503,F824 --per-file-ignores='__init__.py:F401'` — passed with no findings.
- `Get-Command nginx -ErrorAction SilentlyContinue` — no nginx executable is available on this Windows host. Therefore real `nginx -t`, POSIX shell/process/signal checks, the Linux HTTP matrix, and Chromium integration were not run locally; the CI acceptance path must provide that evidence. No packages were installed.

The test and source evidence is currently local to the isolated partial stage. Root must mechanically publish these exact files, mark `installation/bootstrap-web.sh` executable in Git mode (`100755`), and obtain full Linux nginx/Chromium CI and independent source review before integration.

## Frozen whitelist SHA-256

| Path | SHA-256 |
| --- | --- |
| `installation/bootstrap-web.sh` | `1A175209E4F7EF4EBB9488C4F341BA1ADFD4F106B7173CA3025A486CD5C95355` |
| `installation/websetup/launch.py` | `68AFCB0972C68EB3AE5BD2B84A69215465A94F77620B7CB1CF32FD89222A67E2` |
| `resources/default-settings/nginx.bootstrap-loopback.conf` | `2226AE1209B04BA74183A66CA6BCC6D1C2682A58F3CA4DD932FEF13E0514513D` |
| `test/websetup/test_launch.py` | `5BF353967C0945CEEDE389582915242E140AF423B0C2CFE335777D7A89AFF215` |
| `.github/workflows/test_build_webapp_v3.yml` | `8F660F1A25D33FA996E6820AA32B7DE9B0E7AD404EE9ACF02285FD61CABB5297` |

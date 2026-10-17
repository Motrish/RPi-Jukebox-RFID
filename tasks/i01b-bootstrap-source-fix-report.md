# I01b Phase 2 final source fix report

This is the single scoped fix batch for the three findings in `i01b-bootstrap-source-review.md`, based on source c5de66f03f9fb5848213afdf231983dff6e1ecbb. Changes are limited to the launcher, its fixed nginx template, and the whitelisted launcher test. The shell entry and workflow are unchanged.

1. The launcher now probes availability by binding the requested loopback port after bundle verification but before creating either listener or any child process. On success, it creates a fresh 256-bit random readiness token, renders it into the fixed nginx template, and accepts readiness only for `/setup/` with the matching private header, HTTP 204, and a still-running owned nginx child. The initial bind catches an already-active foreign service without sending it requests; the nonce response independently proves the spawned nginx instance during the bind/rebind race. The existing passive collision assertion remains unchanged. A new unit regression runs an active HTTP 200 foreign server, verifies the launcher sends it no requests and prints no ready URLs, and then confirms that the foreign service remains usable. The real-nginx integration collision case is strengthened to use an active HTTP 200 server and checks that it receives no launcher probe.

2. Private nginx root paths containing `$` are rejected by the existing quoting validator before any listener factory or process factory is called. A unit seam uses a real producer bundle under a `$server_port` temporary parent and verifies those factories remain untouched and the private parent is cleaned. The Linux real-nginx acceptance also launches with a `$server_port` TMPDIR and requires safe rejection, no ready URLs, no listener, and no leaked temporary files.

3. Deliberate public diagnostics use `_SafeLaunchError`, whose messages are authored constants. Raw filesystem, process, value, and other unexpected exceptions now produce one fixed generic message instead of `str(error)`. A regression injects an OSError containing a private POSIX path and arbitrary payload and verifies neither reaches output.

## Red/green and validation

Before the source changes, the targeted regression command failed all three cases as expected: the active foreign server's URL was printed, the dollar-bearing path reached the listener factory, and the raw OSError path/payload appeared in stderr. After the changes:

- `python test\websetup\test_launch.py LauncherCliTests.test_active_foreign_http_200_is_never_probed_or_announced LauncherCliTests.test_dollar_private_temp_path_rejects_before_listener_factories LauncherCliTests.test_raw_filesystem_exception_is_replaced_with_fixed_diagnostic` — 3 passed.
- `python -m unittest discover -s test/websetup -p 'test_*.py'` — 58 total, 5 skipped, exit 0 (53 executed). Windows skips cover POSIX process/signal checks, POSIX file modes, and a symlink fixture unavailable on this host.
- `python -m unittest discover -s test/web_bundle -p 'test_*.py'` — 15 total, 2 skipped, exit 0; skips are POSIX-only filename and FIFO cases.
- `python -m py_compile installation\websetup\launch.py test\websetup\test_launch.py` — passed.
- `$env:PYTHONPATH='G:\Entwicklung\phoniebox-tools\python'; python -m flake8 installation\websetup\launch.py test\websetup\test_launch.py --max-line-length=127 --max-complexity=12 --ignore=E126,E127,E128,W503,F824 --per-file-ignores='__init__.py:F401'` — passed with no findings.

There is no nginx executable on this Windows host, so the real nginx config check, POSIX shell/process lifecycle, active foreign service under the Linux integration wrapper, dollar-bearing TMPDIR subprocess case, HTTP matrix, and Chromium run remain unverified locally. The previously supplied CI run 39077664956/job117528073596 failed before reaching bootstrap/browser acceptance on the pre-fix source. Root must publish this exact frozen batch and obtain new CI and independent scoped review before further integration.

## Frozen whitelist SHA-256

| Path | SHA-256 |
| --- | --- |
| `installation/bootstrap-web.sh` | `1A175209E4F7EF4EBB9488C4F341BA1ADFD4F106B7173CA3025A486CD5C95355` |
| `installation/websetup/launch.py` | `1306DAD05E5C77B5770FFEF68A5852AEAFA1D47450DC994B9A04F3922F313174` |
| `resources/default-settings/nginx.bootstrap-loopback.conf` | `5EE781FEF767758F04143D1C3D0B5C5D2E2EDEF14AE0D4BA979A3DEC21E872D1` |
| `test/websetup/test_launch.py` | `AB81E42569565B9B9BE69B8B59B26AAD433D39A8F75ABE6E53EBC478E657BF8D` |
| `.github/workflows/test_build_webapp_v3.yml` | `8F660F1A25D33FA996E6820AA32B7DE9B0E7AD404EE9ACF02285FD61CABB5297` |

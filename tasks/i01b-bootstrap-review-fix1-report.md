# I01b Phase 1 review fix 1 report

Stage: `G:/Entwicklung/phoniebox-staging/i01b-bootstrap`
Changed publish candidate: `test/websetup/test_launch.py` only.
The workflow is unchanged. The three product paths remain absent.

## Review findings closed

1. Reuse one producer-created bundle argument list across CLI option cases (test begins at line 78); fixture creation no longer repeats `mkdir` into the same existing build tree.
2. Browser request policy explicitly permits same-origin GET `/setup/` and `/api/preflight`, while all other network requests remain blocked (lines 248-264).
3. Setup proof waits for the unique successful `#state` text, checks rendered `.fact` rows, and inspects the actual successful `/api/preflight` response for schema and nonempty facts; it also checks private input/output paths are absent from that response (lines 266-327).
4. `wait_for_ready` waits for both flushed URL strings, sends the exact Host authority, and requires HTTP 200 from `/setup/` (lines 185-201).
5. Each lifecycle helper now has unconditional bounded cleanup. The harness retains the launcher process tree, uses a private process group for escalation, and directly inspects `/proc` socket inodes to prove both the nginx listener and in-process preflight listener disappear after SIGINT, SIGTERM, unexpected nginx exit, and quoted-path rejection (lines 333-478, 504-534).
6. Integration writes PASS only after browser, HTTP, input/sentinel, shutdown, signal, child-exit, and quoted-path assertions. Early launch or acceptance failures write a finite `FAIL` report with failure type and a path-free summary (lines 597-643).
7. Added a narrow future product seam contract: `launch.run(argv, *, make_server_factory, popen_factory) -> int`. The invalid-bundle test tampers with a real R01a producer archive, wraps the real `bundle.staged_bundle` and asserts it is invoked, and passes recording listener/process factories that must remain untouched (lines 33-36, 87-115). This provides direct proof that real intake verification completes before any listener/process factory can run.
8. The HTTP matrix now includes an absolute-form request target, unknown `/api/...`, `/setup`, and unknown `/setup/...`; these must fail and return no SPA HTML (lines 203-245).

## Verification

- `python -m py_compile test/websetup/test_launch.py` ? passed.
- V3 flake8 with repository settings (max line 127, complexity 12, ignores `E126,E127,E128,W503,F824`, per-file `__init__.py:F401`) ? passed.
- `python -m unittest discover -s test/websetup -p test_launch.py -v` ? expected RED at unconditional import: `ModuleNotFoundError: No module named 'installation.websetup.launch'`. The product is intentionally absent, so behavioral tests cannot run locally yet.
- Final test SHA-256: `711ac45bdc2c6e224407a3d4856cd41be256b9d70594365c1eb71382837a5424`.

The requested `launch.run` signature and factory names are an explicit test-to-product contract for Phase 2. No product behavior or full acceptance pass is claimed by this report. Actual Linux nginx/Chromium execution remains CI work after the test fix is reviewed and dispatched.

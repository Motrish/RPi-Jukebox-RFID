# I01b Phase 1 review fix 2 report

Stage: `G:/Entwicklung/phoniebox-staging/i01b-bootstrap`
Changed publish candidate: `test/websetup/test_launch.py` only. Workflow and product files were not edited.

## Scoped rereview corrections

- Original finding 5: `finish_owned_process` now snapshots all members of its private process group before teardown and sends cleanup to that group even if the launcher leader has already exited. It then waits for the recorded PIDs and escalates to SIGKILL within finite bounds. This closes the orphan path in finally cleanup.
- New P1: forbidden-route SPA assertions now run only for rejection responses (`status >= 400`), so valid GET `/setup/` 200 remains accepted while negative API/setup/absolute-form cases still must fail without HTML.
- New P2: after killing the observed nginx PID that owns the requested listening socket, the child-exit check waits up to 8 seconds for the launcher to exit on its own. The teardown helper is reached only after that observation or from finally cleanup.

## Commands and results

- `python -m py_compile test/websetup/test_launch.py` ? passed.
- V3 flake8 with max line 127, complexity 12, ignores `E126,E127,E128,W503,F824`, and per-file `__init__.py:F401` ? passed.
- `python -m unittest discover -s test/websetup -p test_launch.py -v` ? expected collection RED: `ModuleNotFoundError: No module named 'installation.websetup.launch'`. The product remains intentionally absent; behavioral tests remain pending Phase 2.
- Final test SHA-256: `9139f6cb0045531b62eed1519c8bcbc24d1cc1ebd9e2be3b63382f43a36534af`.

No full behavioral acceptance, Linux process proof, or product claim is made by this fix report.

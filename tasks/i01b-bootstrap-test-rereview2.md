# I01b Phase1 scoped test re-review, fix round2

Reviewed only tasks/i01b-bootstrap-review-fix2-report.md and tasks/i01b-test-fix2-review-package.md. Root verified final test SHA-256 9139f6cb0045531b62eed1519c8bcbc24d1cc1ebd9e2be3b63382f43a36534af. No code, probes, suites, subagents or remote mutations were performed; unchanged files were not recrawled.

**Scoped spec-compliance verdict: APPROVE. Scoped quality verdict: APPROVE.** All three remaining findings are addressed in the test source. No new important breakage was found in this fix diff.

| Scoped finding | Verdict | Evidence |
| --- | --- | --- |
| Original finding5: orphan cleanup after launcher exits early | ADDRESSED | finish_owned_process at test/websetup/test_launch.py:443 snapshots the private process group, includes its members in the retained PID set, and sends group cleanup even when the launcher leader has exited. Existing bounded wait/escalation then covers surviving members. |
| Fix1 P1: valid /setup/ HTTP200 rejected as forbidden | ADDRESSED | The rejection-body branch at test/websetup/test_launch.py:237 now applies only to status>=400. The existing per-case status assertion still rejects unexpected successes for negative cases, while valid setup HTTP200 bypasses that branch. |
| Fix1 P2: premature SIGTERM during unexpected nginx-exit observation | ADDRESSED | After killing nginx, test/websetup/test_launch.py:505 waits up to8 seconds for launcher exit without signaling it. Only afterward does normal result checking run; finally retains bounded cleanup on failure. |

This closes the findings from the initial review and fix1 rereview at the test-source level. The workflow is unchanged in this round. The three product paths remain intentionally absent, and the explicit launch.run factory interface remains a Phase2 contract. Reported compile/lint success and expected missing-module RED are consistent with Phase1; they do not establish product behavior. Actual full-checkout Linux nginx/Chromium and Python-version proof remain pending SourceCI after product implementation at the exact reviewed head.

# I01b Phase1 scoped test re-review, fix round1

Reviewed only tasks/i01b-bootstrap-review-fix1-report.md and the mechanical fix diff in tasks/i01b-test-fix1-review-package.md, with narrow line-anchor lookups in the changed test. No unchanged dependencies were recrawled; no suites, probes, scripts, subagents or remote mutations were run. Root verified the final local test SHA-256 as 711ac45bdc2c6e224407a3d4856cd41be256b9d70594365c1eb71382837a5424. The workflow is unchanged; product paths remain intentionally absent.

**Spec compliance: REQUEST CHANGES. Quality: REQUEST CHANGES.** Seven original findings are addressed at the test-source level. Finding5 remains incomplete, and two important regressions appear in the fix diff. Actual Linux nginx/Chromium and Python behavior remain pending Phase2 SourceCI. Reported compile/lint results and expected missing-module RED do not establish behavioral acceptance.

## Original findings

| Original finding | Verdict | Evidence in final test |
| --- | --- | --- |
| 1. Repeated real-bundle fixture creation fails | ADDRESSED | Line80 constructs base arguments once before iterating option cases. |
| 2. Browser blocks setup and preflight | ADDRESSED | browser_route at line248 includes both exact same-origin GET paths. |
| 3. Ambiguous static Systemdaten locator | ADDRESSED | Lines308 onward check the unique successful state, rendered fact rows and an actual preflight response; the response observer checks schema, nonempty facts and private test values. |
| 4. Readiness accepts missing-Host HTTP400 | ADDRESSED | wait_for_ready at line185 requires both URL strings, the correct Host and HTTP200 from /setup/. |
| 5. Lifecycle fixture cleanup on failures | NOT ADDRESSED | Helpers now use finally and bounded escalation, but finish_owned_process at lines436-444 still skips group termination when the launcher has already exited. See remaining finding below. |
| 6. PASS published before lifecycle checks | ADDRESSED | PASS at line635 follows primary shutdown and every lifecycle subcheck; caught start/acceptance failures write FAIL. |
| 7. Invalid bundle only checked after process exit | ADDRESSED | The real producer archive is tampered and launch.run is called with forbidden listener/process factories at lines87-115. The real intake function is wrapped and required to be called. The explicit launch.run factory seam is a pending Phase2 product contract, not existing product proof. |
| 8. Missing absolute-form and actual API/setup negatives | ADDRESSED | verify_http_matrix at line203 adds those concrete cases. A new classifier defect blocks their execution, reported below. |

## Remaining original finding

**P2 — Finding5: teardown can still leave an orphan after an early launcher exit.** `test/websetup/test_launch.py:437` sends the requested group signal only while process.poll() is None. Every lifecycle helper and the main acceptance fixture initially record only process.pid; descendants are captured after successful readiness or acceptance (for example lines459 and624). If the launcher exits before that point but leaves a child alive with detached/redirected output, communicate returns normally, the recorded launcher PID has gone, and neither escalation nor survivor cleanup signals the still-owned private process group. The child survives the finally block. Ensure final cleanup terminates the owned session/group even when its leader has exited, and retain/check descendants where possible. The new finally blocks and bounded waits improve the normal case but do not close the original failure-cleanup requirement.

## New important breakage in the fix diff

1. **P1 — The HTTP matrix rejects its first required success response.** `test/websetup/test_launch.py:235` classifies every target beginning with /setup as forbidden. Its first matrix case is the legitimate GET /setup/ with correct Host and expected HTTP200. After that status passes its per-case accepted tuple, the new reject_spa branch raises because status is below400. Every conforming product therefore fails acceptance before the browser check. Apply the rejection-body assertion only to cases whose expected outcome is rejection, or give each matrix case an explicit negative-case flag. Preserve the successful /setup/ GET case.

2. **P2 — The unexpected-child-exit test signals the launcher before observing its response to the child exit.** `test/websetup/test_launch.py:493` kills the owned nginx process and immediately calls finish_owned_process at line494. That helper sends SIGTERM to any still-running launcher at line438, even though this subcheck is intended to prove the launcher independently notices nginx death and exits nonzero. A conforming launcher can receive SIGTERM first, perform its specified clean signal shutdown and return0, causing a timing-dependent failure. Wait with a finite deadline for spontaneous launcher exit after killing nginx; use signaling/escalation only in finally cleanup if that observation fails.

The host autocrlf messages and expected diff-generation exit1 are not source findings. No changes outside the whitelisted test file are requested by this scoped review.

# I01b-dev narrow ownership closure review

Reviewed 2026-10-18. Baseline `4db483906eee57ff13de668b4a753d8039bdecba`; reviewed head `5150de984e523cd23d26230e064dfb9d45eb3d2d`; tree `167270d05665b96c9f9c44f3ef26e9d96891d20e`.

Read `tasks/i01b-bootstrap-ownership-closure-report.md` and the complete `tasks/i01b-ownership-review-package.md` delta. Scope is the remaining response-marker/read-bound findings and the concrete nginx-error-HTML classification correction. Unchanged dependencies, shell, workflow and whole source were not reread. No code, probes, tests, scripts, subagents or remote mutations were performed.

**Scoped spec verdict: APPROVE. Scoped quality verdict: APPROVE.** Both remaining readiness findings are closed in source. The classification correction is appropriate. No new important breakage was found within this narrow fix.

| Scoped item | Verdict | Evidence |
| --- | --- | --- |
| P1 foreign204 response could be announced as owned readiness | CLOSED | The request carries only a fixed `X-I01B-Readiness: probe` value. A fresh random per-launch marker is placed in the fixed nginx response header, never in the request. `_wait_ready` requires HTTP204, exactly one matching `X-I01B-Owned-Instance` value, and a still-running owned child. A generic or request-echoing foreign204 responder therefore cannot satisfy readiness. The new regression bypasses the initial availability check to model the bind race and confirms that this responder produces no ready URLs. |
| P2 unbounded response-body read could defeat the startup deadline | CLOSED | The former body read is removed. The socket becomes nonblocking; sends, header reads and retries share the monotonic readiness deadline. Header accumulation is capped at8,192 bytes and64 fields, and rejected responses are closed. No response-body consumption loop remains. Slow-header and oversized-header regression cases assert rejection within a bounded interval. |
| Built-in nginx error HTML was misclassified as React SPA | ADDRESSED | The matrix first fetches successful nonempty `/index.html`, then compares negative bodies to those exact bytes. Generic nginx400 HTML is no longer treated as SPA merely because it contains an HTML tag. Existing per-case expected statuses are retained, so forbidden200 responses still fail. The focused classifier case checks both generic-error acceptance and actual-index rejection. |

The marker is generated internally as a random hexadecimal constant and rendered through the fixed template; it creates no arbitrary root, upstream or directive option. The parser accepts only the expected HTTP status/header shape for readiness and enforces a single marker value. The existing pre-verification and private-lifetime structure is not reopened by this delta. Earlier dollar-path and diagnostic-redaction closures remain unchanged.

The author reports6 targeted cases passing,61 total setup tests with5 Windows skips (56 executed),15 total R01a tests with2 skips (13 executed), and compile/lint success. These results were not independently rerun in this source-only review. Root's fresh verification and exact-head full-checkout Linux actual-nginx/Chromium/current-bundle/lifecycle evidence remain separate gates. This scoped approval closes the review findings; it does not claim that pending CI has passed or authorize unsupported installer, LAN, ARMv6 or device behavior.

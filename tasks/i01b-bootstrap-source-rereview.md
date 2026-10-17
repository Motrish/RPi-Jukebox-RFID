# I01b-dev scoped source fix re-review

Reviewed 2026-10-18. Baseline source `c5de66f03f9fb5848213afdf231983dff6e1ecbb`; final fix head `4db483906eee57ff13de668b4a753d8039bdecba`; tree `3e2fbdd0952517bf240a78c0a3a76502b9eb3824`.

Read only `tasks/i01b-bootstrap-source-fix-report.md` and the complete `tasks/i01b-source-fix-review-package.md` delta, in the context of the prior whole-branch review. Scope is the three findings and important breakage introduced in the changed launcher/template/test functions. Shell and workflow remain unchanged according to the frozen package information. No executable artifacts, probes, scripts, test reruns, subagents or remote operations were performed.

**Scoped spec verdict: REQUEST CHANGES. Scoped quality verdict: REQUEST CHANGES.** Two findings are closed in source. Ownership remains unproven in a concrete bind-race case, and the changed response read also needs a bound. This head should not be integrated on the strength of the reported green unit cases.

| Prior finding | Verdict | Source assessment |
| --- | --- | --- |
| P1 foreign-listener readiness | NOT CLOSED | The initial bind correctly rejects a listener already occupying the port without probing it. However, the socket is then released before nginx binds; the new request nonce plus generic HTTP204 acceptance still permits a foreign service winning that race to be announced. |
| P2 variable-bearing nginx root | CLOSED | `_nginx_quote` rejects `$` and controls in `_serve` before either listener/process factory. The real-producer unit seam asserts those factories are untouched and private files removed. A subprocess acceptance case also covers a dollar-bearing TMPDIR. |
| P2 raw POSIX exception disclosure | CLOSED | Deliberately authored diagnostics now use `_SafeLaunchError`; raw unexpected exceptions receive one fixed public message. The injected OSError regression checks the private POSIX path and arbitrary payload do not escape. |

## Required residual and introduced issue

1. **P1 — Request nonce does not authenticate a generic HTTP204 response.** `installation/websetup/launch.py:143` sends `X-I01B-Readiness` with the private token, but line158 accepts only HTTP204 and a still-alive child; no unpredictable response value is checked. A foreign service can bind after `_assert_outer_port_available` closes its probe socket, then answer204 while owned nginx remains alive retrying bind. It need not know or process the request token. The template's conditional204 only establishes how the intended nginx answers; it does not establish who answered the network request. Keep the initial collision check, but validate a per-launch unpredictable value emitted by the intended nginx response and do not disclose that expected response value in the readiness request. Add a regression for a foreign204 responder during this bind/rebind interval; it must never publish ready URLs and must leave that service usable. The new active200 fixture covers the pre-existing-listener path, not this residual.

2. **P2 — Readiness now consumes an unbounded foreign response body.** `installation/websetup/launch.py:157` replaces `response.read(1)` with `response.read()` before examining status. In the same bind-race window, a foreign200 responder can stream or trickle a body indefinitely while staying inside each0.25-second socket timeout. The8-second outer loop deadline is not checked during that read, and memory can grow without bound. This is new important breakage in the changed readiness function. Check the expected status/response marker without reading arbitrary bodies, close rejected responses, and keep any required reads byte-bounded and within the startup deadline. A bounded regression should cover a nonterminating/more-than-required response without waiting for the global CI timeout.

These are narrowly contained readiness corrections; neither requires an arbitrary root, template, upstream, command option or changes to the immutable dependency interfaces. Rejection of `$` and fixed diagnostics do not need reopening.

## Evidence boundary

The author reports all three new regression cases failed before the fix and passed after it, followed by58 total setup tests with5 Windows skips (53 executed),15 total R01a tests with2 skips, and compile/lint success. Those commands were not rerun in this source-only review. Root's independent fresh verification and exact-head Linux actual-nginx/Chromium/current-bundle lifecycle proof remain separate gates. The previous failed Linux run belongs to the pre-fix head and supplies no acceptance proof for this one.

The reported tests establish their scoped cases; they do not invalidate the foreign204 counterexample or supply a bound for the new unrestricted read. No broader audit or additional scope is proposed.

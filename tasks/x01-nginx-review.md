# X01 Phase 1 independent review

Reviewed frozen test head25f337922e2ab08f1d59efb71cde7d899df0a4fd, treef5ed082ae809d92cebf87123f93dce19cd6a3bfe, against baseb5190698a7b39abc8e5dc1062cee8334261474fc. Read both complete staged files, x01-nginx-report.md and the integration plan including its Origin ruling and Root approval. Read the base workflow through GitHub MCP to compare preserved checks/triggers. Prose-only review; no executable changes, probes or GitHub mutations.

Result: two P2 test defects require correction before Phase 2 source approval. No P1 finding. Actual missing-template CI RED remains a separate required observation; it does not exercise the currently unreachable assertions below.

## P2: header-overflow arrival contaminates the URI baseline

Source: tests/design-preview/nginx_library_smoke.py:302–335. The before snapshot is taken before the forty-extra-header request, then reused after the entire invalid-URI loop. The header-overflow assertion deliberately checks only authorizer/catalog counters and allows the existing API to reject excess headers. Such a permitted request increments the all-request arrivals counter. Consequently the later URI assertion fails even when every invalid URI was rejected by nginx before upstream arrival. This contradicts the report's explicitly allowed API-boundary header-count rejection and can force an unnecessary nginx header parser or hide the actual failing boundary.

Minimal fix: take a fresh dict(counters) immediately before the invalid-URI loop. Keep the overflow assertion and URI zero-arrivals assertion otherwise separate. No product-template change is needed to address this finding.

## P2: stopped-upstream phase is outside final browser guard assertions

Source: tests/design-preview/nginx_library_smoke.py:510–527. The HTTP/WebSocket guards and pageerror collector remain active, but their only assertions execute before backend shutdown and the refresh/error-state interaction. If the error path triggers an unexpected request, WebSocket or JavaScript error while still displaying the expected message, verify_browser returns normally and main writes PASS. The stated browser acceptance covers this phase as well.

Minimal fix: move the final page_errors/blocked/sockets assertions after the stopped-upstream error checks, or repeat them there before closing the page/context/browser. Retain the same guard policy and synthetic-secret assertion. No new test abstraction is necessary.

## Accepted scope and evidence limits

The harness uses actual LibraryCatalog, make_server and make_read_authorizer, a synthetic valid43-character code and deterministic real files. Its handler observer increments arrivals before request dispatch, independently of authorizer/list/detail counters. Host/Origin negatives use the valid code and proper remaining headers; they are not trivially rejected by a bad bearer. Empty/whitespace Origin requires one real backend arrival with zero authorizer/catalog calls, while distinguishable duplicates require zero arrivals, matching the accepted ruling. Direct-backend tests preserve the existing authority/Origin boundary. URI negatives use otherwise valid Host, Origin and bearer; after the baseline fix their zero-arrivals assertion is meaningful.

The browser has no HTTP testproxy or route fulfillment: approved requests continue to the true nginx origin, and fixture IDs, pagination and MISSING data must appear from the real catalog. A context route guard is interception for allow/abort only. The existing German/English navigator fixture and semantic UI locators are preserved. Browser/context close calls are on the success path inside sync_playwright's context manager; this review does not elevate the absence of an additional browser finally to a separate demonstrated P2 defect. nginx and backend teardown have context/finally ownership and finite stop waits. Compiled nginx temporary-path defaults remain a Phase 2 configuration consideration that actual nginx -t/startup will detect, not a speculative Phase 1 blocker.

Rendering accepts only the three named trusted start parameters, requires each exactly once, quotes the fixed buildroot and invokes subprocesses as argument lists without a shell. The configuration template is deliberately absent. Therefore no conclusion is made yet about actual fixed upstreams, binding/root safety, inheritance, error responses, timeout settings, logging or empty-header relay. Those require review of the eventual template and actual Linux execution; source review cannot substitute for that proof.

The workflow retains the prior build, React tests, Python/web contracts, Chromium and both earlier browser checks unchanged. It retains previous branch/path filters and adds the opt-in template to both push and PR path filters. nginx is downloaded/extracted with an explicit executable check, without package installation or service startup. The new smoke has a three-minute deadline and joins the existing artifact upload. No Pi/LAN/TLS/product-auth claim follows from this review.

Root owns status in the existing todo.md. Correct the two narrow harness defects, freeze/read back the new SHA, rerun relevant lint and obtain the actual missing-template RED before authorizing Phase 2. No expansion beyond the approved three executable paths is needed.

## Narrow Phase 1 fix closure

Reviewed the two authorized staged harness deltas at SHA-256 ff004411b75713d9e9923602577402ec858921c25ce02a35c83933a5592a3a27. At line312 a fresh counter snapshot now immediately precedes the invalid-URI loop, separating its zero-arrivals proof from the permitted backend header-overflow rejection. At lines526–529 pageerror and HTTP/WebSocket guard assertions now run after the stopped-upstream UI error and secret checks. Both P2 findings are closed by source review; no executable probe was run for this closure.

The workflow remains at SHA-256 19f13820582bf4f2df70fa0a2024a23cdd7843c36a71cda60cb3cabbccf5d194 and the template remains absent. Root accepts reuse of the unchanged early missing-template RED from old remote head25f337922e2ab08f1d59efb71cde7d899df0a4fd once observed, because both fixes occur below that sentinel and do not alter its startup behavior. This does not claim that the corrected assertions executed in the old RED. The first source CI containing the template must also contain these accepted harness fixes and execute them. The earlier request for another full missing-template RED after these two deltas is superseded by this explicit Root ruling. No remaining Phase 1 source-review blocker.

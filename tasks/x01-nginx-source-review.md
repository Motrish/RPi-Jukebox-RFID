# X01 independent whole-source SPEC + QUALITY review

Latest reviewed head8aa64245: both P1 findings and the P2 are closed, with no new concrete P1/P2 in the fix. Root subsequently confirmed the real-nginx/Web and full Python acceptance and integration in the author report. Earlier findings and their narrow closure follow below.

Verdict: request changes. Two P1 template defects and one P2 harness defect require one narrow correction wave, then complete real-nginx acceptance on the corrected exact head. No other concrete P1/P2 finding was established.

Reviewed head c407cface8a3fa6c5f72ed1d1a4d71a6798b74cb, tree cd7e17187ca44b4fab502a684ccc132376d7bf48, against base b5190698a7b39abc8e5dc1062cee8334261474fc. Read the complete plan including the overriding Origin ruling, author report, Phase 1 review/closure, all three changed files, and existing API implementation. Local SHA-256 hashes match the frozen handoff: template 0ccfc5b292ae0f640b525e4111a7028a9e2e9910351eb3f04b00233fb08887cd; harness ff004411b75713d9e9923602577402ec858921c25ce02a35c83933a5592a3a27; workflow 19f13820582bf4f2df70fa0a2024a23cdd7843c36a71cda60cb3cabbccf5d194. Prose-only review: no executable edits/probes, GitHub mutations or subagents.

## P1: quote map regex arguments containing quantifier braces

Location: resources/default-settings/nginx.library-loopback.conf:13 through line17. Unquoted {2}/{1,128} are interpreted as configuration block delimiters by [official release-1.24.0 ngx_conf_read_token](https://raw.githubusercontent.com/nginx/nginx/release-1.24.0/src/core/ngx_conf_file.c). Root subsequently observed the exact failure: Web39040497230/job117418879133 fails nginx -t with unexpected opening brace at rendered nginx.conf:13. Actual downloaded package: Ubuntu noble-updates amd64 nginx1.24.0-2ubuntu7.18. Earlier Web checks passed; proxy tests were not reached.

Minimal fix: quote each complete regex argument, preserving the raw-target allowlist. Regression: existing nginx -t on the exact rendered template, then positive list/detail and invalid-URI matrix. No parser/framework expansion.

## P1: replace upstream_addr with startup-fixed backend authority

Location: template:174,176,190. The request is constructed before the peer address exists. [Official release-1.24.0 upstream source](https://raw.githubusercontent.com/nginx/nginx/release-1.24.0/src/http/ngx_http_upstream.c) calls request creation before state initialization/connection; its address getter returns not-found before state exists. The [proxy implementation](https://raw.githubusercontent.com/nginx/nginx/release-1.24.0/src/http/modules/ngx_http_proxy_module.c) omits headers evaluating to empty. Both branches suppress Host; the valid-Origin branch forms http://. Strict backend checks reject valid requests.

Minimal fix: derive authority from the trusted startup backend parameter. Root permits one fixed server variable initialized from the once-only backend-port token and reused for fixed proxy destination and Host/Origin. No request-derived destination. Preserve raw-target gates, both branches, original empty-bucket relay and strict backend checks. Regression: existing exact-Origin/absent-Origin 200s, list/detail/catalog observations, direct-backend strictness and negative Origin counters on actual binary. Source-confirmed; CI has not reached it because syntax fails first.

## P2: request connection closure in EOF-based raw HTTP helper

Location: tests/design-preview/nginx_library_smoke.py:208-225, template:33. HTTP/1.1 requests omit Connection: close, but raw_request reads until EOF with four-second inactivity timeout. nginx holds downstream keepalive for five seconds. A complete valid response can therefore time out before assertions. Upstream Connection controls a separate hop. See [official keepalive_timeout](https://nginx.org/en/docs/http/ngx_http_core_module.html#keepalive_timeout) and upstream source header table, which consumes upstream Connection.

Minimal fix accepted by Root: add one Connection: close to synthetic raw requests; preserve malformed Host/Origin and missing-Host HTTP/1.0 cases. No product keepalive change/general response parser. Regression: existing first valid GET and entire raw matrix finish without EOF timeout with all response/counter assertions retained. Not yet reached in CI.

## SPEC + QUALITY and evidence boundaries

Three paths match the whitelist; API, catalog, React, installer/global default remain unchanged. Template is opt-in with one IPv4 loopback listener/fixed root; raw-target, Host/Origin and method gates precede internal proxy cases. Static allowlisting/plain errors, disabled autoindex/symlink following/access logging, unchanged Authorization, finite header/body limits and inactivity timeouts fit scope. These properties do not establish working integration while P1 defects remain.

Accepted Origin exception is represented by original-header relay for absent/empty/whitespace and fixed rewrite for exact valid nonempty Origin. [Release-1.24.0 unknown-header implementation](https://raw.githubusercontent.com/nginx/nginx/release-1.24.0/src/http/ngx_http_variables.c), lines914-959, gathers all matches and joins duplicates with comma/space; it does not select first Origin. Duplicate/mixed values cannot equal the valid single value or empty/whitespace bucket. Proxy source preserves original empty fields without an override. No extra feasibility P1, API relaxation, parser or runtime expansion follows; actual binary negatives remain required.

Harness uses real catalog/API/authorizer, separate arrival/authorizer/catalog counters, deterministic real files, injected TTL time and actual browser continuation. Valid codes on negative Host/Origin/URI cases make boundaries meaningful. Prior baseline/final-browser-guard defects remain closed. Browser covers same-origin real paging, duplicate titles, MISSING and stopped-upstream UI failure with final traffic/page-error guards. Existing process ownership/finite teardown waits are retained. No broad refactor needed.

Workflow preserves earlier checks, extracts executable nginx without installation/service startup, and gives acceptance a three-minute deadline. Old missing-template RED proves only its early precondition; c407 CI proves syntax failure and prior checks. Lower corrected Phase 1 assertions and proxy/browser behavior still need actual execution. Python lint is not nginx proof.

No Linux execution by this reviewer. Corrected exact head must show nginx -t, isolated startup, version, compiled temp-path behavior, empty-header relay, full counter matrix, real browser/catalog path and stopped-upstream result. Only client-body/proxy temp paths are explicit; unused-module compiled defaults are a runtime consideration, not a separately demonstrated failure here. Socket/proxy timeouts are inactivity limits, CI supplies overall deadline. No Pi/ARMv6/audio/system-service/LAN/TLS/production-auth proof. Root alone owns TODO status.

## Narrow fix review: 8aa64245c2bd7569d124853d8b95aad16296fdab

Source verdict: the two P1 and one P2 findings above are closed by the frozen correction. No new concrete P1/P2 in the fix delta and its immediate context. Reviewed tree fbf9127e7299bac52ada5fda9ce042cee7c6a9a9 against c407; local hashes independently match template b48a14c9712314afa16b19a1d32e90bb9377c8ef7d0facefda36656a2dbbd716 and harness 6636090f5b31d39acbc5bb9f5b7075e8d594a8b8878659812ea4512470d1bdf8. Workflow remains 19f13820582bf4f2df70fa0a2024a23cdd7843c36a71cda60cb3cabbccf5d194.

All five regex keys are now quoted, preserving their raw-request allowlist. A map with only one literal default defines the backend authority from the once-only trusted startup port token. Although keyed by server_port, it has no alternative value, so client input cannot choose a destination. Both proxy destinations and Host headers use this fixed authority; only the valid nonempty Origin branch overrides Origin. The empty bucket has its own Host/Connection directives and no Origin override at its level or any ancestor, preserving original-header relay and the accepted API rejection boundary. No upstream_addr remains.

Both variable proxy_pass URLs have no URI component. The [release-1.24.0 proxy request creation source](https://raw.githubusercontent.com/nginx/nginx/release-1.24.0/src/http/modules/ngx_http_proxy_module.c), lines1175-1180, retains the unparsed URI when the configured URI is empty and the original remains valid. Existing exact raw-target gates, absolute-form rejection, named internal branches and negative counter tests remain the applicable constraints; actual positive and negative URI behavior must still execute in CI. All five body/proxy/FastCGI/uWSGI/SCGI temporary paths are now explicit under the isolated prefix.

The raw helper adds only Connection: close, allowing its existing EOF framing to complete without waiting for nginx keepalive. Response parsing, synthetic malformed-header cases and counter assertions remain intact. No parser expansion, backend relaxation or product keepalive change.

This is source closure, not a Linux GREEN claim. The live corrected-head CI still must prove exact rendered nginx -t/startup, real same-origin API/catalog/browser path, empty-Origin relay, full negative matrix and stopped-upstream behavior. Root retains sole TODO ownership and integration decision.

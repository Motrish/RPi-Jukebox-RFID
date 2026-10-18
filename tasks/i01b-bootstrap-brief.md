# I01b-dev: task brief

Stand 18.10.2026. Binding implementation brief for the local developer setup launcher. Base future3/modern-ui 2002cc2c2de3daa8f0b2b06e6f9513cd71c92886, complete Git tree 3dd4b2240cca9ebf729050a919cd3207074fd5b2. Operative status only in tasks/todo.md. Existing i01b-bootstrap-plan.md gives background, this brief defines this bounded implementation.

## Global constraints

No Astra. Luna alone authors executable artifacts, including tests, configuration and workflows. Root coordinates, reviews, runs authored commands and mechanically publishes exact files. No worker subagents or remote Git mutations. Work solely in G:/Entwicklung/phoniebox-staging/i01b-bootstrap; this is an isolated partial stage, not a full checkout. Full checkout and actual Linux nginx/Chromium proof run in GitHub Actions. Retain stage and evidence. No device access, package installation on recipient, service/defaultsite/firewall changes, LAN exposure, account use, downloads or privileged actions in product code. Existing Python >=3.9 and nginx are prerequisites. Receiver does not build React or need Node.

Exactly five publishable executable paths:

- installation/bootstrap-web.sh (executable Git mode)
- installation/websetup/launch.py
- resources/default-settings/nginx.bootstrap-loopback.conf
- test/websetup/test_launch.py
- .github/workflows/test_build_webapp_v3.yml

All other copied dependencies are immutable context, not publishing candidates. No replacement of existing I01a, R01a/R01b or X01 files. Preserve existing CRA build, React/Jest/contracts/browser/nginx tests, bundle packaging/upload/download verification.

## Product contract

The shell entry locates its repository independent of caller working directory, checks an existing Python3 >=3.9 interpreter and delegates to the fixed module. It passes arguments as arguments, does not eval or build shell command strings, and never invokes apt, npm, curl or a service manager. Missing prerequisites produce a concise actionable diagnosis without install fallback.

CLI accepts required --archive, --manifest, --repository, --commit; optional --port (default8780, integer1024..65535), --nginx-binary (default discovered existing nginx). Do not accept arbitrary template, document root, upstream, command or extra nginx directives. Resolve checkout root from module location. Validate independently expected repository/commit using R01a/R01b rather than deriving them from manifest. Explicit private temporary parent owns staging and nginx prefix. Use staged_bundle for entire serving lifetime; never rewrite src/webapp/build or caller inputs. Verification failure must precede any listener. Paths containing spaces/quotes must either be represented safely in nginx or rejected before listener, with no directive injection.

Reuse unchanged I01a make_server(root=checkout_root, port=0) in-process on127.0.0.1 with a managed thread, so allocated upstream port is held rather than released/rebound. Only the new nginx is a child process. Run nginx in foreground, master_process off, using private config/prefix and all five HTTP temp paths privately. Validate actual config with a finite nginx -t command before start. Manage startup/readiness with finite deadline and early exit detection. A pre-existing outer listener is an error; never adopt it or signal by global pid/pkill/system nginx. Print flushed setup URL `http://127.0.0.1:PORT/setup/` and existing React route `http://127.0.0.1:PORT/#/design-preview` only after own server is ready. Stop on Ctrl-C/SIGTERM, nginx exit or startup failure: close own preflight listener/thread, terminate then bounded-kill/wait only owned child, release private stage. Clean shutdown exits0; startup/config/verification failures nonzero and diagnosed without tracebacks or secret/path contents in logs. Never remove foreign files.

nginx binds exclusively127.0.0.1. Strict outer authority is127.0.0.1:actualport, not localhost/wildcard. GET only. /setup/ proxies to I01a /; /api/preflight proxies to same-named I01a route, fixed upstream Host and same-origin mapping. Reject foreign or duplicate Host/Origin, absolute-form request targets, raw/encoded traversal, query/path tricks. Preserve absent-versus-empty Origin validation for proxied routes using established X01 routing pattern if needed; report exact limitations instead of claiming nginx can distinguish values it cannot. No body forwarding needed. Static assets narrowly allow actual CRA paths from X01 (root/index/favicon/logo/manifest, de/en locales, static subtree) with proper MIME, no symlink traversal. Unknown /api, /setup, /rpc, /ws, /logs, administrative or filesystem routes fail and never return SPA HTML. Serve verified index at / and hash route. Do not connect library backend or invent authentication. Access logs off; bounded timeouts/header/body limits, no arbitrary request data echoed.

I01a page and redacted report remain unchanged. Its bundle observation is about src/webapp/build and is not relabeled as activation. Player/battery remain marked preview. This launcher is local developer transport, not full installer or LAN setup.

## Phase 1: tests and CI first

Copy immutable dependencies from existing stages using byte-preserving file copies: i01a installation/websetup/{server.py,preflight.py,index.html}, test/websetup/test_preflight.py; r01b-bundle-intake installation/websetup/bundle.py and test/websetup/test_bundle.py; r01a-web-bundle tools/web_bundle.py, test/web_bundle/test_web_bundle.py and current workflow. X01 template and tests/design-preview/nginx_library_smoke.py are read-only patterns. Do not create any of the three product paths yet.

Author test/websetup/test_launch.py and workflow changes. Tests must fail for missing launch product rather than skip/fallback. Standard unittest discovery remains fast and dependency-free; integration/browser execution is explicit CLI mode taking actual bundle archive, manifest, expected identity, nginx binary and output directory, with finite deadlines. Keep all proof within the single whitelisted test file; helpers in that file allowed. Windows may skip genuinely POSIX shell/process/signal checks, but Linux CI must run them. Avoid giant mechanical mirrors or synthetic fake-nginx success proof; fake process failures may supplement actual nginx.

Unit/process checks: CLI rejection, missing binary, invalid bundle before any listener, safe arguments/paths, own lifetime and consumer cleanup; temp fixtures via real producer. Actual Linux subprocess checks: shell invoked from a different cwd, port collision does not adopt or affect existing listener, early nginx/config failure, Ctrl-C and SIGTERM cleanup, unexpected child exit, foreign sentinel and input bytes unchanged. Owned children and listeners must disappear after failures, no leaked private directories. Use deterministic synchronization/deadlines, no arbitrary long sleeps.

Actual integration: CI's real current CRA bundle goes through shell launcher and real extracted nginx. Real Chromium loads /setup/, observes fetched redacted I01a facts and no player dependency, then actual React preview root. Seed browser locale de/en as existing harness. Enforce no off-origin requests and no browser errors; save finite report/screenshots, no secrets/base64 output. HTTP matrix probes strict/duplicate/foreign Host and Origin (including empty/whitespace cases), method, raw/encoded traversal, unknownAPI/adminroutes, correct static MIME, stopped upstream behavior if practical without new product test controls. Global nginx files/service and existing sentinels remain untouched. Do not require device files or credentials.

Workflow: extend both existing path filters for launcher, template, intake/server/preflight dependencies and test file. Keep existing branch selection unchanged. Run new unit tests in existing full-checkout Python matrix by ordinary discovery. In web job, run intake regressions if not otherwise covered there; after Package and verify built web bundle and before Upload verified web bundle run explicit bootstrap acceptance using that generated pair, github.repository and actual checkout commit output, existing extracted nginx/Chromium. Add bootstrap report directory to always-uploaded evidence. Preserve old tests and artifact exact-ID roundtrip. Adjust overall job deadline only if justified by actual existing step budgets, report change.

Report phase1 commands and expected Missingmodule RED. Root publishes and reads actual CI RED before product files. Independent frozen test/contract review precedes phase2. Stop phase1 with short status and report at tasks/i01b-bootstrap-report.md; ask Root for missing context only when necessary.

## Phase 2 and completion

After Root dispatch, implement three product files, run covering tests and V3lint. Root publishes exact whitelist, confirms full-checkout CI actual nginx/Chromium and Python3.9-3.13, dispatches independent full source/spec/quality review, batches any fixes through Luna and scoped rereview. Whole-branch final review required before already-authorized integration. No full-installer/ARMv6/LAN/device claims. Report exact commands, results, skips and limits. Tests and source evidence at same exact head. Retain report and mechanical review package; no destructive workspace cleanup.

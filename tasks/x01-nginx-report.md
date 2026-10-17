# X01 – lokaler Bibliotheksanschluss über nginx

Abgeschlossen: PR17 ist als6b872011c2e79263f61ca5384908b23251178a6b in future3/modern-ui integriert. Die geplante echte nginx-/Web-/Python-Abnahme und unabhängigen Reviews sind bestanden. Die folgenden Abschnitte dokumentieren die Test- und Korrekturrunden sowie die Nachweisgrenzen.

Phase 1 is frozen with only the new smoke harness and the existing V3 workflow changed. The nginx template is still absent; the intentional failing condition is the missing template. No Linux CI run has been made from this partial Windows stage. Root owns publishing, obtaining the actual Linux red, and serial independent review.

The harness renders exactly three named template values, each required exactly once: `@@X01_LISTEN_PORT@@` (ephemeral IPv4 loopback port), `@@X01_BUILD_ROOT@@` (quoted absolute built React root), and `@@X01_BACKEND_PORT@@` (the fixture API's fixed loopback port). It runs `nginx -t` against that rendered file, records `nginx -v`, then starts that binary in the harness's own temporary prefix with `daemon off;`. The CI step downloads and extracts the actual `nginx` binary package and verifies `extracted/usr/sbin/nginx` is executable before the harness runs. Ubuntu Noble identifies `nginx-core` as an all-architecture documentation package and lists the nginx executable in its architecture-specific `nginx` package ([Noble nginx package details](https://packages.ubuntu.com/noble-updates/nginx), [nginx-core file list](https://packages.ubuntu.com/noble/all/nginx-core/filelist)). Downloading and extracting `nginx` runs no package maintainer scripts, so it cannot start or enable a host service.

The API fixture uses the real Linux catalog and API. Its observer counts every backend request before method dispatch, and separate counters record authorizer, list, and detail calls. The raw HTTP matrix covers:

- Success: exact outer Host and Origin, absent Origin, list and detail, strict direct-backend authority/Origin, valid bearer, and API no-store headers.
- Host: foreign, absent in HTTP/1.0, duplicate, and empty values; each must fail before backend arrival.
- Origin: foreign, case-changed, same-value duplicate, absent, empty, whitespace, duplicate empty, and mixed empty/nonempty values. Distinguishable invalid values must fail before arrival. Empty and whitespace values must reach the real API unchanged and fail before authorization or catalog access, per the accepted Origin ruling.
- Request target and route: encoded slash and dot segment, literal dot segment, duplicate slash, backslash, malformed percent escape, encoded and invalid query values, duplicate query keys, query on detail, absolute-form target, and unknown API paths. Invalid route forms must fail before backend, authorizer, or catalog. Oversized targets and header limits are also rejected before authorizer/catalog; the API may be the rejecting boundary for a header-count overflow.
- Methods and credentials: HEAD, POST, PUT, DELETE, OPTIONS, and PATCH fail without backend arrival; missing and invalid bearer plus fake-clock expiry retain the API's 401 response.
- Failure and static serving: a real catalog failure retains JSON 503/no-store; stopped upstream is exercised through the browser UI. `/logs`, rawRPC, unknown API paths, and build-root traversal cannot return successful data or SPA HTML. The harness checks that nginx creates no access log.
- Browser: the built React page uses the real same-origin nginx/API/catalog path with no route mock. It submits the synthetic code, pages through deterministic duplicate titles and a MISSING item, and checks that the stopped-upstream message does not expose the code. HTTP and WebSocket guards reject any unapproved browser traffic.

The workflow's previous React, contract, Playwright, and browser checks remain. Both push and pull-request path filters include the future nginx template so template-only changes continue to run this acceptance job. It adds a three-minute real-nginx smoke step and includes its artifact directory in the existing upload. The workflow's nginx dependency step downloads/extracts the binary but does not install or start a system service.

Local checks passed:

```powershell
python -m py_compile tests/design-preview/nginx_library_smoke.py
$env:PYTHONPATH='G:\Entwicklung\phoniebox-tools\python'
python -m flake8 --max-line-length=127 --max-complexity=12 --ignore=E126,E127,E128,W503,F824 --per-file-ignores=__init__.py:F401 tests/design-preview/nginx_library_smoke.py
```

The local intentional-red command was:

```powershell
python -u tests/design-preview/nginx_library_smoke.py --serve-directory src/webapp/build --output-dir "$env:TEMP\x01-nginx-red"
```

It failed specifically with `AssertionError: missing required nginx template: .../resources/default-settings/nginx.library-loopback.conf`, before checking for nginx or a build. Root's Linux workflow invocation, after publishing this phase, is:

```sh
python -u tests/design-preview/nginx_library_smoke.py \
  --serve-directory src/webapp/build \
  --output-dir "$RUNNER_TEMP/design-preview-nginx-library" \
  --nginx-binary "$RUNNER_TEMP/nginx-package/extracted/usr/sbin/nginx"
```

SHA-256 at freeze:

- `tests/design-preview/nginx_library_smoke.py`: `FF004411B75713D9E9923602577402EC858921C25CE02A35C83933A5592A3A27`
- `.github/workflows/test_build_webapp_v3.yml`: `19F13820582BF4F2DF70FA0A2024A23CDD7843C36A71CDA60CB3CABBCCF5D194`

No template, service installation, device change, or LAN claim is part of this phase.

## Phase 2 source handoff

Phase 2 is source-authored and frozen; the actual missing-template RED was observed by Root on the earlier Phase 1 snapshot after the preserved Web checks. That run stopped at the missing-template assertion, so it does not prove the new proxy behavior or later harness assertions. The accepted Phase 1 harness corrections were incorporated before this template. The template and current harness still need the full Linux workflow and independent source review before any green claim.

The new template is a complete standalone nginx configuration with one IPv4 listener on `127.0.0.1`, a fixed upstream bound to the harness-supplied loopback backend port, a fixed build root, its own prefix-relative PID/error/temp paths, and access logging disabled. It has no global nginx include or default-site dependency. Its only parameter tokens occur once each: `@@X01_LISTEN_PORT@@`, `@@X01_BUILD_ROOT@@`, and `@@X01_BACKEND_PORT@@`.

The request gate checks the raw outer Host authority against the actual listening port, allows only GET, and rejects absolute-form request lines. The API route map matches only the list/detail paths and valid list query forms against `$request_uri`; invalid encodings, normalized path aliases, unsupported queries, and API subpaths cannot become allowed routes. Static responses are limited to the exact build entry/locales and `/static/`; static locations reject requests whose raw URI differs from the normalized path. Autoindex is off, symlink following is disabled, and unmatched paths return plain-text 404s.

Origin handling uses the two approved internal proxy cases. A missing, explicit-empty, or whitespace-only Origin uses a fixed upstream and sets only its Host and Connection headers, allowing nginx's unchanged-header relay to preserve the original Origin field. A single exact outer HTTP Origin is rewritten to `http://$upstream_addr`, where the static upstream contains only the fixed loopback API. Other and merged values return before upstream selection. Neither case overrides or stores Authorization; the original bearer is forwarded by normal request-header passing. The upstream is a fixed single server, and proxy retry, cache, and response buffering are disabled. Header/body sizes, client inactivity timeouts, proxy timeouts, and response buffers remain finite.

The configuration follows nginx's documented distinction between raw `$request_uri` and normalized location matching, uses a no-URI `proxy_pass` inside named locations, and relies on the documented rule that `proxy_set_header` inheritance applies only when no directives are set at the current level. See the [nginx core module documentation](https://nginx.org/en/docs/http/ngx_http_core_module.html) and [nginx proxy module documentation](https://nginx.org/en/docs/http/ngx_http_proxy_module.html).

This Windows environment has no nginx executable, so I could not run `nginx -t` or start the rendered config locally. Static verification confirmed the three render tokens each occur exactly once. Actual rendering, `nginx -t`, startup, header relay, URI behavior, browser behavior, and the recorded nginx version remain for the updated Linux workflow. No device, system service, LAN, TLS, or production-auth claim follows.

SHA-256 for the source-authored snapshot:

- `resources/default-settings/nginx.library-loopback.conf`: `0CCFC5B292AE0F640B525E4111A7028A9E2E9910351EB3F04B00233FB08887CD`
- `tests/design-preview/nginx_library_smoke.py`: `FF004411B75713D9E9923602577402EC858921C25CE02A35C83933A5592A3A27`
- `.github/workflows/test_build_webapp_v3.yml`: `19F13820582BF4F2DF70FA0A2024A23CDD7843C36A71CDA60CB3CABBCCF5D194`

## Phase 2 source-review correction freeze

The initial Phase 2 template was rendered in Root's Linux CI and failed `nginx -t` on an unquoted map regex quantifier. The exact failure stopped before proxy/browser checks. Independent source review also found that nginx 1.24 builds the upstream request before a peer address exists, so `$upstream_addr` could not provide the backend Host or rewritten Origin. The corrected template quotes every regex key with quantifiers and initializes one fixed backend authority from the once-only backend-port token; both proxy cases use it for the destination and Host, and the valid-Origin case uses it for the fixed rewritten Origin. No request-selected authority is used. The review's raw HTTP/1.1 EOF/keepalive finding is corrected by adding `Connection: close` to every synthetic raw request. These latter findings are source-level and are not claimed as runtime-observed.

All five compiled HTTP temporary paths now resolve under the harness-owned nginx prefix. The harness fixes are narrow: raw synthetic requests alone gain the close header. The workflow is unchanged. Corrected exact-head nginx syntax, startup, HTTP matrix, and real-browser behavior remain unverified until Root's next Linux CI run; the previous parser failure cannot stand as green evidence.

Correction-freeze SHA-256:

- `resources/default-settings/nginx.library-loopback.conf`: `B48A14C9712314AFA16B19A1D32E90BB9377C8EF7D0FACEFDA36656A2DBBD716`
- `tests/design-preview/nginx_library_smoke.py`: `6636090F5B31D39ACBC5BB9F5B7075E8D594A8B8878659812EA4512470D1BDF8`
- `.github/workflows/test_build_webapp_v3.yml` (unchanged): `19F13820582BF4F2DF70FA0A2024A23CDD7843C36A71CDA60CB3CABBCCF5D194`

Local verification passed Python compile and the V3 flake8 command. The Windows stage has no nginx binary, so corrected `nginx -t` and runtime behavior are not locally verified.

## Tatsächliche Linux-Abnahme durch Root

Weblauf39040992426, Job117420299870, auf Head8aa64245c2bd7569d124853d8b95aad16296fdab ist completed/success. Neben Build,24 Bibliotheks-Jesttests,12 Web- und22 Pythonverträgen sowie beiden bestehenden Chromiumabnahmen besteht der neue vollständige nginx-Harness. Das Origin-/Host-/URI-/Methoden-/Auth-/TTL-/Fehler- und Katalog-/Browserfenster wurde tatsächlich durchlaufen; die Erfolgsmeldung lautet PASS: real nginx library smoke; nginx version: nginx/1.24.0 (Ubuntu). Damit sind exaktes nginx-t, isolierter Start, ursprünglicher leerer Origin und die getrennten Backend-/Authorizer-/Katalogzähler praktisch geprüft. Das enge unabhängige Source-Folgereview schließt beide P1 und P2 ohne neue Befunde. Aktuelle Pythonmatrizen und automatisch ausgelöste unveränderte Bookworm-ARMv7-Installerprüfung laufen bei diesem Zwischenstand noch; Integration wird noch nicht behauptet. Der ARMv7-Installerlauf ist kein Nachweis für den originalen Zero W.

## Integration

Beide Python3.9–3.13-Matrizen39040996371/39040992424 sind einschließlich finish completed/success. Merge6b872011c2e79263f61ca5384908b23251178a6b hat exakt den geprüften Baumfbf9127e7299bac52ada5fda9ce042cee7c6a9a9. Branchref und Eltern wurden remote bestätigt; alle3 lokalen Git-Blobs stimmen bytegenau mit dem Remote-Baum überein. develop bleibt unverändert. Der zusätzlich ausgelöste globale Bookworm-ARMv7-Installerlauf39040992456 lief bei Integration noch und gehört nicht zur opt-in Loopback-Abnahme. Kein Geräte-/LAN-/TLS-/Audio-/ARMv6- oder Produktionssessionnachweis daraus abgeleitet.

# U03a2 – Bibliotheksansicht und Abnahme

Abgeschlossen: echte Reactbibliothek mit Paging und Verfügbarkeit,24 Jestprüfungen, vollständiger Web-/Chromium-/Pythonabnahme und unabhängigen Reviews. PR16 ist alsb5190698a7b39abc8e5dc1062cee8334261474fc integriert; genaue Nachweise stehen am Ende. Die folgenden Abschnitte dokumentieren die Test- und Korrekturrunden.

Phase 1 is frozen at the three authorized paths. `LibraryPage.test.js` declares 10 Jest tests covering code-gated loading, safe text and status rendering, empty/paging/refresh behavior, 401 and forget cleanup, late-response suppression, unmount abort, fixed UI errors, and the actual client request and schema/error boundaries. `library_smoke.py` provides the planned built-browser path through a fixed same-origin loopback proxy to the real Linux catalog/API, using the browser-entered fixed synthetic 43-character test credential and 23 temporary registered files. The proxy relays the exact browser-supplied Authorization value and does not inject credentials. The workflow keeps all existing build, contract, preview-browser, and artifact steps, adds the targeted Jest run after build, then adds a three-minute catalog/browser step.

SHA-256 at freeze:

- `.github/workflows/test_build_webapp_v3.yml`: `5DF023B73F6EB8B1F3D73DA5E2CE09343FECAD0C92CCB58DBD5FF51FEE4FE63D`

- `src/webapp/src/components/DesignPreview/LibraryPage.test.js`: `D0DBFF68E8BDE52E8751E335CC02257AE5D54DF6CFEF32D18431A833CE141C58`

- `tests/design-preview/library_smoke.py`: `D2DE8C6F31E8A73373FA84452EB09903FC50A676BDC6ADF0DF3F3F3DFC7B29FC`

Checks run locally:

- `python -m py_compile tests/design-preview/library_smoke.py` — passed.

- `python -m flake8 --max-line-length=127 --max-complexity=12 --extend-ignore=E126,E127,E128,W503,F824 <absolute-stage-path>/tests/design-preview/library_smoke.py` from `G:\Entwicklung\phoniebox-tools\python` — passed.
- Confirmed `LibraryPage.js` and `libraryClient.js` are absent and the seeded `index.js` and `styles.css` remain untouched.

Jest, the React build, and Chromium were not run locally: the isolated stage has no CRA dependencies or build output, the runtime product modules are deliberately absent in this phase, and this Windows host cannot execute the Linux-only catalog. The workflow's planned RED is the targeted Jest step after the build, failing because the `LibraryPage` and `libraryClient` modules do not exist. Root must capture and match that actual remote CI result before Phase 2 creates either product module.

## Fix Round 1 freeze

Applied the requested corrections within the same three authorized files. The catalog/API imports now follow the canonical `components.library_*` package boundary. The real Chromium success path stores each registration result, derives expected page order from the real catalog, waits until each complete page's visible IDs match that exact order, and checks duplicate filenames against their registered IDs. The proxy preserves backend HTTP error status and bounded body. Separately labelled Fetch-controlled Chromium checks cover loading, empty results, 401 after visible data, 404, 503, malformed JSON, and a delayed old response after forget and re-entry with a new code. These controlled cases do not alter the real-catalog success path or use HTTP control routes.

The guard now permits only GETs to the startup asset map or the exact API route, blocks WebSockets, and checks 1024px overflow. Browser context and browser close in a nested `finally`; each page closes in `finally`. The harness checks that the product modules contain no `localStorage`, `sessionStorage`, or `document.cookie` use, without inspecting browser storage contents. The fixed synthetic credential is entered in the password field; the proxy forwards the exact supplied Authorization header and never injects it.

The Jest file now has 17 top-level test declarations, including a five-case independent invalid-response table (21 test executions total). Coverage adds deadline abort at 10 seconds and timer cleanup on timeout and success, an old response resolving after forget and a new code, valid UNKNOWN availability, independent duplicate-ID/unsafe-ID/cursor/row/list-schema failures, invalid JSON, and a fetch rejection whose raw detail must not escape. The workflow bounds the targeted Jest step to two minutes.

SHA-256 at this freeze:

- `.github/workflows/test_build_webapp_v3.yml`: `E6F6BD2498FE66AD3ECE6E15076A5AC9194CFE7B83069DE1E78A9739D781B078`

- `src/webapp/src/components/DesignPreview/LibraryPage.test.js`: `2B9AC6C8909428B4112232A420A7AE7479FE38A829D9EF7C4E8B53B19860E0E8`

- `tests/design-preview/library_smoke.py`: `3A30952E2C3F442A7288332FA6C2CBDAA6E30029484A4D53B293F8BF5B123D68`

Checks run: Python 3.12 `py_compile` passed; repository flake8 settings (127 columns, complexity 12, existing ignore list) passed; canonical catalog/API imports passed. The product modules remain absent and the seeded index/styles are untouched. I did not run Jest, build, or Chromium locally because CRA dependencies/build are absent and the catalog requires Linux.

The prior remote run `39035764388`, job `117405105177`, built successfully and the targeted Jest step failed with `Cannot find module './libraryClient'`. That result predates this Fix Round 1 head. The current frozen head still needs the serial review/readback and a fresh build-before-Jest RED; no new remote run is claimed here.

### Fix Round 1 final freeze update

Final hashes (these supersede the earlier Fix Round 1 hashes above):

- `.github/workflows/test_build_webapp_v3.yml`: `E6F6BD2498FE66AD3ECE6E15076A5AC9194CFE7B83069DE1E78A9739D781B078`

- `src/webapp/src/components/DesignPreview/LibraryPage.test.js`: `E69E3592CABAD37963646639A07E4AEF6AC197FF14E20A8A424E461DB6A4ABF8`

- `tests/design-preview/library_smoke.py`: `C75971EF9038BD033B8502F92B1FF761F37190CC00F5CE53CE5540E8EBB4C857`

The Linux catalog harness now patches only the catalog's UUID generator during fixture registration to produce stable, sequential IDs while exercising the real filesystem, `LibraryCatalog`, API server, and authorizer. Assertions compare those IDs with each fully rendered real API page. The timeout Jest mock now rejects when its supplied signal is aborted, matching Fetch cancellation behavior; it asserts the abort, safe alert, and cleared timer. The schema table has five independent malformed cases. Current count: 17 top-level Jest declarations, 21 executions after expansion.

Final checks: `python -m py_compile` passed; repository-configured flake8 passed; the canonical package imports and UUID patch seam imported successfully on this host. The temporary test `__pycache__` created by syntax checking was removed. No React/Jest/Chromium or Linux catalog runtime was executed locally. The prior remote RED run remains `39035764388` / job `117405105177`, with successful build then `Cannot find module './libraryClient'`; it predates this freeze and must not be treated as the updated-head result.

## Root-Nachtrag Testfix Runde2

Autor änderte ausschließlich den kontrollierten window.fetch-Wrapper zu async, damit sämtliche Fälle `Promise<Response>` liefern. Root bestätigt per Volltextvergleich ausschließlich diese eine Zeile. Finaler Harness-SHA25647d9cb49d0d5cf2bfaf55463be39f9b41bdd85eb2c801fb4446adec605ec9f69. Autor meldet pycompile und V3lint erfolgreich, keine tatsächliche Browserausführung. Sein Berichtsappend meldete Dateizugriff verweigert; Root ergänzt hier autorisiert die Prosa, keine ACL- oder Sandboxänderung. Generierter Cache bleibt ohne Veröffentlichungsabsicht liegen; keine Bereinigung erforderlich. Test-/Workflowhashes bleiben e69e3592/e6f6bd24; Produktmodule fehlen weiterhin.

Root hat den aktuellen tatsächlichen Web-RED39036483971/117407292781 gelesen: Build erfolgreich, Jest scheitert am fehlenden ./libraryClient. Dieser RED gilt für identische Jestinputs; die spätere einzeilige Harnesskorrektur wurde dabei ausdrücklich noch nicht ausgeführt. Die finale gemeinsame Source-CI muss den kompletten geänderten Harness durchführen.

## Phase 2 product freeze

Implemented the four authorized product paths only. `libraryClient.js` exposes `fetchLibraryPage` and `defaultLibraryPage`; it sends only a relative GET with Authorization, credentials omitted, no-store, redirect error, and AbortSignal, and validates the exact page/row schema, safe identifiers, duplicate IDs, statuses, page bound, and cursor consistency. `LibraryPage.js` keeps the submitted code, visible page, and cursor history in component memory only; it gates requests on valid 43-character code entry, uses a 10-second abort deadline, and combines generation invalidation with request aborts so forget, route unmount, newer requests, timeout, and stale 401s cannot restore or clear newer state. Errors are fixed safe strings; list text is rendered normally with IDs and text labels for all availability states.

`index.js` adds the `/library` route and navigation entry, keeps the seven existing pages, hides the global demo search only on the library route, and clarifies that player/device state is preview while the catalog is real. `styles.css` adds scoped responsive library styles using existing preview tokens.

Local validation: Node 24 module syntax check passed for `libraryClient.js`; source scan found no localStorage/sessionStorage/document.cookie use. React build, Jest, and Chromium were not run because `src/webapp/node_modules` is absent; no dependencies were installed. The frozen Jest and workflow SHA-256 values remain byte-identical to the reviewed RED input: E69E3592CABAD37963646639A07E4AEF6AC197FF14E20A8A424E461DB6A4ABF8 and E6F6BD2498FE66AD3ECE6E15076A5AC9194CFE7B83069DE1E78A9739D781B078. Harness hash remains the accepted Phase 1 value 47D9CB49D0D5CF2BFAF55463BE39F9B41BDD85EB2C801FB4446ADEC605EC9F69; it was not changed or executed in this phase.

Product path SHA-256:

- LibraryPage.js: 5A12375821A89577B3F9091C02A98D9E5F387867648FE1D7B442C2D17EF11A7E
- libraryClient.js: 92021A51377215EE830E49F89E0D3ACD9EFBCC4D7F93B6CA1CAC496613CD1649
- index.js: 22852BB0580F540F3E9BF31105A4D2A89E3FE9B3AE49B9542CF17ABC54300CC7
- styles.css: 45F709ADECC4641170E5DFD125C94A3A4010870FBD515EF8E97EE98C9984C978

### Phase 2 final hash correction

The final static review made small follow-up edits to the two new modules after the preceding report block was written. The authoritative final product hashes are:

- LibraryPage.js: `105A76C76164648BA63BAF6A0DA3350D16215BEBC86C6683F5C03360BB6F58E6`
- libraryClient.js: `8C56C15D6999D6FF9C72F64D80F4ECC928DBD2963EE51C51014D0A3414DCB1E0`
- index.js: `22852BB0580F540F3E9BF31105A4D2A89E3FE9B3AE49B9542CF17ABC54300CC7`
- styles.css: `45F709ADECC4641170E5DFD125C94A3A4010870FBD515EF8E97EE98C9984C978`

The Phase 1 test, harness, and workflow hashes remain as recorded above. No product file changes after these hashes were calculated.

## Phase A test-only response and focus regressions

Only `src/webapp/src/components/DesignPreview/LibraryPage.test.js` changed in this phase. The empty state now queries its heading by role/name and separately asserts that no catalog list is present, avoiding the prior heading-plus-paragraph strictness failure. The outstanding-request race now requires the refresh control to be present and enabled while loading, confirms it starts request two and aborts request one, then retains the resolved-newer/late-older assertion. A separate stale-401 race confirms an old unauthorized rejection cannot clear a newer access session. Focus coverage now checks initial submission to the library heading, 401/forget restoration to the code field, and no focus theft from refresh or paging controls.

Added one client boundary test for catalog `displayName`: accepts 255 UTF-8 bytes and whitespace-only non-empty text; rejects 256 bytes, ASCII control, DEL, and a lone surrogate, asserting `INVALID_RESPONSE` without raw name disclosure. The frozen client was not changed in Phase A. The test file has 19 top-level `test` declarations plus one five-row `test.each` table (24 test executions total).

Actual frozen-client probe result: the 255-byte multibyte boundary passed; five contract mismatches reproduced as RED: 256-byte name, ASCII control, DEL, and lone surrogate were accepted; whitespace-only was rejected with `INVALID_RESPONSE`.

Exact repro command (PowerShell, from `G:\Entwicklung\phoniebox-staging\u03-library-ui`; no file or dependency created):

```powershell
node --input-type=module -e "import{readFile}from'node:fs/promises';const s=await readFile('src/webapp/src/components/DesignPreview/libraryClient.js','utf8');const{fetchLibraryPage}=await import('data:text/javascript;base64,'+Buffer.from(s).toString('base64'));const code='a'.repeat(43);const item=n=>({libraryId:'lib_probe',displayName:n,availability:'AVAILABLE'});for(const[label,n,ok]of[['255-byte multibyte name','é'.repeat(127)+'a',true],['256-byte name','é'.repeat(128),false],['ASCII control','a\\u001fb',false],['DEL','a\\u007fb',false],['unpaired surrogate','\\uD800',false],['whitespace-only','   ',true]]){globalThis.fetch=async()=>({ok:true,status:200,json:async()=>({items:[item(n)],nextCursor:null})});let actual=false;let e='';try{await fetchLibraryPage(code,undefined,new AbortController().signal);actual=true}catch(x){e=x.code||'UNCLASSIFIED'}console.log((actual===ok?'PASS':'RED')+': '+label+'; expected='+(ok?'accept':'reject')+' actual='+(actual?'accept':'reject/'+e))}"
```

Final Phase A test SHA-256: `1527F75235ADBAF27F62955F1349D03825F0200144DDD17EE17436DA47E2B11B`. Product path hashes remain byte-identical to the Phase 2 freeze: LibraryPage.js `105A76C76164648BA63BAF6A0DA3350D16215BEBC86C6683F5C03360BB6F58E6`; libraryClient.js `8C56C15D6999D6FF9C72F64D80F4ECC928DBD2963EE51C51014D0A3414DCB1E0`; index.js `22852BB0580F540F3E9BF31105A4D2A89E3FE9B3AE49B9542CF17ABC54300CC7`; styles.css `45F709ADECC4641170E5DFD125C94A3A4010870FBD515EF8E97EE98C9984C978`. Jest was not run locally because CRA dependencies are absent. This Phase A is ready for Root to publish the single test path and capture its RED before any product correction.

### Phase A exact probe command (corrected copy form)

Use this one-line command as the copy/paste reproduction; it constructs ASCII controls and the lone surrogate through `String.fromCharCode`, avoiding shell escape ambiguity. It was rerun and reproduced the same five RED cases and one accepted boundary case:

```powershell
node --input-type=module -e "import{readFile}from'node:fs/promises';const s=await readFile('src/webapp/src/components/DesignPreview/libraryClient.js','utf8');const{fetchLibraryPage}=await import('data:text/javascript;base64,'+Buffer.from(s).toString('base64'));const code='a'.repeat(43);const item=n=>({libraryId:'lib_probe',displayName:n,availability:'AVAILABLE'});for(const[label,n,ok]of[['255-byte multibyte name','é'.repeat(127)+'a',true],['256-byte name','é'.repeat(128),false],['ASCII control','a'+String.fromCharCode(31)+'b',false],['DEL','a'+String.fromCharCode(127)+'b',false],['unpaired surrogate',String.fromCharCode(0xd800),false],['whitespace-only','   ',true]]){globalThis.fetch=async()=>({ok:true,status:200,json:async()=>({items:[item(n)],nextCursor:null})});let actual=false;let e='';try{await fetchLibraryPage(code,undefined,new AbortController().signal);actual=true}catch(x){e=x.code||'UNCLASSIFIED'}console.log((actual===ok?'PASS':'RED')+': '+label+'; expected='+(ok?'accept':'reject')+' actual='+(actual?'accept':'reject/'+e))}"
```

## Phase B authorized source and harness corrections

Implemented the six reviewed corrections within the seven approved paths. The API client now matches the backend display-name contract: nonempty strings (including whitespace-only), at most 255 UTF-8 bytes, no ASCII controls or DEL, and no unpaired surrogate. The library page keeps one enabled `Aktualisieren` control during loads, aborts/replaces the prior request through its existing generation guard, focuses the library heading after code submission, restores focus to the code field after forget/401, and does not move focus for paging/refresh. The navigation keeps the original first five links in order, places Library after RFID, and splits both groups at index 6. Pagination renders once for authorized state. The real catalog browser pass checks the actual page-two long title and ID at 1024/768/390/320px, records a 390px screenshot, and emits the separately marked bounded mobile review PNG when requested.

The exact Phase A Node24 probe was rerun against the corrected client: all six cases PASS (255-byte multibyte and whitespace-only names accepted; 256-byte, ASCII control, DEL, and lone-surrogate names rejected with `INVALID_RESPONSE`). The 19 top-level Jest tests plus five parameterized closed-schema cases remain unchanged from the Phase A freeze (24 executions expected). Node module syntax check passed. Python syntax compilation and V3 flake8 passed with repository limits (127 columns, complexity 12, only the existing configured ignores). No local CRA dependencies/build are present, so Jest, CRA build, and Chromium browser run were not claimed; Root's full CI is the runtime verification.

Frozen SHA-256 values:

- `LibraryPage.js`: `A5239CB22F2C7419ADA1E2776EB7F9BF6B13EF0B7DC4CA8A4170ACF9F0615B41`

- `libraryClient.js`: `10C4E50D8F4DCFC3AE98C91AFA82E93937189A6B849EB1BA23A77A72FB353A02`

- `index.js`: `359DBAF09F54CBD47F5A614684D0A1BE2B4CC3B621A917D1740A3D0B0D5B2D79`

- `styles.css`: `7564B7BAD51046FFCB7EDE93EBB62FC632B8C17C48C77C618E6A113E248BF038`

- `LibraryPage.test.js`: `1527F75235ADBAF27F62955F1349D03825F0200144DDD17EE17436DA47E2B11B`

- `library_smoke.py`: `9E948CFE8E3292274FD1BFE1E262C146187C598916588209496F73585B0D91C9`

- `.github/workflows/test_build_webapp_v3.yml` (unchanged): `E6F6BD2498FE66AD3ECE6E15076A5AC9194CFE7B83069DE1E78A9739D781B078`

## Root-Nachtrag zur finalen Source-Fixwelle

Autoritative finale Harness-SHA256 ist4e0de6c7dba2846183f5b5312d814a3175bb37cce792dac23e265794b89f395a; vorheriger9e948cfe-Berichtswert ist überholt. Root hat alle7Artefakthashes bestätigt und die Inhalte identisch zurückgelesen. Gleicher tatsächlicher Nodeprobe jetzt6PASS; V3Pythonlint Rootpass. Neue Gesamtprüfungen stehen noch aus, kein Browserpass vorgetäuscht.

Veröffentlichter Sourcefixhead251bd7f43a83cb6b51dd51eefd74d208e7166b8f, Tree6e4dba21c56631f68a00748a3d6debea8c64c329. Einige Autorenänderungen konvertieren LF nach CRLF; Root hat KEINE Produktdateien normalisiert. Reviewpaket verwendet exakte Artefaktkopien und git diff --no-index --ignore-space-at-eol, um die fachlichen Änderungen statt121kZeichen überwiegend EOL-Diff anzuzeigen. Alle tatsächlichen Datei-SHAs bleiben ausdrücklich Bestandteil der Prüfung.

## Narrow follow-up fixes after CI 39038056870

Applied only the three reviewed corrections. `forgetAccess` now marks the pending focus transfer before its state setters, so the focus effect can observe it even when React commits those updates synchronously; request generation invalidation and abort handling are unchanged. The refresh-and-paging Jest fixture now supplies the fourth (back-page) response its existing assertion triggers, avoiding an undefined successful result and the ensuing unhandled render path. The controlled empty browser case now selects the named `heading` role, avoiding the same heading-plus-paragraph ambiguity already corrected in Jest.

Local checks: Node module syntax passed; Python syntax compilation passed; V3 flake8 passed with the repository configuration. CRA/Jest and Chromium were not run locally because the stage lacks the CRA dependencies/build; the reported CI had 23/24 Jest passes and established the focus failure, while the fixture and browser-selector changes are now ready for Root's rerun.

Authoritative SHA-256 for the seven approved paths after this narrow fix:

- `LibraryPage.js`: `3858E481FF4B6C898D6E3599CB095D6B723C1DB9B93D4D1399589CCFF8DE2F0B`

- `libraryClient.js`: `10C4E50D8F4DCFC3AE98C91AFA82E93937189A6B849EB1BA23A77A72FB353A02`

- `index.js`: `359DBAF09F54CBD47F5A614684D0A1BE2B4CC3B621A917D1740A3D0B0D5B2D79`

- `styles.css`: `7564B7BAD51046FFCB7EDE93EBB62FC632B8C17C48C77C618E6A113E248BF038`

- `LibraryPage.test.js`: `CAA3BE383716D30C76F0CBB84126AA62636C84DC29CC6713E492D77A5AE03E29`

- `library_smoke.py`: `90BA9DF6955B4753A9711DB29115E7F59C0A3155B45148D22CEF8F02C0A78623`

- `.github/workflows/test_build_webapp_v3.yml` unchanged: `E6F6BD2498FE66AD3ECE6E15076A5AC9194CFE7B83069DE1E78A9739D781B078`

## Bounded network-guard diagnostic after CI 5291dbd6

The full library browser pass reached its final strict network guard after the real catalog, paging, long-name widths, mobile interactions, and controlled fetch cases. No request source could be identified from the available failure message, so the guard remains unchanged. The harness now records at most 20 forbidden requests as `METHOD scheme://host/path` (path capped at 160 characters); it omits query strings and headers, puts the sanitized entries in failure `report.json`, and includes at most ten in the assertion message. It still aborts every request outside the exact existing same-origin API and built-asset allowlist.

Python syntax compilation and repository V3 flake8 passed. This diagnostic-only change requires one CI rerun to reveal the concrete blocked request before any allowlist or product change.

Diagnostic harness SHA-256: `82F2D1079F1458AB8A35E8724A40492DF382BE477B80151BC5D7D38E2849201D`.

### Mobile-artifact settlement adjustment

Bundled into the same diagnostic harness update: before measuring/capturing either mobile long-title viewport, the harness now requires the native menu toggle to report collapsed, verifies the sidebar has no `sidebar-open` class and computed visibility is hidden, then waits two animation frames and verifies its settled rectangle remains fully left of the viewport. It does not mutate or hide the menu. The observed locale-related network hypothesis remains unproven; this update leaves browser locale, network guard, and asset allowlist unchanged so the bounded diagnostic CI can identify the actual request.

Final diagnostic/mobile-settlement `library_smoke.py` SHA-256: `05A52CF6F078172C711A79E4BFD3079602793A2AE8397DF3BE811D6DE5DB5D1D`. Python syntax compilation and V3 flake8 pass.

## Root handoff: confirmed locale correction

Actual diagnostic CI39038756951/job117413789400 on b39e9d6a identified repeated GET /locales/en-US/translation.json as the blocked request. Luna applied the existing react_smoke.py navigator-language fixture to the browser context before every page startup/reload: de with languages de/en. No storage/cookie write, allowlist expansion, product i18n change or guard weakening. Mobile settlement and bounded diagnostics remain. Final harness SHA256 462445f5928a453747fb95d3cee9a59651ecbf0effc8fc2cadc6b868cf8011ab; Root V3 flake8 and exact remote readback pass. Final full CI and independent narrow harness review remain pending. Root actually viewed the diagnostic mobile PNG and confirms the closed sidebar and full long-title/ID wrapping.

## Root final execution evidence – 8faef107

Full Web CI39039000758/job117414476131 completed/success: build,24/24 library Jest,12/12 web contracts,22/22 Python contracts, unchanged existing preview/legacy Chromium suite, and new real-catalog library Chromium all pass. Root actually viewed fresh desktop and mobile long-title PNGs from this exact run; visual acceptance passes. New harness completed strict HTTP/WS/console/pageerror assertions with the unchanged allowlist. All seven final remote source contents match the frozen stage, and the aggregate base-to-head diff contains exactly the seven approved paths. Independent final source/harness review reports SPEC/QUALITY PASS with F1–F7 closed and no new P1/P2. Full current Python matrices still await final3.13/finish at this checkpoint; integration is not yet claimed.

Final integration completed after both current Python3.9–3.13 matrices including finish succeeded. PR16 merged as b5190698a7b39abc8e5dc1062cee8334261474fc into future3/modern-ui. The merge tree is exactly the independently reviewed/tested 07395ff235641d2b23f928c7e37d69ff20f6f638; both original parents are preserved. Product ref and merge object verified remotely. develop remains42d5023e37dbf8de6477fef5ebcd6eae3cb5087d. U03a2 is verified/integrated within its documented view/testproxy scope; X01 is the separate next nginx slice.

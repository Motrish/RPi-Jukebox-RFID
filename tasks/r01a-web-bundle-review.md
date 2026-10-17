# R01a Phase 1 independent SPEC + QUALITY review

Verdict: request one bundled test correction before Phase 2. No P1 finding; five P2 acceptance gaps below. These concern tests, not an implementation: tools/web_bundle.py is absent.

Reviewed the full approved plan, author report, and both full frozen files. SHA-256 matches: tests 08090e0ebaa45845536b3cb5838fdc5d9d1a41776c3474e8ac391616eb056ddd; workflow f1f15dcbb20c072b69d6db2836cde817626d76693f71b927fdbd798851477788. Compared workflow with exact GitHub base 6b872011c2e79263f61ca5384908b23251178a6b (blob 3a21795341ee969b0e5ad2f2986ca1c0e84899c2). No executable artifacts, probes, workflow changes or GitHub mutations made.

## Findings

1. P2 - Digest verification can be omitted and all tampering cases still pass (test/web_bundle/test_web_bundle.py:133). Both archive mutations change length; the third changes declared size. Identity/schema/size checks alone satisfy these tests without hashing. Minimal regression: change one byte without changing length, retain original valid manifest and require rejection; restore bytes and require success. Also replace archiveSha256 with a different valid lowercase 64-hex digest while retaining original bytes/size. Do not parse the modified TAR.

2. P2 - Determinism can pass with wall-clock gzip metadata and variable ownership (line 75). Two CLI calls may occur within the same second, hiding a default gzip timestamp. Member checks assert mode but omit mtime/uid/gid/uname/gname. Minimal regression: assert fixed gzip timestamp and TAR time/ownership metadata, or force distinct packaging clocks; retain source-mtime and exact-member-byte checks. No npm reproducibility requirement is implied.

3. P2 - Strict verifier schema and bounds are incompletely exercised (lines 149, 209). Limits are tested only through package. A verifier accepting oversized metadata/archive bytes, excessive fileCount, missing keys or boolean/noninteger count/version fields can still pass. Minimal regression: remove each required field; exercise boolean, nonpositive, fractional and string numeric fields as applicable; reject malformed UTF-8/nonfinite constants. Use valid produced fixtures and lowered verifier limits for archive/manifest bounds, plus over-limit fileCount. Require a valid control before mutations. No TAR-content parsing is required.

4. P2 - Explicit producer protections remain unguarded (lines 182-207). Only one internal file symlink, one backslash name and existing manifest.json are covered. A producer silently skipping linked directories, reading FIFOs, accepting control-character names or malformed producer identity, or overwriting an existing archive is not excluded. Minimal Linux regressions: external directory symlink, FIFO, control-character filename, malformed package repository/commit, and independent existing archive/manifest cases preserving sentinel bytes. Bound CLI subprocess execution so FIFO rejection finishes promptly. Check unrelated sentinels survive and rejected packaging leaves no completed output pair. These are producer tests, not extraction tests.

5. P2 - Successful manifest field values are mostly unasserted (line 107). Tests check field names and digest but omit exact formatVersion/kind/repository/backendCommit/archiveName/size/fileCount values and integer types. Producer/verifier can share a wrong assumption, such as a fixed incorrect positive count, and pass. Minimal regression: compare every produced field with fixture identity, actual archive length and known member count; exclude bool for integer fields. Package and verify a second valid repository/commit identity to prove inputs determine output.

## Preserved behavior and limits

The unconditional setUpClass import is a missing-module RED sentinel with no skip/fallback. Actual successful-build-then-import-RED Linux evidence remains Root's CI check, not established by this static review. Fixtures contain real nested HTML/JS/CSS/JSON bytes; tests exercise CLI processes and inspect only their trusted producer output.

All previous workflow commands/guards, trigger entries and ten-minute job deadline are preserved. Packaging follows all previous gates. Actual checkout HEAD supplies the full artifact commit; repository identity comes from GitHub context. Upload/download uses the concrete upload artifact ID and separate runner-temp paths, then repeats offline verification with the same expected identity. No concrete workflow regression found; successful upload/download needs Phase 2 CI evidence.

No source implementation, untrusted extraction, installation, authentication, network delivery, public bootstrap, target-device, or full R01 acceptance is implied. Authenticity requires a later trusted manifest delivery channel. Correct tests together, preserve early import sentinel, refreeze and accept tests before implementing the module.

## Phase 1 correction closure read

Reviewed the complete corrected test file at SHA-256 c97418b224f198b3781f2345f72f1a87b2cd4fcd9241a0d94ea3294dc580697a. The unconditional early tools.web_bundle import is preserved. Root separately confirmed actual Linux build/library success followed by missing-module RED (run 39043364778, job 117427131261). No executable changes or probes made during this closure read.

Findings 1, 2 and 3 are closed for Phase 1: same-length archive corruption and valid-but-wrong digest, fixed gzip/TAR metadata, additional invalid schema documents and verifier byte bounds now have direct checks. FIFO timeout, external linked directory, both clobber sentinels, malformed producer identities and exact manifest values also address most of findings 4 and 5.

Two concrete P2 residuals require a small test-only correction:

- Finding 4 remains partially open: test_producer_rejects_missing_index_and_invalid_relative_names leaves bad-backslash-name.js present when it adds the control-character filename. The control-name rejection can therefore pass solely because the earlier backslash filename is still invalid. Remove the backslash fixture before testing the newline filename, or use separate tests/fresh builds. The control-name test must contain no other invalid input.
- Finding 5 remains partially open: the prior exact manifest key-set assertion was removed. Exact field values are now checked, but a producer/verifier pair sharing an extra field such as foo can pass: the unknown-field negative case only adds extra, and missing-field tests iterate whatever the producer emitted. Restore an assertion that set(manifest) equals the eight approved field names before those mutations.

No additional workflow finding. Re-review only these two corrections at the next freeze; implementation remains outside this review.

Host portability note for residual 4: on Windows a backslash is a separator and a newline filename is unavailable. Isolate these Linux filename regressions with an explicit host skip (or separate platform-gated cases), leaving missing-index coverage cross-platform. This prevents fixture-construction errors from breaking the planned local suite; Linux CI must execute both invalid-name checks.

## Phase1 Abschlussentscheidung

Root hat die zwei engen Restbefunde am eingefrorenen Test b1d6a04c44beda12ea1dcce8bef0d2b0372781d637059a2472431e3931cdc02a selbst gelesen: exakte Achtfeldmenge wiederhergestellt, Backslashfixture vor isolierter Steuerzeichenprobe entfernt; nur POSIX-Namenproben werden auf Windows übersprungen, Missing-index bleibt plattformübergreifend. Producer bleibt zu diesem Zeitpunkt tatsächlich abwesend. Alle5P2 samt2Restpunkten geschlossen. Früher unveränderter Import-Sentinel und tatsächlicher Linux-RED reichen nach dem expliziten Planruling; keine Behauptung, die später korrigierten Tests seien schon auf Linux ausgeführt. Phase2 an Luna freigegeben: ausschließlich tools/web_bundle.py. Vollständiger Source-/Testpass einschließlich Linux-Sonderdateiproben folgt vor Integration.
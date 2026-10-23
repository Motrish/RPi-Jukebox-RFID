#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

readonly SOURCE_COMMIT=19959512c212cbc48a3ff64382fe204f52c659a7
readonly LOCK_BLOB=68fa2e109f03ed820143b005ea5779e6b325c530
readonly IMAGE_REVISION=526d03ddcd2f70e683074b3ea6f75ed300f33132
readonly TARGET=arm-unknown-linux-musleabihf
readonly FEATURES=rustls-tls-webpki-roots,with-libmdns
readonly RUST_VERSION=1.90.0
readonly RING_VERSION=0.17.14

fail() { printf 'S01 probe build: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || fail "required tool not found: $1"; }

export PATH=/opt/rust/bin:$PATH
export CARGO_HOME=/tmp/s01-cargo-home
export CARGO_TARGET_DIR=/tmp/s01-target
for tool in bash sha256sum apt-get dpkg-query rustc cargo timeout qemu-arm file readelf arm-unknown-linux-musleabihf-gcc; do need "$tool"; done

mkdir -p /out
readonly out=/out
if ! command -v python3 >/dev/null 2>&1; then
  [[ "$(id -u)" == 0 ]] || fail 'python3 is absent and the container is not root; cannot install the required JSON/license helper'
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3
fi
need python3
cat /etc/os-release > "$out/container-os-release.txt"
{
  printf 'python_version=%s\n' "$(python3 --version 2>&1)"
  dpkg-query -W -f='${binary:Package}\t${Version}\n' python3 python3-minimal
  apt-cache policy python3 python3-minimal
} > "$out/python-runtime-provenance.txt"

[[ "$(rustc --version | awk '{print $2}')" == "$RUST_VERSION" ]] || fail 'rustc version mismatch'
[[ "$(rustc -vV | awk -F': ' '$1 == "host" {print $2}')" == x86_64-unknown-linux-gnu ]] || fail 'unexpected rustc host'
[[ "$(arm-unknown-linux-musleabihf-gcc -dumpmachine)" == "$TARGET" ]] || fail 'unexpected C linker target'
[[ "$(arm-unknown-linux-musleabihf-gcc -dumpfullversion -dumpversion)" == 14.4.0 ]] || fail 'cross GCC version changed from the audited image'
[[ "$(arm-unknown-linux-musleabihf-gcc -print-sysroot)" == /x-tools/arm-unknown-linux-musleabihf/arm-unknown-linux-musleabihf/sysroot ]] || fail 'cross GCC sysroot changed from the audited image'
compiler_macros="$(printf '' | arm-unknown-linux-musleabihf-gcc -dM -E -x c -)"
grep -Eq '^#define __ARM_ARCH 6$|^#define __ARM_ARCH_6__ 1$' <<< "$compiler_macros" || fail 'C compiler is not targeting ARMv6'
grep -q '^#define __ARM_PCS_VFP 1$' <<< "$compiler_macros" || fail 'C compiler is not using the VFP hard-float ABI'

mkdir -p "$CARGO_HOME"

{
  printf 'S01 Spotify ARMv6 manual probe build\n'
  printf 'toolchain_image=ghcr.io/cross-rs/arm-unknown-linux-musleabihf@sha256:41abfe511a58facf4d07a23fece3b648062c781baa6a7afc17306f9cb6e6ffca\nimage_source_revision=%s\n' "$IMAGE_REVISION"
  printf 'upstream_commit=%s\nlock_git_blob=%s\n' "$SOURCE_COMMIT" "$LOCK_BLOB"
  printf 'lock_sha256=%s\n' "$(sha256sum Cargo.lock | awk '{print $1}')"
  printf 'target=%s\nfeatures=%s\nrust_version=%s\n' "$TARGET" "$FEATURES" "$RUST_VERSION"
  printf 'rustc_verbose:\n%s\n' "$(rustc -vV)"
  printf 'rust_sysroot=%s\n' "$(rustc --print sysroot)"
  printf 'rust_target_cfg:\n%s\n' "$(rustc --print cfg --target "$TARGET")"
  printf 'cargo_version=%s\n' "$(cargo --version)"
  printf 'c_compiler=%s\n' "$(command -v arm-unknown-linux-musleabihf-gcc)"
  arm-unknown-linux-musleabihf-gcc -dumpfullversion -dumpversion
  printf 'c_linker_version:\n'
  linker_path="$(arm-unknown-linux-musleabihf-gcc -print-prog-name=ld)"
  printf 'linker_path=%s\n' "$linker_path"
  "$linker_path" --version | sed -n '1p'
  printf 'rustflags=-C target-cpu=arm1176jzf-s\ncflags=-mcpu=arm1176jzf-s -mfpu=vfp -mfloat-abi=hard\n'
  printf 'sysroot=%s\n' "$(arm-unknown-linux-musleabihf-gcc -print-sysroot)"
  printf 'qemu_version=%s\n' "$(qemu-arm --version | sed -n '1p')"
  printf 'musl_loader_banner:\n'
  loader_banner="$(qemu-arm -cpu arm1176 -L "$(arm-unknown-linux-musleabihf-gcc -print-sysroot)" \
    "$(arm-unknown-linux-musleabihf-gcc -print-sysroot)/lib/ld-musl-armhf.so.1" --help 2>&1)" || [[ $? -eq 1 ]]
  printf '%s\n' "$loader_banner"
  [[ "$loader_banner" == *'Version 1.2.5'* ]] || fail 'target musl loader is not the audited 1.2.5 version'
} > "$out/provenance.txt"

export CC_arm_unknown_linux_musleabihf=arm-unknown-linux-musleabihf-gcc
export AR_arm_unknown_linux_musleabihf=arm-unknown-linux-musleabihf-ar
export CFLAGS_arm_unknown_linux_musleabihf='-mcpu=arm1176jzf-s -mfpu=vfp -mfloat-abi=hard'
export CARGO_TARGET_ARM_UNKNOWN_LINUX_MUSLEABIHF_LINKER=arm-unknown-linux-musleabihf-gcc
export RUSTFLAGS='-C target-cpu=arm1176jzf-s'

printf '== Active locked Cargo feature graph ==\n' | tee "$out/features.txt"
cargo tree --locked --no-default-features --features "$FEATURES" --target "$TARGET" -e features -f '{p} {f}' \
  | tee -a "$out/features.txt"
if grep -Eiq '(^|[^[:alnum:]_-])(native-tls|openssl|openssl-sys|alsa|alsa-sys|rodio|cpal|aws-lc|aws-lc-rs)([^[:alnum:]_-]|$)' "$out/features.txt"; then
  fail 'forbidden native TLS/audio/crypto dependency is active'
fi
grep -Eq 'ring v0\.17\.14([[:space:]]|$)' "$out/features.txt" || fail 'expected ring 0.17.14 is not active'

printf '== Locked release build ==\n'
set -o pipefail
cargo build --locked --release --no-default-features --features "$FEATURES" \
  --bin librespot --target "$TARGET" --message-format=json-render-diagnostics \
  2>&1 | tee "$out/cargo-build.jsonl"
cargo metadata --locked --format-version 1 --filter-platform "$TARGET" > "$out/cargo-metadata.json"

python3 - "$out/cargo-build.jsonl" "$out/ring-selection.json" "$out/cargo-metadata.json" "$out" <<'PY'
import json, pathlib, re, shutil, sys
log = pathlib.Path(sys.argv[1])
metadata = json.loads(pathlib.Path(sys.argv[3]).read_text())
out = pathlib.Path(sys.argv[4])
matches = []
native = []
linked_libs = []
compiled_packages = set()
for line in log.read_text(errors="replace").splitlines():
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        continue
    if obj.get("reason") == "compiler-artifact":
        target = obj.get("target", {})
        package = obj.get("package_id", "")
        compiled_packages.add(package)
        if package.endswith("#ring@0.17.14") and target.get("name") == "ring" and "lib" in target.get("kind", []):
            for filename in obj.get("filenames", []):
                if filename.endswith(".rlib"):
                    matches.append({"package_id": package, "target": target, "rlib": filename, "features": obj.get("features", [])})
    elif obj.get("reason") == "build-script-executed" and obj.get("package_id", "").endswith("#ring@0.17.14"):
        native.extend(obj.get("linked_paths", []))
        linked_libs.extend(obj.get("linked_libs", []))
if len(matches) != 1:
    raise SystemExit(f"expected one ring 0.17.14 lib rlib in Cargo JSON, found {len(matches)}")
pathlib.Path(sys.argv[2]).write_text(json.dumps({"ring": matches[0], "linked_paths": native, "linked_libs": linked_libs}, indent=2) + "\n")

packages = {item["id"]: item for item in metadata["packages"]}
license_root = out / "licenses"
license_root.mkdir(exist_ok=True)
inventory = ["Package ID\tDeclared license\tCopied license/notice files"]
for package_id in sorted(compiled_packages):
    package = packages.get(package_id)
    if package is None:
        inventory.append(f"{package_id}\tUNKNOWN\tmetadata package missing")
        continue
    manifest = pathlib.Path(package["manifest_path"]).resolve()
    root = manifest.parent
    candidates = []
    explicit = package.get("license_file")
    if explicit:
        candidate = pathlib.Path(explicit)
        if not candidate.is_absolute():
            candidate = root / candidate
        candidates.append(candidate)
    for candidate in root.iterdir():
        if candidate.is_file() and re.match(r"^(LICENSE|COPYING|NOTICE)(\b|[._-])", candidate.name, re.I):
            candidates.append(candidate)
    license_dir = root / "licenses"
    if license_dir.is_dir():
        candidates.extend(path for path in license_dir.rglob("*") if path.is_file())
    copied = []
    destination = license_root / f"{package['name']}-{package['version']}"
    for candidate in sorted(set(candidates), key=lambda item: str(item)):
        resolved = candidate.resolve()
        if not resolved.is_file() or not resolved.is_relative_to(root):
            continue
        relative = resolved.relative_to(root)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(resolved, target)
        copied.append(relative.as_posix())
    inventory.append("\t".join((package_id, package.get("license") or "UNDECLARED", "; ".join(copied) or "no matching text file found")))
(out / "dependency-license-inventory.tsv").write_text("\n".join(inventory) + "\n")
PY

binary="$CARGO_TARGET_DIR/$TARGET/release/librespot"
[[ -f "$binary" ]] || fail 'locked Cargo build did not produce the expected librespot binary'
cp "$binary" "$out/librespot-armv6-musl"
python3 - "$out/ring-selection.json" "$out/ring-rlib.sha256" <<'PY'
import hashlib, json, pathlib, sys
record = json.loads(pathlib.Path(sys.argv[1]).read_text())
path = pathlib.Path(record["ring"]["rlib"])
if not path.is_file():
    raise SystemExit(f"selected ring rlib does not exist: {path}")
pathlib.Path(sys.argv[2]).write_text(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path}\n")
PY

printf '== Static ELF and ARMv6 ABI checks ==\n' | tee "$out/elf-inspection.txt"
file "$out/librespot-armv6-musl" | tee -a "$out/elf-inspection.txt"
readelf -h "$out/librespot-armv6-musl" | tee -a "$out/elf-inspection.txt"
headers="$(readelf -h "$out/librespot-armv6-musl")"
grep -Eq 'Class:[[:space:]]+ELF32' <<< "$headers" || fail 'binary is not ELF32'
grep -Eq 'Data:[[:space:]]+2.s complement, little endian' <<< "$headers" || fail 'binary is not little-endian'
grep -Eq 'Machine:[[:space:]]+ARM([[:space:]]|$)' <<< "$headers" || fail 'binary is not ARM'
grep -Eq 'Flags:.*Version5 EABI, hard-float ABI' <<< "$headers" || fail 'binary is not ARM EABI hard-float'
program_headers="$(readelf -l "$out/librespot-armv6-musl")"
printf '%s\n' "$program_headers" >> "$out/elf-inspection.txt"
[[ "$program_headers" != *INTERP* ]] || fail 'binary has a dynamic interpreter'
dynamic="$(readelf -d "$out/librespot-armv6-musl" 2>&1)" || fail 'readelf dynamic inspection failed'
[[ "$dynamic" != *'(NEEDED)'* ]] || fail 'binary has shared-library dependencies'
printf '%s\n' "$dynamic" >> "$out/elf-inspection.txt"
attributes="$(readelf -A "$out/librespot-armv6-musl")"
printf '%s\n' "$attributes" >> "$out/elf-inspection.txt"
grep -Eq 'Tag_CPU_arch: v[67]' <<< "$attributes" || fail 'ELF has no ARMv6-or-newer architecture attribute'
grep -Eq 'Tag_FP_arch: VFPv2|Tag_FP_arch: VFPv3' <<< "$attributes" || fail 'ELF does not declare a VFP architecture'
grep -Eq 'Tag_ABI_VFP_args: VFP registers' <<< "$attributes" || fail 'ELF does not declare hard-float VFP argument ABI'

printf '== ARM1176 CLI startup checks ==\n' | tee "$out/qemu-startup.txt"
version_output="$(timeout 15s qemu-arm -cpu arm1176 "$out/librespot-armv6-musl" --version 2>&1)" || fail 'ARM1176 --version startup failed'
printf '%s\n' "$version_output" | tee -a "$out/qemu-startup.txt"
grep -Eiq 'librespot' <<< "$version_output" || fail 'ARM1176 --version output did not identify librespot'
help_output="$(timeout 15s qemu-arm -cpu arm1176 "$out/librespot-armv6-musl" --help 2>&1)" || fail 'ARM1176 --help startup failed'
printf '%s\n' "$help_output" | tee -a "$out/qemu-startup.txt"
grep -q -- '--backend' <<< "$help_output" || fail 'ARM1176 help output is missing --backend'
grep -q -- '--enable-device-auth' <<< "$help_output" || fail 'ARM1176 help output is missing device authorization'

cat > "$out/ring-crypto-smoke.rs" <<'RUST'
use ring::{digest, hmac, aead, signature};

fn hex_to_bytes(hex: &str) -> Vec<u8> {
    assert!(hex.len() % 2 == 0);
    (0..hex.len()).step_by(2).map(|i| u8::from_str_radix(&hex[i..i + 2], 16).unwrap()).collect()
}

fn main() {
    // SHA256
    // https://github.com/briansmith/ring/blob/2723abbca9e83347d82b056d5b239c6604f786df/tests/digest_tests.txt#L25
    let data = b"abc";
    let expected_sha256 = hex_to_bytes("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    let digest = digest::digest(&digest::SHA256, data);
    assert_eq!(digest.as_ref(), expected_sha256);

    // HMAC-SHA256
    // https://www.rfc-editor.org/rfc/rfc4231.html#section-4.2
    let key = [0x0b; 20];
    let message = b"Hi There";
    let expected_hmac = hex_to_bytes("b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7");
    let hmac_key = hmac::Key::new(hmac::HMAC_SHA256, &key);
    let hmac_tag = hmac::sign(&hmac_key, message);
    assert_eq!(hmac_tag.as_ref(), expected_hmac);
    assert!(hmac::verify(&hmac_key, message, &expected_hmac).is_ok());
    let mut corrupt_hmac = expected_hmac.clone();
    corrupt_hmac[0] ^= 0xff;
    assert!(hmac::verify(&hmac_key, message, &corrupt_hmac).is_err());

    // AES128GCM
    // https://github.com/briansmith/ring/blob/2723abbca9e83347d82b056d5b239c6604f786df/tests/aead_aes_128_gcm_tests.txt#L448
    let key = [0u8; 16];
    let nonce = [0u8; 12];
    let plaintext = [0u8; 16];
    let aad = b"";
    let expected_ciphertext_tag = hex_to_bytes("0388dace60b6a392f328c2b971b2fe78ab6e47d42cec13bdf53a67b21257bddf");
    let sealing_key = aead::LessSafeKey::new(aead::UnboundKey::new(&aead::AES_128_GCM, &key).unwrap());
    let mut buffer = plaintext.to_vec();
    sealing_key.seal_in_place_append_tag(aead::Nonce::assume_unique_for_key(nonce), aead::Aad::from(aad), &mut buffer).unwrap();
    assert_eq!(buffer, expected_ciphertext_tag);
    let opening_key = aead::LessSafeKey::new(aead::UnboundKey::new(&aead::AES_128_GCM, &key).unwrap());
    let mut buffer_copy = expected_ciphertext_tag.clone();
    let opened = opening_key.open_in_place(aead::Nonce::assume_unique_for_key(nonce), aead::Aad::from(aad), &mut buffer_copy).unwrap();
    assert_eq!(opened, &plaintext[..]);
    let mut corrupt_ciphertext_tag = expected_ciphertext_tag.clone();
    corrupt_ciphertext_tag[31] ^= 0xff;
    assert!(opening_key.open_in_place(aead::Nonce::assume_unique_for_key(nonce), aead::Aad::from(aad), &mut corrupt_ciphertext_tag).is_err());

    // Ed25519
    // https://www.rfc-editor.org/rfc/rfc8032.html#section-7.1
    let publickey = hex_to_bytes("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a");
    let sig = hex_to_bytes("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b");
    let public_key = signature::UnparsedPublicKey::new(&signature::ED25519, &publickey);
    assert!(public_key.verify(b"", &sig).is_ok());
    let mut corrupt_sig = sig.clone();
    corrupt_sig[0] ^= 0xff;
    assert!(public_key.verify(b"", &corrupt_sig).is_err());

    println!("S01_ARMV6_CRYPTO_SMOKE_OK");
}
RUST

python3 - "$out/ring-crypto-smoke.rs" <<'PY'
import pathlib, sys
path = pathlib.Path(sys.argv[1])
source = path.read_bytes()
if not source.endswith(b"\n"):
    raise SystemExit("crypto harness here-document ended unexpectedly")
path.write_bytes(source[:-1])
PY
readonly crypto_source_sha=F900A04FF75C8026A1C96B818DA03CF1AD5708EF49D05D46C21397E8F3AC5DB4
actual_crypto_source_sha="$(sha256sum "$out/ring-crypto-smoke.rs" | awk '{print toupper($1)}')"
[[ "$actual_crypto_source_sha" == "$crypto_source_sha" ]] || fail 'embedded reviewed crypto source hash mismatch'
printf '%s  %s\n' "$actual_crypto_source_sha" ring-crypto-smoke.rs > "$out/ring-crypto-smoke.sha256"

python3 - "$out/ring-selection.json" "$out/ring-crypto-smoke.rs" "$out/ring-crypto-smoke" <<'PY'
import json, pathlib, subprocess, sys
record = json.loads(pathlib.Path(sys.argv[1]).read_text())
ring = pathlib.Path(record["ring"]["rlib"])
deps = pathlib.Path("/tmp/s01-target/arm-unknown-linux-musleabihf/release/deps")
cmd = ["/opt/rust/bin/rustc", sys.argv[2], "--edition=2021", "--target", "arm-unknown-linux-musleabihf",
       "--extern", f"ring={ring}", "-L", f"dependency={deps}", "-C", "linker=arm-unknown-linux-musleabihf-gcc",
       "-C", "target-cpu=arm1176jzf-s", "-o", sys.argv[3]]
for item in record.get("linked_paths", []):
    kind, _, path = item.partition("=")
    if kind != "native" or not pathlib.Path(path).is_dir():
        raise SystemExit(f"unexpected ring native link path: {item}")
    cmd += ["-L", f"native={path}"]
for item in record.get("linked_libs", []):
    kind, sep, name = item.partition("=")
    if not sep or kind not in {"static", "dylib", "framework"} or not name:
        raise SystemExit(f"unexpected ring native link library: {item}")
    cmd += ["-l", f"{kind}={name}"]
print("crypto harness rustc command:", " ".join(cmd))
subprocess.run(cmd, check=True)
PY

(
  cd "$out"
  sha256sum ring-crypto-smoke > ring-crypto-smoke-binary.sha256
)
crypto_headers="$(readelf -h "$out/ring-crypto-smoke")" || fail 'could not inspect crypto harness ELF header'
grep -Eq 'Class:[[:space:]]+ELF32' <<< "$crypto_headers" || fail 'crypto harness is not ELF32'
grep -Eq 'Machine:[[:space:]]+ARM([[:space:]]|$)' <<< "$crypto_headers" || fail 'crypto harness is not ARM'
crypto_program_headers="$(readelf -l "$out/ring-crypto-smoke")" || fail 'could not inspect crypto harness program headers'
[[ "$crypto_program_headers" != *INTERP* ]] || fail 'crypto harness has a dynamic interpreter'
printf '%s\n%s\n' "$crypto_headers" "$crypto_program_headers" > "$out/ring-crypto-elf.txt"
printf '== Ring 0.17.14 crypto known-answer smoke on ARM1176 ==\n' | tee "$out/qemu-crypto.txt"
crypto_output="$(timeout 60s qemu-arm -cpu arm1176 "$out/ring-crypto-smoke" 2>&1)" || {
  printf '%s\n' "$crypto_output" | tee -a "$out/qemu-crypto.txt"
  fail 'ARM1176 crypto smoke execution failed'
}
printf '%s\n' "$crypto_output" | tee -a "$out/qemu-crypto.txt"
[[ "$crypto_output" == 'S01_ARMV6_CRYPTO_SMOKE_OK' ]] || fail 'ARM1176 crypto smoke did not emit its exact success marker'

cp LICENSE "$out/librespot-LICENSE"
cat > "$out/ARTIFACT-README.txt" <<'EOF'
Manual ARMv6 Spotify/librespot probe, built from the pinned upstream source and lockfile.
Only use for the bounded manual test in docs/spotify-armv6-probe.md.
This is not a product integration, service, or public release. It contains no user account data.
Inspect provenance.txt, features.txt, ELF inspection, and QEMU startup/crypto reports before use.
Open-source notices are collected for packages compiled in this build; see dependency-license-inventory.tsv.
The inventory reports missing license text and does not claim legal completeness.
EOF
printf 'S01_ARMV6_PROBE_BUILD_COMPLETE\n' >> "$out/provenance.txt"
(
  cd "$out"
  sha256sum librespot-armv6-musl > binary.sha256
)
chmod -R a+rX "$out"

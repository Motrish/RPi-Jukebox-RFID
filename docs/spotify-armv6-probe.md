# Spotify probe on the original Pi Zero W

This is a short, manually started feasibility test for the original ARMv6 Pi Zero W with Raspbian 13 (Trixie, 32-bit) and the confirmed MiniAmp. It uses the standalone librespot binary produced by the `Spotify ARMv6 probe` workflow and the Pi's already-installed `aplay`. It is not a Phoniebox integration, service, public binary release, or promise of queue/stop behavior.

## Build and artifact

Run the workflow on branch `codex/s01-armv6-spotify-probe` or start it manually. It checks out the probe files without persisting a GitHub credential, checks out librespot at commit `19959512c212cbc48a3ff64382fe204f52c659a7`, and verifies the exact Cargo.lock Git blob `68fa2e109f03ed820143b005ea5779e6b325c530`. It builds in the audited immutable image `ghcr.io/cross-rs/arm-unknown-linux-musleabihf@sha256:41abfe511a58facf4d07a23fece3b648062c781baa6a7afc17306f9cb6e6ffca` after checking its OCI source-revision label. The build uses Rust 1.90.0, the `arm-unknown-linux-musleabihf` target, and only `rustls-tls-webpki-roots,with-libmdns` features. The report captures the active Cargo graph, lock/source provenance, compiler and image identity, binary hashes and ELF inspection. The artifact also carries upstream and dependency license/notice texts found for compiled packages and an inventory that records packages with no matching text file; that inventory does not claim legal completeness. The workflow uploads the binary only after locked-build, static ARM ABI, CLI-startup and ring crypto smoke checks all pass. Artifacts expire after seven days.

The ring check links the exact `ring 0.17.14` rlib reported by this build's Cargo JSON output. Its source, SHA-256, selected rlib identity/hash and linker inputs are included with the artifact. QEMU executes SHA-256, HMAC-SHA256, AES-128-GCM and Ed25519 known-answer checks on CPU `arm1176`, including invalid-tag/signature rejection. This checks those provider paths on emulated ARM1176; it does not prove a complete TLS session, Spotify authentication or real hardware playback.

## Prepare the Pi

1. Download the successful workflow artifact to a temporary directory on a trusted workstation. In the artifact directory, run `sha256sum -c binary.sha256`. Read the provenance, feature, ELF and QEMU reports. Transfer the binary over your usual trusted method; do not copy any auth cache into the artifact or repository.
2. On the Pi, create private directories owned by the account that will run librespot. Keep the credential cache out of the repository and shared media directory:

   ```sh
   install -d -m 700 "$HOME/.cache/librespot-probe" "$HOME/.cache/librespot-probe-audio"
   chmod 700 "$HOME/.cache/librespot-probe" "$HOME/.cache/librespot-probe-audio"
   ```

3. Put the binary in a private temporary test directory and enter that directory. Since ZIP extraction may discard executable bits, set them explicitly, then check the binary's native startup before signing in. Confirm the expected card is present and aplay can open it at a low volume. The playback command specifies the stereo MiniAmp card and raw signed 16-bit little-endian PCM at 44.1 kHz. Stop if the card name differs; do not substitute another device by guess.

   ```sh
   chmod 700 ./librespot-armv6-musl
   ./librespot-armv6-musl --version
   ./librespot-armv6-musl --help
   ```

## Sign in and listen

Run this in a local terminal on the Pi, not in CI. The device authorization code and URL remain visible in the terminal because librespot's subprocess backend sends PCM only to the child process's stdin. Pair the code yourself at Spotify's displayed pairing page. Never paste a password, OAuth token, or cache contents into CI, tickets, or chat.

```sh
./librespot-armv6-musl \
  --backend subprocess \
  --device 'aplay -D plughw:CARD=sndrpihifiberry,DEV=0 -t raw -f S16_LE -c 2 -r 44100' \
  --format S16 \
  --volume-ctrl log \
  --initial-volume 8 \
  --cache "$HOME/.cache/librespot-probe-audio" \
  --system-cache "$HOME/.cache/librespot-probe" \
  --enable-device-auth
```

The initial volume is deliberately low. Use the normal Spotify client to select this receiver and start one short track. Verify sound from both MiniAmp channels, pause/resume, then stop the librespot process with Ctrl-C. Check that the particular `aplay` child exits and that the card can be reopened before another run. Do not use a broad `pkill aplay` or stop other audio processes. After the first authorization, restart the same command without `--enable-device-auth` to check cached sign-in; keep the cache private. Adjust volume only in small steps.

For this pinned upstream implementation, subprocess stop closes the PCM input and kills/waits for its child before reporting Paused/Stopped. A natural track end does not itself stop/close the sink; the player may retain it for connection or gapless behavior. The subprocess backend also lacks drop cleanup and has a possible partial-write accounting issue. Treat a short successful listen as a feasibility result only. It does not establish guaranteed card release on every error, lossless long playback, queue mixing, central stop semantics, or service reliability. Stop the test if playback is silent, distorted, unexpectedly loud, the card remains busy, or the child process persists.

## What CI does not do

The workflow builds and emulates only. It has no Spotify credentials, account login, device cache, secrets, or access to the Pi. No service is installed and no account action is performed automatically. Device authorization and real MiniAmp playback are user-run steps after inspecting the artifact.

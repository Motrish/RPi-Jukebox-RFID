# Librespot ARMv6 Cross-Compilation Spike

## Objective
Cross-compile librespot for ARMv6 (arm-unknown-linux-gnueabihf) and verify it runs on Raspberry Pi Zero/1.

## Build Script
See `build-armv6.sh`.

## Systemd Unit
See `librespot.service`. Token refresh is handled internally by librespot using stored credentials (OAuth client ID/secret from config).

## Build Environment
- Host: Ubuntu 22.04 (GitHub Actions runner)
- Rust toolchain: stable
- Target: `arm-unknown-linux-gnueabihf`
- Linker: `arm-linux-gnueabihf-gcc` (installed via `apt-get install gcc-arm-linux-gnueabihf`)

## Results

| Item | Result |
|------|--------|
| Cross-compilation | **Not executed** (Docker daemon unavailable in CI environment) |
| Binary size | N/A |
| Start log | N/A |
| Token refresh test | N/A |

## Next Steps
1. Enable Docker daemon in CI (or use self-hosted ARM runner).
2. Run `build-armv6.sh` inside `arm32v7/debian:bookworm` container.
3. Verify binary runs on target hardware.
4. Integrate with Phoniebox installer (copy binary to `/usr/local/bin/librespot`, install systemd unit, generate default config).

## Notes
- Librespot handles token refresh automatically when credentials are provided.
- For headless operation, use `--disable-audio-cache` if disk space limited.
- Consider using `--backend alsa` for direct ALSA output on Pi.
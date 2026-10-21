#!/usr/bin/env bash
# Cross-compile librespot for ARMv6 (arm-unknown-linux-gnueabihf)
set -euo pipefail

TARGET=arm-unknown-linux-gnueabihf
RELEASE=--release

# Install target if not present
rustup target add $TARGET

# Ensure linker for ARMv6 (requires arm-linux-gnueabihf-gcc)
# On Debian/Ubuntu: apt-get install gcc-arm-linux-gnueabihf

cargo build $RELEASE --target $TARGET

# Output binary location
echo "Binary at target/$TARGET/release/librespot"
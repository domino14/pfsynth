#!/bin/sh
# Guitar-only build: does not replace the piano/fiddle web binaries.
set -eu
cd "$(dirname "$0")/.."
SDK=${WASI_SDK:-build/wasi/wasi-sdk}
# Newer development branches also contain the optional electric-guitar amp.
guitar_amp_source=
if test -f src/core/pf_amp.c; then guitar_amp_source=src/core/pf_amp.c; fi
"$SDK/bin/clang" --target=wasm32-wasip1 --sysroot="$SDK/share/wasi-sysroot" -O3 -std=c99 -Wall -Isrc -mexec-model=reactor \
  -Wl,--initial-memory=16777216 -Wl,--max-memory=67108864 \
  src/core/pf_pluck.c $guitar_amp_source src/host/pf_guitar.c src/host/pfguitarwasm.c \
  -o docs/guitar/pfguitar.wasm

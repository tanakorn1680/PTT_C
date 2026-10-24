#!/usr/bin/env bash
# Syntax-only compile (NDK clang, arm64) of EVERY generated file of the second module (msvcr80).
# usage: compile_crt_check.sh <gen_crt_dir> <pcrecomp_dir> <guest_header> <out_file> [prefix]
set -u
GEN=$1; PC=$2; HDR=$3; OUT=${4:-crt_compile_check.txt}; PFX=${5:-msvcr80_}
: > "$OUT"; say() { echo "$*" | tee -a "$OUT"; }
NDK="${ANDROID_NDK_LATEST_HOME:-${ANDROID_NDK_HOME:-${ANDROID_NDK_ROOT:-}}}"
[ -d "$NDK" ] || NDK=$(ls -d /usr/local/lib/android/sdk/ndk/*/ 2>/dev/null | sort -V | tail -n1)
CLANG="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android26-clang"
[ -x "$CLANG" ] || { say "NDK clang not found"; exit 1; }
FLAGS=(-fsyntax-only -Wno-everything -Werror=implicit-function-declaration -fwrapv -fno-strict-aliasing
  -DRECOMP_STRICT_ICALL -DRECOMP_LOCAL_REGS -DRECOMP_X87_WINDOW "-DRECOMP_MEM_QUAL="
  -I "$PC/runtime/recomp32" -I "$GEN" -include "$HDR")
FILES=("$GEN"/${PFX}recomp_[0-9][0-9][0-9][0-9].c "$GEN/${PFX}recomp_dispatch.c" "$GEN/${PFX}recomp_imports.c")
FAIL=0
for f in "${FILES[@]}"; do
  [ -f "$f" ] || continue
  if "$CLANG" "${FLAGS[@]}" "$f" 2> "$OUT.err"; then say "OK   $(basename "$f")"
  else FAIL=$((FAIL + 1)); say "FAIL $(basename "$f")"; grep -m6 "error:" "$OUT.err" | cut -c1-200 | sed 's/^/    /' | tee -a "$OUT"; fi
done
say "files checked: ${#FILES[@]}, failed: $FAIL"
say "RECOMP_UNIMPL sites: $(cat "$GEN"/${PFX}recomp_[0-9][0-9][0-9][0-9].c 2>/dev/null | grep -c 'RECOMP_UNIMPL(')"
[ "$FAIL" -eq 0 ]

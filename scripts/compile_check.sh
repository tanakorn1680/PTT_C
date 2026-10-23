#!/usr/bin/env bash
# Quick check that the NEW emitted C (fcomi family, lock xadd/cmpxchg/cmpxchg8b) compiles with NDK clang.
# Syntax-only on a few small files that contain those instructions; fails on implicit declarations.
# usage: compile_check.sh <gen_dir> <pcrecomp_dir> <guest_header> <out_file>
set -u
GEN=$1; PC=$2; HDR=$3; OUT=${4:-compile_check.txt}
: > "$OUT"; say() { echo "$*" | tee -a "$OUT"; }
NDK="${ANDROID_NDK_LATEST_HOME:-${ANDROID_NDK_HOME:-${ANDROID_NDK_ROOT:-}}}"
[ -d "$NDK" ] || NDK=$(ls -d /usr/local/lib/android/sdk/ndk/*/ 2>/dev/null | sort -V | tail -n1)
CLANG="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android26-clang"
[ -x "$CLANG" ] || { say "NDK clang not found"; exit 1; }
FLAGS=(-fsyntax-only -Wno-everything -Werror=implicit-function-declaration -fwrapv -fno-strict-aliasing
  -DRECOMP_STRICT_ICALL -DRECOMP_LOCAL_REGS -DRECOMP_X87_WINDOW "-DRECOMP_MEM_QUAL="
  -I "$PC/runtime/recomp32" -I "$GEN" -include "$HDR")
FILES=()
for pat in 'fcompi st(1)' 'fcomi st(' 'lock xadd' 'lock cmpxchg dword' 'lock cmpxchg8b'; do
  f=$(grep -l -F -m1 "$pat" "$GEN"/recomp_[0-9][0-9][0-9][0-9].c 2>/dev/null \
      | while read -r x; do [ "$(stat -c %s "$x")" -lt 8000000 ] && echo "$x" && break; done)
  [ -n "$f" ] && FILES+=("$f")
done
mapfile -t FILES < <(printf '%s\n' "${FILES[@]}" | awk 'NF && !s[$0]++')
say "files with the new instructions (<8MB): ${#FILES[@]}"
FAIL=0
for f in "${FILES[@]}"; do
  if "$CLANG" "${FLAGS[@]}" "$f" 2> "$OUT.err"; then say "OK   $(basename "$f")"
  else FAIL=$((FAIL + 1)); say "FAIL $(basename "$f")"; grep -m8 "error:" "$OUT.err" | cut -c1-200 | sed 's/^/    /' | tee -a "$OUT"; fi
done
say "remaining RECOMP_UNIMPL sites in generated C: $(cat "$GEN"/recomp_[0-9][0-9][0-9][0-9].c | grep -c 'RECOMP_UNIMPL(')"
say "failed files: $FAIL"
[ "$FAIL" -eq 0 ]

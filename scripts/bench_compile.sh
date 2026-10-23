#!/usr/bin/env bash
# Measure the cost of compiling a SAMPLE of the lifted C for Android arm64 (NDK clang),
# with the same flags as nfsu2-recompiled's android CMakeLists (minus ThinLTO).
# usage: bench_compile.sh <gen_dir> <pcrecomp_dir> <guest_header> <n_files> <out_file>
# Output has timings/RSS/errors only; no game code is written to the report.
set -u
GEN=$1; PC=$2; HDR=$3; N=${4:-6}; OUT=${5:-bench.txt}
[ "$N" -lt 2 ] && N=2
: > "$OUT"
say() { echo "$*" | tee -a "$OUT"; }

NDK="${ANDROID_NDK_LATEST_HOME:-${ANDROID_NDK_HOME:-${ANDROID_NDK_ROOT:-}}}"
if [ -z "$NDK" ] || [ ! -d "$NDK" ]; then
  NDK=$(ls -d /usr/local/lib/android/sdk/ndk/*/ 2>/dev/null | sort -V | tail -n1)
fi
CLANG="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android26-clang"
[ -x "$CLANG" ] || { say "NDK clang not found (NDK='$NDK')"; exit 1; }
[ -x /usr/bin/time ] || sudo apt-get install -y time >/dev/null 2>&1
say "compiler: $("$CLANG" --version | head -n1)"
CORES=$(nproc); say "runner: $CORES cores, $(free -m | awk '/Mem:/{print $2}') MB RAM"

mapfile -t ALL < <(ls "$GEN"/recomp_[0-9][0-9][0-9][0-9].c | sort)
M=${#ALL[@]}
[ "$M" -gt 0 ] || { say "no recomp_NNNN.c in $GEN"; exit 1; }
BIG=$(ls -S "$GEN"/recomp_[0-9][0-9][0-9][0-9].c | head -n1)
PICK=("$BIG")
for ((i = 0; i < N - 1; i++)); do PICK+=("${ALL[$(( i * M / (N - 1) ))]}"); done
mapfile -t PICK < <(printf '%s\n' "${PICK[@]}" | awk '!s[$0]++')

TOTAL_BYTES=$(cat "${ALL[@]}" | wc -c)
say "files: $M, total ${TOTAL_BYTES} bytes; sampling ${#PICK[@]} (largest + evenly spaced)"

FLAGS=(-O2 -w -fwrapv -fno-strict-aliasing -fexceptions -ffp-contract=off -g0 -fvisibility=hidden
  -DRECOMP_STRICT_ICALL -DRECOMP_LOCAL_REGS -DRECOMP_X87_WINDOW "-DRECOMP_MEM_QUAL="
  -I "$PC/runtime/recomp32" -I "$GEN" -include "$HDR")

TMP=$(mktemp); ERR=$(mktemp)
SUM_T=0; SUM_B=0; MAXKB=0; FAILS=0
for f in "${PICK[@]}"; do
  b=$(stat -c %s "$f")
  timeout 900 /usr/bin/time -f "%e %M" -o "$TMP" "$CLANG" "${FLAGS[@]}" -c "$f" -o /dev/null 2> "$ERR"
  rc=$?
  read -r t kb < <(tail -n1 "$TMP")
  case "$t" in ''|*[!0-9.]*) t=900; kb=0;; esac
  say "$(basename "$f"): ${b} bytes, ${t}s, peak $((kb / 1024)) MB, rc=$rc"
  if [ $rc -ne 0 ]; then
    FAILS=$((FAILS + 1))
    grep -m5 "error:" "$ERR" | cut -c1-160 | sed 's/^/    /' | tee -a "$OUT"
  fi
  SUM_T=$(awk -v a="$SUM_T" -v b="$t" 'BEGIN{print a+b}')
  SUM_B=$((SUM_B + b))
  [ "$kb" -gt "$MAXKB" ] && MAXKB=$kb
done

say "---- estimate (plain -O2, no LTO; ThinLTO link cost is NOT included) ----"
awk -v t="$SUM_T" -v sb="$SUM_B" -v tb="$TOTAL_BYTES" -v c="$CORES" -v kb="$MAXKB" -v fails="$FAILS" 'BEGIN{
  if (sb == 0) { print "no data"; exit }
  cpu = t / sb * tb;
  printf "sample: %.0f s for %.1f MB (%.2f s/MB)\n", t, sb/1048576, t/(sb/1048576);
  printf "full build: ~%.0f CPU-min => ~%.0f min wall on %d cores\n", cpu/60, cpu/60/c, c;
  printf "peak RSS of one compile: %.0f MB (x parallel jobs = RAM needed)\n", kb/1024;
  printf "files that failed to compile in sample: %d\n", fails;
}' | tee -a "$OUT"

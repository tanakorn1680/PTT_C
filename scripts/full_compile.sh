#!/usr/bin/env bash
# Compile ALL generated C for Android arm64 (NDK clang, flags as nfsu2's CMake) and optionally ThinLTO-link
# the objects into a throw-away .so, timing everything. Output has timings/RSS/errors only (no game code).
# usage: full_compile.sh <gen_dir> <pcrecomp_dir> <guest_header> <work_dir> <report> [lto|nolto]
set -u
GEN=$(realpath "$1"); PC=$(realpath "$2"); HDR=$(realpath "$3"); WD=$4; OUT=$5; MODE=${6:-lto}
mkdir -p "$WD/obj"; WD=$(realpath "$WD"); OUT=$(realpath -m "$OUT"); : > "$OUT"
say() { echo "$*" | tee -a "$OUT"; }
NDK="${ANDROID_NDK_LATEST_HOME:-${ANDROID_NDK_HOME:-${ANDROID_NDK_ROOT:-}}}"
[ -d "$NDK" ] || NDK=$(ls -d /usr/local/lib/android/sdk/ndk/*/ 2>/dev/null | sort -V | tail -n1)
CLANG="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android26-clang"
[ -x "$CLANG" ] || { say "NDK clang not found"; exit 1; }
[ -x /usr/bin/time ] || sudo apt-get install -y time >/dev/null 2>&1
CORES=$(nproc)
say "mode=$MODE, $CORES cores, $(free -m | awk '/Mem:/{print $2}') MB RAM, $(df -m "$WD" | awk 'NR==2{print $4}') MB free disk"
FLAGS="-O2 -w -fwrapv -fno-strict-aliasing -fexceptions -ffp-contract=off -g0 -fvisibility=hidden \
-DRECOMP_STRICT_ICALL -DRECOMP_LOCAL_REGS -DRECOMP_X87_WINDOW -DRECOMP_MEM_QUAL= \
-I $PC/runtime/recomp32 -I $GEN -include $HDR"
[ "$MODE" = lto ] && FLAGS="$FLAGS -flto=thin"

cat > "$WD/cc_one.sh" <<'EOS'
#!/usr/bin/env bash
f=$1; o="$OBJDIR/$(basename "$f" .c).o"
/usr/bin/time -f "%e %M" -o "$o.t" timeout 1800 "$CLANG" $FLAGS -c "$f" -o "$o" 2> "$o.err" || echo "$f" >> "$OBJDIR/failed.txt"
EOS
export CLANG FLAGS OBJDIR="$WD/obj"; rm -f "$OBJDIR/failed.txt"
FILES=$(ls "$GEN"/recomp_[0-9][0-9][0-9][0-9].c "$GEN"/recomp_dispatch.c "$GEN"/recomp_imports.c 2>/dev/null)
say "compiling $(echo "$FILES" | wc -l) files, $(cat $FILES | wc -c) bytes of C"
T0=$(date +%s)
echo "$FILES" | xargs -P "$CORES" -n1 bash "$WD/cc_one.sh"
T1=$(date +%s)
NF=0; [ -f "$OBJDIR/failed.txt" ] && NF=$(wc -l < "$OBJDIR/failed.txt")
CPU=$(cat "$OBJDIR"/*.t 2>/dev/null | awk '{s+=$1; if ($2>m) m=$2} END{printf "%.0f %.0f", s, m/1024}')
say "compile wall: $((T1 - T0)) s, cpu: ${CPU% *} s, max RSS of one compile: ${CPU#* } MB, failed files: $NF"
if [ "$NF" -gt 0 ]; then
  for f in $(head -n 5 "$OBJDIR/failed.txt"); do
    say "FAIL $(basename "$f")"; grep -m4 "error:" "$OBJDIR/$(basename "$f" .c).o.err" | cut -c1-180 | sed 's/^/    /' | tee -a "$OUT"
  done
  exit 1
fi
say "object bytes: $(cat "$OBJDIR"/*.o | wc -c)"

LDF=(-shared -fuse-ld=lld -O2 -Wl,--unresolved-symbols=ignore-all -Wl,--gc-sections -o "$WD/libtest.so")
[ "$MODE" = lto ] && LDF+=(-flto=thin "-Wl,--thinlto-jobs=$CORES")
say "linking ($MODE)..."
T2=$(date +%s)
timeout 6000 /usr/bin/time -f "%e %M" -o "$WD/link.t" "$CLANG" "${LDF[@]}" "$OBJDIR"/*.o 2> "$WD/link.err"; RC=$?
T3=$(date +%s)
read -r LT LK < <(tail -n1 "$WD/link.t")
say "link rc=$RC wall: $((T3 - T2)) s, peak RSS: $((${LK:-0} / 1024)) MB, .so bytes: $(stat -c %s "$WD/libtest.so" 2>/dev/null || echo 0)"
[ $RC -ne 0 ] && grep -m6 -i "error\|killed\|cannot" "$WD/link.err" | cut -c1-200 | sed 's/^/    /' | tee -a "$OUT"
exit $RC

#!/usr/bin/env python3
"""Post-lift diagnostics for the next step (fcomi/fcompi/fucomi/lock support).

  lift_diagnostics.py <lift32.py> <gen_dir> <out_dir> [file_prefix]

Writes:
  lifter_excerpt.txt  - parts of pcrecomp's lift32.py (TOOL source, not game code): the x87
                        compare / sahf / lock / unimplemented-fallback branches and the
                        Lifter method list, so a new branch can be written against the real API
  unimpl_forms.txt    - the unimplemented instructions grouped by exact form (operands
                        normalised), so we know which `lock xxx` and which fcomi variants occur
  big_functions.txt   - largest generated files and the 25 largest generated functions
                        (address + size only, no code): why one file is ~87 MB / 8 GB RAM to compile
"""
import collections, glob, heapq, os, re, sys


def regions(lines, pat, before, after, limit):
    rx = re.compile(pat)
    out, last_end = [], -1
    for i, ln in enumerate(lines):
        if rx.search(ln) and i > last_end:
            a, b = max(0, i - before), min(len(lines), i + after)
            out.append((a, b))
            last_end = b
            if len(out) >= limit:
                break
    return out


def dump(lines, title, pat, before, after, limit, w):
    w.write(f"\n{'=' * 78}\n## {title}   (regex: {pat})\n{'=' * 78}\n")
    rs = regions(lines, pat, before, after, limit)
    if not rs:
        w.write("(no match)\n")
    for a, b in rs:
        w.write(f"--- lines {a + 1}-{b} ---\n")
        for j in range(a, b):
            w.write(f"{j + 1:5d}: {lines[j]}\n")


def main(lift32, gen, outdir, prefix=""):
    os.makedirs(outdir, exist_ok=True)
    lines = open(lift32, errors="replace").read().splitlines()
    with open(os.path.join(outdir, "lifter_excerpt.txt"), "w") as w:
        w.write(f"# {lift32}: {len(lines)} lines\n")
        w.write("\n## all `def` lines (Lifter API)\n")
        for i, ln in enumerate(lines):
            if re.match(r"\s*(def|class) ", ln):
                w.write(f"{i + 1:5d}: {ln}\n")
        dump(lines, "x87 compare branches", r"m (==|in) .*['\"](fcom|fucom|fcomp|fucomp|ftst)", 4, 40, 4, w)
        dump(lines, "sahf (keeps fcom state)", r"m == ['\"]sahf['\"]", 4, 40, 1, w)
        dump(lines, "fnstsw", r"m .*['\"]fnstsw['\"]", 2, 30, 1, w)
        dump(lines, "lock prefix handling", r"(?i)\block\b|prefix", 6, 16, 8, w)
        dump(lines, "UNIMPL fallback", r"RECOMP_UNIMPL", 10, 6, 4, w)
        dump(lines, "x87 operand / stack helpers", r"fp_pop\(\)|fp_push\(|_st\[|X86_REG_ST", 3, 3, 6, w)
        dump(lines, "start of per-instruction dispatch (where ops/m are set)", r"^\s*m = ", 8, 25, 2, w)

    forms = collections.Counter()
    rx = re.compile(r'RECOMP_UNIMPL\(0x[0-9A-Fa-f]+u?, "([^"]*)"')
    for p in sorted(glob.glob(os.path.join(gen, prefix + "recomp_[0-9][0-9][0-9][0-9].c"))):
        with open(p, errors="replace") as fh:
            for ln in fh:
                if "RECOMP_UNIMPL(" in ln:
                    m = rx.search(ln)
                    if m:
                        f = re.sub(r"0x[0-9a-fA-F]+", "N", m.group(1))
                        forms[f[:120]] += 1
    with open(os.path.join(outdir, "unimpl_forms.txt"), "w") as w:
        w.write(f"{sum(forms.values())} unimplemented sites, {len(forms)} distinct forms\n\n")
        for f, n in forms.most_common(150):
            w.write(f"{n:6d}  {f}\n")


def big_functions(gen, outdir, prefix=""):
    rx = re.compile(r"^void sub_([0-9A-Fa-f]{8})\(void\)")
    sizes = sorted(((os.path.getsize(p), os.path.basename(p))
                    for p in glob.glob(os.path.join(gen, prefix + "recomp_[0-9][0-9][0-9][0-9].c"))), reverse=True)
    heap = []  # (bytes, addr, file)
    for _, name in sizes[:6]:
        cur, size = None, 0
        with open(os.path.join(gen, name), errors="replace") as fh:
            for ln in fh:
                m = rx.match(ln)
                if m:
                    if cur:
                        heapq.heappush(heap, (size, cur, name))
                        if len(heap) > 25:
                            heapq.heappop(heap)
                    cur, size = m.group(1).upper(), 0
                size += len(ln)
        if cur:
            heapq.heappush(heap, (size, cur, name))
            if len(heap) > 25:
                heapq.heappop(heap)
    with open(os.path.join(outdir, "big_functions.txt"), "w") as w:
        w.write("largest generated files:\n")
        for b, n in sizes[:10]:
            w.write(f"  {b:>12}  {n}\n")
        w.write("\nlargest functions among the 6 largest files (bytes of C, address, file):\n")
        for b, a, n in sorted(heap, reverse=True):
            w.write(f"  {b:>12}  sub_{a}  {n}\n")


if __name__ == "__main__":
    if len(sys.argv) not in (4, 5):
        sys.exit(__doc__)
    main(*sys.argv[1:])
    big_functions(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) == 5 else "")

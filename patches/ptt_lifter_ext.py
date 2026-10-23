#!/usr/bin/env python3
"""Apply the PTT_C lifter extension to a pcrecomp checkout (run after `git am` of the NFSU2 patches).

  ptt_lifter_ext.py <pcrecomp_dir>

* tools/lift/lift32.py : adds one `elif` before the fnstsw branch and appends patches/ptt_lift_ext_src.py
                         (fcomi/fucomi/fcompi/fucompi, lock xadd/cmpxchg/cmpxchg8b). Fails loudly if an
                         anchor is missing or the file is already patched.
* tools/lift/difftest.py: best effort: adds difftest Cases for the new instructions (warns if no anchor).
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MARK = "PTT_C extension"
ANCHOR = "        elif m == 'fnstsw' or m == 'fstsw':\n"
BRANCH = (
    "        # PTT_C extension: see the end of this file.\n"
    "        elif (m in ('fcomi', 'fucomi', 'fcompi', 'fucompi', 'xadd', 'cmpxchg', 'cmpxchg8b')\n"
    "              and (_ptt_r := _ptt_ext_emit(self, m, ops, comment)) is not None):\n"
    "            lines.extend(_ptt_r)\n\n"
)

# Each: name, hex bytes (the code under test ends with lahf 9f / sete al so flags reach eax), regs, mem
FPU_TAIL = "9f" + "ddd8"
CASES = [
    ("fcomi.less",       "d9e8d9eedbf1" + FPU_TAIL + "ddd8", None, None),
    ("fcomi.greater",   "d9eed9e8dbf1" + FPU_TAIL + "ddd8", None, None),
    ("fcomi.equal",      "d9e8d9e8dbf1" + FPU_TAIL + "ddd8", None, None),
    ("fcompi.less",      "d9e8d9eedff1" + FPU_TAIL, None, None),
    ("fucomi.equal",     "d9e8d9e8dbe9" + FPU_TAIL + "ddd8", None, None),
    ("fucompi.greater",  "d9eed9e8dfe9" + FPU_TAIL, None, None),
    ("lock.xadd",        "f00fc1069f", "{'eax': 5, 'esi': SCRATCH}", "(41).to_bytes(4, 'little')"),
    ("lock.xadd-carry",  "f00fc1069f", "{'eax': 2, 'esi': SCRATCH}", "(0xFFFFFFFF).to_bytes(4, 'little')"),
    ("lock.cmpxchg-eq",  "f00fb10e9f", "{'eax': 41, 'ecx': 7, 'esi': SCRATCH}", "(41).to_bytes(4, 'little')"),
    ("lock.cmpxchg-ne",  "f00fb10e9f", "{'eax': 40, 'ecx': 7, 'esi': SCRATCH}", "(41).to_bytes(4, 'little')"),
    ("lock.cmpxchg8b-eq", "f00fc70e0f94c0",
     "{'eax': 0x55667788, 'edx': 0x11223344, 'ebx': 0xAAAA, 'ecx': 0xBBBB, 'esi': SCRATCH}",
     "(0x1122334455667788).to_bytes(8, 'little')"),
    ("lock.cmpxchg8b-ne", "f00fc70e0f94c0",
     "{'eax': 1, 'edx': 2, 'ebx': 0xAAAA, 'ecx': 0xBBBB, 'esi': SCRATCH}",
     "(0x1122334455667788).to_bytes(8, 'little')"),
]


def patch_lift32(root):
    p = os.path.join(root, "tools", "lift", "lift32.py")
    s = open(p, encoding="utf-8").read()
    if MARK in s:
        sys.exit(f"{p}: already patched")
    if s.count(ANCHOR) != 1:
        sys.exit(f"{p}: anchor for the fnstsw branch found {s.count(ANCHOR)} times (expected 1); "
                 "pcrecomp changed, the extension needs updating")
    s = s.replace(ANCHOR, BRANCH + ANCHOR, 1)
    s += open(os.path.join(HERE, "ptt_lift_ext_src.py"), encoding="utf-8").read()
    open(p, "w", encoding="utf-8", newline="\n").write(s)
    print(f"[*] patched {p}")


def patch_difftest(root):
    p = os.path.join(root, "tools", "lift", "difftest.py")
    s = open(p, encoding="utf-8").read()
    i = s.find("Case('lock.inc'")
    j = s.find(")}),\n", i) if i >= 0 else -1
    if j < 0:
        print("[!] difftest.py: no 'lock.inc' anchor, new cases not added (not fatal)")
        return
    j += len(")}),\n")
    out = "    # PTT_C extension cases\n"
    for name, hx, regs, mem in CASES:
        args = f"bytes.fromhex('{hx}')"
        if regs:
            args += f", {regs}"
        if mem:
            args += f", mem={{SCRATCH: {mem}}}"
        out += f"    Case('ptt.{name}', {args}),\n"
    open(p, "w", encoding="utf-8", newline="\n").write(s[:j] + out + s[j:])
    print(f"[*] patched {p}: +{len(CASES)} cases")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    patch_lift32(sys.argv[1])
    patch_difftest(sys.argv[1])

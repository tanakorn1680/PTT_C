#!/usr/bin/env python3
"""Merge entry point, DLL exports, vtable seeds and RTTI seeds into one seeds file.

  make_seeds.py <dll> <out.json> <seeds1.json> [seeds2.json ...]
"""
import json, os, sys

PCRECOMP = os.environ.get("PCRECOMP", "../pcrecomp")
sys.path.insert(0, os.path.join(PCRECOMP, "tools", "pe"))
from pe_analyze import analyze_pe  # noqa: E402


def main(dll, out, *seed_files):
    info = analyze_pe(dll)
    addrs = {info.image_base + info.entry_point_rva}
    n_exp = 0
    for e in info.exports or []:
        rva = e.get("rva") if isinstance(e, dict) else getattr(e, "rva", None)
        # data exports (e.g. msvcr80's _iob, _HUGE) are not code: skip anything outside the code range
        if rva and info.code_start <= info.image_base + rva < info.code_end:
            addrs.add(info.image_base + rva)
            n_exp += 1
    n_other = 0
    for path in seed_files:
        if not os.path.exists(path):
            continue
        for e in json.load(open(path)):
            a = e.get("address") if isinstance(e, dict) else e
            a = int(a, 0) if isinstance(a, str) else a
            if info.code_start <= a < info.code_end:
                addrs.add(a)
                n_other += 1
    json.dump([{"address": a} for a in sorted(addrs)], open(out, "w"))
    print(f"[*] {len(addrs)} seeds (exports {n_exp}, from scans {n_other}) -> {out}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])

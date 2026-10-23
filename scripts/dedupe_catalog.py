#!/usr/bin/env python3
"""Drop catalog "functions" that are really entry points in the MIDDLE of another function.

  dedupe_catalog.py <catalog.json> <out_catalog.json> <report.txt>

Why: in Prototype's engine DLL, sub_109D0150 (a real ~19 KB function with a prologue) was also catalogued
at ~177 mid-function addresses (probably switch jump-table targets taken for vtable entries). Each copy is
lifted as a separate function containing nearly the whole body (~490 KB of C each) => one 87 MB C file that
needs ~8 GB RAM to compile.

A function F is DROPPED only when ALL hold:
  1. F.address lies inside a basic block of some OTHER function G that starts at a LOWER address
     (the code is lifted there anyway);
  2. no function has F.address in calls_to (nobody calls it directly);
  3. no function H that does NOT itself cover F.address jumps to it (no tail jump from outside);
  4. F.entry_kind is not an export/entry kind, and F is not a thunk.
Everything dropped is listed (counts + hosts) in the report; the catalog schema is unchanged.
Not dropped: anything reachable only through a function pointer is still a risk if it points mid-function;
the report's "dropped by entry_kind" tells how much of that there could be.
"""
import collections, json, sys


def sweep(blocks, queries, cb):
    """blocks: [(start, end, fidx)]; queries: [(pos, key)] sorted by pos; cb(key, active_counts)."""
    ev = []
    for s, e, f in blocks:
        if e > s:
            ev.append((s, 1, f))
            ev.append((e, -1, f))
    ev.sort()
    active = collections.Counter()
    i, n = 0, len(ev)
    for pos, key in queries:
        while i < n and ev[i][0] <= pos:
            _, d, f = ev[i]
            active[f] += d
            if active[f] <= 0:
                del active[f]
            i += 1
        cb(key, active)


def main(src, dst, report):
    doc = json.load(open(src))
    funcs = doc["functions"]
    n = len(funcs)
    index = {f["address"]: i for i, f in enumerate(funcs)}
    blocks = [(b[0], b[1], i) for i, f in enumerate(funcs) for b in f["blocks"]]

    # 1. inside another function's block
    inside = {}
    queries = sorted((f["address"], i) for i, f in enumerate(funcs))

    def cb1(i, active):
        # only a host that STARTS EARLIER counts: a mid-function copy can loop back over the real start,
        # but the real start (lowest address) must never be dropped
        others = [g for g in active if g != i and funcs[g]["address"] < funcs[i]["address"]]
        if others:
            inside[i] = others

    sweep(blocks, queries, cb1)

    # 2. directly called
    called = set()
    for f in funcs:
        called.update(f["calls_to"])

    # 3. tail-jumped from a function that does not cover the address
    jumpers = collections.defaultdict(list)
    for i, f in enumerate(funcs):
        for t in f["jump_targets"]:
            j = index.get(t)
            if j is not None and j != i and j in inside:
                jumpers[j].append(i)
    outside_jump = set()
    q2 = sorted((funcs[j]["address"], j) for j in jumpers)

    def cb2(j, active):
        if any(h not in active for h in jumpers[j]):
            outside_jump.add(j)

    sweep(blocks, q2, cb2)

    def keep_kind(k):
        k = str(k).lower()
        return any(w in k for w in ("export", "entry", "main", "dllmain"))

    drop = set()
    kept_called = kept_jump = kept_kind = 0
    for i in inside:
        f = funcs[i]
        if f["address"] in called:
            kept_called += 1
        elif i in outside_jump:
            kept_jump += 1
        elif f.get("is_thunk") or keep_kind(f.get("entry_kind")):
            kept_kind += 1
        else:
            drop.add(i)

    doc["functions"] = [f for i, f in enumerate(funcs) if i not in drop]
    json.dump(doc, open(dst, "w"))

    kinds_all = collections.Counter(str(f.get("entry_kind")) for f in funcs)
    kinds_drop = collections.Counter(str(funcs[i].get("entry_kind")) for i in drop)
    hosts = collections.Counter()
    for i in drop:
        hosts[funcs[inside[i][0]]["address"]] += 1
    with open(report, "w") as w:
        w.write(f"functions: {n} -> {len(doc['functions'])}  (dropped {len(drop)})\n")
        w.write(f"inside another function: {len(inside)}; kept because directly called: {kept_called}, "
                f"tail-jumped from outside: {kept_jump}, export/thunk kind: {kept_kind}\n")
        w.write("\nentry_kind (all / dropped):\n")
        for k, c in kinds_all.most_common():
            w.write(f"  {k:<24} {c:>8} / {kinds_drop.get(k, 0)}\n")
        w.write("\ntop host functions by number of dropped mid-function entries (address, count, size):\n")
        for a, c in hosts.most_common(25):
            w.write(f"  sub_{a:08X}  {c:>6}  {funcs[index[a]]['size']} bytes\n")
        w.write("\ndropped inside sub_109D0150: %d\n" % hosts.get(0x109D0150, 0))
    print(open(report).read())


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])

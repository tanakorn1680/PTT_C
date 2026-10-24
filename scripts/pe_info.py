#!/usr/bin/env python3
"""Print what a PE file is made of: sections (with entropy, a packed/encrypted section is ~7.5+),
overlay size, entry point, imports, exports, resources. Used to understand the launcher exe.

  pe_info.py <file.exe|dll>
"""
import collections, math, os, sys
import pefile


def entropy(b):
    if not b:
        return 0.0
    c = collections.Counter(b)
    n = len(b)
    return -sum(v / n * math.log2(v / n) for v in c.values())


def sec_name(s):
    return s.Name.rstrip(b"\0").decode(errors="replace")


def main(path):
    data = open(path, "rb").read()
    pe = pefile.PE(data=data)
    oh = pe.OPTIONAL_HEADER
    print(f"file: {os.path.basename(path)}  {len(data)} bytes  machine={hex(pe.FILE_HEADER.Machine)}  "
          f"timestamp={pe.FILE_HEADER.TimeDateStamp}  dll={bool(pe.FILE_HEADER.Characteristics & 0x2000)}")
    print(f"image_base={hex(oh.ImageBase)} entry_rva={hex(oh.AddressOfEntryPoint)} size_of_image={hex(oh.SizeOfImage)} "
          f"subsystem={oh.Subsystem} large_address_aware={bool(pe.FILE_HEADER.Characteristics & 0x20)}")
    end = 0
    print("\nsections: name  vaddr  vsize  rawsize  entropy  flags")
    for s in pe.sections:
        raw = s.get_data()
        end = max(end, s.PointerToRawData + s.SizeOfRawData)
        print(f"  {sec_name(s):<8} {s.VirtualAddress:#010x} {s.Misc_VirtualSize:#10x} "
              f"{s.SizeOfRawData:#10x}  {entropy(raw[:1<<20]):.2f}  {s.Characteristics:#010x}")
    print(f"\noverlay (bytes after the last section): {max(0, len(data) - end)}")
    ep = oh.AddressOfEntryPoint
    sec = pe.get_section_by_rva(ep)
    print(f"entry point is in section: {sec_name(sec) if sec else '(none)'}")
    print("\nimports:")
    for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
        names = [(i.name.decode() if i.name else f"#{i.ordinal}") for i in entry.imports]
        print(f"  {entry.dll.decode()} ({len(names)}): {', '.join(names)}")
    exp = getattr(pe, "DIRECTORY_ENTRY_EXPORT", None)
    if exp:
        print(f"\nexports ({len(exp.symbols)}): " + ", ".join((s.name.decode() if s.name else f"#{s.ordinal}") for s in exp.symbols[:80]))
    res = getattr(pe, "DIRECTORY_ENTRY_RESOURCE", None)
    if res:
        print("\nresource types: " + ", ".join(str(e.id if e.id is not None else (e.name or '?')) for e in res.entries))
    for d in pe.OPTIONAL_HEADER.DATA_DIRECTORY:
        if d.name in ("IMAGE_DIRECTORY_ENTRY_SECURITY", "IMAGE_DIRECTORY_ENTRY_TLS") and d.Size:
            print(f"data directory {d.name}: rva={d.VirtualAddress:#x} size={d.Size:#x}")
    print("\nstrings that hint at protection / launcher logic:")
    import re
    for pat in (rb"SecuROM|StarForce|SafeDisc|Steam|securom|ArxanGuard|Denuvo|\.cdd|CLCD", rb"[A-Za-z_]*Engine[A-Za-z_]*|MainWin32|prototype[a-z_.]*", rb"-[a-z]{3,16}"):
        found = sorted(set(m.group().decode(errors="replace") for m in re.finditer(pat, data)))[:40]
        print(f"  {pat.decode()[:30]}: {found}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])

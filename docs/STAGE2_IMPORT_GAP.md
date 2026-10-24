# Stage 2: what the host layer must provide for Prototype's engine DLL

Source: import table of `prototypeenginef.dll` (367 imports, 17 DLLs; full list in `docs/prototype_imports.txt`),
compared by NAME against what nfsu2-recompiled's Android host implements (rough: string match only).
NFSU2 links its CRT statically, Prototype imports **msvcr80.dll**, so the biggest block is new work.

| DLL | imports | not in NFSU2 host | what it is / plan |
|---|---:|---:|---|
| msvcr80.dll | 140 | 140 | CRT (malloc, stdio, string, math `_CIsqrt`/`_CIpow`..., setjmp/longjmp, SEH `_except_handler4_common`, C++ RTTI/throw). See options below |
| kernel32.dll | 100 | 30 | fibers (CreateFiber/SwitchToFiber/ConvertThreadToFiber/DeleteFiber/ConvertFiberToThread), semaphores, VirtualAlloc/Free, Suspend/TerminateThread, SetThreadAffinityMask, GetLocalTime, GlobalMemoryStatus, GetDiskFreeSpaceExA, volume/file attrs, FormatMessageA, RaiseException, UnhandledExceptionFilter, TerminateProcess, TryEnterCriticalSection |
| ws2_32.dll | 29 | 29 | sockets by ordinal + getaddrinfo: single-player => stubs that fail cleanly (+ iphlpapi 4 stubs) |
| user32.dll | 19 | 7 | wsprintfA, CharLowerBuffA, DestroyWindow, CallWindowProcA, MapVirtualKeyExA, GetKeyboardLayout, UnregisterClassA |
| binkw32.dll | 17 | 17 | Bink video (closed source): stub, `BinkOpen` returns NULL so the game skips movies (to be verified in game) |
| advapi32.dll | 17 | 12 | CryptoAPI (acquire/hash/encrypt/genrandom: needs real MD5/SHA1-class behaviour if used for save data), RegCreateKeyExA, RegEnumKeyA |
| winmm.dll | 11 | 8 | `waveOut*` (8) is the REAL audio path => AAudio bridge |
| oleaut32.dll | 9 | 9 | by ordinal: BSTR/Variant basics (SysAllocString etc.) |
| setupapi.dll | 6 | 6 | HID/device enumeration: stub "no devices" |
| ole32.dll | 6 | 6 | CoCreateInstance/CoInitialize...: stub (fail) except CoCreateGuid/CLSIDFromString |
| iphlpapi.dll | 4 | 4 | stub |
| xinput1_3.dll | 3 | 3 | ordinals #2/#3/#4 (likely GetState/SetState/GetCapabilities) => touch/gamepad |
| rpcrt4.dll | 2 | 2 | UuidToStringA, RpcStringFreeA |
| d3d9.dll | 1 | 0 | `Direct3DCreate9` only => DXVK path already exists upstream |
| dsound.dll | 1 | 1 | ordinal #2 (probably DirectSoundEnumerateA): enumeration only; output is waveOut |
| shlwapi.dll / shell32.dll | 1 / 1 | 1 / 0 | PathRelativePathToA |

Ordinal-to-name mappings above are from memory of the Windows SDK exports, not verified: check with the real DLLs.

## The big decision: msvcr80 (140 functions)
* **A. HLE on bionic**: implement each function natively on the host with 32-bit pointer marshalling.
  Fast for hot paths (memcpy/memset/strlen), but 140 functions of exact MSVC semantics (printf/scanf/locale/stat/time) to get right.
* **B. Lift msvcr80.dll as a second module** (run_lift.py already supports `--prefix` for a second module, used by upstream
  for server.dll) and then override only the hot functions with native versions via `config/overrides.txt`.
  Exact CRT behaviour, much less hand-written code; needs a copy of msvcr80.dll (8.0.50727.x, redistributable) and adds ~0.5 MB of code.
* Recommended: B + native overrides for memcpy/memmove/memset/memchr/strlen-class functions and the `_CI*` math intrinsics.
  SEH (`_except_handler4_common`) and C++ `_CxxThrowException` need separate thought: check how often the engine throws.

## Other design notes
* **Fibers**: lifted code uses the HOST stack for call frames, so a fiber needs its own host stack. Simplest robust design: each fiber
  is a host thread; SwitchToFiber = hand the machine lock to it and block the current one (fits the existing machine-lock model).
* **Machine lock** (patch 0008): guest threads are serialized, so `lock`-prefixed ops are already atomic (see `ptt_lift_ext_src.py`).
* **Launcher**: do not lift `prototypef.exe` (~8 KB of real code). The host loads the DLL itself (base 0x10000000, relocations, IAT)
  and calls its exports (EngineInitialize, EngineService, EngineTerminate, MainWin32, ...).
* **Memory**: DLL is not large-address-aware => 2 GB guest space is enough; reserve it low like upstream's guest_memory.

## Decision (2026-10-24): option B, msvcr80.dll obtained
* The user has no msvcr80.dll, but supplied `vcredist_x86.exe` (VC++ 2005 SP1). It was unpacked (exe -> CAB -> exe -> MSI -> embedded CAB,
  using libarchive) and `msvcr80.dll` **8.0.50727.762** (626,688 bytes, sha256 starts `02bdde38e4c6bd79`) is now in `crt/msvcr80.dll`.
* It exports 1,466 names and covers **all 140** msvcr80 functions Prototype imports (checked by name).
* It imports 160 kernel32 functions + `msvcrt!_getdrives`. Together with Prototype's own imports the kernel32 gap grows from ~30 to ~96 names
  (by-name compare with NFSU2's host; many are trivial: wide-char file APIs, locale/LCMap/CompareString, console I/O, process/pipe stubs, HeapWalk/Validate).
  Full lists: `docs/msvcr80_imports.txt`, `docs/prototype_imports.txt`.
* CI lifts it as a second module with `run_lift.py --prefix msvcr80_` (see workflow step "Lift msvcr80.dll as a second module").
  Its `_DllMainCRTStartup` must run before Prototype's DLL starts; hot functions get native overrides later (`config/overrides.txt`).

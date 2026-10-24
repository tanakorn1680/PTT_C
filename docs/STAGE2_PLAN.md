# Stage 2 plan: Android app for Prototype (based on nfsu2-recompiled's `android/`, MIT)

Upstream layout (c27896e3): `android/app/src/main/cpp` (~490 KB: guest_runtime.cpp 59 KB, main.cpp 28 KB, guest_*.inc,
d3d9 bridge, AAudio, input), `src/` (shared runtime), `android/app/src/main/java/...` (launcher UI, controls ~120 KB), `ports/dxvk_android`.

## What stays, what changes
| Part | Plan |
|---|---|
| guest_memory.h (4 GB reservation) | keep |
| guest_heap.h | **change arenas**: first arena starts at 0x10000000 = where Prototype's DLL lives. New layout: DLL 0x10000000+size, arena A 0x11000000-0x1f000000, arena B 0x30000000-0x70000000, arena C 0x80000000-0xe0000000. msvcr80 at 0x78130000. Stack 0x20000000, TIB 0x21000000, import stubs 0x7f000000 stay |
| guest_modules.inc | generalise: two modules mapped at their PREFERRED bases (no relocation needed because the lifted code was lifted at those bases): msvcr80 first (run DllMain), then the engine DLL |
| guest_runtime.cpp `connectGuestRuntime` | replace the EXE boot (`loadImage` + CRT entry at SPEED2.EXE) with: map modules, bind imports (Prototype's msvcr80 imports resolve to msvcr80's guest exports), then the host-written launcher sequence (below) |
| NFSU2-only code | remove: 0x005bf610 resolution hook, widescreen .dat patcher, language list, online server, trace shims |
| guest_kernel/files/threads/window/input/audio | keep, add the ~96 missing kernel32 names (docs/msvcr80_imports.txt, prototype_imports.txt), fibers as host threads handing over the machine lock, waveOut -> existing AAudio mixer |
| d3d9 bridge + DXVK | keep (Prototype imports only Direct3DCreate9) |
| binkw32 (17 imports) | first: stubs (BinkOpen returns NULL, movies skipped). Later option: the real `binkw32.dll` (167 KB, in the game folder) lifted as a third module |
| Java UI (launcher, controls) | rename package/app id, game folder picker, simple touch controls first |

## Boot sequence (to be confirmed by `analyze-launcher.yml` on prototypef.exe)
1. DllMain(msvcr80, PROCESS_ATTACH); DllMain(engine DLL, PROCESS_ATTACH)
2. what prototypef.exe does before calling the engine exports (command line, window class, config) -> reproduced on the host
3. call the engine exports (EngineInitialize / EngineService loop / EngineTerminate / MainWin32)

## Game files on the phone (from the user's screenshots)
`Prototype/` has movies 2.76 GB, art 1.08 GB, Audio 1.91 GB, scripts, atg, init.lua, prototypef.exe, prototypeenginef.dll (19.27 MB),
binkw32.dll (167 KB), *.p3d, proto_uv.dat. The app only needs read access to this folder (+ writable save/config area).

Attribution: files adapted from nfsu2-recompiled keep its MIT notice (NOTICE file to be added with the first copied source).

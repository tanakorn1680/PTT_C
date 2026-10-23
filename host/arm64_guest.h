#pragma once
// Force-included (-include) into every lifted C file when building for Android arm64.
// Generic version: derived from nfsu2-recompiled's arm64_guest.h WITHOUT the NFSU2-specific
// resolution hook (0x005BF610). Game-specific hooks go in a separate header, not here.
#include <time.h>
#define RECOMP_GENERATED_CODE
#include "recomp_types.h"
static inline uint64_t ptt_guest_rdtsc(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    // Stable virtual 1 GHz counter, not an ARM cycle counter.
    return (uint64_t)t.tv_sec * 1000000000ull + (uint64_t)t.tv_nsec;
}
#define __rdtsc() ptt_guest_rdtsc()
static inline void ptt_guest_cpuid(uint32_t leaf) {
    g_eax = g_ebx = g_ecx = g_edx = 0;
    if (leaf == 0) {
        g_eax = 1; g_ebx = 0x756e6547; g_edx = 0x49656e69; g_ecx = 0x6c65746e;
    } else if (leaf == 1) {
        g_eax = 0x00000663;
        // x87, TSC, CX8, CMOV, MMX, SSE, SSE2; no SSE3/AVX/3DNow.
        g_edx = ((1u<<0)|(1u<<4)|(1u<<8)|(1u<<15)|(1u<<23)|(1u<<25)|(1u<<26)) & g_cpuid_edx1;
    } else if (leaf == 0x80000000u) g_eax = 0x80000001u;
}
#undef CPUID
#define CPUID(a,b,c,d) do { RECOMP_REGS_OUT(); ptt_guest_cpuid((a)); RECOMP_REGS_IN(); } while (0)

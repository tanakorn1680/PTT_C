

# ======================================================================================
# PTT_C extension (appended to lift32.py by patches/ptt_lifter_ext.py) -- DO NOT EDIT HERE
# fcomi / fucomi / fcompi / fucompi, and `lock xadd` / `lock cmpxchg` / `lock cmpxchg8b`.
# Guest threads run under one machine lock, so the locked forms need no host atomics.
# ======================================================================================
def _ptt_eflags_stmt(kind, x, y):
    """C statements that set the lazy flag state to an EFLAGS image of `_r = x +/- y` (32-bit)."""
    cf = f"(_r < {x})" if kind == 'add' else f"({x} < {y})"
    of = (f"((({x} ^ _r) & ({y} ^ _r)) >> 31)" if kind == 'add'
          else f"((({x} ^ {y}) & ({x} ^ _r)) >> 31)")
    return ("_flag_a = (uint32_t)" + cf
            + " | ((((0x6996u >> ((_r ^ (_r >> 4)) & 0xFu)) & 1u) ^ 1u) << 2)"
            + f" | (({x} ^ {y} ^ _r) & 0x10u) | ((uint32_t)(_r == 0) << 6)"
            + f" | ((_r >> 31) << 7) | ({of} << 11); "
            + "_flag_b = 0; _flag_k = FK_EFLAGS; _cf = _flag_a & 1u;")


def _ptt_ext_emit(lifter, m, ops, comment):
    """C lines for the mnemonics above, or None when this exact form is not handled
    (the caller then falls through to the loud RECOMP_UNIMPL)."""
    if m in ('fcomi', 'fucomi', 'fcompi', 'fucompi'):
        # Same model as the existing fcomip branch (FPU_CMP + the 'fcom' flag state),
        # but with the real st(i) operand instead of a fixed st(1).
        src = reg_name(ops[-1].reg) if ops and ops[-1].type == X86_OP_REG else "_st[1]"
        lines = [f"_fpu_cmp = FPU_CMP(_st[0], {src}); {comment}"]
        if m in ('fcompi', 'fucompi'):
            lines.append("fp_pop();")
        lines.append("_flag_a = (uint32_t)_fpu_cmp; _flag_b = 0;")
        lifter._flag_state = ('fcom', '_fpu_cmp')
        lifter._flag_seq += 1
        return lines

    if (m in ('xadd', 'cmpxchg') and len(ops) == 2 and ops[0].type == X86_OP_MEM
            and op_bits(ops[0]) == 32):
        ea = lifter._fmt_mem_addr(ops[0].mem)
        src = lifter._fmt_read(ops[1])
        if m == 'xadd':
            # TEMP = SRC + DEST; SRC = DEST; DEST = TEMP; flags as add.
            body = (f"uint32_t _ea = {ea}; uint32_t _d = MEM32(_ea); uint32_t _s = {src}; "
                    f"uint32_t _r = _d + _s; MEM32(_ea) = _r; {lifter._fmt_write(ops[1], '_d')}; "
                    + _ptt_eflags_stmt('add', '_d', '_s'))
        else:
            # if (eax == DEST) { ZF = 1; DEST = SRC } else { ZF = 0; eax = DEST }; flags as cmp eax, DEST.
            body = (f"uint32_t _ea = {ea}; uint32_t _d = MEM32(_ea); uint32_t _s = {src}; "
                    f"uint32_t _a = eax; uint32_t _r = _a - _d; "
                    + _ptt_eflags_stmt('sub', '_a', '_d')
                    + " if (_a == _d) { MEM32(_ea) = _s; } else { eax = _d; }")
        lifter._flag_state = ('eflags', '_flag_a, _flag_b')
        lifter._flag_seq += 1
        return [f"{{ {body} }} {comment}"]

    if m == 'cmpxchg8b' and len(ops) == 1 and ops[0].type == X86_OP_MEM:
        ea = lifter._fmt_mem_addr(ops[0].mem)
        body = (f"uint32_t _ea = {ea}; uint32_t _lo = MEM32(_ea), _hi = MEM32(_ea + 4); "
                "uint32_t _e = recomp_eflags(_flag_k, _flag_a, _flag_b, _cf, _df); "
                "if (_lo == eax && _hi == edx) { MEM32(_ea) = ebx; MEM32(_ea + 4) = ecx; _e |= 0x40u; } "
                "else { eax = _lo; edx = _hi; _e &= ~0x40u; } "
                "_flag_a = _e; _flag_b = 0; _flag_k = FK_EFLAGS; _cf = _flag_a & 1u;")
        lifter._flag_state = ('eflags', '_flag_a, _flag_b')
        lifter._flag_seq += 1
        return [f"{{ {body} }} {comment}"]
    return None

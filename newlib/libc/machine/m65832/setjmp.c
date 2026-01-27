/*
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright © 2026 M65832 Project
 *
 * setjmp/longjmp for M65832
 *
 * jmp_buf layout (32 bytes):
 *   0-3:   SP (stack pointer)
 *   4-7:   PC (return address) 
 *   8-11:  R16 (callee-saved)
 *  12-15:  R17 (callee-saved)
 *  16-19:  R18 (callee-saved)
 *  20-23:  R19 (callee-saved)
 *  24-27:  R20 (callee-saved)
 *  28-31:  R21 (callee-saved)
 */

#include <setjmp.h>

int
setjmp(jmp_buf env)
{
    /* TODO: Implement proper assembly version */
    /* For now, stub that returns 0 (first call) */
    (void)env;
    return 0;
}

void
longjmp(jmp_buf env, int val)
{
    /* TODO: Implement proper assembly version */
    (void)env;
    (void)val;
    /* Should never return */
    __builtin_unreachable();
}

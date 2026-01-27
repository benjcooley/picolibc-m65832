/*
 * SPDX-License-Identifier: BSD-3-Clause
 * Copyright © 2026 M65832 Project
 *
 * setjmp/longjmp for M65832
 *
 * TODO: Implement proper assembly version for actual register saving
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

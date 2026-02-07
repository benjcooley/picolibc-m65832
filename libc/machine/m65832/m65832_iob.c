/*
 * SPDX-License-Identifier: BSD-3-Clause
 *
 * Copyright © 2024 M65832 Project
 *
 * M65832 stdio implementation for picolibc
 *
 * Uses _write() / _read() syscall stubs for I/O, which go through
 * TRAP-based syscalls when running with the system emulator.
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <sys/types.h>

/* Declare syscall functions provided by libsys.a */
extern ssize_t _write(int fd, const void *buf, size_t len);
extern ssize_t _read(int fd, void *buf, size_t len);

/*
 * Output a character via _write(1, &c, 1) — stdout fd
 */
static int
sys_putc(char c, FILE *file)
{
    (void)file;
    ssize_t r = _write(1, &c, 1);
    if (r < 0) return EOF;
    return (unsigned char)c;
}

/*
 * Read a character via _read(0, &c, 1) — stdin fd
 */
static int
sys_getc(FILE *file)
{
    (void)file;
    char c;
    ssize_t r = _read(0, &c, 1);
    if (r <= 0) return EOF;
    return (unsigned char)c;
}

/* Create the stdio FILE structure using syscall-based I/O */
static FILE __stdio = FDEV_SETUP_STREAM(sys_putc, sys_getc, NULL, _FDEV_SETUP_RW);

/* Define stdin, stdout, stderr to all use the same stream */
#ifdef __strong_reference
#define STDIO_ALIAS(x) __strong_reference(stdin, x);
#else
#define STDIO_ALIAS(x) FILE * const x = &__stdio;
#endif

FILE * const stdin = &__stdio;
STDIO_ALIAS(stdout);
STDIO_ALIAS(stderr);

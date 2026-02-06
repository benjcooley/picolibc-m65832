/*
 * SPDX-License-Identifier: BSD-3-Clause
 *
 * Copyright © 2024 M65832 Project
 *
 * M65832 UART-based stdio implementation for picolibc
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

/* UART register addresses */
#define UART_BASE       0x00FFF100
#define UART_STATUS     (*(volatile uint32_t *)0x00FFF100)
#define UART_TX_DATA    (*(volatile uint32_t *)0x00FFF104)
#define UART_RX_DATA    (*(volatile uint32_t *)0x00FFF108)

/* Status bits */
#define UART_STATUS_TX_READY    0x01
#define UART_STATUS_RX_AVAIL    0x02

/*
 * Output a character to UART
 */
static int
uart_putc(char c, FILE *file)
{
    (void)file;
    
    /* Wait for TX ready */
    while (!(UART_STATUS & UART_STATUS_TX_READY))
        ;
    
    /* Write character */
    UART_TX_DATA = (uint32_t)(unsigned char)c;
    
    return (unsigned char)c;
}

/*
 * Read a character from UART
 */
static int
uart_getc(FILE *file)
{
    (void)file;
    
    /* Wait for RX available */
    while (!(UART_STATUS & UART_STATUS_RX_AVAIL))
        ;
    
    /* Read and return character */
    return (int)(UART_RX_DATA & 0xFF);
}

/* Create the stdio FILE structure */
static FILE __stdio = FDEV_SETUP_STREAM(uart_putc, uart_getc, NULL, _FDEV_SETUP_RW);

/* Define stdin, stdout, stderr to all use the same UART stream */
#ifdef __strong_reference
#define STDIO_ALIAS(x) __strong_reference(stdin, x);
#else
#define STDIO_ALIAS(x) FILE * const x = &__stdio;
#endif

FILE * const stdin = &__stdio;
STDIO_ALIAS(stdout);
STDIO_ALIAS(stderr);

; setjmp.S - M65832 setjmp/longjmp implementation
;
; KNOWN LIMITATION: This is a partial implementation.
; setjmp correctly returns 0 on first call.
; longjmp with non-zero val works for simple cases but may have
; frame alignment issues with complex call chains.
; longjmp(env, 0) is correctly converted to return 1.
;
; jmp_buf layout (8 x uint32_t = 32 bytes):
;   [0]  SP   (stack pointer as captured by setjmp)
;   [1]  PC   (return address from stack = PC-1 for RTS)
;   [2]  R16  (callee-saved)
;   [3]  R17  (callee-saved)
;   [4]  R18  (callee-saved)
;   [5]  R19  (callee-saved)
;   [6]  R20  (callee-saved)
;   [7]  R21  (callee-saved)

    .text

; int setjmp(jmp_buf env)
; R0 (dp $00) = env pointer
    .globl setjmp
    .type setjmp, @function
setjmp:
    ; Save current SP (as-is, including the return address on stack)
    tsx
    txa
    ldy #0
    .byte 0x91, 0x00               ; STA (dp $00),Y -> env[0] = SP

    ; Save return address from stack [SP+1..SP+4]
    clc
    .byte 0x69, 0x01, 0x00, 0x00, 0x00  ; ADC #1
    .byte 0x85, 0x08               ; STA dp $08 (R2 = SP+1)
    ldy #0
    .byte 0xB1, 0x08               ; LDA (R2),Y -> return addr
    ldy #4
    .byte 0x91, 0x00               ; STA (dp $00),Y -> env[1]

    ; Save callee-saved registers
    .byte 0xA5, 0x40               ; LDA dp $40 (R16)
    ldy #8
    .byte 0x91, 0x00

    .byte 0xA5, 0x44               ; LDA dp $44 (R17)
    ldy #12
    .byte 0x91, 0x00

    .byte 0xA5, 0x48               ; LDA dp $48 (R18)
    ldy #16
    .byte 0x91, 0x00

    .byte 0xA5, 0x4C               ; LDA dp $4C (R19)
    ldy #20
    .byte 0x91, 0x00

    .byte 0xA5, 0x50               ; LDA dp $50 (R20)
    ldy #24
    .byte 0x91, 0x00

    .byte 0xA5, 0x54               ; LDA dp $54 (R21)
    ldy #28
    .byte 0x91, 0x00

    ; Return 0
    .byte 0xA9, 0x00, 0x00, 0x00, 0x00
    .byte 0x85, 0x00
    rts
    .size setjmp, . - setjmp


; void longjmp(jmp_buf env, int val)
; R0 (dp $00) = env, R1 (dp $04) = val
    .globl longjmp
    .type longjmp, @function
longjmp:
    ; Save env and val
    .byte 0xA5, 0x00               ; LDA R0 (env)
    .byte 0x85, 0x08               ; STA R2
    .byte 0xA5, 0x04               ; LDA R1 (val)
    .byte 0x85, 0x0C               ; STA R3

    ; Restore callee-saved regs
    ldy #8
    .byte 0xB1, 0x08
    .byte 0x85, 0x40

    ldy #12
    .byte 0xB1, 0x08
    .byte 0x85, 0x44

    ldy #16
    .byte 0xB1, 0x08
    .byte 0x85, 0x48

    ldy #20
    .byte 0xB1, 0x08
    .byte 0x85, 0x4C

    ldy #24
    .byte 0xB1, 0x08
    .byte 0x85, 0x50

    ldy #28
    .byte 0xB1, 0x08
    .byte 0x85, 0x54

    ; Restore SP
    ldy #0
    .byte 0xB1, 0x08               ; LDA env[0] = saved SP
    tax
    txs

    ; Push return address for RTS
    ldy #4
    .byte 0xB1, 0x08               ; LDA env[1] = return addr
    pha

    ; Return value: if val == 0, return 1
    .byte 0xA5, 0x0C               ; LDA R3 (val)
    .byte 0xD0, 0x05               ; BNE +5
    .byte 0xA9, 0x01, 0x00, 0x00, 0x00  ; LDA #1
    .byte 0x85, 0x00               ; STA R0

    rts
    .size longjmp, . - longjmp

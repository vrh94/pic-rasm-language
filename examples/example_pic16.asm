; ============================================================
; PIC16 Readable Assembly Example — LED Blink on PIC16F877A
; ============================================================
; This .rasm file demonstrates readable PIC16 syntax.
; Run through pic18_translator.py to get standard PIC16 asm.
; ============================================================

    LIST P=16F877A
    #include <p16f877a.inc>

; ── Configuration bits ──────────────────────────────────────
    __CONFIG _FOSC_HS & _WDTE_OFF & _PWRTE_ON & _LVP_OFF

; ── Variables ───────────────────────────────────────────────
    CBLOCK 0x20
        DELAY_COUNT1
        DELAY_COUNT2
        DELAY_COUNT3
    ENDC

; ── Reset vector ────────────────────────────────────────────
    ORG 0x0000
    GOTO MAIN

; ── Interrupt vector (unused) ───────────────────────────────
    ORG 0x0004
    RETFIE

; ── Main Program ────────────────────────────────────────────
    ORG 0x0010
MAIN:
    ; Select bank 1 for TRISB
    BSF STATUS, RP0
    BCF STATUS, RP1

    ; Configure PORTB as all outputs
    CLRF TRISB

    ; Back to bank 0
    BCF STATUS, RP0

    ; Clear PORTB (all LEDs off)
    CLRF PORTB

LOOP:
    ; Toggle all LEDs on PORTB
    COMF PORTB, F

    ; Delay
    CALL DELAY

    ; Repeat forever
    GOTO LOOP

; ── Delay subroutine ────────────────────────────────────────
DELAY:
    MOVLW 0x05
    MOVWF DELAY_COUNT3
DELAY_OUTER:
    MOVLW 0xFF
    MOVWF DELAY_COUNT2
DELAY_MIDDLE:
    MOVLW 0xFF
    MOVWF DELAY_COUNT1
DELAY_INNER:
    DECFSZ DELAY_COUNT1, F
    GOTO DELAY_INNER

    DECFSZ DELAY_COUNT2, F
    GOTO DELAY_MIDDLE

    DECFSZ DELAY_COUNT3, F
    GOTO DELAY_OUTER

    RETURN

; ── Arithmetic demo ─────────────────────────────────────────
ARITH_DEMO:
    MOVLW 0x0A          ; W = 10
    ADDLW 0x05           ; W = W + 5  = 15
    MOVWF 0x30                ; store result

    ; Rotate operations (PIC16 style)
    RLF 0x30, F           ; rotate left through carry
    RRF 0x30, F          ; rotate right through carry

    ; Bit manipulation
    BSF 0x30, 7               ; set bit 7
    BTG 0x30, 3            ; toggle bit 3
    BTFSS 0x30, 7
    GOTO SKIP_TARGET

SKIP_TARGET:
    NOP
    RETURN

    END

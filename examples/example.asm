; ============================================================
; PIC18 Readable Assembly Example — LED Blink
; ============================================================
; This .rasm file demonstrates the readable PIC18 syntax.
; Run it through pic18_translator.py to get standard PIC18 asm.
; ============================================================

    LIST P=18F4550
    #include <p18f4550.inc>

; ── Configuration bits ──────────────────────────────────────
    CONFIG FOSC = HS
    CONFIG WDT  = OFF
    CONFIG LVP  = OFF
    CONFIG PBADEN = OFF

; ── Variables ───────────────────────────────────────────────
DELAY_COUNT1 EQU 0x20
DELAY_COUNT2 EQU 0x21
DELAY_COUNT3 EQU 0x22
move_w_to_f reg_1

; ── Reset vector ────────────────────────────────────────────
    ORG 0x0000
    GOTO MAIN

; ── Interrupt vector (unused) ───────────────────────────────
    ORG 0x0008
    RETFIE 0

; ── Main Program ────────────────────────────────────────────
    ORG 0x0020
MAIN:
    ; Select bank 0
    MOVLB 0

    ; Configure PORTB as all outputs
    CLRF TRISB, ACCESS

    ; Clear PORTB (all LEDs off)
    CLRF LATB, ACCESS

LOOP:
    ; Turn on LED on RB0 — set bit 0 of LATB
    BSF LATB, 0, ACCESS

    ; Delay
    CALL DELAY, 0

    ; Turn off LED on RB0 — clear bit 0 of LATB
    BCF LATB, 0, ACCESS

    ; Delay again
    CALL DELAY, 0

    ; Repeat forever
    BRA LOOP

; ── Delay subroutine ────────────────────────────────────────
DELAY:
    MOVLW 0x05
    MOVWF DELAY_COUNT3, ACCESS
DELAY_OUTER:
    MOVLW 0xFF
    MOVWF DELAY_COUNT2, ACCESS
DELAY_MIDDLE:
    MOVLW 0xFF
    MOVWF DELAY_COUNT1, ACCESS
DELAY_INNER:
    DECFSZ DELAY_COUNT1, F, ACCESS
    BRA DELAY_INNER

    DECFSZ DELAY_COUNT2, F, ACCESS
    BRA DELAY_MIDDLE

    DECFSZ DELAY_COUNT3, F, ACCESS
    BRA DELAY_OUTER

    RETURN 0

; ── Another example: table read demo ────────────────────────
TABLE_DEMO:
    ; Load table pointer with address of MY_TABLE
    MOVLW UPPER(MY_TABLE)
    MOVWF TBLPTRU, ACCESS
    MOVLW HIGH(MY_TABLE)
    MOVWF TBLPTRH, ACCESS
    MOVLW LOW(MY_TABLE)
    MOVWF TBLPTRL, ACCESS

    ; Read first byte from table
    TBLRD*+
    MOVF TABLAT, W, ACCESS     ; result now in W

    ; Read second byte
    TBLRD*+
    MOVF TABLAT, W, ACCESS

    RETURN 0

; ── Arithmetic demo ─────────────────────────────────────────
ARITH_DEMO:
    MOVLW 0x0A              ; W = 10
    ADDLW 0x05               ; W = W + 5  = 15
    MOVWF 0x30, ACCESS            ; store result

    MOVLW 0x03
    MULLW 0x04        ; PRODH:PRODL = 3 * 4 = 12

    MOVLW 0xFF
    COMF 0x30, F, ACCESS        ; complement the value at 0x30
    SWAPF 0x30, F, ACCESS      ; swap nibbles

    ; Bit manipulation
    BSF 0x30, 7, ACCESS           ; set bit 7
    BTG 0x30, 3, ACCESS        ; toggle bit 3
    BTFSS 0x30, 7, ACCESS
    BRA SKIP_TARGET

SKIP_TARGET:
    NOP
    RETURN 0

; ── Data in program memory ──────────────────────────────────
    ORG 0x0800
MY_TABLE:
    DB 0x48, 0x65, 0x6C, 0x6C, 0x6F    ; "Hello"

    END

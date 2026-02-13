; ============================================================
; PIC16F1xxx Readable Assembly — Enhanced Mid-Range Demo
; ============================================================
; Demonstrates PIC16 enhanced mid-range instructions.
; Target: PIC16F1847 or similar PIC16F1xxx device.
; ============================================================

    LIST P=16F1847
    #include <p16f1847.inc>

; ── Configuration bits ──────────────────────────────────────
    __CONFIG _CONFIG1, _FOSC_INTOSC & _WDTE_OFF & _PWRTE_ON
    __CONFIG _CONFIG2, _LVP_OFF & _PLLEN_ON

; ── Variables ───────────────────────────────────────────────
    CBLOCK 0x20
        TEMP
        RESULT
        SHIFT_VAL
    ENDC

; ── Reset vector ────────────────────────────────────────────
    ORG 0x0000
    GOTO MAIN

; ── Interrupt vector ────────────────────────────────────────
    ORG 0x0004
    RETFIE

; ── Main Program ────────────────────────────────────────────
    ORG 0x0010
MAIN:
    ; Use MOVLB to set bank (enhanced mid-range)
    MOVLB 0x01         ; select bank 1

    ; Configure PORTB as outputs
    CLRF TRISB

    ; Back to bank 0
    MOVLB 0x00

    ; Clear PORTB
    CLRF PORTB

    ; ── Shift operations demo ───────────────────────────────
    MOVLW 0b10110100
    MOVWF SHIFT_VAL

    LSLF SHIFT_VAL, F   ; shift left (0 into LSB)
    LSRF SHIFT_VAL, F  ; shift right (0 into MSB)
    ASRF SHIFT_VAL, F ; arithmetic shift right (sign extend)

    ; ── Indirect addressing with FSR (enhanced) ─────────────
    ; Point FSR0 to TEMP
    MOVLW TEMP
    MOVWF FSR0L
    CLRF FSR0H

    ; Store value via indirect
    MOVLW 0x42
    MOVWI FSR0         ; MOVWI — store W at [FSR0]

    ; Read back via indirect
    MOVIW FSR0         ; MOVIW — load [FSR0] into W

    ; ── Relative branch demo ────────────────────────────────
    MOVLW 0x00
    BRA SKIP_OVER           ; BRA — relative branch
    NOP                        ; this is skipped
SKIP_OVER:
    NOP

    ; ── Computed jump using BRW ─────────────────────────────
    MOVLW 0x02
    BRW              ; BRW — jump PC + W
    NOP                        ; W=0 lands here
    NOP                        ; W=1 lands here
    GOTO DONE                   ; W=2 lands here

DONE:
    ; ── MOVLP demo ──────────────────────────────────────────
    MOVLP 0x00         ; set PCLATH

    ; Adjust FSR using ADDFSR
    ADDFSR FSR0, 4      ; FSR0 += 4

    SLEEP

    END

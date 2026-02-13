; ============================================================
; PIC18 Berljiv zbirnik — Utripanje LED
; ============================================================
; Ta .rasm datoteka prikazuje slovensko berljivo sintakso.
; Pozeni pic18_translator.py za prevod v standardni PIC18 asm.
; ============================================================

    LIST P=18F4550
    #include <p18f4550.inc>

; ── Konfiguracijski biti ────────────────────────────────────
    CONFIG FOSC = HS
    CONFIG WDT  = OFF
    CONFIG LVP  = OFF
    CONFIG PBADEN = OFF

; ── Spremenljivke ───────────────────────────────────────────
STEVEC_ZAKASNITVE1 EQU 0x20
STEVEC_ZAKASNITVE2 EQU 0x21
STEVEC_ZAKASNITVE3 EQU 0x22

; ── Ponastavitveni vektor ───────────────────────────────────
    ORG 0x0000
    GOTO GLAVNI

; ── Prekinitveni vektor (neuporabljen) ──────────────────────
    ORG 0x0008
    RETFIE 0

; ── Glavni program ──────────────────────────────────────────
    ORG 0x0020
GLAVNI:
    ; Izberi banko 0
    MOVLB 0

    ; Nastavi PORTB kot izhode
    CLRF TRISB, ACCESS

    ; Pocisti PORTB (vse LED ugasnjene)
    CLRF LATB, ACCESS

ZANKA:
    ; Prizgi LED na RB0 — nastavi bit 0 registra LATB
    BSF LATB, 0, ACCESS

    ; Zakasnitev
    CALL ZAKASNITEV, 0

    ; Ugasni LED na RB0 — pocisti bit 0 registra LATB
    BCF LATB, 0, ACCESS

    ; Ponovno zakasnitev
    CALL ZAKASNITEV, 0

    ; Ponovi v nedogled
    BRA ZANKA

; ── Podprogram za zakasnitev ────────────────────────────────
ZAKASNITEV:
    MOVLW 0x05
    MOVWF STEVEC_ZAKASNITVE3, ACCESS
ZUNANJA_ZANKA:
    MOVLW 0xFF
    MOVWF STEVEC_ZAKASNITVE2, ACCESS
SREDNJA_ZANKA:
    MOVLW 0xFF
    MOVWF STEVEC_ZAKASNITVE1, ACCESS
NOTRANJA_ZANKA:
    DECFSZ STEVEC_ZAKASNITVE1, F, ACCESS
    BRA NOTRANJA_ZANKA

    DECFSZ STEVEC_ZAKASNITVE2, F, ACCESS
    BRA SREDNJA_ZANKA

    DECFSZ STEVEC_ZAKASNITVE3, F, ACCESS
    BRA ZUNANJA_ZANKA

    RETURN 0

; ── Primer branja tabele ────────────────────────────────────
BRANJE_TABELE:
    ; Nalozi kazalec tabele z naslovom MOJA_TABELA
    MOVLW UPPER(MOJA_TABELA)
    MOVWF TBLPTRU, ACCESS
    MOVLW HIGH(MOJA_TABELA)
    MOVWF TBLPTRH, ACCESS
    MOVLW LOW(MOJA_TABELA)
    MOVWF TBLPTRL, ACCESS

    ; Preberi prvi bajt iz tabele
    TBLRD*+
    MOVF TABLAT, W, ACCESS     ; rezultat je zdaj v W

    ; Preberi drugi bajt
    TBLRD*+
    MOVF TABLAT, W, ACCESS

    RETURN 0

; ── Aritmeticni primer ──────────────────────────────────────
ARITMETIKA:
    MOVLW 0x0A              ; W = 10
    ADDLW 0x05               ; W = W + 5  = 15
    MOVWF 0x30, ACCESS              ; shrani rezultat

    MOVLW 0x03
    MULLW 0x04               ; PRODH:PRODL = 3 * 4 = 12

    MOVLW 0xFF
    COMF 0x30, F, ACCESS         ; komplementiraj vrednost na 0x30
    SWAPF 0x30, F, ACCESS      ; zamenjaj polbajta

    ; Bitne operacije
    BSF 0x30, 7, ACCESS            ; nastavi bit 7
    BTG 0x30, 3, ACCESS           ; preklopi bit 3
    BTFSS 0x30, 7, ACCESS
    BRA CILJ_PRESKOKA

CILJ_PRESKOKA:
    NOP
    RETURN 0

; ── Podatki v programskem pomnilniku ────────────────────────
    ORG 0x0800
MOJA_TABELA:
    DB 0x50, 0x6F, 0x7A, 0x64, 0x72, 0x61, 0x76    ; "Pozdrav"

    END

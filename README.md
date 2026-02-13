# PIC16/PIC18 Readable Assembly

Write PIC16 and PIC18 assembly code using **human-readable instruction names** instead of cryptic mnemonics — in **English** or **Slovenian**.

**PIC18 example** — instead of:

```asm
MOVLW 0x05
MOVWF DELAY_COUNT, ACCESS
DECFSZ DELAY_COUNT, F, ACCESS
BRA LOOP
```

You write:

```
move_literal_to_w 0x05
move_w_to_f DELAY_COUNT, ACCESS
decrement_f_skip_if_zero DELAY_COUNT, F, ACCESS
branch_always LOOP
```

**PIC16 example** — instead of:

```asm
CLRW
RLF PORTB, F
BTFSS STATUS, Z
GOTO LOOP
```

You write:

```
clear_w
rotate_left_f PORTB, F
bit_test_f_skip_if_set STATUS, Z
goto_address LOOP
```

Or in **Slovenian**:

```
premakni_konstanto_v_w 0x05
premakni_w_v_f STEVEC_ZAKASNITVE, ACCESS
zmanjsaj_f_preskoci_ce_nic STEVEC_ZAKASNITVE, F, ACCESS
vejitev_vedno ZANKA
```

---

## Project Structure

```
PIC18_redable_assembly_code/
├── instructions/                      # Instruction definition JSON files
│   ├── pic18_instructions.json        #   PIC18 (EN + SI)
│   └── pic16_instructions.json        #   PIC16 (EN + SI)
├── examples/                          # Example .rasm and translated .asm files
│   ├── example.rasm                   #   PIC18 English example (LED blink)
│   ├── example.asm
│   ├── primer.rasm                    #   PIC18 Slovenian example (LED blink)
│   ├── primer.asm
│   ├── example_pic16.rasm             #   PIC16 mid-range example (LED blink)
│   ├── example_pic16.asm
│   ├── example_pic16f1xxx.rasm        #   PIC16 enhanced mid-range example
│   └── example_pic16f1xxx.asm
├── ide/                               # PyQt5 IDE (MPLAB v8.92 style)
│   └── pic_rasm_ide.py                #   IDE source code
├── dist/                              # Compiled exe output
│   └── PIC_RASM_IDE.exe               #   Standalone Windows IDE
├── pic18_translator.py                # Readable .rasm → standard .asm
├── pic18_reverse_translator.py        # Standard .asm → readable .rasm
├── pic18-readable-asm/                # VS Code extension for syntax highlighting
│   ├── package.json
│   ├── language-configuration.json
│   └── syntaxes/
│       └── pic18rasm.tmLanguage.json
└── README.md
```

Instruction definitions are stored in **JSON files** under `instructions/` and loaded at runtime by both the forward and reverse translators. To add or modify instructions, edit the JSON files — no Python code changes needed.

---

## Requirements

**Command-line tools:**
- Python 3.10 or later
- No external dependencies (standard library only: `json`, `re`, `argparse`, `pathlib`)

**IDE (optional):**
- PyQt5 (`pip install PyQt5`)
- Or use the prebuilt `dist/PIC_RASM_IDE.exe` — no Python needed

---

## Usage

### Forward Translation: `.rasm` → `.asm`

Convert readable assembly to standard PIC16/PIC18 assembly that can be assembled by MPASM / MPLAB XC8 PIC Assembler.

```bash
# Output to file
python pic18_translator.py input.rasm -o output.asm

# Output to stdout
python pic18_translator.py input.rasm

# Print the full instruction reference table (PIC18 + PIC16, EN + SI)
python pic18_translator.py --ref
```

### Reverse Translation: `.asm` → `.rasm`

Convert existing standard PIC16/PIC18 assembly into readable format.

```bash
# To English readable names (default)
python pic18_reverse_translator.py input.asm -o output.rasm

# To Slovenian readable names
python pic18_reverse_translator.py input.asm -o output.rasm --lang si

# Output to stdout
python pic18_reverse_translator.py input.asm --lang en
```

### Round-Trip

Both translators are fully round-trip safe:

```bash
python pic18_translator.py example.rasm -o temp.asm
python pic18_reverse_translator.py temp.asm -o roundtrip.rasm
# roundtrip.rasm will match example.rasm exactly
```

---

## IDE (MPLAB v8.92 Style)

A standalone PyQt5 IDE modelled after MPLAB IDE v8.92 is included.

### Features

- **Project tree** (left panel) — browse and open `.rasm` / `.asm` files
- **Tabbed code editor** — syntax highlighting, line numbers, current-line highlight
- **Output window** (bottom panel) — build output, errors
- **Integrated Build** — press **F7** to translate `.rasm → .asm`
- **Integrated Reverse Translate** — press **Shift+F7** to convert `.asm → .rasm`
- **Find / Replace** (Ctrl+F), Go to Line (Ctrl+G)
- Classic MPLAB grey/blue theme with Fusion style

### Run from source

```bash
pip install PyQt5
python ide/pic_rasm_ide.py
```

### Run the prebuilt exe

The standalone `dist/PIC_RASM_IDE.exe` (≈36 MB) includes all dependencies — just double-click to launch. The exe bundles the translator scripts and instruction JSON files.

### Rebuild the exe

```bash
pip install PyQt5 pyinstaller
pyinstaller --noconfirm --onefile --windowed --name PIC_RASM_IDE \
  --add-data "instructions;instructions" \
  --add-data "pic18_translator.py;." \
  --add-data "pic18_reverse_translator.py;." \
  ide/pic_rasm_ide.py
```

---

## VS Code Syntax Highlighting

The `pic18-readable-asm/` folder is a VS Code extension that provides syntax highlighting and bracket matching for `.rasm` files.

### Install

1. Copy (or symlink) the `pic18-readable-asm` folder into your VS Code extensions directory:
   - **Windows:** `%USERPROFILE%\.vscode\extensions\`
   - **macOS/Linux:** `~/.vscode/extensions/`
2. Restart VS Code.
3. Open any `.rasm` file — it will be highlighted automatically.

### Features

- All English and Slovenian readable mnemonics highlighted as **keywords** (PIC16 + PIC18)
- Labels, comments (`;`), numbers (hex `0x`, binary `0b`, decimal), strings highlighted
- Assembler directives (`ORG`, `EQU`, `CONFIG`, `#include`, etc.) highlighted
- Bracket matching and auto-closing for `()`, `[]`, `<>`, `""`

---

## Complete Instruction Reference

All 75 PIC18 instructions (including 8 extended XINST) plus 19 PIC16-specific instructions are supported. Both English and Slovenian names can be **mixed freely** in a single `.rasm` file. Many instructions (ADDWF, BCF, GOTO, etc.) are shared between PIC16 and PIC18 and use the same readable names.

---

### PIC18 Instructions

#### Byte-Oriented File Register Operations (31)

| PIC18 Mnemonic | English Readable Name | Slovenian Readable Name |
|---|---|---|
| `ADDWF` | `add_w_to_f` | `pristej_w_k_f` |
| `ADDWFC` | `add_w_to_f_with_carry` | `pristej_w_k_f_s_prenosom` |
| `ANDWF` | `and_w_with_f` | `in_w_z_f` |
| `CLRF` | `clear_f` | `pocisti_f` |
| `COMF` | `complement_f` | `komplementiraj_f` |
| `CPFSEQ` | `compare_f_skip_if_equal` | `primerjaj_f_preskoci_ce_enako` |
| `CPFSGT` | `compare_f_skip_if_greater` | `primerjaj_f_preskoci_ce_vecje` |
| `CPFSLT` | `compare_f_skip_if_less` | `primerjaj_f_preskoci_ce_manjse` |
| `DECF` | `decrement_f` | `zmanjsaj_f` |
| `DECFSZ` | `decrement_f_skip_if_zero` | `zmanjsaj_f_preskoci_ce_nic` |
| `DCFSNZ` | `decrement_f_skip_if_not_zero` | `zmanjsaj_f_preskoci_ce_ni_nic` |
| `INCF` | `increment_f` | `povecaj_f` |
| `INCFSZ` | `increment_f_skip_if_zero` | `povecaj_f_preskoci_ce_nic` |
| `INFSNZ` | `increment_f_skip_if_not_zero` | `povecaj_f_preskoci_ce_ni_nic` |
| `IORWF` | `or_w_with_f` | `ali_w_z_f` |
| `MOVF` | `move_f` | `premakni_f` |
| `MOVFF` | `move_f_to_f` | `premakni_f_v_f` |
| `MOVWF` | `move_w_to_f` | `premakni_w_v_f` |
| `MULWF` | `multiply_w_with_f` | `pomnozi_w_z_f` |
| `NEGF` | `negate_f` | `negiraj_f` |
| `RLCF` | `rotate_left_f_through_carry` | `zavrti_levo_f_skozi_prenos` |
| `RLNCF` | `rotate_left_f_no_carry` | `zavrti_levo_f_brez_prenosa` |
| `RRCF` | `rotate_right_f_through_carry` | `zavrti_desno_f_skozi_prenos` |
| `RRNCF` | `rotate_right_f_no_carry` | `zavrti_desno_f_brez_prenosa` |
| `SETF` | `set_f` | `nastavi_f` |
| `SUBFWB` | `subtract_f_from_w_with_borrow` | `odstej_f_od_w_z_izposojo` |
| `SUBWF` | `subtract_w_from_f` | `odstej_w_od_f` |
| `SUBWFB` | `subtract_w_from_f_with_borrow` | `odstej_w_od_f_z_izposojo` |
| `SWAPF` | `swap_nibbles_f` | `zamenjaj_polbajta_f` |
| `TSTFSZ` | `test_f_skip_if_zero` | `testiraj_f_preskoci_ce_nic` |
| `XORWF` | `xor_w_with_f` | `xali_w_z_f` |

#### Bit-Oriented File Register Operations (5)

| PIC18 Mnemonic | English Readable Name | Slovenian Readable Name |
|---|---|---|
| `BCF` | `bit_clear_f` | `bit_pocisti_f` |
| `BSF` | `bit_set_f` | `bit_nastavi_f` |
| `BTFSC` | `bit_test_f_skip_if_clear` | `bit_testiraj_f_preskoci_ce_pociscen` |
| `BTFSS` | `bit_test_f_skip_if_set` | `bit_testiraj_f_preskoci_ce_nastavljen` |
| `BTG` | `bit_toggle_f` | `bit_preklopi_f` |

#### Literal Operations (8)

| PIC18 Mnemonic | English Readable Name | Slovenian Readable Name |
|---|---|---|
| `ADDLW` | `add_literal_to_w` | `pristej_konstanto_k_w` |
| `ANDLW` | `and_literal_with_w` | `in_konstanto_z_w` |
| `IORLW` | `or_literal_with_w` | `ali_konstanto_z_w` |
| `MOVLB` | `move_literal_to_bsr` | `premakni_konstanto_v_bsr` |
| `MOVLW` | `move_literal_to_w` | `premakni_konstanto_v_w` |
| `MULLW` | `multiply_literal_with_w` | `pomnozi_konstanto_z_w` |
| `SUBLW` | `subtract_w_from_literal` | `odstej_w_od_konstante` |
| `XORLW` | `xor_literal_with_w` | `xali_konstanto_z_w` |

#### Control / Branch Operations (22)

| PIC18 Mnemonic | English Readable Name | Slovenian Readable Name |
|---|---|---|
| `BC` | `branch_if_carry` | `vejitev_ce_prenos` |
| `BN` | `branch_if_negative` | `vejitev_ce_negativno` |
| `BNC` | `branch_if_not_carry` | `vejitev_ce_ni_prenosa` |
| `BNN` | `branch_if_not_negative` | `vejitev_ce_ni_negativno` |
| `BNOV` | `branch_if_not_overflow` | `vejitev_ce_ni_prekoracitve` |
| `BNZ` | `branch_if_not_zero` | `vejitev_ce_ni_nic` |
| `BOV` | `branch_if_overflow` | `vejitev_ce_prekoracitev` |
| `BRA` | `branch_always` | `vejitev_vedno` |
| `BZ` | `branch_if_zero` | `vejitev_ce_nic` |
| `CALL` | `call_subroutine` | `klici_podprogram` |
| `CLRWDT` | `clear_watchdog_timer` | `pocisti_casovnik_psa` |
| `DAW` | `decimal_adjust_w` | `decimalno_prilagodi_w` |
| `GOTO` | `goto_address` | `pojdi_na_naslov` |
| `NOP` | `no_operation` | `brez_operacije` |
| `POP` | `pop_return_stack` | `odvzemi_iz_sklada` |
| `PUSH` | `push_return_stack` | `potisni_na_sklad` |
| `RCALL` | `relative_call` | `relativni_klic` |
| `RESET` | `software_reset` | `programska_ponastavitev` |
| `RETFIE` | `return_from_interrupt` | `vrni_se_iz_prekinitve` |
| `RETLW` | `return_with_literal_in_w` | `vrni_se_s_konstanto_v_w` |
| `RETURN` | `return_from_subroutine` | `vrni_se_iz_podprograma` |
| `SLEEP` | `enter_sleep_mode` | `vstopi_v_spanje` |

#### Table Read / Write Operations (8)

| PIC18 Mnemonic | English Readable Name | Slovenian Readable Name |
|---|---|---|
| `TBLRD*` | `table_read` | `beri_tabelo` |
| `TBLRD*+` | `table_read_post_increment` | `beri_tabelo_povecaj_po` |
| `TBLRD*-` | `table_read_post_decrement` | `beri_tabelo_zmanjsaj_po` |
| `TBLRD+*` | `table_read_pre_increment` | `beri_tabelo_povecaj_pred` |
| `TBLWT*` | `table_write` | `pisi_tabelo` |
| `TBLWT*+` | `table_write_post_increment` | `pisi_tabelo_povecaj_po` |
| `TBLWT*-` | `table_write_post_decrement` | `pisi_tabelo_zmanjsaj_po` |
| `TBLWT+*` | `table_write_pre_increment` | `pisi_tabelo_povecaj_pred` |

#### Extended Instruction Set — XINST (8)

| PIC18 Mnemonic | English Readable Name | Slovenian Readable Name |
|---|---|---|
| `ADDFSR` | `add_literal_to_fsr` | `pristej_konstanto_k_fsr` |
| `ADDULNK` | `add_literal_to_fsr2_and_return` | `pristej_konstanto_k_fsr2_in_vrni` |
| `CALLW` | `call_subroutine_using_w` | `klici_podprogram_z_w` |
| `MOVSF` | `move_indexed_to_f` | `premakni_indeksirano_v_f` |
| `MOVSS` | `move_indexed_to_indexed` | `premakni_indeksirano_v_indeksirano` |
| `PUSHL` | `push_literal` | `potisni_konstanto` |
| `SUBFSR` | `subtract_literal_from_fsr` | `odstej_konstanto_od_fsr` |
| `SUBULNK` | `subtract_literal_from_fsr2_and_return` | `odstej_konstanto_od_fsr2_in_vrni` |

### PIC16 Instructions

#### PIC16 Base Set — Unique to PIC16 (5)

These instructions exist only in the PIC16 mid-range instruction set and have no PIC18 equivalent.

| PIC16 Mnemonic | English Readable Name | Slovenian Readable Name |
|---|---|---|
| `CLRW` | `clear_w` | `pocisti_w` |
| `RLF` | `rotate_left_f` | `zavrti_levo_f` |
| `RRF` | `rotate_right_f` | `zavrti_desno_f` |
| `OPTION` | `option_load` | `nalozi_opcijo` |
| `TRIS` | `load_tris` | `nalozi_tris` |

#### PIC16 Enhanced Mid-Range — PIC16F1xxx (14)

These instructions were added in the enhanced mid-range PIC16F1xxx family. Some share mnemonics with PIC18 (ADDWFC, SUBWFB, BRA, CALLW, ADDFSR, MOVLB, RESET); the PIC16 variants use a `_16` suffix to distinguish them.

| PIC16 Mnemonic | English Readable Name | Slovenian Readable Name |
|---|---|---|
| `ADDWFC` | `add_w_to_f_with_carry_16` | `pristej_w_k_f_s_prenosom_16` |
| `SUBWFB` | `subtract_w_from_f_with_borrow_16` | `odstej_w_od_f_z_izposojo_16` |
| `LSLF` | `logical_shift_left_f` | `logicni_pomik_levo_f` |
| `LSRF` | `logical_shift_right_f` | `logicni_pomik_desno_f` |
| `ASRF` | `arithmetic_shift_right_f` | `aritmeticni_pomik_desno_f` |
| `BRA` | `branch_relative` | `vejitev_relativna` |
| `BRW` | `branch_relative_with_w` | `vejitev_relativna_z_w` |
| `CALLW` | `call_subroutine_with_w` | `klici_podprogram_z_w_16` |
| `ADDFSR` | `add_literal_to_fsr_16` | `pristej_konstanto_k_fsr_16` |
| `MOVIW` | `move_indirect_from_fsr` | `premakni_posredno_iz_fsr` |
| `MOVWI` | `move_w_indirect_to_fsr` | `premakni_w_posredno_v_fsr` |
| `MOVLB` | `move_literal_to_bsr_16` | `premakni_konstanto_v_bsr_16` |
| `MOVLP` | `move_literal_to_pclath` | `premakni_konstanto_v_pclath` |
| `RESET` | `software_reset_16` | `programska_ponastavitev_16` |

> **Note:** PIC16 and PIC18 share many instructions (ADDWF, ANDWF, BCF, BSF, CALL, GOTO, MOVLW, etc.). These shared instructions use the **same readable names** listed in the PIC18 tables above, so no duplication is needed. Use them freely in PIC16 `.rasm` files.

---

## Writing `.rasm` Files

### Basic Rules

1. **One instruction per line** — same as standard PIC16/PIC18 assembly.
2. **Operands are unchanged** — register names, literals, `ACCESS`/`BANKED`, `W`/`F` are written exactly as in standard asm.
3. **Labels** end with `:` and go at the start of a line (e.g. `MAIN:`).
4. **Comments** start with `;` — they are preserved through translation.
5. **Directives** (`ORG`, `EQU`, `CONFIG`, `#include`, `LIST`, `DB`, `END`, etc.) are passed through unchanged.
6. **English and Slovenian names can be mixed** in the same file.
7. **PIC16 and PIC18 instructions can be mixed** — the translator handles both.

### PIC18 Example

```
; Reset vector
    ORG 0x0000
    goto_address MAIN

MAIN:
    move_literal_to_bsr 0           ; select bank 0
    clear_f TRISB, ACCESS           ; PORTB = output
    clear_f LATB, ACCESS            ; all LEDs off

LOOP:
    bit_set_f LATB, 0, ACCESS       ; LED on
    call_subroutine DELAY, 0
    bit_clear_f LATB, 0, ACCESS     ; LED off
    call_subroutine DELAY, 0
    branch_always LOOP              ; repeat
```

### PIC16 Example

```
    LIST p=16F877A
    ORG 0x0000

MAIN:
    bit_clear_f STATUS, RP0         ; bank 0
    clear_f TRISB                   ; PORTB = output

LOOP:
    move_literal_to_w 0xFF
    move_w_to_f PORTB               ; all LEDs on
    call_subroutine DELAY
    clear_w
    move_w_to_f PORTB               ; all LEDs off
    call_subroutine DELAY
    goto_address LOOP
```

---

## Reference Data Sources

- Microchip PIC18F instruction set reference (DS39500)
- PIC18 Extended Instruction Set (XINST) documentation
- Microchip PIC16 mid-range MCU instruction set (DS33023)
- PIC16F1xxx enhanced mid-range reference (DS40001239)

---

## License

This project is provided as-is for educational and development use.

#!/usr/bin/env python3
"""
PIC Reverse Translator  (PIC16 + PIC18)
========================================
Converts standard PIC16/PIC18 assembly (.asm) back into human-readable
assembly (.rasm).

Supports two target languages:
  --lang en   →  English readable names   (default)
  --lang si   →  Slovenian readable names

Usage:
    python pic18_reverse_translator.py input.asm [-o output.rasm] [--lang en|si]

If no output file is specified, the result is printed to stdout.
"""

import re
import sys
import argparse
import io

# =============================================================================
# Standard PIC18 mnemonic → English readable name
# =============================================================================
REVERSE_MAP_EN: dict[str, str] = {
    # ── Byte-oriented file register operations ──────────────────────────
    "ADDWF":    "add_w_to_f",
    "ADDWFC":   "add_w_to_f_with_carry",
    "ANDWF":    "and_w_with_f",
    "CLRF":     "clear_f",
    "COMF":     "complement_f",
    "CPFSEQ":   "compare_f_skip_if_equal",
    "CPFSGT":   "compare_f_skip_if_greater",
    "CPFSLT":   "compare_f_skip_if_less",
    "DECF":     "decrement_f",
    "DECFSZ":   "decrement_f_skip_if_zero",
    "DCFSNZ":   "decrement_f_skip_if_not_zero",
    "INCF":     "increment_f",
    "INCFSZ":   "increment_f_skip_if_zero",
    "INFSNZ":   "increment_f_skip_if_not_zero",
    "IORWF":    "or_w_with_f",
    "MOVF":     "move_f",
    "MOVFF":    "move_f_to_f",
    "MOVWF":    "move_w_to_f",
    "MULWF":    "multiply_w_with_f",
    "NEGF":     "negate_f",
    "RLCF":     "rotate_left_f_through_carry",
    "RLNCF":    "rotate_left_f_no_carry",
    "RRCF":     "rotate_right_f_through_carry",
    "RRNCF":    "rotate_right_f_no_carry",
    "SETF":     "set_f",
    "SUBFWB":   "subtract_f_from_w_with_borrow",
    "SUBWF":    "subtract_w_from_f",
    "SUBWFB":   "subtract_w_from_f_with_borrow",
    "SWAPF":    "swap_nibbles_f",
    "TSTFSZ":   "test_f_skip_if_zero",
    "XORWF":    "xor_w_with_f",

    # ── Bit-oriented file register operations ───────────────────────────
    "BCF":      "bit_clear_f",
    "BSF":      "bit_set_f",
    "BTFSC":    "bit_test_f_skip_if_clear",
    "BTFSS":    "bit_test_f_skip_if_set",
    "BTG":      "bit_toggle_f",

    # ── Literal operations ──────────────────────────────────────────────
    "ADDLW":    "add_literal_to_w",
    "ANDLW":    "and_literal_with_w",
    "IORLW":    "or_literal_with_w",
    "MOVLB":    "move_literal_to_bsr",
    "MOVLW":    "move_literal_to_w",
    "MULLW":    "multiply_literal_with_w",
    "SUBLW":    "subtract_w_from_literal",
    "XORLW":    "xor_literal_with_w",

    # ── Control / branch operations ─────────────────────────────────────
    "BC":       "branch_if_carry",
    "BN":       "branch_if_negative",
    "BNC":      "branch_if_not_carry",
    "BNN":      "branch_if_not_negative",
    "BNOV":     "branch_if_not_overflow",
    "BNZ":      "branch_if_not_zero",
    "BOV":      "branch_if_overflow",
    "BRA":      "branch_always",
    "BZ":       "branch_if_zero",
    "CALL":     "call_subroutine",
    "CLRWDT":   "clear_watchdog_timer",
    "DAW":      "decimal_adjust_w",
    "GOTO":     "goto_address",
    "NOP":      "no_operation",
    "POP":      "pop_return_stack",
    "PUSH":     "push_return_stack",
    "RCALL":    "relative_call",
    "RESET":    "software_reset",
    "RETFIE":   "return_from_interrupt",
    "RETLW":    "return_with_literal_in_w",
    "RETURN":   "return_from_subroutine",
    "SLEEP":    "enter_sleep_mode",

    # ── Table read / write operations ───────────────────────────────────
    "TBLRD*":   "table_read",
    "TBLRD*+":  "table_read_post_increment",
    "TBLRD*-":  "table_read_post_decrement",
    "TBLRD+*":  "table_read_pre_increment",
    "TBLWT*":   "table_write",
    "TBLWT*+":  "table_write_post_increment",
    "TBLWT*-":  "table_write_post_decrement",
    "TBLWT+*":  "table_write_pre_increment",

    # ── Extended instruction set (XINST = 1) ────────────────────────────
    "ADDFSR":   "add_literal_to_fsr",
    "ADDULNK":  "add_literal_to_fsr2_and_return",
    "CALLW":    "call_subroutine_using_w",
    "MOVSF":    "move_indexed_to_f",
    "MOVSS":    "move_indexed_to_indexed",
    "PUSHL":    "push_literal",
    "SUBFSR":   "subtract_literal_from_fsr",
    "SUBULNK":  "subtract_literal_from_fsr2_and_return",
}

# =============================================================================
# PIC16-only standard mnemonic → English readable name
# =============================================================================
REVERSE_MAP_PIC16_EN: dict[str, str] = {
    "CLRW":     "clear_w",
    "RLF":      "rotate_left_f",
    "RRF":      "rotate_right_f",
    "OPTION":   "option_load",
    "TRIS":     "load_tris",
    # Enhanced mid-range (PIC16F1xxx)
    "LSLF":     "logical_shift_left_f",
    "LSRF":     "logical_shift_right_f",
    "ASRF":     "arithmetic_shift_right_f",
    "BRW":      "branch_relative_with_w",
    "MOVIW":    "move_indirect_from_fsr",
    "MOVWI":    "move_w_indirect_to_fsr",
    "MOVLP":    "move_literal_to_pclath",
}

# =============================================================================
# Standard PIC18 mnemonic → Slovenian readable name
# =============================================================================
REVERSE_MAP_SI: dict[str, str] = {
    # ── Bajtno usmerjene operacije ──────────────────────────────────────
    "ADDWF":    "pristej_w_k_f",
    "ADDWFC":   "pristej_w_k_f_s_prenosom",
    "ANDWF":    "in_w_z_f",
    "CLRF":     "pocisti_f",
    "COMF":     "komplementiraj_f",
    "CPFSEQ":   "primerjaj_f_preskoci_ce_enako",
    "CPFSGT":   "primerjaj_f_preskoci_ce_vecje",
    "CPFSLT":   "primerjaj_f_preskoci_ce_manjse",
    "DECF":     "zmanjsaj_f",
    "DECFSZ":   "zmanjsaj_f_preskoci_ce_nic",
    "DCFSNZ":   "zmanjsaj_f_preskoci_ce_ni_nic",
    "INCF":     "povecaj_f",
    "INCFSZ":   "povecaj_f_preskoci_ce_nic",
    "INFSNZ":   "povecaj_f_preskoci_ce_ni_nic",
    "IORWF":    "ali_w_z_f",
    "MOVF":     "premakni_f",
    "MOVFF":    "premakni_f_v_f",
    "MOVWF":    "premakni_w_v_f",
    "MULWF":    "pomnozi_w_z_f",
    "NEGF":     "negiraj_f",
    "RLCF":     "zavrti_levo_f_skozi_prenos",
    "RLNCF":    "zavrti_levo_f_brez_prenosa",
    "RRCF":     "zavrti_desno_f_skozi_prenos",
    "RRNCF":    "zavrti_desno_f_brez_prenosa",
    "SETF":     "nastavi_f",
    "SUBFWB":   "odstej_f_od_w_z_izposojo",
    "SUBWF":    "odstej_w_od_f",
    "SUBWFB":   "odstej_w_od_f_z_izposojo",
    "SWAPF":    "zamenjaj_polbajta_f",
    "TSTFSZ":   "testiraj_f_preskoci_ce_nic",
    "XORWF":    "xali_w_z_f",

    # ── Bitno usmerjene operacije ───────────────────────────────────────
    "BCF":      "bit_pocisti_f",
    "BSF":      "bit_nastavi_f",
    "BTFSC":    "bit_testiraj_f_preskoci_ce_pociscen",
    "BTFSS":    "bit_testiraj_f_preskoci_ce_nastavljen",
    "BTG":      "bit_preklopi_f",

    # ── Operacije s konstantami ─────────────────────────────────────────
    "ADDLW":    "pristej_konstanto_k_w",
    "ANDLW":    "in_konstanto_z_w",
    "IORLW":    "ali_konstanto_z_w",
    "MOVLB":    "premakni_konstanto_v_bsr",
    "MOVLW":    "premakni_konstanto_v_w",
    "MULLW":    "pomnozi_konstanto_z_w",
    "SUBLW":    "odstej_w_od_konstante",
    "XORLW":    "xali_konstanto_z_w",

    # ── Krmilne / vejne operacije ───────────────────────────────────────
    "BC":       "vejitev_ce_prenos",
    "BN":       "vejitev_ce_negativno",
    "BNC":      "vejitev_ce_ni_prenosa",
    "BNN":      "vejitev_ce_ni_negativno",
    "BNOV":     "vejitev_ce_ni_prekoracitve",
    "BNZ":      "vejitev_ce_ni_nic",
    "BOV":      "vejitev_ce_prekoracitev",
    "BRA":      "vejitev_vedno",
    "BZ":       "vejitev_ce_nic",
    "CALL":     "klici_podprogram",
    "CLRWDT":   "pocisti_casovnik_psa",
    "DAW":      "decimalno_prilagodi_w",
    "GOTO":     "pojdi_na_naslov",
    "NOP":      "brez_operacije",
    "POP":      "odvzemi_iz_sklada",
    "PUSH":     "potisni_na_sklad",
    "RCALL":    "relativni_klic",
    "RESET":    "programska_ponastavitev",
    "RETFIE":   "vrni_se_iz_prekinitve",
    "RETLW":    "vrni_se_s_konstanto_v_w",
    "RETURN":   "vrni_se_iz_podprograma",
    "SLEEP":    "vstopi_v_spanje",

    # ── Operacije branja / pisanja tabele ───────────────────────────────
    "TBLRD*":   "beri_tabelo",
    "TBLRD*+":  "beri_tabelo_povecaj_po",
    "TBLRD*-":  "beri_tabelo_zmanjsaj_po",
    "TBLRD+*":  "beri_tabelo_povecaj_pred",
    "TBLWT*":   "pisi_tabelo",
    "TBLWT*+":  "pisi_tabelo_povecaj_po",
    "TBLWT*-":  "pisi_tabelo_zmanjsaj_po",
    "TBLWT+*":  "pisi_tabelo_povecaj_pred",

    # ── Razširjeni nabor ukazov (XINST = 1) ────────────────────────────
    "ADDFSR":   "pristej_konstanto_k_fsr",
    "ADDULNK":  "pristej_konstanto_k_fsr2_in_vrni",
    "CALLW":    "klici_podprogram_z_w",
    "MOVSF":    "premakni_indeksirano_v_f",
    "MOVSS":    "premakni_indeksirano_v_indeksirano",
    "PUSHL":    "potisni_konstanto",
    "SUBFSR":   "odstej_konstanto_od_fsr",
    "SUBULNK":  "odstej_konstanto_od_fsr2_in_vrni",
}

# =============================================================================
# PIC16-only standard mnemonic → Slovenian readable name
# =============================================================================
REVERSE_MAP_PIC16_SI: dict[str, str] = {
    "CLRW":     "pocisti_w",
    "RLF":      "zavrti_levo_f",
    "RRF":      "zavrti_desno_f",
    "OPTION":   "nalozi_opcijo",
    "TRIS":     "nalozi_tris",
    # Enhanced mid-range (PIC16F1xxx)
    "LSLF":     "logicni_pomik_levo_f",
    "LSRF":     "logicni_pomik_desno_f",
    "ASRF":     "aritmeticni_pomik_desno_f",
    "BRW":      "vejitev_relativna_z_w",
    "MOVIW":    "premakni_posredno_iz_fsr",
    "MOVWI":    "premakni_w_posredno_v_fsr",
    "MOVLP":    "premakni_konstanto_v_pclath",
}

# =============================================================================
# Assembler directives / pseudo-ops that should NOT be translated
# =============================================================================
_DIRECTIVES = {
    "LIST", "INCLUDE", "#INCLUDE", "CONFIG", "ORG", "EQU", "SET", "CONSTANT",
    "VARIABLE", "CBLOCK", "ENDC", "DB", "DW", "DE", "DT", "DATA", "RES",
    "FILL", "IF", "ELSE", "ENDIF", "IFDEF", "IFNDEF", "WHILE", "ENDW",
    "MACRO", "ENDM", "LOCAL", "EXITM", "EXPAND", "NOEXPAND", "MESSG",
    "ERROR", "ERRORLEVEL", "PAGE", "TITLE", "SUBTITLE", "SPACE", "NOLIST",
    "RADIX", "PROCESSOR", "END", "BANKSEL", "BANKISEL", "PAGESEL",
    "__CONFIG", "__IDLOCS", "__BADRAM", "__MAXRAM",
}


def _build_reverse_regex() -> re.Pattern:
    """Build a regex that matches any standard PIC16/PIC18 mnemonic.

    Table instructions (TBLRD*+, TBLWT+*, etc.) require special handling
    because they contain regex metacharacters (* and +).
    Longer mnemonics are tried first to avoid partial matches
    (e.g. TBLRD*+ before TBLRD*).
    """
    # Merge PIC18 + PIC16 mnemonics
    all_mnemonics = set(REVERSE_MAP_EN.keys()) | set(REVERSE_MAP_PIC16_EN.keys())
    sorted_mnemonics = sorted(all_mnemonics, key=len, reverse=True)
    pattern = "|".join(re.escape(m) for m in sorted_mnemonics)
    return re.compile(
        r"(?<!\w)(" + pattern + r")(?!\w)",
        re.IGNORECASE,
    )


_STD_MNEMONIC_RE = _build_reverse_regex()


def reverse_translate_line(line: str, rev_map: dict[str, str]) -> str:
    """Translate one line of standard PIC18 assembly into readable assembly.

    Labels, comments, directives, and operands are preserved verbatim.
    Only recognised PIC18 mnemonics are replaced with readable names.
    """
    stripped = line.rstrip("\n\r")

    # Fast path: empty or comment-only lines
    if stripped.strip() == "" or stripped.lstrip().startswith(";"):
        return stripped

    # Check if the first non-label token is a directive → pass through
    tokens = stripped.split()
    for tok in tokens:
        if tok.endswith(":"):
            continue  # skip label
        upper_tok = tok.upper().lstrip(".")
        if upper_tok in _DIRECTIVES or tok.startswith("#"):
            return stripped
        break

    def _replace(m: re.Match) -> str:
        key = m.group(1).upper()
        return rev_map.get(key, m.group(0))

    return _STD_MNEMONIC_RE.sub(_replace, stripped)


def reverse_translate(source: str, lang: str = "en") -> str:
    """Translate a full standard PIC16/PIC18 assembly source to readable assembly.

    Args:
        source: The standard assembly source code.
        lang:   "en" for English readable names, "si" for Slovenian.
    """
    if lang == "si":
        rev_map = {**REVERSE_MAP_SI, **REVERSE_MAP_PIC16_SI}
    else:
        rev_map = {**REVERSE_MAP_EN, **REVERSE_MAP_PIC16_EN}
    return "\n".join(
        reverse_translate_line(line, rev_map) for line in source.splitlines()
    )


# ── CLI ─────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert standard PIC16/PIC18 assembly (.asm) to readable assembly (.rasm).",
    )
    parser.add_argument(
        "input",
        help="Input file with standard PIC18 assembly (.asm).",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file for the readable assembly (.rasm).  Defaults to stdout.",
    )
    parser.add_argument(
        "--lang",
        choices=["en", "si"],
        default="en",
        help="Target language for readable names: 'en' (English, default) or 'si' (Slovenian).",
    )
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        source = f.read()

    result = reverse_translate(source, lang=args.lang)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result + "\n")
        out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        out.write(f"Readable assembly written to: {args.output}\n")
        out.flush()
    else:
        out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        out.write(result + "\n")
        out.flush()


if __name__ == "__main__":
    main()

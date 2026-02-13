#!/usr/bin/env python3
"""
PIC Readable Assembly Translator  (PIC16 + PIC18)
===================================================
Translates human-readable PIC assembly mnemonics into standard Microchip
assembly that can be assembled by MPASM / MPLAB XC8 PIC Assembler.

Supports:
  - PIC18 full instruction set (75 instructions incl. XINST)
  - PIC16 mid-range instruction set (35 base instructions)
  - PIC16 enhanced mid-range additions (16 instructions, PIC16F1xxx)
  - English and Slovenian readable names (can be mixed)

Instruction definitions are loaded from external JSON files:
  - pic18_instructions.json   (PIC18 EN + SI)
  - pic16_instructions.json   (PIC16 EN + SI)

Usage:
    python pic18_translator.py input.rasm [-o output.asm]

If no output file is specified, the result is printed to stdout.
"""

import json
import re
import sys
import argparse
from pathlib import Path

# =============================================================================
# Load instruction maps from JSON files
# =============================================================================
_SCRIPT_DIR = Path(__file__).resolve().parent

def _load_json(filename: str) -> dict:
    """Load an instruction JSON file from the same directory as this script."""
    path = _SCRIPT_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

_pic18_data = _load_json("pic18_instructions.json")
_pic16_data = _load_json("pic16_instructions.json")

# Forward maps: readable name → standard mnemonic
INSTRUCTION_MAP: dict[str, str]          = _pic18_data["en"]
INSTRUCTION_MAP_SI: dict[str, str]       = _pic18_data["si"]
INSTRUCTION_MAP_PIC16: dict[str, str]    = _pic16_data["en"]
INSTRUCTION_MAP_PIC16_SI: dict[str, str] = _pic16_data["si"]

# =============================================================================
# Merged map: all readable names (PIC18 EN/SI + PIC16 EN/SI) → standard mnemonic
# =============================================================================
INSTRUCTION_MAP_ALL: dict[str, str] = {
    **INSTRUCTION_MAP,
    **INSTRUCTION_MAP_SI,
    **INSTRUCTION_MAP_PIC16,
    **INSTRUCTION_MAP_PIC16_SI,
}

# Build reverse map (standard → readable) for reference / future use
REVERSE_MAP: dict[str, str] = {v: k for k, v in INSTRUCTION_MAP.items()}

# Pre-compile a single regex that matches any readable mnemonic at a word
# boundary.  Longer names are tried first so that e.g.
# "add_literal_to_fsr2_and_return" is matched before "add_literal_to_fsr".
_SORTED_KEYS = sorted(INSTRUCTION_MAP_ALL.keys(), key=len, reverse=True)
_MNEMONIC_RE = re.compile(
    r"(?<!\w)(" + "|".join(re.escape(k) for k in _SORTED_KEYS) + r")(?!\w)",
    re.IGNORECASE,
)


def translate_line(line: str) -> str:
    """Translate one source line from readable assembly to standard PIC asm.

    Rules:
    - Lines starting with ';' are pure comments → pass through.
    - Assembler directives (lines where the first token starts with '.' or '#',
      or is a well-known directive like ORG, EQU, LIST, etc.) → pass through.
    - Labels (tokens ending with ':') are preserved.
    - Everything after ';' on a line is a comment → preserved.
    - The readable mnemonic is replaced with the standard mnemonic;
      operands are kept verbatim.
    """
    # Preserve leading whitespace
    stripped = line.rstrip("\n\r")

    # Fast path: empty or comment-only lines
    if stripped.strip() == "" or stripped.lstrip().startswith(";"):
        return stripped

    # Replace ALL readable mnemonics found on the line (handles labels +
    # instructions on the same line, etc.)
    def _replace(m: re.Match) -> str:
        return INSTRUCTION_MAP_ALL[m.group(1).lower()]

    return _MNEMONIC_RE.sub(_replace, stripped)


def translate(source: str) -> str:
    """Translate a full readable-assembly source string to standard PIC assembly."""
    return "\n".join(translate_line(line) for line in source.splitlines())


def print_instruction_reference() -> None:
    """Print a nicely formatted reference table of all readable names."""

    # ── English categories ──────────────────────────────────────────────
    categories_en = {
        "Byte-oriented file register operations": [
            "add_w_to_f", "add_w_to_f_with_carry", "and_w_with_f", "clear_f",
            "complement_f", "compare_f_skip_if_equal", "compare_f_skip_if_greater",
            "compare_f_skip_if_less", "decrement_f", "decrement_f_skip_if_zero",
            "decrement_f_skip_if_not_zero", "increment_f",
            "increment_f_skip_if_zero", "increment_f_skip_if_not_zero",
            "or_w_with_f", "move_f", "move_f_to_f", "move_w_to_f",
            "multiply_w_with_f", "negate_f", "rotate_left_f_through_carry",
            "rotate_left_f_no_carry", "rotate_right_f_through_carry",
            "rotate_right_f_no_carry", "set_f", "subtract_f_from_w_with_borrow",
            "subtract_w_from_f", "subtract_w_from_f_with_borrow",
            "swap_nibbles_f", "test_f_skip_if_zero", "xor_w_with_f",
        ],
        "Bit-oriented file register operations": [
            "bit_clear_f", "bit_set_f", "bit_test_f_skip_if_clear",
            "bit_test_f_skip_if_set", "bit_toggle_f",
        ],
        "Literal operations": [
            "add_literal_to_w", "and_literal_with_w", "or_literal_with_w",
            "move_literal_to_bsr", "move_literal_to_w", "multiply_literal_with_w",
            "subtract_w_from_literal", "xor_literal_with_w",
        ],
        "Control / branch operations": [
            "branch_if_carry", "branch_if_negative", "branch_if_not_carry",
            "branch_if_not_negative", "branch_if_not_overflow",
            "branch_if_not_zero", "branch_if_overflow", "branch_always",
            "branch_if_zero", "call_subroutine", "clear_watchdog_timer",
            "decimal_adjust_w", "goto_address", "no_operation",
            "pop_return_stack", "push_return_stack", "relative_call",
            "software_reset", "return_from_interrupt",
            "return_with_literal_in_w", "return_from_subroutine",
            "enter_sleep_mode",
        ],
        "Table read / write operations": [
            "table_read", "table_read_post_increment",
            "table_read_post_decrement", "table_read_pre_increment",
            "table_write", "table_write_post_increment",
            "table_write_post_decrement", "table_write_pre_increment",
        ],
        "Extended instruction set (XINST = 1)": [
            "add_literal_to_fsr", "add_literal_to_fsr2_and_return",
            "call_subroutine_using_w", "move_indexed_to_f",
            "move_indexed_to_indexed", "push_literal",
            "subtract_literal_from_fsr",
            "subtract_literal_from_fsr2_and_return",
        ],
    }

    # ── Slovenian categories ────────────────────────────────────────────
    categories_si = {
        "Bajtno usmerjene operacije z registrom": [
            "pristej_w_k_f", "pristej_w_k_f_s_prenosom", "in_w_z_f", "pocisti_f",
            "komplementiraj_f", "primerjaj_f_preskoci_ce_enako",
            "primerjaj_f_preskoci_ce_vecje", "primerjaj_f_preskoci_ce_manjse",
            "zmanjsaj_f", "zmanjsaj_f_preskoci_ce_nic",
            "zmanjsaj_f_preskoci_ce_ni_nic", "povecaj_f",
            "povecaj_f_preskoci_ce_nic", "povecaj_f_preskoci_ce_ni_nic",
            "ali_w_z_f", "premakni_f", "premakni_f_v_f", "premakni_w_v_f",
            "pomnozi_w_z_f", "negiraj_f", "zavrti_levo_f_skozi_prenos",
            "zavrti_levo_f_brez_prenosa", "zavrti_desno_f_skozi_prenos",
            "zavrti_desno_f_brez_prenosa", "nastavi_f",
            "odstej_f_od_w_z_izposojo", "odstej_w_od_f",
            "odstej_w_od_f_z_izposojo", "zamenjaj_polbajta_f",
            "testiraj_f_preskoci_ce_nic", "xali_w_z_f",
        ],
        "Bitno usmerjene operacije z registrom": [
            "bit_pocisti_f", "bit_nastavi_f",
            "bit_testiraj_f_preskoci_ce_pociscen",
            "bit_testiraj_f_preskoci_ce_nastavljen", "bit_preklopi_f",
        ],
        "Operacije s konstantami": [
            "pristej_konstanto_k_w", "in_konstanto_z_w", "ali_konstanto_z_w",
            "premakni_konstanto_v_bsr", "premakni_konstanto_v_w",
            "pomnozi_konstanto_z_w", "odstej_w_od_konstante",
            "xali_konstanto_z_w",
        ],
        "Krmilne / vejne operacije": [
            "vejitev_ce_prenos", "vejitev_ce_negativno",
            "vejitev_ce_ni_prenosa", "vejitev_ce_ni_negativno",
            "vejitev_ce_ni_prekoracitve", "vejitev_ce_ni_nic",
            "vejitev_ce_prekoracitev", "vejitev_vedno", "vejitev_ce_nic",
            "klici_podprogram", "pocisti_casovnik_psa",
            "decimalno_prilagodi_w", "pojdi_na_naslov", "brez_operacije",
            "odvzemi_iz_sklada", "potisni_na_sklad", "relativni_klic",
            "programska_ponastavitev", "vrni_se_iz_prekinitve",
            "vrni_se_s_konstanto_v_w", "vrni_se_iz_podprograma",
            "vstopi_v_spanje",
        ],
        "Operacije branja / pisanja tabele": [
            "beri_tabelo", "beri_tabelo_povecaj_po",
            "beri_tabelo_zmanjsaj_po", "beri_tabelo_povecaj_pred",
            "pisi_tabelo", "pisi_tabelo_povecaj_po",
            "pisi_tabelo_zmanjsaj_po", "pisi_tabelo_povecaj_pred",
        ],
        "Razsirjeni nabor ukazov (XINST = 1)": [
            "pristej_konstanto_k_fsr", "pristej_konstanto_k_fsr2_in_vrni",
            "klici_podprogram_z_w", "premakni_indeksirano_v_f",
            "premakni_indeksirano_v_indeksirano", "potisni_konstanto",
            "odstej_konstanto_od_fsr",
            "odstej_konstanto_od_fsr2_in_vrni",
        ],
    }

    # Use sys.stdout with UTF-8 to avoid cp1250 encoding issues on Windows
    import io
    out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    def _print_section(title: str, categories: dict, instr_map: dict) -> None:
        out.write("=" * 72 + "\n")
        out.write(f"  {title}\n")
        out.write("=" * 72 + "\n")
        for cat_name, keys in categories.items():
            pad = max(55 - len(cat_name), 4)
            out.write(f"\n-- {cat_name} {'-' * pad}\n")
            out.write(f"  {'Readable Name':<48} {'PIC18 Mnemonic'}\n")
            out.write(f"  {'-' * 48} {'-' * 14}\n")
            for k in keys:
                out.write(f"  {k:<48} {instr_map[k]}\n")
        out.write("\n")
        out.flush()

    # ── PIC16 English categories ─────────────────────────────────────────
    categories_pic16_en = {
        "PIC16 base set (unique to PIC16)": [
            "clear_w", "rotate_left_f", "rotate_right_f",
            "option_load", "load_tris",
        ],
        "PIC16 enhanced mid-range (PIC16F1xxx)": [
            "add_w_to_f_with_carry_16", "subtract_w_from_f_with_borrow_16",
            "logical_shift_left_f", "logical_shift_right_f",
            "arithmetic_shift_right_f", "branch_relative",
            "branch_relative_with_w", "call_subroutine_with_w",
            "add_literal_to_fsr_16", "move_indirect_from_fsr",
            "move_w_indirect_to_fsr", "move_literal_to_bsr_16",
            "move_literal_to_pclath", "software_reset_16",
        ],
    }

    # ── PIC16 Slovenian categories ──────────────────────────────────────
    categories_pic16_si = {
        "PIC16 osnovna (samo PIC16)": [
            "pocisti_w", "zavrti_levo_f", "zavrti_desno_f",
            "nalozi_opcijo", "nalozi_tris",
        ],
        "PIC16 razsirjeni srednji razred (PIC16F1xxx)": [
            "pristej_w_k_f_s_prenosom_16", "odstej_w_od_f_z_izposojo_16",
            "logicni_pomik_levo_f", "logicni_pomik_desno_f",
            "aritmeticni_pomik_desno_f", "vejitev_relativna",
            "vejitev_relativna_z_w", "klici_podprogram_z_w_16",
            "pristej_konstanto_k_fsr_16", "premakni_posredno_iz_fsr",
            "premakni_w_posredno_v_fsr", "premakni_konstanto_v_bsr_16",
            "premakni_konstanto_v_pclath", "programska_ponastavitev_16",
        ],
    }

    _print_section(
        "PIC18 READABLE ASSEMBLY — INSTRUCTION REFERENCE (ENGLISH)",
        categories_en,
        INSTRUCTION_MAP,
    )
    _print_section(
        "PIC18 BERLJIV ZBIRNIK — SEZNAM UKAZOV (SLOVENŠČINA)",
        categories_si,
        INSTRUCTION_MAP_SI,
    )
    _print_section(
        "PIC16 READABLE ASSEMBLY — INSTRUCTION REFERENCE (ENGLISH)",
        categories_pic16_en,
        INSTRUCTION_MAP_PIC16,
    )
    _print_section(
        "PIC16 BERLJIV ZBIRNIK — SEZNAM UKAZOV (SLOVENŠČINA)",
        categories_pic16_si,
        INSTRUCTION_MAP_PIC16_SI,
    )


# ── CLI ─────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Translate readable PIC16/PIC18 assembly (.rasm) to standard PIC assembly.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Input file with readable assembly (.rasm).  Omit to print the instruction reference.",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file for the translated assembly.  Defaults to stdout.",
    )
    parser.add_argument(
        "--ref",
        action="store_true",
        help="Print the full instruction reference table and exit.",
    )
    args = parser.parse_args()

    if args.ref or args.input is None:
        print_instruction_reference()
        if args.input is None:
            return

    with open(args.input, "r", encoding="utf-8") as f:
        source = f.read()

    result = translate(source)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result + "\n")
        print(f"Translated assembly written to: {args.output}")
    else:
        print(result)


if __name__ == "__main__":
    main()

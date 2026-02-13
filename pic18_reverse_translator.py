#!/usr/bin/env python3
"""
PIC Reverse Translator  (PIC16 + PIC18)
========================================
Converts standard PIC16/PIC18 assembly (.asm) back into human-readable
assembly (.rasm).

Supports two target languages:
  --lang en   →  English readable names   (default)
  --lang si   →  Slovenian readable names

Instruction definitions are loaded from external JSON files:
  - pic18_instructions.json   (PIC18 EN + SI)
  - pic16_instructions.json   (PIC16 EN + SI)

Usage:
    python pic18_reverse_translator.py input.asm [-o output.rasm] [--lang en|si]

If no output file is specified, the result is printed to stdout.
"""

import json
import re
import sys
import argparse
import io
from pathlib import Path

# =============================================================================
# Load instruction maps from JSON files and build reverse maps
# =============================================================================
_SCRIPT_DIR = Path(__file__).resolve().parent

def _load_json(filename: str) -> dict:
    """Load an instruction JSON file from the instructions/ subdirectory."""
    path = _SCRIPT_DIR / "instructions" / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

_pic18_data = _load_json("pic18_instructions.json")
_pic16_data = _load_json("pic16_instructions.json")

def _invert(mapping: dict[str, str]) -> dict[str, str]:
    """Invert a readable→mnemonic map to mnemonic→readable."""
    return {v: k for k, v in mapping.items()}

# Reverse maps: standard mnemonic → readable name
REVERSE_MAP_EN: dict[str, str]       = _invert(_pic18_data["en"])
REVERSE_MAP_SI: dict[str, str]       = _invert(_pic18_data["si"])
REVERSE_MAP_PIC16_EN: dict[str, str] = _invert(_pic16_data["en"])
REVERSE_MAP_PIC16_SI: dict[str, str] = _invert(_pic16_data["si"])

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


# =============================================================================
# Assignment-syntax generation for MOVLW / MOVWF / MOVFF
# =============================================================================
# Regex to match MOVLW, MOVWF, MOVFF as the instruction on a line.
# Captures: indent, optional label, mnemonic, operands, optional comment.
_MOV_ASSIGN_RE = re.compile(
    r"^(?P<indent>\s*)"
    r"(?:(?P<label>\w+):\s*)?"
    r"(?P<mnemonic>MOVLW|MOVWF|MOVFF)\s+"
    r"(?P<operands>[^;]+?)"
    r"(?P<comment>\s*;.*)?"
    r"$",
    re.IGNORECASE,
)


def _reverse_assignment(line: str) -> str | None:
    """Try to convert MOVLW/MOVWF/MOVFF to assignment syntax.

    Returns None if the line does not match.

    Conversion rules:
      MOVLW <literal>        →  wreg = <literal>
      MOVWF <dest>[, access] →  <dest> = wreg[, access]
      MOVFF <src>, <dest>    →  <dest> = <src>
    """
    m = _MOV_ASSIGN_RE.match(line.rstrip("\n\r"))
    if not m:
        return None

    indent = m.group("indent") or ""
    label = m.group("label")
    mnemonic = m.group("mnemonic").upper()
    operands = m.group("operands").strip()
    comment = (m.group("comment") or "").rstrip()

    label_prefix = f"{label}: " if label else ""

    if mnemonic == "MOVLW":
        return f"{indent}{label_prefix}wreg = {operands}{comment}"

    if mnemonic == "MOVWF":
        # MOVWF <dest>[, ACCESS/BANKED]
        parts = [p.strip() for p in operands.split(",", 1)]
        dest = parts[0]
        extra = f", {parts[1]}" if len(parts) > 1 else ""
        return f"{indent}{label_prefix}{dest} = wreg{extra}{comment}"

    if mnemonic == "MOVFF":
        # MOVFF <src>, <dest>
        parts = [p.strip() for p in operands.split(",", 1)]
        if len(parts) == 2:
            src, dest = parts
            return f"{indent}{label_prefix}{dest} = {src}{comment}"

    return None


def reverse_translate_line(line: str, rev_map: dict[str, str]) -> str:
    """Translate one line of standard PIC18 assembly into readable assembly.

    Assignment-syntax is used for MOVLW, MOVWF, and MOVFF.
    Other mnemonics are replaced with readable names.
    Labels, comments, directives, and operands are preserved verbatim.
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

    # ── Try assignment syntax for MOVLW/MOVWF/MOVFF first ──
    result = _reverse_assignment(stripped)
    if result is not None:
        return result

    # ── Standard mnemonic replacement ──
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

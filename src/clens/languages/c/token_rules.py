"""The ordered C token rule table (R1.2, R1.3). Knows nothing about scanning
mechanics — that lives in `core/lexer_base.py`.

Literal patterns (integer bases and suffixes, float exponent/suffix forms,
string/char escape handling) are adapted from pycparser's `c_lexer.py`
(BSD-licensed; see `docs/third-party.md`), simplified to the suffix and
escape forms this subset actually needs — see
`.agents/skills/pycparser-reference/SKILL.md`.

Rule order encodes maximal munch (R1.3) and is load-bearing:

- Comments and string/char literals must precede the `/`, `"`-adjacent
  operator rules, or `//`, `/*`, and quoted text would be chopped up.
- FLOAT_LIT must precede INT_LIT and the `.` operator, or `1.5` lexes as
  `1` `.` `5` and `.5` lexes as `.` `5`.
- Within OPERATOR, multi-character forms are listed before the single
  characters that prefix them (`<=` before `<`, `->` before `-`, ...).
- "Unterminated" variants are listed directly after their terminated
  counterpart, so a well-formed literal always matches first (R1.6, R1.7).
"""

from __future__ import annotations

import re

from clens.core.lexer_base import TokenRule
from clens.core.token import TokenType

# --- Comments -----------------------------------------------------------

_LINE_COMMENT = r"//[^\n]*"
_BLOCK_COMMENT = r"/\*.*?\*/"
_UNTERMINATED_BLOCK_COMMENT = r"/\*.*"

# --- String and char literals --------------------------------------------
# A literal's content may not contain a raw newline (escaped or not); this
# is what makes the "unterminated" variants stop exactly at end of line.

_STRING_CHAR = r'(?:[^"\\\n]|\\[^\n])'
_STRING_LIT = f'"{_STRING_CHAR}*"'
_UNTERMINATED_STRING = f'"{_STRING_CHAR}*'

_CHAR_CHAR = r"(?:[^'\\\n]|\\[^\n])"
_CHAR_LIT = f"'{_CHAR_CHAR}*'"

# --- Numeric literals ------------------------------------------------------
# Adapted from pycparser's c_lexer.py integer/float constant regexes,
# trimmed to the u/U/l/L suffix forms this subset documents (R1.2) rather
# than pycparser's full ll/LL/combinations.

_INT_SUFFIX = r"(?:[uU][lL]?|[lL][uU]?)?"
_HEX_INT = r"0[xX][0-9a-fA-F]+" + _INT_SUFFIX
_BIN_INT = r"0[bB][01]+" + _INT_SUFFIX
_DEC_OR_OCTAL_INT = r"(?:0[0-7]*|[1-9][0-9]*)" + _INT_SUFFIX
_INT_LIT = f"(?:{_HEX_INT})|(?:{_BIN_INT})|(?:{_DEC_OR_OCTAL_INT})"

_EXPONENT = r"[eE][-+]?[0-9]+"
_FRACTIONAL = r"(?:[0-9]*\.[0-9]+)|(?:[0-9]+\.)"
_FLOAT_SUFFIX = r"[FfLl]?"
_FLOAT_LIT = f"(?:(?:{_FRACTIONAL})(?:{_EXPONENT})?|[0-9]+{_EXPONENT}){_FLOAT_SUFFIX}"

# --- Identifiers and preprocessor directives -------------------------------

_IDENT = r"[a-zA-Z_][a-zA-Z0-9_]*"
_PREPROC = r"#[^\n]*"

# --- Operators and delimiters -----------------------------------------------
# Longest-first within the alternation so maximal munch falls out of order.

_OPERATOR_LEXEMES = [
    "<=", ">=", "==", "!=", "->", "++", "--", "&&", "||",
    "+=", "-=", "*=", "/=", "%=",
    "=", "+", "-", "*", "/", "%", "<", ">", "!", "&", "~", "?", ":", ".",
]  # fmt: skip
_OPERATOR = "|".join(re.escape(op) for op in _OPERATOR_LEXEMES)

_DELIMITER_LEXEMES = ["{", "}", "(", ")", "[", "]", ";", ","]
_DELIMITER = "|".join(re.escape(d) for d in _DELIMITER_LEXEMES)

_WHITESPACE = r"[ \t\r\n]+"

C_TOKEN_RULES: list[TokenRule] = [
    TokenRule("LINE_COMMENT", TokenType.LINE_COMMENT, _LINE_COMMENT),
    TokenRule("BLOCK_COMMENT", TokenType.BLOCK_COMMENT, _BLOCK_COMMENT),
    TokenRule(
        "UNTERMINATED_BLOCK_COMMENT",
        TokenType.BLOCK_COMMENT,
        _UNTERMINATED_BLOCK_COMMENT,
        diagnostic="unterminated block comment",
        diagnostic_code="E003-unterminated-block-comment",
        diagnostic_span=2,
    ),
    TokenRule("STRING_LIT", TokenType.STRING_LIT, _STRING_LIT),
    TokenRule(
        "UNTERMINATED_STRING",
        TokenType.STRING_LIT,
        _UNTERMINATED_STRING,
        diagnostic="unterminated string literal",
        diagnostic_code="E002-unterminated-string",
        diagnostic_span=1,
    ),
    TokenRule("CHAR_LIT", TokenType.CHAR_LIT, _CHAR_LIT),
    TokenRule("FLOAT_LIT", TokenType.FLOAT_LIT, _FLOAT_LIT),
    TokenRule("INT_LIT", TokenType.INT_LIT, _INT_LIT),
    TokenRule("PREPROC", TokenType.PREPROC, _PREPROC),
    TokenRule("IDENT", TokenType.IDENT, _IDENT),
    TokenRule("OPERATOR", TokenType.OPERATOR, _OPERATOR),
    TokenRule("DELIMITER", TokenType.DELIMITER, _DELIMITER),
    TokenRule("WHITESPACE", TokenType.WHITESPACE, _WHITESPACE),
]

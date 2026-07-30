"""The reserved-word set for the C subset (project/03-c-subset.md).

Keywords are not their own regex rules (R1.4): the lexer matches an
identifier and this set is consulted afterwards to retype it. A `\\bwhile\\b`
style rule would mis-lex `while_count`.

`static`, `extern`, `volatile`, and `register` are recognized here even
though the subset "parses and ignores, or rejects" them — that choice is the
parser's to make (Stage 4); the lexer's job is only to recognize that they
are keywords, not plain identifiers.
"""

from __future__ import annotations

KEYWORDS: frozenset[str] = frozenset(
    {
        # Types
        "void",
        "char",
        "int",
        "float",
        "double",
        "struct",
        "const",
        # Storage-class / qualifiers (parsed, disposition decided by the parser)
        "static",
        "extern",
        "volatile",
        "register",
        # Statements
        "if",
        "else",
        "while",
        "for",
        "return",
        "break",
        "continue",
        # Operators spelled as words
        "sizeof",
    }
)

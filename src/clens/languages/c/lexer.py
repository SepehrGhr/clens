"""Wires the C token rule table into the generic lexer engine and applies
keyword retyping (R1.4).
"""

from __future__ import annotations

from clens.core.diagnostics import DiagnosticCollector
from clens.core.lexer_base import LexerEngine
from clens.core.source import SourceFile
from clens.core.token import Token, TokenType
from clens.languages.c.keywords import KEYWORDS
from clens.languages.c.token_rules import C_TOKEN_RULES


def _retype_keywords(lexeme: str, token_type: TokenType) -> TokenType:
    """Match as identifier first, then check keyword membership (R1.4)."""
    if token_type is TokenType.IDENT and lexeme in KEYWORDS:
        return TokenType.KEYWORD
    return token_type


_ENGINE = LexerEngine(C_TOKEN_RULES, retype=_retype_keywords)


def tokenize(source: SourceFile, diagnostics: DiagnosticCollector) -> list[Token]:
    """Scan a C source file into a flat token list. Never raises (R1.5)."""
    return _ENGINE.tokenize(source, diagnostics)

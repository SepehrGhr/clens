"""Language-agnostic token representation: TokenType, Token, and Span.

Every lexer (regardless of source language) produces Token instances from this
module. Category names are generic (KEYWORD, IDENT, OPERATOR, ...); the set of
actual keywords/operators is language data that lives under ``languages/``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    """Token categories required by R1.2."""

    KEYWORD = auto()
    IDENT = auto()
    INT_LIT = auto()
    FLOAT_LIT = auto()
    STRING_LIT = auto()
    CHAR_LIT = auto()
    OPERATOR = auto()
    DELIMITER = auto()
    LINE_COMMENT = auto()
    BLOCK_COMMENT = auto()
    WHITESPACE = auto()
    PREPROC = auto()
    INVALID = auto()
    EOF = auto()


#: Token types that are retained for byte-faithful rendering (R1.8) but are
#: filtered out of the view the parser consumes.
TRIVIA_TYPES = frozenset({TokenType.WHITESPACE, TokenType.LINE_COMMENT, TokenType.BLOCK_COMMENT})


@dataclass(slots=True, frozen=True)
class Span:
    """A source range: 0-based half-open offsets plus the 1-based position of
    its first character. Shared by tokens, diagnostics, and AST nodes so there
    is one shape for "where in the source" everywhere in the codebase.
    """

    start_offset: int
    end_offset: int
    line: int
    column: int


@dataclass(slots=True)
class Token:
    """A single lexical token, carrying the fields required by R1.1."""

    type: TokenType
    lexeme: str
    file: str
    line: int
    column: int
    start_offset: int
    end_offset: int

    @property
    def is_trivia(self) -> bool:
        """Whitespace and comment tokens are trivia (R1.8)."""
        return self.type in TRIVIA_TYPES

    @property
    def span(self) -> Span:
        """This token's location as a :class:`Span`."""
        return Span(self.start_offset, self.end_offset, self.line, self.column)

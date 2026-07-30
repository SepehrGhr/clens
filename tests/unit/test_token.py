"""R1.1, R1.2 — Token, TokenType, is_trivia, Span."""

import pytest

from clens.core.token import Span, Token, TokenType


def make_token(type_: TokenType, lexeme: str) -> Token:
    return Token(
        type=type_,
        lexeme=lexeme,
        file="a.c",
        line=1,
        column=1,
        start_offset=0,
        end_offset=len(lexeme),
    )


@pytest.mark.parametrize(
    "type_,expected",
    [
        (TokenType.WHITESPACE, True),
        (TokenType.LINE_COMMENT, True),
        (TokenType.BLOCK_COMMENT, True),
        (TokenType.KEYWORD, False),
        (TokenType.IDENT, False),
        (TokenType.OPERATOR, False),
        (TokenType.EOF, False),
    ],
)
def test_is_trivia(type_, expected):
    assert make_token(type_, "x").is_trivia is expected


def test_token_span_matches_fields():
    tok = Token(
        type=TokenType.IDENT,
        lexeme="factorial",
        file="a.c",
        line=3,
        column=16,
        start_offset=40,
        end_offset=49,
    )
    assert tok.span == Span(start_offset=40, end_offset=49, line=3, column=16)


def test_all_r1_2_categories_exist():
    required = {
        "KEYWORD",
        "IDENT",
        "INT_LIT",
        "FLOAT_LIT",
        "STRING_LIT",
        "CHAR_LIT",
        "OPERATOR",
        "DELIMITER",
        "LINE_COMMENT",
        "BLOCK_COMMENT",
        "WHITESPACE",
        "PREPROC",
        "INVALID",
        "EOF",
    }
    assert required <= {member.name for member in TokenType}

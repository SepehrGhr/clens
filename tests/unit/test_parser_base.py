"""R3.1, R3.3 — the generic ParserBase cursor, exercised with hand-built
token streams (no real lexer needed)."""

import pytest

from clens.core.diagnostics import DiagnosticCollector
from clens.core.parser_base import ParseError, ParserBase
from clens.core.token import Token, TokenType


def tok(type_: TokenType, lexeme: str, line: int = 1, column: int = 1) -> Token:
    return Token(
        type=type_,
        lexeme=lexeme,
        file="a.c",
        line=line,
        column=column,
        start_offset=column - 1,
        end_offset=column - 1 + len(lexeme),
    )


def make_parser(tokens: list[Token]) -> tuple[ParserBase, DiagnosticCollector]:
    diagnostics = DiagnosticCollector()
    tokens = [*tokens, tok(TokenType.EOF, "", line=99, column=1)]
    return ParserBase(tokens, diagnostics), diagnostics


def test_requires_eof_terminated_stream():
    with pytest.raises(ValueError):
        ParserBase([tok(TokenType.IDENT, "x")], DiagnosticCollector())
    with pytest.raises(ValueError):
        ParserBase([], DiagnosticCollector())


def test_peek_and_advance():
    parser, _ = make_parser([tok(TokenType.IDENT, "x"), tok(TokenType.DELIMITER, ";")])
    assert parser.peek().lexeme == "x"
    assert parser.peek(1).lexeme == ";"
    first = parser.advance()
    assert first.lexeme == "x"
    assert parser.peek().lexeme == ";"
    assert parser.previous().lexeme == "x"


def test_peek_past_eof_clamps_to_eof():
    parser, _ = make_parser([tok(TokenType.IDENT, "x")])
    assert parser.peek(50).type == TokenType.EOF


def test_advance_at_end_does_not_move_past_eof():
    parser, _ = make_parser([])
    assert parser.at_end()
    eof1 = parser.advance()
    eof2 = parser.advance()
    assert eof1.type is eof2.type is TokenType.EOF
    assert parser.at_end()


def test_check_and_match():
    parser, _ = make_parser([tok(TokenType.KEYWORD, "if")])
    assert parser.check(TokenType.KEYWORD)
    assert not parser.check(TokenType.IDENT)
    assert parser.match(TokenType.IDENT) is None
    matched = parser.match(TokenType.KEYWORD)
    assert matched is not None and matched.lexeme == "if"


def test_check_lexeme_and_match_lexeme():
    parser, _ = make_parser([tok(TokenType.OPERATOR, "+")])
    assert parser.check_lexeme("+", "-")
    assert not parser.check_lexeme("*")
    assert parser.match_lexeme("*") is None
    matched = parser.match_lexeme("+", "-")
    assert matched is not None and matched.lexeme == "+"


def test_expect_consumes_on_match():
    parser, _ = make_parser([tok(TokenType.DELIMITER, ")")])
    token = parser.expect(TokenType.DELIMITER, ")")
    assert token.lexeme == ")"
    assert parser.at_end()


def test_expect_raises_and_records_diagnostic_with_r3_5_message():
    parser, diagnostics = make_parser([tok(TokenType.DELIMITER, "{", line=2, column=1)])
    with pytest.raises(ParseError):
        parser.expect(TokenType.DELIMITER, ")", "to close parameter list")
    assert len(diagnostics.errors) == 1
    assert diagnostics.errors[0].message == "expected ')' to close parameter list, got '{'"


def test_expect_reports_end_of_file():
    parser, diagnostics = make_parser([])
    with pytest.raises(ParseError):
        parser.expect(TokenType.DELIMITER, ";")
    assert "end of file" in diagnostics.errors[0].message


def test_expect_type_consumes_regardless_of_lexeme():
    parser, _ = make_parser([tok(TokenType.IDENT, "n")])
    token = parser.expect_type(TokenType.IDENT, "identifier")
    assert token.lexeme == "n"


def test_expect_type_failure_message():
    parser, diagnostics = make_parser([tok(TokenType.DELIMITER, ";")])
    with pytest.raises(ParseError):
        parser.expect_type(TokenType.IDENT, "expression")
    assert diagnostics.errors[0].message == "expected expression, got ';'"


def test_synchronize_consumes_semicolon_and_stops():
    parser, _ = make_parser([tok(TokenType.DELIMITER, ";"), tok(TokenType.KEYWORD, "return")])
    parser.synchronize(frozenset({"return"}))
    assert parser.peek().lexeme == "return"


def test_synchronize_stops_before_close_brace_without_consuming():
    parser, _ = make_parser([tok(TokenType.IDENT, "garbage"), tok(TokenType.DELIMITER, "}")])
    parser.synchronize(frozenset())
    assert parser.peek().lexeme == "}"


def test_synchronize_stops_at_sync_lexeme_without_consuming():
    parser, _ = make_parser([tok(TokenType.IDENT, "garbage"), tok(TokenType.KEYWORD, "if")])
    parser.synchronize(frozenset({"if"}))
    assert parser.peek().lexeme == "if"


def test_synchronize_stops_at_eof():
    parser, _ = make_parser([tok(TokenType.IDENT, "garbage")])
    parser.synchronize(frozenset())
    assert parser.at_end()


def test_guard_progress_forces_advance_when_stuck():
    parser, _ = make_parser([tok(TokenType.DELIMITER, "}"), tok(TokenType.IDENT, "x")])
    pos_before = parser.pos
    parser.synchronize(frozenset())  # stops immediately, no progress
    assert parser.pos == pos_before
    parser.guard_progress(pos_before)
    assert parser.pos == pos_before + 1


def test_guard_progress_is_a_no_op_when_progress_was_made():
    parser, _ = make_parser([tok(TokenType.DELIMITER, ";"), tok(TokenType.IDENT, "x")])
    pos_before = parser.pos
    parser.synchronize(frozenset())
    moved_pos = parser.pos
    assert moved_pos != pos_before
    parser.guard_progress(pos_before)
    assert parser.pos == moved_pos


def test_guard_progress_never_advances_past_eof():
    parser, _ = make_parser([])
    pos_before = parser.pos
    parser.guard_progress(pos_before)
    assert parser.at_end()

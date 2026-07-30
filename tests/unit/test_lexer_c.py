"""R1.2-R1.7 — the C lexer: one test per token category, maximal munch,
keyword priority, and the golden error-recovery cases.
"""

import pytest

from clens.core.diagnostics import DiagnosticCollector
from clens.core.source import SourceFile
from clens.core.token import Token, TokenType
from clens.languages.c.lexer import tokenize


def lex(text: str) -> tuple[list[Token], DiagnosticCollector]:
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    return tokenize(source, diagnostics), diagnostics


def significant_lexemes(text: str) -> list[tuple[TokenType, str]]:
    tokens, _ = lex(text)
    return [(t.type, t.lexeme) for t in tokens if t.type != TokenType.EOF]


def test_empty_file_yields_only_eof():
    tokens, diagnostics = lex("")
    assert [t.type for t in tokens] == [TokenType.EOF]
    assert diagnostics.diagnostics == []


# --- One test per R1.2 category --------------------------------------------


def test_keyword():
    assert significant_lexemes("while") == [(TokenType.KEYWORD, "while")]


def test_ident():
    assert significant_lexemes("factorial") == [(TokenType.IDENT, "factorial")]


@pytest.mark.parametrize(
    "text",
    ["42", "0xFF", "0b1010", "0755", "10u", "10UL", "0"],
)
def test_int_lit(text):
    assert significant_lexemes(text) == [(TokenType.INT_LIT, text)]


@pytest.mark.parametrize("text", ["3.14", "1.0e-5", ".5f", "1.", "1e10"])
def test_float_lit(text):
    assert significant_lexemes(text) == [(TokenType.FLOAT_LIT, text)]


@pytest.mark.parametrize("text", ['"hello\\n"', '"say \\"hi\\""', '""'])
def test_string_lit(text):
    assert significant_lexemes(text) == [(TokenType.STRING_LIT, text)]


@pytest.mark.parametrize("text", ["'a'", "'\\t'", "'\\0'", "'\\''"])
def test_char_lit(text):
    assert significant_lexemes(text) == [(TokenType.CHAR_LIT, text)]


@pytest.mark.parametrize("text", ["+", "->", "==", "&&", "?", ":"])
def test_operator(text):
    assert significant_lexemes(text) == [(TokenType.OPERATOR, text)]


@pytest.mark.parametrize("text", ["{", "}", "(", ")", "[", "]", ";", ","])
def test_delimiter(text):
    assert significant_lexemes(text) == [(TokenType.DELIMITER, text)]


def test_line_comment_stops_at_newline():
    tokens, _ = lex("// hi\nx")
    assert (tokens[0].type, tokens[0].lexeme) == (TokenType.LINE_COMMENT, "// hi")
    assert tokens[0].is_trivia


def test_block_comment_spans_lines():
    tokens, diagnostics = lex("/* a\nb */x")
    comment = tokens[0]
    assert comment.type == TokenType.BLOCK_COMMENT
    assert comment.lexeme == "/* a\nb */"
    assert not diagnostics.diagnostics


def test_whitespace_is_trivia():
    tokens, _ = lex("  \t\n ")
    assert [t.type for t in tokens] == [TokenType.WHITESPACE, TokenType.EOF]
    assert tokens[0].is_trivia


def test_preproc_is_single_token_per_line():
    tokens, _ = lex('#include "foo.h"\nint x;')
    assert (tokens[0].type, tokens[0].lexeme) == (TokenType.PREPROC, '#include "foo.h"')


def test_invalid_character():
    assert significant_lexemes("@") == [(TokenType.INVALID, "@")]


def test_eof_sentinel_position():
    tokens, _ = lex("int x;")
    eof = tokens[-1]
    assert eof.type == TokenType.EOF
    assert (eof.line, eof.column) == (1, 7)
    assert eof.start_offset == eof.end_offset == 6


# --- Maximal munch (R1.3) --------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["<=", ">=", "==", "!=", "->", "++", "--", "&&", "||"],
)
def test_maximal_munch_two_char_operators(text):
    assert significant_lexemes(text) == [(TokenType.OPERATOR, text)]


@pytest.mark.parametrize("text", ["+=", "-=", "*=", "/=", "%="])
def test_maximal_munch_compound_assignment(text):
    assert significant_lexemes(text) == [(TokenType.OPERATOR, text)]


def test_le_is_one_token_not_lt_then_eq():
    assert significant_lexemes("a<=b") == [
        (TokenType.IDENT, "a"),
        (TokenType.OPERATOR, "<="),
        (TokenType.IDENT, "b"),
    ]


def test_float_before_int_and_dot():
    assert significant_lexemes("1.5") == [(TokenType.FLOAT_LIT, "1.5")]
    assert significant_lexemes(".5") == [(TokenType.FLOAT_LIT, ".5")]


def test_dot_operator_not_swallowed_by_float_rule():
    assert significant_lexemes("a.b") == [
        (TokenType.IDENT, "a"),
        (TokenType.OPERATOR, "."),
        (TokenType.IDENT, "b"),
    ]


def test_hex_int_not_split_by_octal_rule():
    assert significant_lexemes("0xFF") == [(TokenType.INT_LIT, "0xFF")]


# --- Keyword priority (R1.4) ------------------------------------------------


def test_while_is_keyword_while_count_is_ident():
    assert significant_lexemes("while") == [(TokenType.KEYWORD, "while")]
    assert significant_lexemes("while_count") == [(TokenType.IDENT, "while_count")]


# --- Call vs bare variable: same lexeme, lexer treats both as IDENT --------
# (Distinguishing them is the *highlighter's* job in Stage 5, via the AST.)


def test_call_and_bare_identifier_lex_identically():
    call_tokens = significant_lexemes("factorial(n)")
    bare_tokens = significant_lexemes("factorial;")
    assert call_tokens[0] == bare_tokens[0] == (TokenType.IDENT, "factorial")


# --- Golden error cases -----------------------------------------------------


def test_golden_invalid_char_at_1_6_then_clean_line():
    """R1.5 — 'int x@ = 5;' -> INVALID('@') at 1:6; line 2 lexes clean."""
    tokens, diagnostics = lex("int x@ = 5;\nint y = 10;\n")
    invalid = next(t for t in tokens if t.type == TokenType.INVALID)
    assert invalid.lexeme == "@"
    assert (invalid.line, invalid.column) == (1, 6)

    assert len(diagnostics.errors) == 1
    assert "unrecognized character '@'" in diagnostics.errors[0].message

    line2 = [
        t for t in tokens if t.line == 2 and t.type not in (TokenType.WHITESPACE, TokenType.EOF)
    ]
    assert [t.type for t in line2] == [
        TokenType.KEYWORD,
        TokenType.IDENT,
        TokenType.OPERATOR,
        TokenType.INT_LIT,
        TokenType.DELIMITER,
    ]


def test_unterminated_string_recovers_at_next_line():
    """R1.6 — one diagnostic, string terminates at the newline, next line clean."""
    tokens, diagnostics = lex('char *s = "oops\nint y = 10;\n')
    assert len(diagnostics.errors) == 1
    assert "unterminated string literal" in diagnostics.errors[0].message

    unterminated = next(t for t in tokens if t.type == TokenType.STRING_LIT)
    assert unterminated.lexeme == '"oops'
    assert unterminated.line == 1

    line2 = [
        t for t in tokens if t.line == 2 and t.type not in (TokenType.WHITESPACE, TokenType.EOF)
    ]
    assert [t.type for t in line2] == [
        TokenType.KEYWORD,
        TokenType.IDENT,
        TokenType.OPERATOR,
        TokenType.INT_LIT,
        TokenType.DELIMITER,
    ]


def test_unterminated_block_comment_is_exactly_one_diagnostic():
    """R1.7 — consumed to EOF, exactly one diagnostic (not one per line)."""
    tokens, diagnostics = lex("/* start\nline two\nline three")
    assert len(diagnostics.errors) == 1
    assert "unterminated block comment" in diagnostics.errors[0].message

    comment = tokens[0]
    assert comment.type == TokenType.BLOCK_COMMENT
    assert comment.lexeme == "/* start\nline two\nline three"
    assert tokens[1].type == TokenType.EOF


def test_never_raises_on_random_bytes():
    """R9.5 robustness smoke test for the C lexer specifically."""
    garbage = "\x00\x01\x02�\ud800".encode("utf-8", errors="surrogatepass").decode(
        "utf-8", errors="replace"
    )
    tokens, diagnostics = lex(garbage)
    assert tokens[-1].type == TokenType.EOF
    assert diagnostics.diagnostics  # every byte here is unrecognized

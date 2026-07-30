"""R1.3, R1.5 — the generic LexerEngine, exercised with a toy rule set.

Deliberately not C: this is the language-agnostic engine, and the C rule
table is tested separately against the real C token categories.
"""

from clens.core.diagnostics import DiagnosticCollector
from clens.core.lexer_base import LexerEngine, TokenRule
from clens.core.source import SourceFile
from clens.core.token import TokenType

TOY_RULES = [
    TokenRule("CLOSED_BRACKET", TokenType.STRING_LIT, r"\[[^\]\n]*\]"),
    TokenRule(
        "UNCLOSED_BRACKET",
        TokenType.STRING_LIT,
        r"\[[^\]\n]*",
        diagnostic="unclosed bracket",
        diagnostic_code="TEST001-unclosed-bracket",
        diagnostic_span=1,
    ),
    TokenRule("NUMBER", TokenType.INT_LIT, r"[0-9]+"),
    TokenRule("WORD", TokenType.IDENT, r"[a-zA-Z]+"),
    TokenRule("WS", TokenType.WHITESPACE, r"[ \t\n]+"),
]

ORDERING_RULES = [
    TokenRule("AB", TokenType.OPERATOR, "ab"),
    TokenRule("A", TokenType.OPERATOR, "a"),
    TokenRule("B", TokenType.OPERATOR, "b"),
]


def tokenize(text: str, rules=TOY_RULES):
    source = SourceFile(text, "toy.txt")
    diagnostics = DiagnosticCollector()
    engine = LexerEngine(rules)
    return engine.tokenize(source, diagnostics), diagnostics


def test_empty_source_yields_only_eof():
    tokens, diagnostics = tokenize("")
    assert [t.type for t in tokens] == [TokenType.EOF]
    assert diagnostics.diagnostics == []


def test_basic_tokens_and_positions():
    tokens, diagnostics = tokenize("abc 123")
    types = [t.type for t in tokens]
    assert types == [
        TokenType.IDENT,
        TokenType.WHITESPACE,
        TokenType.INT_LIT,
        TokenType.EOF,
    ]
    assert not diagnostics.diagnostics
    ident = tokens[0]
    assert (ident.lexeme, ident.start_offset, ident.end_offset) == ("abc", 0, 3)
    number = tokens[2]
    assert (number.lexeme, number.start_offset, number.end_offset) == ("123", 4, 7)


def test_earlier_rule_wins_at_same_position():
    """R1.3 — alternation is leftmost-first: 'ab' must beat 'a' when listed first."""
    tokens, _ = tokenize("ab", rules=ORDERING_RULES)
    assert [t.lexeme for t in tokens if t.type != TokenType.EOF] == ["ab"]


def test_later_rule_order_splits_the_match():
    reordered = [ORDERING_RULES[1], ORDERING_RULES[2]]  # A, then B; no AB rule
    tokens, _ = tokenize("ab", rules=reordered)
    assert [t.lexeme for t in tokens if t.type != TokenType.EOF] == ["a", "b"]


def test_unrecognized_character_becomes_invalid_and_recovers():
    """R1.5 — one INVALID token, one diagnostic, scanning continues."""
    tokens, diagnostics = tokenize("a @ b")
    types_and_lexemes = [(t.type, t.lexeme) for t in tokens if t.type != TokenType.WHITESPACE]
    assert types_and_lexemes == [
        (TokenType.IDENT, "a"),
        (TokenType.INVALID, "@"),
        (TokenType.IDENT, "b"),
        (TokenType.EOF, ""),
    ]
    assert len(diagnostics.errors) == 1
    assert "unrecognized character '@'" in diagnostics.errors[0].message


def test_invalid_token_position_is_exact():
    tokens, diagnostics = tokenize("ab@cd")
    invalid = next(t for t in tokens if t.type == TokenType.INVALID)
    assert (invalid.line, invalid.column) == (1, 3)
    assert diagnostics.errors[0].start.offset == invalid.start_offset


def test_diagnostic_rule_emits_token_and_diagnostic():
    tokens, diagnostics = tokenize("[abc")
    bracket = next(t for t in tokens if t.type == TokenType.STRING_LIT)
    assert bracket.lexeme == "[abc"
    assert len(diagnostics.errors) == 1
    diag = diagnostics.errors[0]
    assert diag.message == "unclosed bracket"
    assert diag.code == "TEST001-unclosed-bracket"
    assert (diag.start.line, diag.start.column) == (1, 1)
    assert diag.length == 1  # underlines only the opening '[' per diagnostic_span


def test_closed_bracket_has_no_diagnostic():
    tokens, diagnostics = tokenize("[abc]")
    bracket = next(t for t in tokens if t.type == TokenType.STRING_LIT)
    assert bracket.lexeme == "[abc]"
    assert not diagnostics.diagnostics


def test_never_raises_on_unusual_unicode_input():
    tokens, diagnostics = tokenize("héllo ☃ wörld")
    assert tokens[-1].type == TokenType.EOF
    # The snowman and accented letters outside [a-zA-Z] all become INVALID
    # tokens rather than raising.
    assert any(t.type == TokenType.INVALID for t in tokens)
    assert diagnostics.errors


def test_zero_length_match_cannot_hang_the_scanner():
    """Rule 1 (never crash/hang): a pathological rule that can match empty
    must not stall the scanner in place; it recovers like an INVALID char.
    """
    zero_width_rules = [
        TokenRule("MAYBE_X", TokenType.OPERATOR, "x*"),
        TokenRule("WS", TokenType.WHITESPACE, r"[ \t\n]+"),
    ]
    tokens, diagnostics = tokenize("y", rules=zero_width_rules)
    assert [t.type for t in tokens] == [TokenType.INVALID, TokenType.EOF]
    assert diagnostics.errors

"""S5.2 — cursor context detection: MEMBER, GENERAL, ARGUMENT, and the
comment/string-literal suppression case. `::` (scope resolution) has no
lexeme in this C subset at all, so there is nothing to detect - N/A,
documented here rather than in a dedicated branch of the implementation.
"""

from clens.core.diagnostics import DiagnosticCollector
from clens.core.source import SourceFile
from clens.languages.c.lexer import tokenize
from clens.languages.c.parser import parse
from clens.languages.c.queries import completions_at
from clens.languages.c.semantic import analyze


def build_model(text: str):
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    tokens = tokenize(source, diagnostics)
    program = parse(source, diagnostics)
    return analyze(program, source, diagnostics, tokens=tokens)


def test_member_context_after_dot():
    text = "struct P { int x; };\nvoid f(void) { struct P p; p. }\n"
    model = build_model(text)
    offset = text.index("p.") + 2
    items = completions_at(model, offset)
    assert {i.label for i in items} == {"x"}


def test_member_context_after_arrow():
    text = "struct P { int x; };\nvoid f(void) { struct P *p; p-> }\n"
    model = build_model(text)
    offset = text.index("p->") + 3
    items = completions_at(model, offset)
    assert {i.label for i in items} == {"x"}


def test_general_context_at_statement_start():
    text = "int g;\nvoid f(void) { \n}\n"
    model = build_model(text)
    offset = text.rindex("{") + 1
    items = completions_at(model, offset)
    assert any(i.label == "g" for i in items)


def test_general_context_after_operator():
    text = "int g;\nvoid f(void) { int x; x = \n}\n"
    model = build_model(text)
    offset = text.index("x = ") + len("x = ")
    items = completions_at(model, offset)
    assert any(i.label == "g" for i in items)


def test_argument_context_inside_call_parens():
    text = "int add(int a, int b) { return a + b; }\nvoid f(void) { int total; add(total, \n}\n"
    model = build_model(text)
    offset = text.index("add(total, ") + len("add(total, ")
    items = completions_at(model, offset)
    assert any(i.label == "total" for i in items)


def test_no_completions_inside_a_line_comment():
    text = "int g;\nvoid f(void) { // g\n}\n"
    model = build_model(text)
    offset = text.index("// g") + 3  # inside the comment, just before 'g'
    assert completions_at(model, offset) == []


def test_no_completions_inside_a_block_comment():
    text = "int g;\nvoid f(void) { /* g */ }\n"
    model = build_model(text)
    offset = text.index("/* g */") + 3
    assert completions_at(model, offset) == []


def test_no_completions_inside_a_string_literal():
    text = 'int g;\nvoid f(void) { "g"; }\n'
    model = build_model(text)
    offset = text.index('"g"') + 2
    assert completions_at(model, offset) == []


def test_scope_resolution_operator_is_not_a_c_construct():
    """S5.2: '::' is N/A for C - the lexer has no such operator lexeme at
    all (see languages/c/token_rules.py's operator set), so there is no
    context branch to test; this is the one-line documentation the skill
    asks for.
    """
    from clens.languages.c.token_rules import _OPERATOR_LEXEMES

    assert "::" not in _OPERATOR_LEXEMES

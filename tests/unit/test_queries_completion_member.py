"""S5.3, S5.6 — member completion, including the course document's golden
example, against the seeded member_completion.c fixture. Works on an
incomplete parse (a bare `p.` is a syntax error) since context detection is
token-based, not AST-based.
"""

from pathlib import Path

from clens.core.diagnostics import DiagnosticCollector
from clens.core.source import SourceFile
from clens.languages.c.lexer import tokenize
from clens.languages.c.parser import parse
from clens.languages.c.queries import completions_at
from clens.languages.c.semantic import analyze

FIXTURE = Path(__file__).parent.parent / "fixtures" / "valid" / "member_completion.c"


def build_model(text: str):
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    tokens = tokenize(source, diagnostics)
    program = parse(source, diagnostics)
    return analyze(program, source, diagnostics, tokens=tokens)


def test_s5_6_golden_example_via_the_real_fixture():
    """Cursor immediately after the '.' in `p.x = 1;` - completion_member.txt
    pins this to exactly x and y, kind Field, detail int, in that order."""
    text = FIXTURE.read_text()
    model = build_model(text)
    offset = text.index("p.x = 1;") + len("p.")

    items = completions_at(model, offset)

    assert [(i.label, i.kind, i.detail) for i in items] == [
        ("x", "field", "int"),
        ("y", "field", "int"),
    ]


def test_arrow_completion_on_a_pointer_via_the_same_fixture():
    text = FIXTURE.read_text()
    model = build_model(text)
    offset = text.index("q->y = 2;") + len("q->")

    items = completions_at(model, offset)

    assert [(i.label, i.kind, i.detail) for i in items] == [
        ("x", "field", "int"),
        ("y", "field", "int"),
    ]


def test_member_completion_on_incomplete_parse():
    """`p.` with nothing after it is a syntax error - the parser cannot
    build a MemberExpr - and is the normal state while a user is
    mid-typing. This is the single most common real-world path."""
    text = "struct Point { int x; int y; };\nvoid f(void) { struct Point p; p. }\n"
    model = build_model(text)
    offset = text.index("p. ") + len("p.")

    items = completions_at(model, offset)

    assert [(i.label, i.kind, i.detail) for i in items] == [
        ("x", "field", "int"),
        ("y", "field", "int"),
    ]


def test_member_completion_filters_by_prefix():
    text = "struct Point { int x; int y; };\nvoid f(void) { struct Point p; p.x }\n"
    model = build_model(text)
    offset = text.index("p.x") + len("p.x")

    items = completions_at(model, offset)

    assert [i.label for i in items] == ["x"]


def test_member_completion_on_undeclared_base_is_empty():
    text = "void f(void) { missing.field; }\n"
    model = build_model(text)
    offset = text.index("missing.") + len("missing.")
    assert completions_at(model, offset) == []


def test_member_completion_on_non_struct_base_is_empty():
    text = "void f(void) { int x; x. }\n"
    model = build_model(text)
    offset = text.index("x. ") + len("x.")
    assert completions_at(model, offset) == []

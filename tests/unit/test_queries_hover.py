"""S7 — hover: signature, enclosing scope description, and doc comment,
for each symbol kind, against the seeded doc_comments.c fixture plus
targeted cases for scope description and member-field hover.
"""

from pathlib import Path

from clens.core.diagnostics import DiagnosticCollector
from clens.core.source import SourceFile
from clens.languages.c.lexer import tokenize
from clens.languages.c.parser import parse
from clens.languages.c.queries import hover_at
from clens.languages.c.semantic import analyze

FIXTURE = Path(__file__).parent.parent / "fixtures" / "valid" / "doc_comments.c"


def build_model(text: str):
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    tokens = tokenize(source, diagnostics)
    program = parse(source, diagnostics)
    return analyze(program, source, diagnostics, tokens=tokens)


def offset_of(text: str, needle: str) -> int:
    return text.index(needle) + 1  # land inside the identifier, not at its start


# --- doc comments (R1.8), against the real fixture --------------------------


def test_block_comment_doc_attaches_to_the_function():
    text = FIXTURE.read_text()
    model = build_model(text)
    info = hover_at(model, offset_of(text, "factorial(int n)"))
    assert info is not None
    assert info.signature == "(int) -> int"
    assert info.scope_description == "global scope"
    assert info.doc_comment == "Computes n factorial recursively."


def test_two_line_comments_are_joined_into_one_doc():
    text = FIXTURE.read_text()
    model = build_model(text)
    info = hover_at(model, offset_of(text, "total = 0"))
    assert info is not None
    assert info.doc_comment == "A running total.\nSpans two line comments, which hover must join."


def test_decorated_block_comment_strips_leading_asterisks():
    text = FIXTURE.read_text()
    model = build_model(text)
    info = hover_at(model, offset_of(text, "decorated(void)"))
    assert info is not None
    assert info.doc_comment == "Decorated block comment; leading asterisks must be stripped."


def test_declaration_with_no_preceding_comment_has_no_doc():
    text = "int plain = 1;\n"
    model = build_model(text)
    info = hover_at(model, offset_of(text, "plain"))
    assert info is not None
    assert info.doc_comment is None


def test_unrelated_earlier_comment_does_not_attach_across_a_blank_declaration():
    """A comment separated from the declaration by another declaration in
    between must not attach - only immediately preceding comments count."""
    text = "/* about g */\nint g;\nint h;\n"
    model = build_model(text)
    info = hover_at(model, offset_of(text, "h;"))
    assert info is not None
    assert info.doc_comment is None


# --- signature per symbol kind -----------------------------------------


def test_hover_over_a_variable_shows_its_type():
    text = "int count = 1;\n"
    model = build_model(text)
    info = hover_at(model, offset_of(text, "count"))
    assert info.signature == "int"


def test_hover_over_a_function_shows_its_full_signature():
    text = "int add(int a, int b) { return a + b; }\n"
    model = build_model(text)
    info = hover_at(model, offset_of(text, "add(int"))
    assert info.signature == "(int, int) -> int"


def test_hover_over_a_parameter_shows_its_type():
    text = "int add(int a, int b) { return a + b; }\n"
    model = build_model(text)
    info = hover_at(model, offset_of(text, "a, int b"))
    assert info.signature == "int"
    assert "add" in info.scope_description


def test_hover_over_a_struct_tag_shows_struct_type():
    text = "struct Point { int x; };\nvoid f(void) { struct Point p; }\n"
    model = build_model(text)
    info = hover_at(model, offset_of(text, "Point p"))
    assert info.signature == "struct Point"


def test_hover_over_a_struct_field_reference():
    text = "struct Point { int x; };\nvoid f(void) { struct Point p; p.x; }\n"
    model = build_model(text)
    offset = text.rindex("p.x") + 2  # land inside 'x', after the '.'
    info = hover_at(model, offset)
    assert info is not None
    assert info.signature == "int"
    assert info.scope_description == "struct 'Point'"


# --- scope description ---------------------------------------------------


def test_scope_description_for_a_local_variable_names_its_function():
    text = "void f(void) { int local; }\n"
    model = build_model(text)
    info = hover_at(model, offset_of(text, "local;"))
    assert info.scope_description == "function 'f'"


def test_scope_description_for_a_loop_variable():
    text = "void f(void) { for (int i = 0; i < 1; i++) { } }\n"
    model = build_model(text)
    info = hover_at(model, offset_of(text, "i = 0"))
    assert info.scope_description in ("for-loop scope", "function 'f'")


# --- no hover in the empty case ------------------------------------------


def test_hover_over_whitespace_returns_none():
    text = "int g;\n\n"
    model = build_model(text)
    assert hover_at(model, len(text) - 1) is None


def test_hover_over_an_undefined_name_returns_none():
    text = "void f(void) { missing; }\n"
    model = build_model(text)
    info = hover_at(model, offset_of(text, "missing"))
    assert info is None

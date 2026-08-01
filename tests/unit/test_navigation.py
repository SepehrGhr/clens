"""A4.1-A4.4 navigation: go-to-definition, find-all-references, and the
exact §6.3 JSON response shape.
"""

from __future__ import annotations

from clens.core.diagnostics import DiagnosticCollector
from clens.core.source import SourceFile
from clens.languages.c.lexer import tokenize
from clens.languages.c.parser import parse
from clens.languages.c.queries import (
    definition_info_to_dict,
    find_references,
    find_references_by_name,
    find_references_to_dict,
    goto_definition_at,
    references_at,
)
from clens.languages.c.semantic import analyze


def _model(text: str):
    source = SourceFile(text, "main.c")
    diagnostics = DiagnosticCollector()
    program = parse(source, diagnostics)
    tokens = tokenize(source, diagnostics)
    return analyze(program, source, diagnostics, tokens=tokens)


def _offset_of(text: str, needle: str, occurrence: int = 0) -> int:
    index = -1
    for _ in range(occurrence + 1):
        index = text.index(needle, index + 1)
    return index


# --- goto-definition ------------------------------------------------------


def test_goto_definition_for_a_function_call():
    text = "int factorial(int n) { return n; }\nint g(void) { return factorial(1); }\n"
    model = _model(text)
    offset = _offset_of(text, "factorial", occurrence=1)
    info = goto_definition_at(model, offset)
    assert info is not None
    assert info.symbol.name == "factorial"
    assert info.location.line == 1


def test_cursor_on_the_definition_itself_returns_that_definition():
    text = "int factorial(int n) { return n; }\n"
    model = _model(text)
    offset = _offset_of(text, "factorial")
    info = goto_definition_at(model, offset)
    assert info is not None
    assert info.symbol.name == "factorial"
    assert info.location.start_offset == info.symbol.definition_loc.start_offset


def test_goto_definition_for_a_parameter():
    text = "int f(int value) { return value; }\n"
    model = _model(text)
    offset = _offset_of(text, "value", occurrence=1)  # the `return value` use
    info = goto_definition_at(model, offset)
    assert info is not None
    assert info.symbol.name == "value"


def test_goto_definition_for_a_struct_field():
    text = "struct Point { int x; int y; };\nint f(struct Point p) { return p.x; }\n"
    model = _model(text)
    offset = _offset_of(text, ".x") + 1
    info = goto_definition_at(model, offset)
    assert info is not None
    assert info.symbol.name == "x"


def test_goto_definition_returns_none_for_a_keyword():
    text = "int f(void) { return 1; }\n"
    model = _model(text)
    offset = _offset_of(text, "return")
    assert goto_definition_at(model, offset) is None


# --- find-references --------------------------------------------------------


def test_find_references_includes_the_definition_site_flagged():
    text = (
        "int factorial(int n) { return n; }\nint g(void) { return factorial(1) + factorial(2); }\n"
    )
    model = _model(text)
    symbol = next(s for s in model.global_scope.symbols.values() if s.name == "factorial")
    refs = find_references(model, symbol)
    assert refs[0].is_definition is True
    non_def = [r for r in refs if not r.is_definition]
    assert len(non_def) == 2
    # Sorted by offset.
    assert [r.span.start_offset for r in refs] == sorted(r.span.start_offset for r in refs)


def test_references_at_cursor_position():
    text = "int factorial(int n) { return n; }\nint g(void) { return factorial(1); }\n"
    model = _model(text)
    offset = _offset_of(text, "factorial")
    refs = references_at(model, offset)
    assert refs is not None
    assert any(not r.is_definition for r in refs)


def test_find_references_by_name_lists_every_ambiguous_match():
    text = "int n;\nint f(int n) { return n; }\n"
    model = _model(text)
    results = find_references_by_name(model, "n")
    assert len(results) == 2  # the global `n` and the parameter `n`


# --- JSON shape (A4.4) -------------------------------------------------------


def test_definition_info_to_dict_shape():
    text = "int factorial(int n) { return n; }\n"
    model = _model(text)
    offset = _offset_of(text, "factorial")
    info = goto_definition_at(model, offset)
    payload = definition_info_to_dict(model, info)
    assert payload == {
        "symbol": "factorial",
        "kind": "function",
        "type": "(int) -> int",
        "defined_at": {"file": "main.c", "line": 1, "col": 5},
    }


def test_find_references_to_dict_matches_course_document_shape_exactly():
    """§6.3: the key is `col`, not `column`; `references` does not repeat
    the definition site since `defined_at` already carries it."""
    text = (
        "int factorial(int n) { return n; }\nint g(void) { return factorial(1) + factorial(2); }\n"
    )
    model = _model(text)
    symbol = next(s for s in model.global_scope.symbols.values() if s.name == "factorial")
    refs = find_references(model, symbol)
    payload = find_references_to_dict(model, symbol, refs)
    assert set(payload) == {"symbol", "kind", "type", "defined_at", "references"}
    assert payload["symbol"] == "factorial"
    assert payload["kind"] == "function"
    assert payload["type"] == "(int) -> int"
    assert set(payload["defined_at"]) == {"file", "line", "col"}
    assert payload["defined_at"] == {"file": "main.c", "line": 1, "col": 5}
    assert len(payload["references"]) == 2
    for entry in payload["references"]:
        assert set(entry) == {"file", "line", "col"}

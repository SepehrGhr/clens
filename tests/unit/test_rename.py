"""A5.1-A5.3 safe rename: scope-aware, by symbol identity -- never text
substitution. `.agents/skills/refactoring/SKILL.md`.
"""

from __future__ import annotations

from pathlib import Path

from clens.core.diagnostics import DiagnosticCollector
from clens.core.source import SourceFile
from clens.languages.c.lexer import tokenize
from clens.languages.c.parser import parse
from clens.languages.c.queries import goto_definition_at
from clens.languages.c.rename import rename_symbol, rename_symbol_at
from clens.languages.c.semantic import analyze

FIXTURE = (
    Path(__file__).parent.parent.parent / ".agents" / "fixtures" / "analysis" / "rename_target.c"
)


def _model_and_source(text: str):
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    program = parse(source, diagnostics)
    tokens = tokenize(source, diagnostics)
    model = analyze(program, source, diagnostics, tokens=tokens)
    return model, source


def _offset_of(text: str, needle: str, occurrence: int = 0) -> int:
    index = -1
    for _ in range(occurrence + 1):
        index = text.index(needle, index + 1)
    return index


def _factorial_n_symbol(model, text: str):
    # `n <= 1` inside factorial uniquely identifies factorial's own `n`.
    offset = _offset_of(text, "n <= 1")
    return goto_definition_at(model, offset).symbol


# --- A5.3 golden test ---------------------------------------------------------


def test_golden_rename_n_to_number_leaves_other_functions_untouched():
    text = FIXTURE.read_text()
    model, source = _model_and_source(text)
    symbol = _factorial_n_symbol(model, text)
    assert symbol.name == "n"

    result = rename_symbol(model, source, symbol, "number")
    assert result.ok, result.error
    assert result.new_text is not None

    old_lines = text.splitlines()
    new_lines = result.new_text.splitlines()
    assert len(old_lines) == len(new_lines)

    factorial_start = next(i for i, line in enumerate(old_lines) if "int factorial" in line)
    factorial_end = next(
        i for i, line in enumerate(old_lines) if i > factorial_start and line == "}"
    )

    for i, (old_line, new_line) in enumerate(zip(old_lines, new_lines, strict=True)):
        if factorial_start <= i <= factorial_end:
            continue
        # Every other function's `n` (other(), shadow_demo()) must be
        # byte-identical -- the whole point of the contrast fixture.
        assert old_line == new_line, f"line {i + 1} changed outside factorial: {old_line!r}"

    factorial_new = "\n".join(new_lines[factorial_start : factorial_end + 1])
    assert "int factorial(int number)" in factorial_new
    assert "if (number <= 1)" in factorial_new
    assert "number * factorial(number - 1)" in factorial_new
    assert "int result" in factorial_new  # untouched local, not renamed


def test_golden_rename_produces_a_unified_diff():
    text = FIXTURE.read_text()
    model, source = _model_and_source(text)
    symbol = _factorial_n_symbol(model, text)
    result = rename_symbol(model, source, symbol, "number")
    assert result.ok
    assert "--- a.c" in result.diff
    assert "+++ a.c" in result.diff
    assert "-int factorial(int n) {" in result.diff
    assert "+int factorial(int number) {" in result.diff


# --- Refusal cases -------------------------------------------------------------


def test_rename_to_existing_name_in_same_scope_is_refused():
    text = "int f(int n) { int existing = 1; return n + existing; }\n"
    model, source = _model_and_source(text)
    symbol = goto_definition_at(model, _offset_of(text, "n)")).symbol
    result = rename_symbol(model, source, symbol, "existing")
    assert not result.ok
    assert "existing" in result.error


def test_rename_that_would_shadow_a_global_is_refused():
    text = FIXTURE.read_text()
    model, source = _model_and_source(text)
    symbol = _factorial_n_symbol(model, text)
    result = rename_symbol(model, source, symbol, "g")
    assert not result.ok
    assert "shadow" in result.error


def test_rename_that_would_be_shadowed_by_a_nested_local_is_refused():
    """Renaming factorial's `n` to `result` collides with the block-scoped
    local `result` already declared inside factorial -- our own renamed
    references would resolve to that inner declaration instead of us."""
    text = FIXTURE.read_text()
    model, source = _model_and_source(text)
    symbol = _factorial_n_symbol(model, text)
    result = rename_symbol(model, source, symbol, "result")
    assert not result.ok


def test_rename_to_its_own_current_name_is_refused():
    text = "int f(int n) { return n; }\n"
    model, source = _model_and_source(text)
    symbol = goto_definition_at(model, _offset_of(text, "n)")).symbol
    result = rename_symbol(model, source, symbol, "n")
    assert not result.ok


# --- Renaming each kind of symbol ----------------------------------------------


def test_rename_a_parameter():
    text = "int f(int n) { return n; }\n"
    model, source = _model_and_source(text)
    symbol = goto_definition_at(model, _offset_of(text, "n)")).symbol
    result = rename_symbol(model, source, symbol, "count")
    assert result.ok
    assert result.new_text == "int f(int count) { return count; }\n"


def test_rename_a_global_variable():
    text = "int g = 0;\nint f(void) { return g; }\n"
    model, source = _model_and_source(text)
    symbol = goto_definition_at(model, _offset_of(text, "g =")).symbol
    result = rename_symbol(model, source, symbol, "counter")
    assert result.ok
    assert result.new_text == "int counter = 0;\nint f(void) { return counter; }\n"


def test_rename_a_function():
    text = "int f(void) { return 1; }\nint g(void) { return f(); }\n"
    model, source = _model_and_source(text)
    symbol = goto_definition_at(model, _offset_of(text, "f(void)")).symbol
    result = rename_symbol(model, source, symbol, "helper")
    assert result.ok
    assert result.new_text == "int helper(void) { return 1; }\nint g(void) { return helper(); }\n"


def test_rename_a_struct_field():
    text = "struct Point { int x; int y; };\nint f(struct Point p) { return p.x; }\n"
    model, source = _model_and_source(text)
    offset = _offset_of(text, "x;")
    symbol = goto_definition_at(model, offset).symbol
    result = rename_symbol(model, source, symbol, "value")
    assert result.ok
    assert "struct Point { int value; int y; };" in result.new_text
    assert "return p.value;" in result.new_text


# --- Cursor-driven entry point --------------------------------------------------


def test_rename_symbol_at_resolves_the_cursor():
    text = "int f(int n) { return n; }\n"
    model, source = _model_and_source(text)
    result = rename_symbol_at(model, source, _offset_of(text, "n)"), "count")
    assert result.ok
    assert result.new_text == "int f(int count) { return count; }\n"


def test_rename_symbol_at_no_symbol_is_refused_not_crashed():
    text = "int f(void) { return 1; }\n"
    model, source = _model_and_source(text)
    result = rename_symbol_at(model, source, _offset_of(text, "return"), "whatever")
    assert not result.ok

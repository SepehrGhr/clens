"""S6.3 — the crude use-before-initialization (row 12, warning) and
unused-variable (row 13, info) checks, against the seeded
init_and_unused.c fixture and targeted unit cases.
"""

from pathlib import Path

from clens.core.diagnostics import DiagnosticCollector, SemanticCode, Severity
from clens.core.source import SourceFile
from clens.languages.c.parser import parse
from clens.languages.c.semantic import analyze

FIXTURE = Path(__file__).parent.parent / "fixtures" / "semantic-errors" / "init_and_unused.c"


def analyze_text(text: str, filename: str = "a.c"):
    source = SourceFile(text, filename)
    diagnostics = DiagnosticCollector()
    program = parse(source, diagnostics)
    model = analyze(program, source, diagnostics)
    return model, diagnostics


def test_init_and_unused_fixture_exactly_two_diagnostics():
    text = FIXTURE.read_text()
    _, diagnostics = analyze_text(text, "init_and_unused.c")
    ordered = diagnostics.sorted()
    assert len(ordered) == 2
    assert [d.severity for d in ordered] == [Severity.INFO, Severity.WARNING]
    assert ordered[0].code == SemanticCode.UNUSED_VARIABLE
    assert ordered[1].code == SemanticCode.USE_BEFORE_INITIALIZATION


def test_unused_variable_message_names_it():
    text = FIXTURE.read_text()
    _, diagnostics = analyze_text(text, "init_and_unused.c")
    unused = next(d for d in diagnostics.sorted() if d.code == SemanticCode.UNUSED_VARIABLE)
    assert "never_read" in unused.message


def test_use_before_init_message_names_it():
    text = FIXTURE.read_text()
    _, diagnostics = analyze_text(text, "init_and_unused.c")
    warning = next(
        d for d in diagnostics.sorted() if d.code == SemanticCode.USE_BEFORE_INITIALIZATION
    )
    assert "uninitialized" in warning.message


def test_parameter_never_read_is_not_flagged_unused():
    """flag is a parameter and is never read in the fixture; unused
    parameters are normal in C and must not be flagged (row 13's explicit
    exclusion)."""
    text = FIXTURE.read_text()
    _, diagnostics = analyze_text(text, "init_and_unused.c")
    assert not any("flag" in d.message for d in diagnostics.diagnostics)


def test_written_then_read_is_clean():
    text = "int f(void) { int x; x = 1; return x; }\n"
    _, diagnostics = analyze_text(text)
    assert not diagnostics.diagnostics


def test_initialized_at_declaration_then_read_is_clean():
    text = "int f(void) { int x = 1; return x; }\n"
    _, diagnostics = analyze_text(text)
    assert not diagnostics.diagnostics


def test_read_before_any_write_in_straight_line_code_warns():
    """Even when the variable is eventually written later, a read that
    comes first in source order is a genuine use-before-init - list order,
    not final is_initialized state, is what this must catch."""
    text = "int f(void) { int x; int y = x; x = 1; return y; }\n"
    _, diagnostics = analyze_text(text)
    assert len(diagnostics.diagnostics) == 1
    assert diagnostics.diagnostics[0].code == SemanticCode.USE_BEFORE_INITIALIZATION


def test_unused_global_is_not_flagged():
    text = "int unused_global;\nint f(void) { return 0; }\n"
    _, diagnostics = analyze_text(text)
    assert not diagnostics.diagnostics


def test_unused_parameter_alone_is_not_flagged():
    text = "int f(int unused_param) { return 0; }\n"
    _, diagnostics = analyze_text(text)
    assert not diagnostics.diagnostics


def test_struct_field_is_never_flagged_unused_even_though_never_read():
    """`x` (a FIELD, not a VARIABLE) is never read anywhere; only `p`
    itself (a genuinely unused local VARIABLE) may be flagged."""
    text = "struct P { int x; };\nvoid f(void) { struct P p; }\n"
    _, diagnostics = analyze_text(text)
    assert all("x" not in d.message for d in diagnostics.diagnostics)
    assert all(d.code == SemanticCode.UNUSED_VARIABLE for d in diagnostics.diagnostics)
    assert any("p" in d.message for d in diagnostics.diagnostics)

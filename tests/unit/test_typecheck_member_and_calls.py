"""P4.2, P4.3 — MemberExpr and CallExpr type checking, against the seeded
member_errors.c and call_errors.c fixtures.
"""

from pathlib import Path

from clens.core.diagnostics import DiagnosticCollector, SemanticCode, Severity
from clens.core.source import SourceFile
from clens.languages.c.parser import parse
from clens.languages.c.semantic import analyze

FIXTURES = Path(__file__).parent.parent / "fixtures" / "semantic-errors"


def analyze_text(text: str, filename: str = "a.c"):
    source = SourceFile(text, filename)
    diagnostics = DiagnosticCollector()
    program = parse(source, diagnostics)
    model = analyze(program, source, diagnostics)
    return model, diagnostics


def analyze_fixture(name: str):
    return analyze_text((FIXTURES / name).read_text(), name)


# --- MemberExpr (P4.2) -------------------------------------------------


def test_member_errors_fixture_exactly_three_errors():
    _, diagnostics = analyze_fixture("member_errors.c")
    assert len(diagnostics.diagnostics) == 3
    assert all(d.severity is Severity.ERROR for d in diagnostics.diagnostics)
    assert all(d.code == SemanticCode.BAD_MEMBER_ACCESS for d in diagnostics.diagnostics)


def test_arrow_on_non_pointer_message():
    _, diagnostics = analyze_fixture("member_errors.c")
    assert any("arrow on non-pointer" in d.message for d in diagnostics.diagnostics)


def test_dot_on_pointer_message():
    _, diagnostics = analyze_fixture("member_errors.c")
    assert any("member access on pointer" in d.message for d in diagnostics.diagnostics)


def test_unknown_field_names_the_struct():
    _, diagnostics = analyze_fixture("member_errors.c")
    messages = [d.message for d in diagnostics.diagnostics]
    assert any("has no field 'z'" in m and "Point" in m for m in messages)


def test_successful_member_access_has_no_diagnostics():
    _, diagnostics = analyze_text(
        "struct P { int x; };\nvoid f(void) { struct P p; struct P *q; p.x; q->x; }\n"
    )
    assert not diagnostics.diagnostics


# --- CallExpr (P4.3) -----------------------------------------------------


def test_call_errors_fixture_exactly_three_errors():
    _, diagnostics = analyze_fixture("call_errors.c")
    assert len(diagnostics.diagnostics) == 3


def test_wrong_arity_does_not_also_check_argument_types():
    """add(1) and add(1, 2, 3) both have the wrong arity; each is exactly
    one diagnostic, not also a type-mismatch report."""
    _, diagnostics = analyze_fixture("call_errors.c")
    arity_errors = [
        d for d in diagnostics.diagnostics if d.code == SemanticCode.ARGUMENT_COUNT_MISMATCH
    ]
    assert len(arity_errors) == 2
    assert all(d.severity is Severity.ERROR for d in arity_errors)
    assert "expected 2 argument(s), got 1" in arity_errors[0].message
    assert "expected 2 argument(s), got 3" in arity_errors[1].message


def test_per_argument_type_mismatch():
    _, diagnostics = analyze_fixture("call_errors.c")
    type_errors = [d for d in diagnostics.diagnostics if d.code == SemanticCode.CALL_TYPE_MISMATCH]
    assert len(type_errors) == 1
    assert "argument 2" in type_errors[0].message


def test_calling_a_non_function_is_an_error():
    _, diagnostics = analyze_text("int g;\nvoid f(void) { g(); }\n")
    assert len(diagnostics.diagnostics) == 1
    d = diagnostics.diagnostics[0]
    assert d.code == SemanticCode.NOT_CALLABLE
    assert d.severity is Severity.ERROR
    assert "'g' is not a function" in d.message


def test_calling_an_undefined_function_reports_undefined_not_not_callable():
    _, diagnostics = analyze_text("void f(void) { missing_func(1, 2); }\n")
    assert len(diagnostics.diagnostics) == 1
    assert diagnostics.diagnostics[0].code == SemanticCode.UNDEFINED_SYMBOL


def test_clean_call_has_no_diagnostics():
    text = "int add(int a, int b) { return a + b; }\nvoid f(void) { add(1, 2); }\n"
    _, diagnostics = analyze_text(text)
    assert not diagnostics.diagnostics

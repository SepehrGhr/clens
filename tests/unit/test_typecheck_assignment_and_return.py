"""P4.4, P4.5 — assignment checking (narrowing warning / incompatible
error, for both VarDecl initializers and AssignExpr) and return checking
against the enclosing function, using the seeded return_errors.c fixture.
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


# --- assignment (P4.4) --------------------------------------------------


def test_var_decl_narrowing_is_a_warning():
    _, diagnostics = analyze_text("int x = 3.14;\n")
    assert len(diagnostics.diagnostics) == 1
    d = diagnostics.diagnostics[0]
    assert d.severity is Severity.WARNING
    assert d.code == SemanticCode.NARROWING_CONVERSION
    assert "conversion from 'double' to 'int' may lose precision" in d.message


def test_var_decl_incompatible_is_an_error():
    _, diagnostics = analyze_text("char *s = 42;\n")
    assert len(diagnostics.diagnostics) == 1
    d = diagnostics.diagnostics[0]
    assert d.severity is Severity.ERROR
    assert d.code == SemanticCode.ASSIGNMENT_TYPE_MISMATCH
    assert "cannot assign 'int' to 'char*'" in d.message


def test_var_decl_widening_is_clean():
    _, diagnostics = analyze_text("double x = 1;\n")
    assert not diagnostics.diagnostics


def test_assign_expr_narrowing_is_a_warning():
    _, diagnostics = analyze_text("void f(void) { int x; x = 3.14; x; }\n")
    assert len(diagnostics.diagnostics) == 1
    assert diagnostics.diagnostics[0].code == SemanticCode.NARROWING_CONVERSION


def test_assign_expr_incompatible_is_an_error():
    _, diagnostics = analyze_text("void f(void) { char *s; s = 42; s; }\n")
    assert len(diagnostics.diagnostics) == 1
    assert diagnostics.diagnostics[0].code == SemanticCode.ASSIGNMENT_TYPE_MISMATCH


def test_int_to_pointer_incompatible_symmetric_direction_too():
    _, diagnostics = analyze_text("void f(void) { int *p; int n; n = p; n; }\n")
    assert len(diagnostics.diagnostics) == 1
    assert diagnostics.diagnostics[0].code == SemanticCode.ASSIGNMENT_TYPE_MISMATCH


def test_assignment_to_undefined_target_is_not_a_cascade():
    """The target being undefined already produced one diagnostic in
    Stage 3; the assignment check itself must not add a second one."""
    _, diagnostics = analyze_text("void f(void) { missing = 3.14; }\n")
    assert len(diagnostics.diagnostics) == 1
    assert diagnostics.diagnostics[0].code == SemanticCode.UNDEFINED_SYMBOL


# --- return checking (P4.5) ----------------------------------------------


def test_return_errors_fixture_exactly_three_errors():
    text = (FIXTURES / "return_errors.c").read_text()
    _, diagnostics = analyze_text(text, "return_errors.c")
    assert len(diagnostics.diagnostics) == 3
    assert all(d.severity is Severity.ERROR for d in diagnostics.diagnostics)
    assert all(d.code == SemanticCode.RETURN_TYPE_MISMATCH for d in diagnostics.diagnostics)


def test_void_function_returning_a_value_is_an_error():
    _, diagnostics = analyze_text("void f(void) { return 5; }\n")
    assert len(diagnostics.diagnostics) == 1
    assert "void function should not return a value" in diagnostics.diagnostics[0].message


def test_non_void_function_with_bare_return_is_an_error():
    _, diagnostics = analyze_text("int f(void) { return; }\n")
    assert len(diagnostics.diagnostics) == 1
    assert "non-void function must return a value" in diagnostics.diagnostics[0].message


def test_wrong_return_type_is_an_error():
    _, diagnostics = analyze_text('int f(void) { return "text"; }\n')
    assert len(diagnostics.diagnostics) == 1
    message = diagnostics.diagnostics[0].message
    assert "cannot return 'char*' from a function returning 'int'" in message


def test_narrowing_return_is_a_warning_not_an_error():
    _, diagnostics = analyze_text("int f(void) { return 3.14; }\n")
    assert len(diagnostics.diagnostics) == 1
    assert diagnostics.diagnostics[0].severity is Severity.WARNING
    assert diagnostics.diagnostics[0].code == SemanticCode.NARROWING_CONVERSION


def test_clean_return_has_no_diagnostics():
    _, diagnostics = analyze_text("int f(void) { return 1; }\n")
    assert not diagnostics.diagnostics

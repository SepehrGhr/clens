"""S6.1 rows 5, 8, 11 — undefined symbol, duplicate declaration, and
shadowing, audited against the seeded semantic-errors fixtures with exact
codes and severities.
"""

from pathlib import Path

from clens.core.diagnostics import DiagnosticCollector, SemanticCode, Severity
from clens.core.source import SourceFile
from clens.languages.c.parser import parse
from clens.languages.c.resolver import resolve

FIXTURES = Path(__file__).parent.parent / "fixtures" / "semantic-errors"


def analyze(text: str, filename: str = "a.c"):
    source = SourceFile(text, filename)
    diagnostics = DiagnosticCollector()
    program = parse(source, diagnostics)
    resolve(program, source, diagnostics)
    return diagnostics


def analyze_fixture(name: str):
    return analyze((FIXTURES / name).read_text())


def test_row_5_undefined_symbol():
    """No-cascade (S9.2): 'counter' undefined, used five times, one error."""
    diagnostics = analyze_fixture("undefined_symbol.c")
    assert len(diagnostics.diagnostics) == 1
    d = diagnostics.diagnostics[0]
    assert d.severity is Severity.ERROR
    assert d.code == SemanticCode.UNDEFINED_SYMBOL
    assert "counter" in d.message


def test_row_8_duplicate_declaration():
    """int a = 1, a = 2; and int b = 0; int b = 1; both fire; the inner-
    scope redeclaration of b is shadowing (row 11), not a duplicate."""
    diagnostics = analyze_fixture("duplicate_declaration.c")
    duplicates = [
        d for d in diagnostics.diagnostics if d.code == SemanticCode.DUPLICATE_DECLARATION
    ]
    shadows = [d for d in diagnostics.diagnostics if d.code == SemanticCode.SHADOWED_DECLARATION]
    assert len(duplicates) == 2
    assert all(d.severity is Severity.ERROR for d in duplicates)
    assert len(shadows) == 1
    assert shadows[0].severity is Severity.WARNING


def test_row_11_shadowing_at_three_depths_minus_the_excluded_case():
    """x shadowed at: parameter-vs-global (excluded, no warning), block-vs-
    parameter, and nested-block-vs-block (2 warnings total)."""
    diagnostics = analyze_fixture("shadowing.c")
    shadows = [d for d in diagnostics.diagnostics if d.code == SemanticCode.SHADOWED_DECLARATION]
    assert len(shadows) == 2
    assert all(d.severity is Severity.WARNING for d in shadows)
    assert all("shadows an outer declaration at" in d.message for d in shadows)
    # No diagnostic at all for the parameter shadowing the global.
    assert not any(d.code == SemanticCode.DUPLICATE_DECLARATION for d in diagnostics.diagnostics)

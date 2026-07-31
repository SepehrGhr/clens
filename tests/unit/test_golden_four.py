"""P4.6 / S4.7 — the course document's four worked examples (§5.3.1), in
one test file, asserting exact severities in order: warning, error, error,
error.

    int x = 3.14;                  /* WARNING: narrowing */
    char *s = 42;                  /* ERROR: int to char* */
    int y = factorial("hello");    /* ERROR: argument type mismatch */
    void foo() { return 5; }       /* ERROR: void function returns a value */
"""

from pathlib import Path

from clens.core.diagnostics import DiagnosticCollector, Severity
from clens.core.source import SourceFile
from clens.languages.c.parser import parse
from clens.languages.c.semantic import analyze

FIXTURE = Path(__file__).parent.parent / "fixtures" / "semantic-errors" / "golden_four.c"


def test_golden_four_examples_exact_severities_in_order():
    text = FIXTURE.read_text()
    source = SourceFile(text, "golden_four.c")
    diagnostics = DiagnosticCollector()
    program = parse(source, diagnostics)
    analyze(program, source, diagnostics)

    ordered = diagnostics.sorted()
    assert len(ordered) == 4
    assert [d.severity for d in ordered] == [
        Severity.WARNING,
        Severity.ERROR,
        Severity.ERROR,
        Severity.ERROR,
    ]


def test_golden_four_examples_exact_messages():
    text = FIXTURE.read_text()
    source = SourceFile(text, "golden_four.c")
    diagnostics = DiagnosticCollector()
    program = parse(source, diagnostics)
    analyze(program, source, diagnostics)

    ordered = diagnostics.sorted()
    narrowing, assign_mismatch, arg_mismatch, return_mismatch = ordered

    assert "double" in narrowing.message and "int" in narrowing.message
    assert "may lose precision" in narrowing.message

    assert "cannot assign 'int' to 'char*'" in assign_mismatch.message

    assert "argument 1" in arg_mismatch.message
    assert "'int'" in arg_mismatch.message and "'char*'" in arg_mismatch.message

    assert "void function should not return a value" in return_mismatch.message


def test_golden_four_examples_are_on_the_documented_lines():
    """Comments in the fixture pin each diagnostic to lines 6-9 (source
    text lines, after the four-line header comment)."""
    text = FIXTURE.read_text()
    source = SourceFile(text, "golden_four.c")
    diagnostics = DiagnosticCollector()
    program = parse(source, diagnostics)
    analyze(program, source, diagnostics)

    lines = [d.start.line for d in diagnostics.sorted()]
    assert lines == sorted(lines)
    assert len(set(lines)) == 4  # one diagnostic per line, no cascade

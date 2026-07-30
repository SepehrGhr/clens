"""R3.3, R3.4 — panic-mode recovery, including both golden cases from the
course document, and the real fixture files from .agents/fixtures/syntax-errors.
"""

from pathlib import Path

from clens.core.diagnostics import DiagnosticCollector
from clens.core.source import SourceFile
from clens.languages.c import ast_nodes as ast
from clens.languages.c.parser import parse

FIXTURES = Path(__file__).parent.parent / "fixtures" / "syntax-errors"


def parse_program(text: str) -> tuple[ast.Program, DiagnosticCollector]:
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    return parse(source, diagnostics), diagnostics


def parse_fixture(name: str) -> tuple[ast.Program, DiagnosticCollector]:
    return parse_program((FIXTURES / name).read_text())


def test_golden_missing_expression_recovers_and_continues():
    """R3.3/R3.4 golden case: 'int x = ;' errors at 1:9, 'int y = 42;'
    still parses.
    """
    program, diagnostics = parse_fixture("missing_expression.c")

    assert len(diagnostics.errors) == 1
    error = diagnostics.errors[0]
    assert error.message == "expected expression, got ';'"
    assert (error.start.line, error.start.column) == (1, 9)

    names = [d.name for d in program.declarations if isinstance(d, ast.VarDecl)]
    assert "y" in names
    y = next(d for d in program.declarations if getattr(d, "name", None) == "y")
    assert y.init.value == 42


def test_golden_missing_paren_recovers_block():
    """R3.3/R3.4 golden case: 'if (y > 0 {' -- missing ')' before '{' is
    reported, and the block's 'return y;' still parses.
    """
    program, diagnostics = parse_fixture("missing_paren.c")

    assert any("expected ')'" in d.message for d in diagnostics.errors)

    func = next(d for d in program.declarations if isinstance(d, ast.FuncDecl) and d.name == "f")
    assert any(
        isinstance(stmt, ast.ReturnStmt)
        and isinstance(stmt.value, ast.Identifier)
        and stmt.value.name == "y"
        for stmt in func.body.body
    ), func.body.body


def test_unbalanced_braces_does_not_crash():
    program, diagnostics = parse_fixture("unbalanced_braces.c")
    assert diagnostics.has_errors
    assert isinstance(program, ast.Program)  # parse() returned, didn't raise


def test_unsupported_typedef_reports_and_keeps_going():
    program, diagnostics = parse_fixture("unsupported_typedef.c")

    assert any(
        "unsupported construct" in d.message and "typedef" in d.message for d in diagnostics.errors
    )
    func = next(
        (d for d in program.declarations if isinstance(d, ast.FuncDecl) and d.name == "f"), None
    )
    assert func is not None, "function after the unsupported typedef must still parse"
    assert isinstance(func.body, ast.Block)
    assert any(isinstance(s, ast.ReturnStmt) for s in func.body.body)


def test_recovery_never_raises_and_always_terminates():
    """R9.5 — every syntax-error fixture: parse() returns, never raises."""
    for path in FIXTURES.glob("*.c"):
        source = SourceFile(path.read_text(), path.name)
        diagnostics = DiagnosticCollector()
        program = parse(source, diagnostics)  # must not raise
        assert isinstance(program, ast.Program)

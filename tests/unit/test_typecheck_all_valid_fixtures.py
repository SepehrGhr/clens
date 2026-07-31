"""S4.1 / type-system skill's definition of done: "Every Expr node in every
valid fixture has a non-None type_annotation." A sweep across every real
fixture, not just the individual snippets the other type-checking tests
build by hand.
"""

from pathlib import Path

import pytest

from clens.core.ast_nodes import Expr
from clens.core.diagnostics import DiagnosticCollector
from clens.core.source import SourceFile
from clens.core.visitor import walk
from clens.languages.c.parser import parse
from clens.languages.c.semantic import analyze

FIXTURES_VALID = Path(__file__).parent.parent / "fixtures" / "valid"
FIXTURE_FILES = sorted(FIXTURES_VALID.glob("*.c"))


@pytest.mark.parametrize("path", FIXTURE_FILES, ids=lambda p: p.name)
def test_every_expr_has_a_type_annotation(path: Path):
    source = SourceFile(path.read_text(), path.name)
    diagnostics = DiagnosticCollector()
    program = parse(source, diagnostics)
    model = analyze(program, source, diagnostics)

    exprs = [node for node in walk(model.program) if isinstance(node, Expr)]
    untyped = [e for e in exprs if e.type_annotation is None]

    assert untyped == [], (
        f"{len(untyped)} Expr node(s) in {path.name} never got a "
        f"type_annotation: {[type(e).__name__ for e in untyped]}"
    )


def test_at_least_one_fixture_actually_has_expressions():
    """Guard against the parametrized test above silently passing vacuously
    if FIXTURE_FILES or the fixtures themselves were ever empty."""
    assert len(FIXTURE_FILES) >= 10

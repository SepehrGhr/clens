"""A6 dead-code detection, against `.agents/fixtures/analysis/dead_code.c`
(the course document's section 6.5 example, adapted): all five categories
in one file, each firing exactly once.
"""

from __future__ import annotations

from pathlib import Path

from clens.core.diagnostics import DiagnosticCollector
from clens.core.source import SourceFile
from clens.languages.c.dead_code import find_dead_code
from clens.languages.c.parser import parse
from clens.languages.c.program_analysis import analyze_program
from clens.languages.c.semantic import analyze

FIXTURE = Path(__file__).parent.parent.parent / ".agents" / "fixtures" / "analysis" / "dead_code.c"


def _report_for(text: str):
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    program = parse(source, diagnostics)
    model = analyze(program, source, diagnostics)
    analysis = analyze_program(model)
    return find_dead_code(analysis)


def _fixture_report():
    return _report_for(FIXTURE.read_text())


def test_unreachable_function_fires_exactly_once():
    report = _fixture_report()
    assert report.unreachable_functions == ["helper"]


def test_unreachable_block_fires_exactly_once():
    report = _fixture_report()
    assert len(report.unreachable_blocks) == 1
    assert report.unreachable_blocks[0].function == "foo"


def test_post_jump_statements_fire_for_the_trailing_code_in_foo():
    report = _fixture_report()
    assert [p.function for p in report.post_jump_statements] == ["foo", "foo"]
    texts = {p.text for p in report.post_jump_statements}
    assert texts == {"int x = 0", "return x"}


def test_unused_variable_fires_exactly_once():
    report = _fixture_report()
    assert len(report.unused_variables) == 1
    assert report.unused_variables[0].symbol.name == "z"
    assert report.unused_variables[0].function == "bar"


def test_dead_assignment_fires_exactly_once():
    report = _fixture_report()
    assert len(report.dead_assignments) == 1
    assert report.dead_assignments[0].symbol.name == "y"
    assert report.dead_assignments[0].function == "bar"


def test_main_and_bar_are_not_flagged_dead_functions():
    report = _fixture_report()
    assert "main" not in report.unreachable_functions
    assert "bar" not in report.unreachable_functions
    assert "foo" not in report.unreachable_functions


def test_clean_function_reports_nothing():
    report = _report_for("int f(int n) { return n; }\n")
    assert report.unreachable_functions == []
    assert report.unreachable_blocks == []
    assert report.post_jump_statements == []
    assert report.unused_variables == []
    assert report.dead_assignments == []

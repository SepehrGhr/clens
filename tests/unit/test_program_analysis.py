"""`ProgramAnalysis` / `analyze_program` (D25): the Phase 3 artifact built
alongside `SemanticModel`.
"""

from __future__ import annotations

from clens.core.diagnostics import DiagnosticCollector
from clens.core.source import SourceFile
from clens.languages.c.parser import parse
from clens.languages.c.program_analysis import ProgramAnalysis, analyze_program
from clens.languages.c.semantic import analyze


def _analyze(text: str) -> ProgramAnalysis:
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    program = parse(source, diagnostics)
    model = analyze(program, source, diagnostics)
    return analyze_program(model)


def test_analyze_program_builds_a_cfg_per_function_with_a_body():
    analysis = _analyze(
        "int declared_only(int n);\n"
        "int factorial(int n) {\n"
        "    if (n <= 1) return 1;\n"
        "    return n * factorial(n - 1);\n"
        "}\n"
    )
    assert set(analysis.cfgs) == {"factorial"}
    assert analysis.cfgs["factorial"].function_name == "factorial"


def test_analyze_program_never_raises_on_an_empty_file():
    analysis = _analyze("")
    assert analysis.cfgs == {}
    assert analysis.dataflow == {}


def test_analyze_program_call_graph_still_a_placeholder():
    analysis = _analyze("int f(void) { return 1; }\n")
    assert analysis.call_graph is None


def test_analyze_program_builds_dataflow_results_per_function():
    analysis = _analyze(
        "int report(int value);\n"
        "int f(int condition) {\n"
        "    int x;\n"
        "    if (condition) { x = 42; }\n"
        "    return report(x);\n"
        "}\n"
    )
    assert set(analysis.dataflow) == {"f"}
    violations = analysis.dataflow["f"].uninitialized_uses
    assert {v.symbol.name for v in violations} == {"x"}

"""P4.7 / S9.2 — one undefined symbol used five times, through the full
analyze() pipeline (resolution + type checking together), still produces
exactly one diagnostic. Stage 3 already covers this at the resolver level
(test_resolver_diagnostics.py); this confirms type checking doesn't add a
second diagnostic on top when it independently looks up the same name for
each of its five uses.
"""

from pathlib import Path

from clens.core.diagnostics import DiagnosticCollector, SemanticCode
from clens.core.source import SourceFile
from clens.languages.c.parser import parse
from clens.languages.c.semantic import analyze

FIXTURE = Path(__file__).parent.parent / "fixtures" / "semantic-errors" / "undefined_symbol.c"


def analyze_text(text: str, filename: str = "a.c"):
    source = SourceFile(text, filename)
    diagnostics = DiagnosticCollector()
    program = parse(source, diagnostics)
    model = analyze(program, source, diagnostics)
    return model, diagnostics


def test_undefined_symbol_fixture_end_to_end_is_one_diagnostic():
    text = FIXTURE.read_text()
    _, diagnostics = analyze_text(text, "undefined_symbol.c")
    assert len(diagnostics.diagnostics) == 1
    assert diagnostics.diagnostics[0].code == SemanticCode.UNDEFINED_SYMBOL


def test_undefined_name_used_in_five_typed_contexts_is_still_one_diagnostic():
    """The same undefined name used as a binary operand, a comparison, a
    call argument, an assignment target, and a return value - five
    distinct type-checking code paths - must still yield one diagnostic."""
    text = (
        "int use(void) {\n"
        "    int local = counter + 1;\n"
        "    if (counter < 0) { }\n"
        "    use2(counter);\n"
        "    counter = 5;\n"
        "    return counter;\n"
        "}\n"
        "int use2(int n) { return n; }\n"
    )
    _, diagnostics = analyze_text(text)
    assert len(diagnostics.diagnostics) == 1
    assert diagnostics.diagnostics[0].code == SemanticCode.UNDEFINED_SYMBOL
    assert "counter" in diagnostics.diagnostics[0].message


def test_undefined_call_used_as_operand_five_times_is_one_diagnostic():
    text = (
        "int use(void) {\n"
        "    int a = missing() + missing();\n"
        "    int b = missing() * missing();\n"
        "    return missing();\n"
        "}\n"
    )
    _, diagnostics = analyze_text(text)
    assert len(diagnostics.diagnostics) == 1
    assert diagnostics.diagnostics[0].code == SemanticCode.UNDEFINED_SYMBOL


def test_for_loop_and_if_else_bodies_are_type_checked_too():
    """A narrowing assignment inside a for-loop body and an if/else branch
    must still be caught - the type checker's statement walk covers every
    statement kind, not just the top-level body."""
    text = (
        "int f(void) {\n"
        "    int total = 0;\n"
        "    for (int i = 0; i < 3; i++) {\n"
        "        total = 3.14;\n"
        "    }\n"
        "    if (total > 0) {\n"
        "        total = 1;\n"
        "    } else {\n"
        "        total = 2;\n"
        "    }\n"
        "    while (total > 0) {\n"
        "        total = total - 1;\n"
        "    }\n"
        "    return total;\n"
        "}\n"
    )
    _, diagnostics = analyze_text(text)
    assert len(diagnostics.diagnostics) == 1
    assert diagnostics.diagnostics[0].code == SemanticCode.NARROWING_CONVERSION

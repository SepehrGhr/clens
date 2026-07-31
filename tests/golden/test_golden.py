"""Golden snapshot tests for ANSI and HTML output of the canonical
factorial.c fixture, and for the `--json` diagnostics shape of the S4.7
golden-four semantic-error fixture. Regenerate with `pytest --regen-golden`
after an intentional rendering/schema change, and eyeball the diff before
committing.
"""

from pathlib import Path

from clens.core.diagnostics import DiagnosticCollector
from clens.core.source import SourceFile
from clens.core.token import iter_significant
from clens.languages.c.highlighter import highlight
from clens.languages.c.lexer import tokenize
from clens.languages.c.parser import Parser
from clens.languages.c.semantic import analyze
from clens.render.ansi import render_ansi
from clens.render.html import render_html

FIXTURE = Path(__file__).parent.parent / "fixtures" / "valid" / "factorial.c"
SEMANTIC_FIXTURE = Path(__file__).parent.parent / "fixtures" / "semantic-errors" / "golden_four.c"
EXPECTED_DIR = Path(__file__).parent / "expected"


def _process():
    text = FIXTURE.read_text()
    source = SourceFile(text, "factorial.c")
    diagnostics = DiagnosticCollector()
    tokens = tokenize(source, diagnostics)
    program = Parser(list(iter_significant(tokens)), diagnostics).parse_program()
    return source, tokens, highlight(tokens, program)


def test_ansi_golden_factorial(golden):
    source, tokens, highlight_map = _process()
    golden(EXPECTED_DIR / "factorial.ansi.txt", render_ansi(source, tokens, highlight_map))


def test_html_golden_factorial(golden):
    source, tokens, highlight_map = _process()
    golden(EXPECTED_DIR / "factorial.html", render_html(source, tokens, highlight_map))


def test_json_golden_semantic_diagnostics(golden):
    """`clens check --json` on the S4.7 golden-four fixture — the --json
    shape for semantic diagnostics, pinned exactly like the ANSI/HTML
    output above (phase2-acceptance.md's own requirement)."""
    text = SEMANTIC_FIXTURE.read_text()
    source = SourceFile(text, "golden_four.c")
    diagnostics = DiagnosticCollector()
    tokens = list(iter_significant(tokenize(source, diagnostics)))
    program = Parser(tokens, diagnostics).parse_program()
    analyze(program, source, diagnostics)
    golden(EXPECTED_DIR / "golden_four.diagnostics.json", diagnostics.to_json() + "\n")

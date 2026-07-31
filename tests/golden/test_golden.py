"""Golden snapshot tests for ANSI and HTML output of the canonical
factorial.c fixture. Regenerate with `pytest --regen-golden` after an
intentional rendering change, and eyeball the diff before committing.
"""

from pathlib import Path

from clens.core.diagnostics import DiagnosticCollector
from clens.core.source import SourceFile
from clens.core.token import iter_significant
from clens.languages.c.highlighter import highlight
from clens.languages.c.lexer import tokenize
from clens.languages.c.parser import Parser
from clens.render.ansi import render_ansi
from clens.render.html import render_html

FIXTURE = Path(__file__).parent.parent / "fixtures" / "valid" / "factorial.c"
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

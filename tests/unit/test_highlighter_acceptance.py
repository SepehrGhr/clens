"""R5.1, R5.3 — the acceptance test the whole highlighter stage exists to
pass, plus the round-trip fidelity test run over every valid fixture.

Per `.agents/skills/highlighter/SKILL.md`: "in a file where 'factorial'
appears both as a call target and as a bare variable reference, the two get
different categories. Write that test early; it is the thing being checked."
"""

import html as html_stdlib
import re
from pathlib import Path

from clens.core.diagnostics import DiagnosticCollector
from clens.core.highlight import Category
from clens.core.source import SourceFile
from clens.core.token import iter_significant
from clens.languages.c.highlighter import highlight
from clens.languages.c.lexer import tokenize
from clens.languages.c.parser import Parser
from clens.render.ansi import render_ansi
from clens.render.html import render_html

FIXTURES_VALID = Path(__file__).parent.parent / "fixtures" / "valid"
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
_TAG = re.compile(r"<[^>]+>")


def process(text: str, filename: str = "a.c"):
    source = SourceFile(text, filename)
    diagnostics = DiagnosticCollector()
    tokens = tokenize(source, diagnostics)
    program = Parser(list(iter_significant(tokens)), diagnostics).parse_program()
    highlight_map = highlight(tokens, program)
    return source, tokens, highlight_map


def test_r5_1_call_vs_variable_get_different_categories():
    """THE acceptance test: same identifier, call site vs. bare variable
    reference, must not share a category. A token-only or regex-only
    highlighter cannot pass this (R5.1)."""
    text = (FIXTURES_VALID / "call_vs_variable.c").read_text()
    _, tokens, highlight_map = process(text, "call_vs_variable.c")

    call_site_index = next(
        i
        for i, t in enumerate(tokens)
        if t.lexeme == "factorial" and tokens[i + 1].lexeme == "(" and t.line == 7
    )
    # The bare variable reference: 'return factorial + 1;' inside use().
    bare_var_index = next(
        i for i, t in enumerate(tokens) if t.lexeme == "factorial" and t.line == 11
    )

    call_category = highlight_map.get(call_site_index)
    bare_category = highlight_map.get(bare_var_index)

    assert call_category is Category.FUNCTION
    assert bare_category is Category.VARIABLE
    assert call_category != bare_category


def _valid_fixtures():
    return sorted(FIXTURES_VALID.glob("*.c"))


def test_ansi_round_trip_over_every_valid_fixture():
    for path in _valid_fixtures():
        text = path.read_text()
        source, tokens, highlight_map = process(text, path.name)
        rendered = render_ansi(source, tokens, highlight_map)
        stripped = _ANSI_ESCAPE.sub("", rendered)
        assert stripped == text, f"{path.name}: ANSI round-trip mismatch"


def test_html_round_trip_over_every_valid_fixture():
    for path in _valid_fixtures():
        text = path.read_text()
        source, tokens, highlight_map = process(text, path.name)
        rendered = render_html(source, tokens, highlight_map)
        match = re.search(r"<pre>(.*)</pre>", rendered, re.DOTALL)
        assert match, f"{path.name}: no <pre> block in output"
        stripped = html_stdlib.unescape(_TAG.sub("", match.group(1)))
        assert stripped == text, f"{path.name}: HTML round-trip mismatch"


def test_token_spans_tile_the_source_with_no_gaps_or_overlaps():
    """Span-coverage invariant the highlighter skill calls out explicitly:
    if this fails, the renderer would silently drop or duplicate characters.
    """
    for path in _valid_fixtures():
        text = path.read_text()
        source, tokens, _ = process(text, path.name)
        cursor = 0
        for token in tokens:
            if token.start_offset == token.end_offset:  # EOF sentinel
                continue
            assert token.start_offset == cursor, f"{path.name}: gap/overlap before {token!r}"
            cursor = token.end_offset
        assert cursor == len(source.text), f"{path.name}: tokens don't reach end of file"

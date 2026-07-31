"""R5.3, R6.1 — ANSI renderer: byte-faithful round-trip and styling."""

import re
from pathlib import Path

from clens.core.diagnostics import DiagnosticCollector
from clens.core.highlight import Category
from clens.core.source import SourceFile
from clens.core.theme import ANSI_RESET, THEME
from clens.core.token import iter_significant
from clens.languages.c.highlighter import highlight
from clens.languages.c.lexer import tokenize
from clens.languages.c.parser import Parser
from clens.render.ansi import render_ansi

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def render_text(text: str) -> str:
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    tokens = tokenize(source, diagnostics)
    program = Parser(list(iter_significant(tokens)), diagnostics).parse_program()
    highlight_map = highlight(tokens, program)
    return render_ansi(source, tokens, highlight_map)


def strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE.sub("", text)


def test_round_trip_strips_to_original_source():
    text = (Path(__file__).parent.parent / "fixtures" / "valid" / "factorial.c").read_text()
    rendered = render_text(text)
    assert strip_ansi(rendered) == text


def test_keyword_is_wrapped_in_its_style_and_reset():
    rendered = render_text("return 1;")
    keyword_style = THEME[Category.KEYWORD]
    assert f"{keyword_style.ansi}return{ANSI_RESET}" in rendered


def test_every_styled_token_gets_its_own_reset():
    """Each span is individually wrapped, not batched: as many resets as
    styled tokens."""
    rendered = render_text("int x = 1;")
    assert rendered.count(ANSI_RESET) == 4  # int, x, =, 1 (';' is an unstyled delimiter)


def test_empty_file_renders_to_empty_string():
    assert render_text("") == ""


def test_comments_are_preserved_verbatim_in_round_trip():
    text = "// a comment\nint x; /* block */\n"
    assert strip_ansi(render_text(text)) == text

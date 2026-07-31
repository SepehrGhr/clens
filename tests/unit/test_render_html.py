"""R5.3, R6.2 — HTML renderer: escaping, structure, and round-trip fidelity."""

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
from clens.render.html import render_html

_TAG = re.compile(r"<[^>]+>")


def render_text(text: str) -> str:
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    tokens = tokenize(source, diagnostics)
    program = Parser(list(iter_significant(tokens)), diagnostics).parse_program()
    highlight_map = highlight(tokens, program)
    return render_html(source, tokens, highlight_map)


def extract_pre_body(document: str) -> str:
    match = re.search(r"<pre>(.*)</pre>", document, re.DOTALL)
    assert match, document
    return match.group(1)


def strip_tags_and_unescape(document: str) -> str:
    body = extract_pre_body(document)
    return html_stdlib.unescape(_TAG.sub("", body))


def test_round_trip_strips_to_original_source():
    text = (Path(__file__).parent.parent / "fixtures" / "valid" / "factorial.c").read_text()
    rendered = render_text(text)
    assert strip_tags_and_unescape(rendered) == text


def test_escapes_ampersand_less_than_greater_than():
    rendered = render_text('int x = 1 < 2 && 3 > 2;\nchar *s = "a & b";')
    body = extract_pre_body(rendered)
    assert "&lt;" in body
    assert "&gt;" in body
    assert "&amp;&amp;" in body
    assert '"a &amp; b"' in body
    # No raw '<' or '>' outside of real HTML tags.
    assert "< " not in body.replace("&lt;", "")


def test_no_javascript_present():
    rendered = render_text("int x;")
    assert "<script" not in rendered.lower()
    assert "onclick" not in rendered.lower()
    assert "javascript:" not in rendered.lower()


def test_self_contained_document_structure():
    rendered = render_text("int x;")
    assert rendered.startswith("<!doctype html>")
    assert "<style>" in rendered and "</style>" in rendered
    assert "<pre>" in rendered and "</pre>" in rendered
    # No external stylesheet or script references.
    assert "<link" not in rendered
    assert "src=" not in rendered


def test_keyword_gets_its_own_span_class():
    rendered = render_text("return 1;")
    assert '<span class="keyword">return</span>' in rendered


def test_call_callee_gets_function_class():
    rendered = render_text("int f(void) { return f(); }")
    assert rendered.count('<span class="function">f</span>') == 2


def test_delimiters_are_not_wrapped_in_a_span():
    rendered = render_text("int x;")
    assert ";" in extract_pre_body(rendered)
    assert not re.search(r'<span class="[^"]*">;</span>', rendered)


def test_empty_file_has_empty_pre_body():
    rendered = render_text("")
    assert extract_pre_body(rendered) == ""


def test_all_twelve_categories_have_a_css_rule():
    rendered = render_text("int x;")
    for category in Category:
        assert f".{category.value} {{" in rendered

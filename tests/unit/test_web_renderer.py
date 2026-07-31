"""S8.3 — web/renderer.py: the interactive renderer, separate from the
frozen render/html.py, emitting data-start/data-end for the front end.
"""

from clens.core.diagnostics import DiagnosticCollector
from clens.core.highlight import Category
from clens.core.source import SourceFile
from clens.core.theme import THEME
from clens.core.token import iter_significant
from clens.languages.c.highlighter import highlight
from clens.languages.c.lexer import tokenize
from clens.languages.c.parser import Parser
from clens.web.renderer import generate_theme_css, render_interactive


def render(text: str) -> str:
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    tokens = tokenize(source, diagnostics)
    program = Parser(list(iter_significant(tokens)), diagnostics).parse_program()
    highlight_map = highlight(tokens, program)
    return render_interactive(source, tokens, highlight_map)


def test_renders_one_pre_block():
    html = render("int x;\n")
    assert html.startswith("<pre>")
    assert html.endswith("</pre>")


def test_every_span_carries_offset_attributes():
    html = render("int x;\n")
    assert 'data-start="0" data-end="3"' in html  # 'int'
    assert 'data-start="4" data-end="5"' in html  # 'x'


def test_categories_appear_as_css_classes():
    html = render("void f(void) { return; }\n")
    assert 'class="keyword"' in html
    html2 = render("int x;\n")
    assert 'class="variable"' in html2


def test_html_special_characters_are_escaped():
    html = render('char *s = "a < b && c > d";\n')
    assert "&lt;" in html
    assert "&gt;" in html
    assert "&amp;&amp;" in html
    assert "a < b" not in html
    assert "c > d" not in html


def test_round_trips_byte_faithfully_once_tags_are_stripped():
    """Stripping every span tag (not the escaping) must reproduce the
    original source, matching R5.3's round-trip requirement for the other
    renderers."""
    import re

    text = "int main(void) {\n    return 0; // done\n}\n"
    html = render(text)
    inner = html[len("<pre>") : -len("</pre>")]
    stripped = re.sub(r"<span[^>]*>|</span>", "", inner)
    unescaped = stripped.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    assert unescaped == text


def test_generate_theme_css_covers_every_category_with_its_real_color():
    """The web UI's theme.css must be provably shared with core/theme.py,
    not a hand-duplicated set of hex values (skill's own requirement)."""
    css = generate_theme_css()
    for category in Category:
        assert f".{category.value} {{" in css
        assert THEME[category].hex_color in css


def test_does_not_touch_render_html_module():
    """web/renderer.py must be a separate module from render/html.py, not
    a wrapper that imports and mutates it."""
    import clens.render.html as frozen_html
    import clens.web.renderer as web_renderer

    assert web_renderer.__file__ != frozen_html.__file__

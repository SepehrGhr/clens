"""The web UI's own HTML renderer (S8.3) — separate from `render/html.py`,
which R6.2 requires to stay self-contained and JavaScript-free, pinned by a
golden test. This renderer emits `data-start`/`data-end` offset attributes
on every span instead, so `web/static/app.js` can map a click or hover back
to a source position and drive `/api/complete` and `/api/hover`.

Both renderers consume the same `HighlightMap` from the same highlighter
and the same `core/theme.py` — R6.3's whole point (a third output format
needs no highlighter changes) now actually being exercised.
"""

from __future__ import annotations

from clens.core.highlight import Category, HighlightMap
from clens.core.source import SourceFile
from clens.core.theme import THEME
from clens.core.token import Token, TokenType

__all__ = ["generate_theme_css", "render_interactive"]


def render_interactive(source: SourceFile, tokens: list[Token], highlight_map: HighlightMap) -> str:
    """An HTML fragment (one `<pre>...</pre>`, no document shell) for the
    web UI's rendered pane. Byte-faithful the same way `render_html` is:
    each run is sliced from `source.text` by offset, not reassembled from
    lexemes, so whitespace and trivia round-trip exactly.
    """
    parts: list[str] = []
    for index, token in enumerate(tokens):
        if token.type is TokenType.EOF:
            continue
        text = _escape_html(source.text[token.start_offset : token.end_offset])
        category = highlight_map.get(index)
        class_attr = f' class="{category.value}"' if category is not None else ""
        parts.append(
            f'<span{class_attr} data-start="{token.start_offset}" '
            f'data-end="{token.end_offset}">{text}</span>'
        )
    return f"<pre>{''.join(parts)}</pre>"


def generate_theme_css() -> str:
    """The `.category { ... }` rule for every highlight `Category`,
    generated from `core/theme.py` — the same table `render_html`'s
    `_build_css` reads. Served as `/static/theme.css` (`web/server.py`)
    rather than hand-duplicated in a static stylesheet, so the web UI's
    token colors can never drift from the ANSI/HTML renderers' (a test
    asserts this directly).
    """
    lines = [f".{category.value} {{ {THEME[category].css_declarations} }}" for category in Category]
    return "\n".join(lines)


def _escape_html(text: str) -> str:
    # Order matters: '&' first, or the '&' introduced by the '<'/'>'
    # replacements below would itself get escaped.
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

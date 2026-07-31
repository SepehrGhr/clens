"""HTML renderer (R6.2). Consumes the same `HighlightMap` as
`render/ansi.py` (R6.3) — adding a third output format means reading
`core/theme.py` differently, never touching the highlighter.

Produces one self-contained `.html` file: a `<pre>` block with one
`<span class="category">` per styled run and an embedded `<style>` block.
No JavaScript, no external resources — renders correctly with scripting
disabled.
"""

from __future__ import annotations

from clens.core.highlight import Category, HighlightMap
from clens.core.source import SourceFile
from clens.core.theme import THEME
from clens.core.token import Token, TokenType

__all__ = ["render_html"]


def render_html(
    source: SourceFile,
    tokens: list[Token],
    highlight_map: HighlightMap,
    *,
    title: str = "clens",
) -> str:
    """Render `tokens` (the full, trivia-included list) as a standalone
    HTML document. Byte-faithful (R5.3): see `render.ansi.render_ansi` for
    why offsets are sliced from `source.text` rather than reassembled.
    HTML-escaping is applied to each sliced run individually, never to the
    document afterward.
    """
    body_parts: list[str] = []
    for index, token in enumerate(tokens):
        if token.type is TokenType.EOF:
            continue
        text = _escape_html(source.text[token.start_offset : token.end_offset])
        category = highlight_map.get(index)
        if category is None:
            body_parts.append(text)
        else:
            body_parts.append(f'<span class="{category.value}">{text}</span>')

    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{_escape_html(title)}</title>\n"
        f"<style>\n{_build_css()}\n</style>\n"
        "</head>\n"
        "<body>\n"
        f"<pre>{''.join(body_parts)}</pre>\n"
        "</body>\n"
        "</html>\n"
    )


def _escape_html(text: str) -> str:
    # Order matters: '&' first, or the '&' introduced by the '<'/'>'
    # replacements below would itself get escaped.
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _build_css() -> str:
    lines = [
        "pre { background: #1E1E1E; color: #D4D4D4; padding: 1em; "
        "font-family: Consolas, Menlo, 'Fira Code', monospace; "
        "font-size: 14px; line-height: 1.5; overflow-x: auto; white-space: pre; }"
    ]
    for category in Category:
        lines.append(f".{category.value} {{ {THEME[category].css_declarations} }}")
    return "\n".join(lines)

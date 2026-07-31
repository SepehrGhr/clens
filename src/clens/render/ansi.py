"""ANSI terminal renderer (R6.1). Consumes the same `HighlightMap` as
`render/html.py` (R6.3) — adding a third output format means reading
`core/theme.py` differently, never touching the highlighter.
"""

from __future__ import annotations

from clens.core.highlight import HighlightMap
from clens.core.source import SourceFile
from clens.core.theme import ANSI_RESET, THEME
from clens.core.token import Token, TokenType

__all__ = ["render_ansi"]


def render_ansi(source: SourceFile, tokens: list[Token], highlight_map: HighlightMap) -> str:
    """Render `tokens` (the full, trivia-included list) as ANSI-escaped
    text.

    Byte-faithful (R5.3): iterates tokens in source order and slices
    `source.text` by each token's offsets rather than reassembling from
    lexemes, so stripping the escape codes back out reproduces the input
    exactly. A token with no `highlight_map` entry (delimiters, whitespace)
    passes through unstyled.
    """
    parts: list[str] = []
    for index, token in enumerate(tokens):
        if token.type is TokenType.EOF:
            continue
        text = source.text[token.start_offset : token.end_offset]
        category = highlight_map.get(index)
        if category is None:
            parts.append(text)
        else:
            parts.append(f"{THEME[category].ansi}{text}{ANSI_RESET}")
    return "".join(parts)

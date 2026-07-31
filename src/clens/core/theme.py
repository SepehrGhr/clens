"""One Category -> Style table (D10), consumed identically by both
renderers. Adding a third output format means reading this table
differently — it must never require touching the highlighter (R6.3).

Hex values are VS Code Dark+'s. Two categories intentionally swap VS Code's
own default assignment: the course document (R5.2) asks for `number`=orange
and `string`=warm green, which is the *reverse* of VS Code Dark+'s actual
palette (there, strings are the orange-salmon tone and numbers are the light
green). We keep the recognizable VS Code hex values but remap them onto the
categories the course document specifies, since R5.2's semantic mapping is
the graded contract and the exact hex values are "the document's
suggestions" (R5.2 header note).
"""

from __future__ import annotations

from dataclasses import dataclass

from clens.core.highlight import Category

__all__ = ["ANSI_RESET", "THEME", "Style"]


@dataclass(frozen=True, slots=True)
class Style:
    """A category's visual style, independent of output format."""

    hex_color: str
    bold: bool = False
    italic: bool = False
    underline: bool = False

    @property
    def ansi(self) -> str:
        """24-bit ANSI escape sequence for this style (no reset — see
        ANSI_RESET, applied once per span by the renderer).
        """
        attrs = [
            code for code, on in (("1", self.bold), ("3", self.italic), ("4", self.underline)) if on
        ]
        r, g, b = (int(self.hex_color[i : i + 2], 16) for i in (1, 3, 5))
        attrs.append(f"38;2;{r};{g};{b}")
        return f"\x1b[{';'.join(attrs)}m"

    @property
    def css_declarations(self) -> str:
        """CSS declarations (no selector) for this style."""
        parts = [f"color: {self.hex_color}"]
        if self.bold:
            parts.append("font-weight: bold")
        if self.italic:
            parts.append("font-style: italic")
        if self.underline:
            parts.append("text-decoration: underline")
        return "; ".join(parts) + ";"


#: Terminal reset code, emitted after every styled span.
ANSI_RESET = "\x1b[0m"

THEME: dict[Category, Style] = {
    Category.KEYWORD: Style("#569CD6", bold=True),
    Category.TYPE: Style("#4EC9B0"),
    Category.VARIABLE: Style("#D4D4D4"),
    Category.FUNCTION: Style("#DCDCAA"),
    Category.TYPE_NAME: Style("#3FB950"),
    Category.NUMBER: Style("#CE9178"),
    Category.STRING: Style("#B5CEA8"),
    Category.BOOLEAN: Style("#CE9178"),
    Category.OPERATOR: Style("#C0C0C0"),
    Category.COMMENT: Style("#808080", italic=True),
    Category.PREPROCESSOR: Style("#C586C0"),
    Category.ERROR: Style("#F44747", underline=True),
}

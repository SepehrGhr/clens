"""SVG rendering for the CFG and call-graph panes (D28): emitted as plain
text from Python, no drawing library, no new runtime dependency. The same
`Layout` (`core/graph_layout.py`) and this same renderer serve both
graphs -- only node/edge content differs, matching the two-renderers-
one-map pattern from Phase 1's ANSI/HTML split.

Colors come from `core/theme.py`, the same table the highlighter uses,
so the CFG reads as part of the same visual system rather than an
unrelated widget bolted on.
"""

from __future__ import annotations

from html import escape

from clens.core.graph_layout import Layout, LayoutEdge, LayoutNode
from clens.core.highlight import Category
from clens.core.theme import THEME

__all__ = ["render_svg"]

_NODE_WIDTH = 150.0
_NODE_HEIGHT = 50.0
_LINE_HEIGHT = 14.0
_FONT = "monospace"

_BACKGROUND = "#1e1e1e"
_NODE_FILL = "#2d2d2d"
_TRUE_COLOR = THEME[Category.TYPE_NAME].hex_color
_FALSE_COLOR = THEME[Category.ERROR].hex_color
_NEUTRAL_COLOR = THEME[Category.OPERATOR].hex_color
_NORMAL_BORDER = THEME[Category.FUNCTION].hex_color
_ENTRY_EXIT_BORDER = THEME[Category.KEYWORD].hex_color
_TEXT_COLOR = THEME[Category.VARIABLE].hex_color


def render_svg(layout: Layout, highlighted_ids: frozenset[str] = frozenset()) -> str:
    """`highlighted_ids` get the "entry/exit" accent border -- ENTRY/EXIT
    for a CFG, or left empty for a call graph, which has no such concept.
    """
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{layout.width:.0f}" '
        f'height="{layout.height:.0f}" viewBox="0 0 {layout.width:.0f} {layout.height:.0f}" '
        f'font-family="{_FONT}">',
        _marker_defs(),
        f'<rect width="100%" height="100%" fill="{_BACKGROUND}" />',
    ]
    for edge in layout.edges:
        parts.append(_render_edge(layout, edge))
    for node in layout.nodes.values():
        parts.append(_render_node(node, node.id in highlighted_ids))
    parts.append("</svg>")
    return "\n".join(parts)


def _marker_defs() -> str:
    return (
        "<defs>"
        '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{_NEUTRAL_COLOR}" />'
        "</marker>"
        "</defs>"
    )


def _render_node(node: LayoutNode, is_entry_exit: bool) -> str:
    x = node.x - _NODE_WIDTH / 2
    y = node.y - _NODE_HEIGHT / 2
    border = _ENTRY_EXIT_BORDER if is_entry_exit else _NORMAL_BORDER
    lines = node.label.split("\n")
    first_line_y = y + _NODE_HEIGHT / 2 - (len(lines) - 1) * _LINE_HEIGHT / 2
    tspans = "".join(
        f'<tspan x="{node.x:.1f}" y="{first_line_y + i * _LINE_HEIGHT:.1f}">{escape(line)}</tspan>'
        for i, line in enumerate(lines)
    )
    return (
        f'<g id="node-{escape(node.id)}">'
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{_NODE_WIDTH:.0f}" height="{_NODE_HEIGHT:.0f}" '
        f'rx="8" fill="{_NODE_FILL}" stroke="{border}" stroke-width="2" />'
        f'<text text-anchor="middle" font-size="11" fill="{_TEXT_COLOR}">{tspans}</text>'
        "</g>"
    )


def _render_edge(layout: Layout, edge: LayoutEdge) -> str:
    source = layout.nodes[edge.source]
    target = layout.nodes[edge.target]
    color = {"true": _TRUE_COLOR, "false": _FALSE_COLOR}.get(edge.label, _NEUTRAL_COLOR)
    x1, y1 = source.x, source.y + _NODE_HEIGHT / 2
    x2, y2 = target.x, target.y - _NODE_HEIGHT / 2

    if edge.back:
        # Curve to the left of the node column, per D28, so a
        # loop-closing edge reads as a loop rather than overlapping the
        # forward edges running straight down the same column.
        control_x = min(x1, x2, target.x, source.x) - 70
        path = (
            f"M {x1:.1f} {source.y:.1f} "
            f"C {control_x:.1f} {source.y:.1f}, {control_x:.1f} {target.y:.1f}, "
            f"{x2:.1f} {target.y:.1f}"
        )
        line = (
            f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2" '
            f'marker-end="url(#arrow)" />'
        )
    else:
        line = (
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-width="2" marker-end="url(#arrow)" />'
        )

    label_svg = ""
    if edge.label and edge.label != "fallthrough":
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        label_svg = (
            f'<text x="{mx:.1f}" y="{my - 4:.1f}" font-size="10" fill="{color}" '
            f'text-anchor="middle">{escape(edge.label)}</text>'
        )
    return line + label_svg

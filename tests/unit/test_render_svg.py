"""`render/svg.py`: SVG emission from a `Layout`, using `core/theme.py`
colors, with no external references (D28's definition of done).
"""

from __future__ import annotations

from clens.core.graph_layout import layered_layout
from clens.core.highlight import Category
from clens.core.theme import THEME
from clens.render.svg import render_svg


def test_render_svg_is_well_formed_and_self_contained():
    layout = layered_layout(
        node_ids=["ENTRY", "B1", "EXIT"],
        labels={"ENTRY": "ENTRY", "B1": "n <= 1", "EXIT": "EXIT"},
        edges=[("ENTRY", "B1", "fallthrough"), ("B1", "EXIT", "true")],
        root="ENTRY",
    )
    svg = render_svg(layout, highlighted_ids=frozenset({"ENTRY", "EXIT"}))
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    assert "http" not in svg or "http://www.w3.org/2000/svg" in svg  # no external refs
    assert "n &lt;= 1" in svg  # escaped, not raw `<`


def test_render_svg_tags_each_node_group_with_its_id_for_click_to_navigate():
    layout = layered_layout(
        node_ids=["main", "helper"],
        labels={},
        edges=[("main", "helper", "")],
        root="main",
    )
    svg = render_svg(layout)
    assert 'id="node-main"' in svg
    assert 'id="node-helper"' in svg


def test_render_svg_uses_theme_colors_not_hardcoded_ones():
    layout = layered_layout(
        node_ids=["a", "b"],
        labels={},
        edges=[("a", "b", "true")],
        root="a",
    )
    svg = render_svg(layout)
    assert THEME[Category.TYPE_NAME].hex_color in svg  # true-edge color
    assert THEME[Category.ERROR].hex_color not in svg  # no false edge here


def test_render_svg_escapes_labels():
    layout = layered_layout(
        node_ids=["a"],
        labels={"a": 'x < y && "z"'},
        edges=[],
        root="a",
    )
    svg = render_svg(layout)
    assert "<tspan" in svg
    assert 'x < y && "z"' not in svg  # raw, unescaped text must not appear
    assert "&lt;" in svg and "&amp;" in svg


def test_back_edge_renders_as_a_curved_path_not_a_straight_line():
    layout = layered_layout(
        node_ids=["header", "body"],
        labels={},
        edges=[("header", "body", "true"), ("body", "header", "back")],
        root="header",
    )
    svg = render_svg(layout)
    assert "<path" in svg  # the back edge
    assert "<line" in svg  # the forward edge

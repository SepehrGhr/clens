"""`core/graph_layout.py`: pure layered-layout geometry, tested
independently of any SVG output (D28's definition of done).
"""

from __future__ import annotations

from clens.core.graph_layout import layered_layout


def test_linear_chain_ranks_increase_by_one():
    layout = layered_layout(
        node_ids=["a", "b", "c"],
        labels={},
        edges=[("a", "b", ""), ("b", "c", "")],
        root="a",
    )
    assert layout.nodes["a"].rank == 0
    assert layout.nodes["b"].rank == 1
    assert layout.nodes["c"].rank == 2
    # y increases monotonically with rank.
    assert layout.nodes["a"].y < layout.nodes["b"].y < layout.nodes["c"].y


def test_diamond_branches_share_a_rank_and_join_is_deeper():
    layout = layered_layout(
        node_ids=["head", "true_b", "false_b", "join"],
        labels={},
        edges=[
            ("head", "true_b", "true"),
            ("head", "false_b", "false"),
            ("true_b", "join", ""),
            ("false_b", "join", ""),
        ],
        root="head",
    )
    assert layout.nodes["true_b"].rank == layout.nodes["false_b"].rank == 1
    assert layout.nodes["join"].rank == 2
    # Same-rank nodes are horizontally separated.
    assert layout.nodes["true_b"].x != layout.nodes["false_b"].x


def test_back_edge_is_flagged_and_forward_edges_are_not():
    layout = layered_layout(
        node_ids=["header", "body"],
        labels={},
        edges=[("header", "body", "true"), ("body", "header", "back")],
        root="header",
    )
    forward = next(e for e in layout.edges if e.source == "header")
    back = next(e for e in layout.edges if e.source == "body")
    assert forward.back is False
    assert back.back is True


def test_disconnected_node_still_gets_a_position():
    layout = layered_layout(
        node_ids=["reachable", "orphan"],
        labels={},
        edges=[],
        root="reachable",
    )
    assert "orphan" in layout.nodes
    assert layout.nodes["orphan"].rank > layout.nodes["reachable"].rank


def test_labels_default_to_the_node_id():
    layout = layered_layout(node_ids=["x"], labels={}, edges=[], root="x")
    assert layout.nodes["x"].label == "x"


def test_labels_are_used_when_provided():
    layout = layered_layout(node_ids=["x"], labels={"x": "custom"}, edges=[], root="x")
    assert layout.nodes["x"].label == "custom"


def test_width_and_height_are_positive_and_grow_with_the_graph():
    small = layered_layout(node_ids=["a"], labels={}, edges=[], root="a")
    large = layered_layout(
        node_ids=["a", "b", "c", "d"],
        labels={},
        edges=[("a", "b", ""), ("a", "c", ""), ("a", "d", "")],
        root="a",
    )
    assert small.width > 0 and small.height > 0
    assert large.width > small.width
    assert large.height > small.height

"""Layered graph layout (D28): pure geometry, no I/O, no SVG -- shared by
the CFG and call-graph renderers. Rank each node by BFS depth from a
chosen root, order within a rank by first-visit order, and treat any edge
that does not strictly increase rank as a back edge to be curved. This
subset's CFGs are always small and reducible (no `goto`/`switch`), so a
crossing-minimization pass would cost real code and buy nothing visible.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

__all__ = ["Layout", "LayoutEdge", "LayoutNode", "layered_layout"]

_COL_WIDTH = 160.0
_ROW_HEIGHT = 90.0
_MARGIN = 50.0


@dataclass(slots=True, frozen=True)
class LayoutNode:
    id: str
    label: str
    rank: int
    x: float
    y: float


@dataclass(slots=True, frozen=True)
class LayoutEdge:
    source: str
    target: str
    label: str
    back: bool


@dataclass(slots=True)
class Layout:
    nodes: dict[str, LayoutNode] = field(default_factory=dict)
    edges: list[LayoutEdge] = field(default_factory=list)
    width: float = 0.0
    height: float = 0.0


def layered_layout(
    node_ids: list[str],
    labels: dict[str, str],
    edges: list[tuple[str, str, str]],
    root: str,
) -> Layout:
    """`edges` is a plain `(source, target, label)` triple list -- no
    dependency on `core.cfg.BasicBlock` or `core.graph.DirectedGraph`, so
    the same function lays out both the CFG and the call graph.

    `root` seeds rank 0 (`ENTRY` for a CFG; `main`, or an arbitrary node if
    absent, for a call graph). A node BFS never reaches -- a genuinely
    disconnected block, or a function no one calls -- still needs to
    render, so it gets its own trailing rank rather than being dropped.
    """
    adjacency: dict[str, list[str]] = {n: [] for n in node_ids}
    for source, target, _label in edges:
        adjacency.setdefault(source, []).append(target)

    rank: dict[str, int] = {}
    order_in_rank: dict[int, list[str]] = {}
    if root in adjacency:
        rank[root] = 0
        order_in_rank[0] = [root]
        queue: deque[str] = deque([root])
        while queue:
            node = queue.popleft()
            for neighbor in adjacency.get(node, []):
                if neighbor in rank:
                    continue  # already placed: a back edge or a second path in
                rank[neighbor] = rank[node] + 1
                order_in_rank.setdefault(rank[neighbor], []).append(neighbor)
                queue.append(neighbor)

    next_rank = max(rank.values(), default=-1) + 1
    for node in node_ids:
        if node not in rank:
            rank[node] = next_rank
            order_in_rank.setdefault(next_rank, []).append(node)
            next_rank += 1

    max_count = max((len(members) for members in order_in_rank.values()), default=1)
    row_width = max_count * _COL_WIDTH

    layout_nodes: dict[str, LayoutNode] = {}
    for r, members in order_in_rank.items():
        start_x = (row_width - len(members) * _COL_WIDTH) / 2
        for i, node_id in enumerate(members):
            x = _MARGIN + start_x + (i + 0.5) * _COL_WIDTH
            y = _MARGIN + r * _ROW_HEIGHT
            layout_nodes[node_id] = LayoutNode(
                id=node_id, label=labels.get(node_id, node_id), rank=r, x=x, y=y
            )

    layout_edges = [
        LayoutEdge(source=s, target=t, label=lbl, back=rank.get(t, 0) <= rank.get(s, 0))
        for s, t, lbl in edges
    ]

    height = _MARGIN * 2 + max(rank.values(), default=0) * _ROW_HEIGHT
    width = _MARGIN * 2 + row_width
    return Layout(nodes=layout_nodes, edges=layout_edges, width=width, height=height)

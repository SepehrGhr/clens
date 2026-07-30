"""R4.4 — NodeVisitor and walk(), tested independently of any real language's
AST (per the ast-and-visitors skill: "test the visitor on its own with a
counting subclass").
"""

from dataclasses import dataclass, field

from clens.core.ast_nodes import Node
from clens.core.token import Span
from clens.core.visitor import NodeVisitor, iter_child_nodes, walk

SPAN = Span(start_offset=0, end_offset=1, line=1, column=1)


@dataclass(slots=True)
class Leaf(Node):
    value: int = 0


@dataclass(slots=True)
class Pair(Node):
    left: Node | None = None
    right: Node | None = None


@dataclass(slots=True)
class Container(Node):
    children: list[Node] = field(default_factory=list)


def leaf(value: int) -> Leaf:
    return Leaf(span=SPAN, value=value)


def test_iter_child_nodes_skips_non_node_fields():
    node = Leaf(span=SPAN, value=42)
    assert list(iter_child_nodes(node)) == []


def test_iter_child_nodes_yields_direct_node_fields_in_order():
    pair = Pair(span=SPAN, left=leaf(1), right=leaf(2))
    children = list(iter_child_nodes(pair))
    assert children == [pair.left, pair.right]


def test_iter_child_nodes_expands_list_fields():
    container = Container(span=SPAN, children=[leaf(1), leaf(2), leaf(3)])
    assert list(iter_child_nodes(container)) == container.children


def test_iter_child_nodes_skips_none_optional_children():
    pair = Pair(span=SPAN, left=leaf(1), right=None)
    assert list(iter_child_nodes(pair)) == [pair.left]


def test_walk_yields_node_then_descendants_preorder():
    tree = Pair(span=SPAN, left=leaf(1), right=Pair(span=SPAN, left=leaf(2), right=leaf(3)))
    visited = list(walk(tree))
    assert visited == [tree, tree.left, tree.right, tree.right.left, tree.right.right]


def test_generic_visit_recurses_into_every_descendant():
    class CountingVisitor(NodeVisitor):
        def __init__(self) -> None:
            self.count = 0

        def generic_visit(self, node: Node):
            self.count += 1
            super().generic_visit(node)

    tree = Container(span=SPAN, children=[leaf(1), Pair(span=SPAN, left=leaf(2), right=leaf(3))])
    visitor = CountingVisitor()
    visitor.visit(tree)
    assert visitor.count == 5  # Container, Leaf(1), Pair, Leaf(2), Leaf(3)


def test_visit_dispatches_to_type_specific_method():
    class RecordingVisitor(NodeVisitor):
        def __init__(self) -> None:
            self.leaf_values: list[int] = []

        def visit_Leaf(self, node: Leaf):
            self.leaf_values.append(node.value)
            # Deliberately does not call generic_visit: Leaf has no children.

        def visit_Pair(self, node: Pair):
            self.generic_visit(node)

    tree = Pair(span=SPAN, left=leaf(10), right=Pair(span=SPAN, left=leaf(20), right=leaf(30)))
    visitor = RecordingVisitor()
    visitor.visit(tree)
    assert visitor.leaf_values == [10, 20, 30]


def test_unhandled_node_type_falls_back_to_generic_visit():
    class OnlyHandlesLeaf(NodeVisitor):
        def __init__(self) -> None:
            self.leaves_seen = 0

        def visit_Leaf(self, node: Leaf):
            self.leaves_seen += 1

    tree = Pair(span=SPAN, left=leaf(1), right=leaf(2))
    visitor = OnlyHandlesLeaf()
    visitor.visit(tree)  # Pair has no visit_Pair, so falls to generic_visit
    assert visitor.leaves_seen == 2

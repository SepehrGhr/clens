"""Generic AST traversal (R4.4): type-based dispatch plus a flat `walk()`.

Used once in Phase 1 (the highlighter's AST walk) and reused, unmodified, by
each later phase's passes — write it once, properly, per
`.agents/skills/ast-and-visitors/SKILL.md`.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from typing import Any

from clens.core.ast_nodes import Node

__all__ = ["NodeVisitor", "iter_child_nodes", "walk"]


def iter_child_nodes(node: Node) -> Iterator[Node]:
    """Yield every Node directly reachable from ``node``'s dataclass fields,
    in field-declaration order.

    Works off `dataclasses.fields()` rather than a per-node registration
    list, so a new node type is walkable the moment it is defined. List/tuple
    field values (e.g. a call's argument list) are expanded in order.
    """
    for field in dataclasses.fields(node):
        value = getattr(node, field.name)
        if isinstance(value, Node):
            yield value
        elif isinstance(value, list | tuple):
            for item in value:
                if isinstance(item, Node):
                    yield item


class NodeVisitor:
    """Dispatches `visit(node)` to `visit_<NodeClassName>` if the subclass
    defines one, else falls back to `generic_visit`, which recurses into
    every child node without doing anything itself.
    """

    def visit(self, node: Node) -> Any:
        method = getattr(self, f"visit_{type(node).__name__}", self.generic_visit)
        return method(node)

    def generic_visit(self, node: Node) -> Any:
        for child in iter_child_nodes(node):
            self.visit(child)


def walk(node: Node) -> Iterator[Node]:
    """Yield ``node`` and every node reachable from it, depth-first,
    pre-order. For passes that want a flat scan instead of visitor dispatch.
    """
    yield node
    for child in iter_child_nodes(node):
        yield from walk(child)

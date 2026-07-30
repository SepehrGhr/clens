"""AST pretty-printer (R4.2): the indented, field-labelled dump used by
`clens ast` and diffed against `.agents/fixtures/golden/factorial_ast.txt` in
tests.

Entirely generic over `dataclasses.fields()`, like `core.visitor` — it knows
nothing about any specific node type. Each node class controls its own
rendering only through two `ClassVar`s declared in `core.ast_nodes.Node`:

- `INLINE_FIELDS`: scalar field names shown as `name=value` inside the
  class-name parens, e.g. `BinaryExpr(op='*')`.
- `SHOW_LOC`: whether `loc=line:column` is appended to those parens. Reserved
  for nodes that anchor a name/value/call site to a source position
  (`Identifier`, literals, `CallExpr`); structural nodes leave it off since
  their position is redundant with their first child's.

Node-valued fields (and list-of-Node fields, indexed as `field[i]`) are
rendered as separate indented lines, one level deeper, with sibling field
labels padded to a common column so they line up — matching the course
document's own formatting in section 4.3.2.
"""

from __future__ import annotations

import dataclasses

from clens.core.ast_nodes import Node

__all__ = ["format_ast"]


def _inline_repr(node: Node) -> str:
    parts = [f"{name}={getattr(node, name)!r}" for name in node.INLINE_FIELDS]
    if node.SHOW_LOC:
        parts.append(f"loc={node.span.line}:{node.span.column}")
    class_name = type(node).__name__
    if not parts:
        return class_name
    return f"{class_name}({', '.join(parts)})"


def _child_entries(node: Node) -> list[tuple[str, Node]]:
    """(label, child) pairs for node's Node-valued fields, in declaration
    order; list-of-Node fields expand to `name[i]` labels.
    """
    entries: list[tuple[str, Node]] = []
    for f in dataclasses.fields(node):
        value = getattr(node, f.name)
        if isinstance(value, Node):
            entries.append((f.name, value))
        elif isinstance(value, list | tuple):
            for i, item in enumerate(value):
                if isinstance(item, Node):
                    entries.append((f"{f.name}[{i}]", item))
    return entries


def _render_children(node: Node, indent: int) -> list[str]:
    entries = _child_entries(node)
    if not entries:
        return []
    width = max(len(label) for label, _ in entries) + 2
    prefix = "  " * indent
    lines: list[str] = []
    for label, child in entries:
        padded = f"{label}:".ljust(width)
        lines.append(f"{prefix}{padded}{_inline_repr(child)}")
        lines.extend(_render_children(child, indent + 1))
    return lines


def format_ast(root: Node) -> str:
    """Render ``root`` in the course document's §4.3.2 indented shape."""
    lines = [_inline_repr(root)]
    lines.extend(_render_children(root, 1))
    return "\n".join(lines)

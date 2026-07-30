"""Language-agnostic AST base types (R4.1-R4.3).

`Span` is reused from `core.token` rather than redefined here: a token's
location and a node's location are the same shape (0-based start/end offsets,
1-based line/column of the first character), and one shared type means the
lexer, the parser, and diagnostics all agree on what "where" means.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from clens.core.token import Span

__all__ = ["Decl", "ErrorExpr", "ErrorStmt", "Expr", "Node", "Stmt", "join"]


@dataclass(slots=True)
class Node:
    """Base for every AST node. Every node carries a span (R4.2): the start
    of its first token to the end of its last, with the first token's
    1-based line/column.
    """

    span: Span

    #: Fields to render inline as `name=value` in the AST printer, e.g.
    #: ("op",) for BinaryExpr. Overridden per node class; see
    #: core/ast_printer.py.
    INLINE_FIELDS: ClassVar[tuple[str, ...]] = ()

    #: Whether the printer also renders this node's `loc=line:column`.
    #: Reserved for nodes that anchor a name, value, or call site to a
    #: specific source position; structural/compound nodes leave it off
    #: since their position is redundant with their first child's.
    SHOW_LOC: ClassVar[bool] = False


@dataclass(slots=True)
class Expr(Node):
    """Base for expression nodes."""

    # Filled in by Phase 2's semantic analyzer; untouched (always None) in
    # Phase 1. `Type` does not exist yet, so this is an intentionally
    # unresolved forward reference rather than a real import — nothing in
    # Phase 1 calls typing.get_type_hints() on AST nodes, so it is never
    # evaluated.
    type_annotation: Type | None = None  # noqa: F821


@dataclass(slots=True)
class Stmt(Node):
    """Base for statement nodes."""


@dataclass(slots=True)
class Decl(Node):
    """Base for declaration nodes."""


@dataclass(slots=True)
class ErrorExpr(Expr):
    """Placeholder emitted where the parser expected an expression but
    could not build one (R3.4). Carries a span so the highlighter can still
    color the broken region and the AST printer can show where recovery
    gave up, instead of leaving a hole in the tree.
    """

    message: str = ""

    INLINE_FIELDS: ClassVar[tuple[str, ...]] = ("message",)
    SHOW_LOC: ClassVar[bool] = True


@dataclass(slots=True)
class ErrorStmt(Stmt):
    """Placeholder emitted where the parser expected a statement but could
    not build one (R3.4). See :class:`ErrorExpr`.
    """

    message: str = ""

    INLINE_FIELDS: ClassVar[tuple[str, ...]] = ("message",)
    SHOW_LOC: ClassVar[bool] = True


def join(start: Span, end: Span) -> Span:
    """Build a parent span covering from the start of ``start`` to the end
    of ``end``. The result keeps ``start``'s line/column, since a node's
    position is its first token's position (R4.2). Use this instead of
    hand-computing parent spans from child spans.
    """
    return Span(
        start_offset=start.start_offset,
        end_offset=end.end_offset,
        line=start.line,
        column=start.column,
    )

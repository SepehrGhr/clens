"""Control flow graph data structures (A1.2-A1.4). Language-agnostic: a
`BasicBlock` holds plain AST `Node`s as opaque statements, so this module
never imports anything from `languages/`.

`switch`, `goto`, and labels are out of the C subset (see
`project/10-phase2-interfaces.md`), so every CFG built from this AST is
reducible and structured — no irreducible loops, no arbitrary jumps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clens.core.ast_nodes import Node

__all__ = ["BasicBlock", "BlockKind", "ControlFlowGraph", "EdgeLabel"]


class BlockKind(Enum):
    ENTRY = "entry"
    EXIT = "exit"
    NORMAL = "normal"


class EdgeLabel(Enum):
    TRUE = "true"
    FALSE = "false"
    FALLTHROUGH = "fallthrough"
    BACK = "back"


@dataclass(slots=True)
class BasicBlock:
    """A maximal run of statements with no branches: control enters at the
    top and leaves at the bottom, with at most two successors (A1.2).
    `statements` is empty for ENTRY/EXIT.
    """

    id: int
    kind: BlockKind
    statements: list[Node] = field(default_factory=list)
    successors: list[tuple[BasicBlock, EdgeLabel]] = field(default_factory=list)
    predecessors: list[BasicBlock] = field(default_factory=list)

    def add_successor(self, target: BasicBlock, label: EdgeLabel) -> None:
        """Wire `self -> target` and keep `target.predecessors` in sync
        (A2.3's unreachable-block detection and every backward analysis
        read `predecessors`, so it must never be derived separately).
        """
        self.successors.append((target, label))
        target.predecessors.append(self)

    def label(self) -> str:
        if self.kind is BlockKind.ENTRY:
            return "ENTRY"
        if self.kind is BlockKind.EXIT:
            return "EXIT"
        return f"B{self.id}"


@dataclass(slots=True)
class ControlFlowGraph:
    """One CFG per function with a body (A1.1). A single EXIT node is
    simpler than several and still satisfies A1.4 ("one or more") — every
    `return` and the implicit fallthrough at the end of the function flow
    into it.
    """

    function_name: str
    entry: BasicBlock
    exit: BasicBlock
    blocks: list[BasicBlock] = field(default_factory=list)

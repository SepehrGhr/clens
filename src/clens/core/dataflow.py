"""The generic worklist data-flow solver (D26). The course document
describes data-flow analysis as a fixed-point computation over a lattice;
one solver parameterized by direction, join, and transfer *is* that
abstraction made concrete. Definite assignment, live variables, and
reaching definitions (`languages/c/analyses.py`) are each ~15 lines of
configuration against this one function, not three bespoke loops.

Language-agnostic: works over `core.cfg.ControlFlowGraph` only.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

from clens.core.cfg import BasicBlock, ControlFlowGraph

__all__ = ["Analysis", "Direction", "solve"]

T = TypeVar("T")


class Direction(Enum):
    FORWARD = "forward"
    BACKWARD = "backward"


@dataclass(frozen=True, slots=True)
class Analysis(Generic[T]):
    """One data-flow problem. `join` combines the `out` sets of a block's
    relevant neighbours (predecessors for forward, successors for
    backward) into its `in`; `transfer` derives a block's `out` from that
    `in`. `boundary` is the value fixed at the direction's entry point
    (`ENTRY` forward, `EXIT` backward); `initial` seeds every other block
    before the first iteration.

    Must-analyses (definite assignment) need `initial` to be the *full*
    lattice element, not empty -- intersection with an empty seed
    collapses to empty immediately and everything looks unassigned. This
    is the classic bug the skill document calls out explicitly.
    """

    direction: Direction
    join: Callable[[list[T]], T]
    transfer: Callable[[BasicBlock, T], T]
    boundary: T
    initial: T


def solve(cfg: ControlFlowGraph, analysis: Analysis[T]) -> dict[int, tuple[T, T]]:
    """Run `analysis` to a fixed point over `cfg`. Standard worklist:
    seed every block, then pop, recompute `in`/`out`, and re-push affected
    neighbours only when `out` actually changes.

    Keyed by `id(block)`, not the `BasicBlock` object itself: the dataclass
    is intentionally not frozen/hashable (it holds mutable successor/
    predecessor lists built incrementally), and every block in one CFG is a
    distinct, never-recycled object for the analysis's lifetime, so
    identity is an exact and simple key.
    """
    forward = analysis.direction is Direction.FORWARD
    entry_point = cfg.entry if forward else cfg.exit

    def preds(block: BasicBlock) -> list[BasicBlock]:
        if forward:
            return block.predecessors
        return [target for target, _ in block.successors]

    def succs(block: BasicBlock) -> list[BasicBlock]:
        if forward:
            return [target for target, _ in block.successors]
        return block.predecessors

    in_of: dict[int, T] = {}
    out_of: dict[int, T] = {}
    for block in cfg.blocks:
        in_of[id(block)] = analysis.boundary if block is entry_point else analysis.initial
        out_of[id(block)] = analysis.initial

    worklist: deque[BasicBlock] = deque(cfg.blocks)
    while worklist:
        block = worklist.popleft()
        if block is entry_point:
            new_in = analysis.boundary
        else:
            incoming = [out_of[id(p)] for p in preds(block)]
            new_in = analysis.join(incoming) if incoming else analysis.initial
        in_of[id(block)] = new_in

        new_out = analysis.transfer(block, new_in)
        if new_out != out_of[id(block)]:
            out_of[id(block)] = new_out
            worklist.extend(succs(block))

    return {id(block): (in_of[id(block)], out_of[id(block)]) for block in cfg.blocks}

"""The three required data-flow analyses (A2.1-A2.3) plus the reaching-
definitions bonus, all configured through `core/dataflow.py`'s one generic
solver (D26). See `docs/program-analysis.md` for direction/lattice/
transfer/join stated explicitly per analysis (A2.4).

Gen/kill sets come entirely from `Reference.is_read`/`is_write`, recorded
during Phase 2 resolution specifically for this (D27,
`10-phase2-interfaces.md`) -- nothing here re-walks the AST to rediscover
which identifiers are reads or writes.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from clens.core.cfg import BasicBlock, ControlFlowGraph
from clens.core.dataflow import Analysis, Direction, solve
from clens.core.scopes import Scope, ScopeKind
from clens.core.symbols import Reference, Symbol, SymbolKind

if TYPE_CHECKING:
    from clens.languages.c.ast_nodes import FuncDecl
    from clens.languages.c.semantic import SemanticModel

__all__ = [
    "DataFlowResults",
    "DeadAssignment",
    "UninitializedUse",
    "analyze_function",
    "collect_local_symbols",
    "definite_assignment",
    "find_dead_assignments",
    "find_uninitialized_uses",
    "live_variables",
    "reaching_definitions",
    "unreachable_blocks",
]

_VarSet = frozenset[int]
_Def = tuple[int, int]
_DefSet = frozenset[_Def]


def collect_local_symbols(model: SemanticModel, func: FuncDecl) -> list[Symbol]:
    """Every `VARIABLE`/`PARAMETER` symbol declared inside `func`: its
    `FUNCTION` scope plus every nested `BLOCK`/`FOR_INIT` scope, found by
    walking `model.all_scopes` for the one owned by `func` rather than
    re-deriving scope membership from the AST.
    """
    root = next(
        (s for s in model.all_scopes if s.kind is ScopeKind.FUNCTION and s.owner is func),
        None,
    )
    if root is None:
        return []
    symbols: list[Symbol] = []
    _collect_scope(root, symbols)
    return symbols


def _collect_scope(scope: Scope, out: list[Symbol]) -> None:
    for symbol in scope.symbols.values():
        if symbol.kind in (SymbolKind.VARIABLE, SymbolKind.PARAMETER):
            out.append(symbol)
    for child in scope.children:
        if child.kind is not ScopeKind.STRUCT:
            _collect_scope(child, out)


def _block_for_offset(cfg: ControlFlowGraph, offset: int) -> BasicBlock | None:
    for block in cfg.blocks:
        for stmt in block.statements:
            if stmt.span.start_offset <= offset < stmt.span.end_offset:
                return block
    return None


def _references_by_block(
    cfg: ControlFlowGraph, symbols: list[Symbol]
) -> dict[int, list[tuple[Symbol, Reference]]]:
    """`id(block) -> [(symbol, reference), ...]`, in source order, for
    every reference that falls inside one of `cfg`'s blocks. A reference
    with no owning block (e.g. a parameter's own declaration, which lives
    outside the body) contributes nothing to any block's gen/kill set.
    """
    tagged: list[tuple[int, BasicBlock, Symbol, Reference]] = []
    for symbol in symbols:
        for reference in symbol.references:
            block = _block_for_offset(cfg, reference.span.start_offset)
            if block is not None:
                tagged.append((reference.span.start_offset, block, symbol, reference))
    tagged.sort(key=lambda entry: entry[0])

    by_block: dict[int, list[tuple[Symbol, Reference]]] = {id(b): [] for b in cfg.blocks}
    for _, block, symbol, reference in tagged:
        by_block[id(block)].append((symbol, reference))
    return by_block


def _union(sets: list[_VarSet]) -> _VarSet:
    result: set[int] = set()
    for s in sets:
        result |= s
    return frozenset(result)


# --- A2.1 Definite assignment: forward, must, intersection ------------------


def definite_assignment(
    cfg: ControlFlowGraph, symbols: list[Symbol]
) -> dict[int, tuple[_VarSet, _VarSet]]:
    """Forward must-analysis: the set of variables (`id(symbol)`)
    definitely assigned on entry to / exit from each block. Lattice
    `(2^Vars, superset)`; transfer `out = in | defs(b)`; join is
    intersection -- a variable only counts if it is assigned on *every*
    incoming path.
    """
    refs_by_block = _references_by_block(cfg, symbols)
    universe: _VarSet = frozenset(id(s) for s in symbols)
    # Parameters are bound by the call, not by any write Reference inside
    # the body -- they are definitely assigned from the very first block,
    # unlike a local `int x;` with no initializer.
    boundary: _VarSet = frozenset(id(s) for s in symbols if s.kind is SymbolKind.PARAMETER)

    def defs_of(block: BasicBlock) -> _VarSet:
        return frozenset(
            id(symbol) for symbol, reference in refs_by_block[id(block)] if reference.is_write
        )

    def transfer(block: BasicBlock, in_set: _VarSet) -> _VarSet:
        return in_set | defs_of(block)

    def intersection(sets: list[_VarSet]) -> _VarSet:
        result = set(sets[0])
        for s in sets[1:]:
            result &= s
        return frozenset(result)

    analysis: Analysis[_VarSet] = Analysis(
        direction=Direction.FORWARD,
        join=intersection,
        transfer=transfer,
        boundary=boundary,  # parameters only; locals start unassigned
        initial=universe,  # must-analysis: optimistic until proven otherwise
    )
    return solve(cfg, analysis)


@dataclass(slots=True, frozen=True)
class UninitializedUse:
    """A read of `symbol` at `reference` with no definite prior write on
    every path from ENTRY (A2.1's diagnostic)."""

    symbol: Symbol
    reference: Reference


def find_uninitialized_uses(cfg: ControlFlowGraph, symbols: list[Symbol]) -> list[UninitializedUse]:
    """Per-block `in` sets only capture whole-block granularity; the
    actual violation is at a specific read, so this walks each block's
    references in source order, starting from that block's `in`, to catch
    `printf(x)` after `if (c) { x = 1; }` (no prior write on the false
    path) while also catching a read-before-write *within* one block that
    the block-level fact alone wouldn't localize to a position.
    """
    in_out = definite_assignment(cfg, symbols)
    refs_by_block = _references_by_block(cfg, symbols)
    violations: list[UninitializedUse] = []
    for block in cfg.blocks:
        assigned = set(in_out[id(block)][0])
        for symbol, reference in refs_by_block[id(block)]:
            key = id(symbol)
            if reference.is_read and key not in assigned:
                violations.append(UninitializedUse(symbol=symbol, reference=reference))
            if reference.is_write:
                assigned.add(key)
    violations.sort(key=lambda v: v.reference.span.start_offset)
    return violations


# --- A2.2 Live variables: backward, may, union -------------------------------


def live_variables(
    cfg: ControlFlowGraph, symbols: list[Symbol]
) -> dict[int, tuple[_VarSet, _VarSet]]:
    """Backward may-analysis: a variable is live at a point if its current
    value may be used on some future path. Lattice `(2^Vars, subset)`;
    transfer `in = use(b) | (out - def(b))`; join is union.
    """
    refs_by_block = _references_by_block(cfg, symbols)

    def use_and_def(block: BasicBlock) -> tuple[_VarSet, _VarSet]:
        use: set[int] = set()
        defined: set[int] = set()
        for symbol, reference in refs_by_block[id(block)]:
            key = id(symbol)
            if reference.is_read and key not in defined:
                use.add(key)
            if reference.is_write:
                defined.add(key)
        return frozenset(use), frozenset(defined)

    cache = {id(b): use_and_def(b) for b in cfg.blocks}

    def transfer(block: BasicBlock, out_set: _VarSet) -> _VarSet:
        use, defined = cache[id(block)]
        return use | (out_set - defined)

    analysis: Analysis[_VarSet] = Analysis(
        direction=Direction.BACKWARD,
        join=_union,
        transfer=transfer,
        boundary=frozenset(),  # nothing live after EXIT
        initial=frozenset(),
    )
    return solve(cfg, analysis)


@dataclass(slots=True, frozen=True)
class DeadAssignment:
    """A write to `symbol` at `reference` whose value is never live
    afterward: overwritten, or never read again before the function
    returns (A6's "dead assignment" category)."""

    symbol: Symbol
    reference: Reference


def find_dead_assignments(cfg: ControlFlowGraph, symbols: list[Symbol]) -> list[DeadAssignment]:
    """Per-block `out` (live-after-block) sets are whole-block granularity;
    this walks each block's references backward from that `out`, mirroring
    the transfer at statement granularity, so a write overwritten later in
    the *same* block is caught too (`y = compute(); y = 99;` flags only
    the first write).
    """
    live = live_variables(cfg, symbols)
    refs_by_block = _references_by_block(cfg, symbols)
    dead: list[DeadAssignment] = []
    for block in cfg.blocks:
        running = set(live[id(block)][1])
        for symbol, reference in reversed(refs_by_block[id(block)]):
            key = id(symbol)
            if reference.is_write and key not in running:
                dead.append(DeadAssignment(symbol=symbol, reference=reference))
            if reference.is_read:
                running.add(key)
            elif reference.is_write:
                running.discard(key)
    dead.sort(key=lambda d: d.reference.span.start_offset)
    return dead


# --- A2.3 Unreachable code: structural, not data-flow ------------------------


def unreachable_blocks(cfg: ControlFlowGraph) -> list[BasicBlock]:
    """Every block not reachable from ENTRY by a BFS over successor edges.

    A plain "no predecessors" check is not enough: it misses a block whose
    only predecessor is itself unreachable (the classic case is
    `while(1)` with no `break` -- EXIT still has one *structural* edge
    into it from the loop's unreachable false-branch landing pad, so it
    has a predecessor, just not a reachable one). BFS from ENTRY is the
    transitive version that correctly reports EXIT as unreachable there
    (A8.1) rather than hiding it, and it still catches the simple cases
    (an orphan post-jump block `cfg_builder` deliberately leaves
    disconnected) for free.
    """
    reachable = {id(cfg.entry)}
    queue = deque([cfg.entry])
    while queue:
        block = queue.popleft()
        for target, _ in block.successors:
            if id(target) not in reachable:
                reachable.add(id(target))
                queue.append(target)
    return [block for block in cfg.blocks if id(block) not in reachable]


# --- Bonus: reaching definitions, forward, may, union ------------------------


def reaching_definitions(
    cfg: ControlFlowGraph, symbols: list[Symbol]
) -> dict[int, tuple[_DefSet, _DefSet]]:
    """Forward may-analysis over *definitions* rather than variables: a
    definition is identified by `(id(symbol), id(defining_block))`, at
    block granularity (matching the CFG's own granularity). Lattice
    `(2^Defs, subset)`; transfer `out = gen(b) | (in - kill(b))` where
    `kill(b)` is every *other* block's definition of a variable this block
    redefines; join is union.
    """
    refs_by_block = _references_by_block(cfg, symbols)

    gen_by_block: dict[int, _DefSet] = {}
    for block in cfg.blocks:
        gen_by_block[id(block)] = frozenset(
            (id(symbol), id(block))
            for symbol, reference in refs_by_block[id(block)]
            if reference.is_write
        )

    def transfer(block: BasicBlock, in_set: _DefSet) -> _DefSet:
        gen = gen_by_block[id(block)]
        redefined_vars = {var for var, _ in gen}
        survives = frozenset(
            (var, def_block)
            for var, def_block in in_set
            if var not in redefined_vars or def_block == id(block)
        )
        return gen | survives

    def union(sets: list[_DefSet]) -> _DefSet:
        result: set[_Def] = set()
        for s in sets:
            result |= s
        return frozenset(result)

    analysis: Analysis[_DefSet] = Analysis(
        direction=Direction.FORWARD,
        join=union,
        transfer=transfer,
        boundary=frozenset(),
        initial=frozenset(),
    )
    return solve(cfg, analysis)


# --- Bundling everything for one function ------------------------------------


@dataclass(slots=True)
class DataFlowResults:
    """Everything Stage 2 computes for one function's CFG."""

    definite_assignment: dict[int, tuple[_VarSet, _VarSet]] = field(default_factory=dict)
    live_variables: dict[int, tuple[_VarSet, _VarSet]] = field(default_factory=dict)
    reaching_definitions: dict[int, tuple[_DefSet, _DefSet]] = field(default_factory=dict)
    uninitialized_uses: list[UninitializedUse] = field(default_factory=list)
    dead_assignments: list[DeadAssignment] = field(default_factory=list)
    unreachable: list[BasicBlock] = field(default_factory=list)


def analyze_function(cfg: ControlFlowGraph, symbols: list[Symbol]) -> DataFlowResults:
    """Run every Stage 2 analysis for one function's CFG."""
    return DataFlowResults(
        definite_assignment=definite_assignment(cfg, symbols),
        live_variables=live_variables(cfg, symbols),
        reaching_definitions=reaching_definitions(cfg, symbols),
        uninitialized_uses=find_uninitialized_uses(cfg, symbols),
        dead_assignments=find_dead_assignments(cfg, symbols),
        unreachable=unreachable_blocks(cfg),
    )

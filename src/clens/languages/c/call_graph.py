"""Program-wide call graph (A3.1-A3.5): nodes are function *definitions*,
edges are resolved call sites, and the seven required queries are thin
wrappers over `core/graph.py`'s generic directed graph.

Virtual dispatch (A3.4) is N/A for C: no methods, no inheritance, so every
call site names exactly one candidate symbol -- there is no "callable
given the declared receiver type and class hierarchy" to compute.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from clens.core.graph import DirectedGraph
from clens.core.symbols import Symbol, SymbolKind
from clens.core.token import Span
from clens.core.visitor import walk
from clens.languages.c.ast_nodes import CallExpr, FuncDecl

if TYPE_CHECKING:
    from clens.languages.c.semantic import SemanticModel

__all__ = [
    "CallEdge",
    "CallGraph",
    "UnresolvedCall",
    "build_call_graph",
    "dead_functions",
    "recursive_functions",
]


@dataclass(slots=True, frozen=True)
class CallEdge:
    """One resolved call site: `caller` contains a `CallExpr` at `site`
    resolving to `callee`. The web UI's click-to-navigate wants the span;
    it costs nothing to keep now.
    """

    caller: str
    callee: str
    site: Span


@dataclass(slots=True, frozen=True)
class UnresolvedCall:
    """A call site resolving to a declared-but-never-defined function (a
    prototype with no matching body in this file). Not an error -- Phase 2
    already resolved the name successfully -- just a call with no node to
    point an edge at, recorded so it is still accounted for.
    """

    caller: str
    callee_name: str
    site: Span


@dataclass(slots=True)
class CallGraph:
    graph: DirectedGraph[str] = field(default_factory=DirectedGraph)
    edges: list[CallEdge] = field(default_factory=list)
    unresolved: list[UnresolvedCall] = field(default_factory=list)
    has_main: bool = False


def build_call_graph(model: SemanticModel) -> CallGraph:
    """A3.1-A3.3: one node per `FuncDecl` with a body, one edge per
    resolved call site. Reuses Phase 2's resolution rather than matching
    callee names again: a `CallExpr`'s resolved `Symbol` is found by
    matching its `callee_span` against that symbol's own recorded
    `Reference` spans (`resolver._resolve_call` stamps
    `Reference(span=expr.callee_span, ...)` on the symbol it resolved to),
    not by re-running a fresh scope lookup.
    """
    defined: dict[str, FuncDecl] = {
        decl.name: decl
        for decl in model.program.declarations
        if isinstance(decl, FuncDecl) and decl.body is not None
    }
    call_site_symbol = _call_site_symbol_index(model)

    call_graph = CallGraph(has_main="main" in defined)
    for name in defined:
        call_graph.graph.add_node(name)

    for caller_name, func in defined.items():
        for node in walk(func):
            if not isinstance(node, CallExpr):
                continue
            symbol = call_site_symbol.get(node.callee_span.start_offset)
            if symbol is None or symbol.kind is not SymbolKind.FUNCTION:
                continue  # unresolved call (already diagnosed by Phase 2)
            if symbol.name in defined:
                call_graph.graph.add_edge(caller_name, symbol.name)
                call_graph.edges.append(
                    CallEdge(caller=caller_name, callee=symbol.name, site=node.callee_span)
                )
            else:
                call_graph.unresolved.append(
                    UnresolvedCall(
                        caller=caller_name, callee_name=symbol.name, site=node.callee_span
                    )
                )
    return call_graph


def _call_site_symbol_index(model: SemanticModel) -> dict[int, Symbol]:
    index: dict[int, Symbol] = {}
    for symbols in model.symbols_by_name.values():
        for symbol in symbols:
            if symbol.kind is not SymbolKind.FUNCTION:
                continue
            for reference in symbol.references:
                index[reference.span.start_offset] = symbol
    return index


# --- A3.5's seven queries -----------------------------------------------------
# Rows 1-4 are direct wrappers over core.graph.DirectedGraph; call_graph.graph
# already carries the adjacency both ways, so nothing here re-scans edges.


def recursive_functions(call_graph: CallGraph) -> set[str]:
    """A3.5 row 5: DFS with white/grey/black colour marking, a distinct
    algorithm from SCC (row 7) even though the two overlap -- a
    single-node SCC is only actually recursive if it has a self-edge, and
    this DFS naturally makes that distinction rather than needing a
    special case bolted onto Tarjan's output.

    A grey node reached again (a "grey -> grey" edge) closes a cycle:
    every node currently on the DFS stack from that ancestor onward is
    part of it, so all of them get marked, not just the two endpoints --
    this is what makes a 3-cycle report all three members, not two.
    """
    white, gray, black = 0, 1, 2
    color: dict[str, int] = dict.fromkeys(call_graph.graph.nodes, white)
    stack: list[str] = []
    recursive: set[str] = set()

    def visit(node: str) -> None:
        color[node] = gray
        stack.append(node)
        for successor in call_graph.graph.successors(node):
            if color[successor] == white:
                visit(successor)
            elif color[successor] == gray:
                start = stack.index(successor)
                recursive.update(stack[start:])
        stack.pop()
        color[node] = black

    for node in call_graph.graph.nodes:
        if color[node] == white:
            visit(node)
    return recursive


def dead_functions(call_graph: CallGraph) -> set[str]:
    """A3.5 row 6: functions unreachable from `main`.

    If there is no `main` (a library-style file), there is no principled
    entry point to measure reachability from. Rather than declaring every
    function dead -- the file may genuinely be a library, not a mistake --
    nothing is flagged, equivalent to treating every function as its own
    root. This choice is documented in `docs/program-analysis.md`.
    """
    if not call_graph.has_main:
        return set()
    alive = {"main"} | call_graph.graph.reachable_from("main")
    return call_graph.graph.nodes - alive

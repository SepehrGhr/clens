"""A6 dead-code detection: five categories, combining the call graph, CFG
unreachability, and liveness that Stage 2/3 already computed. This module
is a thin aggregation layer over `ProgramAnalysis` (D25's whole point:
build each analysis once, reuse it everywhere) -- it introduces no new
analysis of its own.

Unreachable basic blocks and post-jump statements are, in this CFG
construction, the *same* underlying finding reported two ways: code
following an unconditional `return`/`break`/`continue` lands in a fresh,
disconnected block (`cfg_builder._build_block`), which is exactly what
"no incoming edges" (A2.3) catches. `.agents/fixtures/analysis/
dead_code.c` documents this explicitly: "the same statement, reported
structurally".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from clens.core.symbols import Symbol, SymbolKind
from clens.core.token import Span
from clens.languages.c.analyses import collect_local_symbols
from clens.languages.c.ast_nodes import FuncDecl
from clens.languages.c.call_graph import dead_functions
from clens.languages.c.cfg_builder import describe_node

if TYPE_CHECKING:
    from clens.languages.c.program_analysis import ProgramAnalysis

__all__ = [
    "DeadAssignmentFinding",
    "DeadCodeReport",
    "PostJumpStatement",
    "UnreachableBlock",
    "UnusedVariable",
    "find_dead_code",
]


@dataclass(slots=True, frozen=True)
class UnreachableBlock:
    function: str
    block_label: str


@dataclass(slots=True, frozen=True)
class PostJumpStatement:
    function: str
    text: str
    span: Span


@dataclass(slots=True, frozen=True)
class UnusedVariable:
    function: str
    symbol: Symbol


@dataclass(slots=True, frozen=True)
class DeadAssignmentFinding:
    function: str
    symbol: Symbol
    span: Span


@dataclass(slots=True)
class DeadCodeReport:
    """All five A6 categories. Unreachable/dead-assignment categories are
    **warning** severity; unused variables are **info**, matching row 13.
    """

    unreachable_functions: list[str] = field(default_factory=list)
    unreachable_blocks: list[UnreachableBlock] = field(default_factory=list)
    post_jump_statements: list[PostJumpStatement] = field(default_factory=list)
    unused_variables: list[UnusedVariable] = field(default_factory=list)
    dead_assignments: list[DeadAssignmentFinding] = field(default_factory=list)


def find_dead_code(analysis: ProgramAnalysis) -> DeadCodeReport:
    """Every category, gathered from what `analyze_program` already built:
    `analysis.call_graph` for unreachable functions, `analysis.dataflow`
    for the CFG- and liveness-based categories. Never re-runs the CFG
    builder, the call-graph builder, or the data-flow solver.
    """
    report = DeadCodeReport(unreachable_functions=sorted(dead_functions(analysis.call_graph)))

    functions_by_name = {
        decl.name: decl
        for decl in analysis.model.program.declarations
        if isinstance(decl, FuncDecl) and decl.body is not None
    }

    for name, results in analysis.dataflow.items():
        for block in results.unreachable:
            report.unreachable_blocks.append(
                UnreachableBlock(function=name, block_label=block.label())
            )
            for stmt in block.statements:
                report.post_jump_statements.append(
                    PostJumpStatement(function=name, text=describe_node(stmt), span=stmt.span)
                )

        func = functions_by_name.get(name)
        if func is not None:
            for symbol in collect_local_symbols(analysis.model, func):
                if symbol.kind is SymbolKind.VARIABLE and not symbol.is_used:
                    report.unused_variables.append(UnusedVariable(function=name, symbol=symbol))

        for dead in results.dead_assignments:
            # A symbol that is never read anywhere is already reported as
            # an unused variable; do not also double-report its one write
            # as a "dead assignment" -- that categorization is for a value
            # that *is* read, just not from this particular write (e.g. it
            # gets overwritten first).
            if dead.symbol.is_used:
                report.dead_assignments.append(
                    DeadAssignmentFinding(
                        function=name, symbol=dead.symbol, span=dead.reference.span
                    )
                )

    return report

"""`ProgramAnalysis` — the Phase 3 analysis artifact built alongside
`SemanticModel`, not inside it (D25). CFGs, the call graph, and data-flow
results all cost something to build; a `SemanticModel` consumer that never
asks for Phase 3 analysis (completion, hover, `clens check`) should never
pay for it.

`call_graph` and `dataflow` start as placeholders and are typed and filled
in as Stage 2 (data-flow) and Stage 3 (call graph) land.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from clens.languages.c.ast_nodes import FuncDecl
from clens.languages.c.cfg_builder import build_cfg

if TYPE_CHECKING:
    from clens.core.cfg import ControlFlowGraph
    from clens.languages.c.semantic import SemanticModel

__all__ = ["ProgramAnalysis", "analyze_program"]


@dataclass(slots=True)
class ProgramAnalysis:
    """Everything Phase 3 computes over one `SemanticModel`, keyed by
    function name where per-function (one file, so name is unique enough
    for this subset -- `10-phase2-interfaces.md`'s single-file-only note).
    """

    model: SemanticModel
    cfgs: dict[str, ControlFlowGraph] = field(default_factory=dict)
    call_graph: object = None
    dataflow: dict[str, object] = field(default_factory=dict)


def analyze_program(model: SemanticModel) -> ProgramAnalysis:
    """Build every Phase 3 analysis for `model`. Mirrors `analyze()`'s
    contract (D25): takes the already-built `SemanticModel`, never raises,
    never returns `None`.
    """
    cfgs: dict[str, ControlFlowGraph] = {}
    for decl in model.program.declarations:
        if isinstance(decl, FuncDecl):
            cfg = build_cfg(decl)
            if cfg is not None:
                cfgs[decl.name] = cfg
    return ProgramAnalysis(model=model, cfgs=cfgs)

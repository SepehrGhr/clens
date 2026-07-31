"""`analyze()` — the Phase 2 entry point mirroring `parser.parse()` — and
`SemanticModel`, the artifact it returns and nothing ever discards (D19,
S1.3). Completion, hover, and every later navigation feature read this
object rather than re-deriving it.

`SemanticModel` lives in `languages/c/`, not `core/`, because it embeds
`ast.Program`, a C-specific node — the same reason `resolve_type_spec` lives
in `languages/c/typecheck.py` rather than `core/types.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from clens.core.scopes import Scope
from clens.core.symbols import Symbol
from clens.languages.c.resolver import resolve
from clens.languages.c.typecheck import type_check
from clens.languages.c.usage import check_usage

if TYPE_CHECKING:
    from clens.core.diagnostics import DiagnosticCollector
    from clens.core.source import SourceFile
    from clens.core.token import Token
    from clens.languages.c.ast_nodes import Program

__all__ = ["SemanticModel", "analyze"]


@dataclass(slots=True)
class SemanticModel:
    """The result of analyzing one file: the (now type-annotated) AST, the
    scope tree, and a flat name index over it.

    `tokens` and `diagnostics` exist for `languages/c/queries.py` (Stage 5):
    completion's context detection and hover's doc-comment lookup both need
    the raw token stream (including trivia), not just the significant view
    the parser consumed, and `diagnostics_of(model)` needs a diagnostics
    collection to read from without re-running analysis.
    """

    program: Program
    global_scope: Scope
    source: SourceFile
    diagnostics: DiagnosticCollector
    all_scopes: list[Scope] = field(default_factory=list)
    symbols_by_name: dict[str, list[Symbol]] = field(default_factory=dict)
    tokens: list[Token] = field(default_factory=list)


def analyze(
    program: Program,
    source: SourceFile,
    diagnostics: DiagnosticCollector,
    tokens: list[Token] | None = None,
) -> SemanticModel:
    """Run name resolution (S2), type checking (S4), and the crude usage
    checks (S6.3) over `program`, returning the resulting `SemanticModel`.
    Mirrors `lexer.tokenize()` / `parser.parse()`: takes a
    `DiagnosticCollector` to add to, never raises, never returns `None`.

    `tokens` is optional and defaults to empty: most callers (`clens check`,
    plain semantic analysis) never need it, but a caller building a model
    for completion or hover should pass the full token stream it already
    has from `tokenize()` — `07-phase1-interfaces.md` is updated in this
    same commit to reflect the added parameter.
    """
    global_scope, all_scopes, symbols_by_name = resolve(program, source, diagnostics)
    model = SemanticModel(
        program=program,
        global_scope=global_scope,
        source=source,
        diagnostics=diagnostics,
        all_scopes=all_scopes,
        symbols_by_name=symbols_by_name,
        tokens=tokens or [],
    )
    type_check(model, source, diagnostics)
    check_usage(model, diagnostics)
    return model

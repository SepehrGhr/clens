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

if TYPE_CHECKING:
    from clens.core.diagnostics import DiagnosticCollector
    from clens.core.source import SourceFile
    from clens.languages.c.ast_nodes import Program

__all__ = ["SemanticModel", "analyze"]


@dataclass(slots=True)
class SemanticModel:
    """The result of analyzing one file: the (now type-annotated) AST, the
    scope tree, and a flat name index over it.
    """

    program: Program
    global_scope: Scope
    source: SourceFile
    all_scopes: list[Scope] = field(default_factory=list)
    symbols_by_name: dict[str, list[Symbol]] = field(default_factory=dict)


def analyze(
    program: Program, source: SourceFile, diagnostics: DiagnosticCollector
) -> SemanticModel:
    """Run name resolution (S2) then type checking (S4) over `program` and
    return the resulting `SemanticModel`. Mirrors `lexer.tokenize()` /
    `parser.parse()`: takes a `DiagnosticCollector` to add to, never raises,
    never returns `None`.
    """
    global_scope, all_scopes, symbols_by_name = resolve(program, source, diagnostics)
    model = SemanticModel(
        program=program,
        global_scope=global_scope,
        source=source,
        all_scopes=all_scopes,
        symbols_by_name=symbols_by_name,
    )
    type_check(model, source, diagnostics)
    return model

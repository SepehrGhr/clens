"""`SemanticModel` — the artifact `analyze()` (Stage 3) returns and nothing
ever discards (D19, S1.3). Completion, hover, and every later navigation
feature read this object rather than re-deriving it.

Lives in `languages/c/`, not `core/`, because it embeds `ast.Program`, a
C-specific node — the same reason `resolve_type_spec` lives in
`languages/c/typecheck.py` rather than `core/types.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from clens.core.scopes import Scope
from clens.core.symbols import Symbol

if TYPE_CHECKING:
    from clens.core.source import SourceFile
    from clens.languages.c.ast_nodes import Program

__all__ = ["SemanticModel"]


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

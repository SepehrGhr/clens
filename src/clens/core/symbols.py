"""Symbol, SymbolKind, and Reference — S1.1's nine required entry fields.

`references` and `is_used` are the fields most likely to get skipped; three
Phase 3 features (find-all-references, go-to-definition, safe rename) are
all built on `references`, so it is populated as resolution happens, not in
a later sweep.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from clens.core.token import Span
from clens.core.types import FunctionType, Type

if TYPE_CHECKING:
    from clens.core.scopes import Scope

__all__ = ["Reference", "Symbol", "SymbolKind"]


class SymbolKind(Enum):
    """C uses five of the course document's seven kinds — no CLASS or
    METHOD in this subset."""

    VARIABLE = "variable"
    FUNCTION = "function"
    PARAMETER = "parameter"
    TYPE = "type"
    FIELD = "field"


@dataclass(slots=True, frozen=True)
class Reference:
    """One use of a symbol. `is_read` and `is_write` are independent, not
    mutually exclusive: `x += 1` is both. Phase 3 liveness analysis needs
    that distinction, so it is recorded now rather than reconstructed later.
    """

    span: Span
    is_read: bool = False
    is_write: bool = False


@dataclass(slots=True)
class Symbol:
    """One declared name. All nine S1.1 fields."""

    name: str
    kind: SymbolKind
    type: Type
    scope: Scope
    definition_loc: Span
    references: list[Reference] = field(default_factory=list)
    signature: FunctionType | None = None
    is_initialized: bool = False
    is_used: bool = False

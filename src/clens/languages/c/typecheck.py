"""Bridges syntactic `TypeSpec` (what was written) to semantic `Type` (what
the checker reasons about) — D15. This lives in `languages/c/`, not
`core/types.py`, because `TypeSpec` is a C-specific node and core must never
import from a language module.
"""

from __future__ import annotations

from typing import Protocol

from clens.core.types import PointerType, PrimitiveType, Type, UnknownType
from clens.languages.c.ast_nodes import TypeSpec

__all__ = ["resolve_type_spec"]


class _HasType(Protocol):
    """What a scope's lookup result needs to expose. `core/symbols.py`'s
    real `Symbol` (Stage 2) satisfies this structurally — nothing here
    imports it, so this module has no forward dependency on Stage 2 landing
    first.
    """

    type: Type


class _ScopeLike(Protocol):
    """The minimal shape `resolve_type_spec` needs from a scope: enough to
    look up a struct tag's symbol. `core/symbols.py`'s real `Scope` (Stage 2)
    satisfies this structurally.
    """

    def lookup(self, name: str) -> _HasType | None: ...


def resolve_type_spec(spec: TypeSpec, scope: _ScopeLike) -> Type:
    """Resolve a syntactic `TypeSpec` to its semantic `Type`.

    `const` and the storage-class keyword are not modeled in `Type` at all
    in this subset — they don't affect assignability or conversion rank
    here, so they are dropped rather than wrapped.

    An unresolvable struct tag (undeclared, or the name refers to something
    else) yields `UnknownType` rather than raising or reporting a
    diagnostic itself: this is a pure query reused by hover and completion
    as well as type checking, and reporting "undefined struct" is name
    resolution's job (S3.3's "struct tag in a TypeSpec" reference), not
    this function's.
    """
    base: Type = _resolve_base(spec, scope)
    for _ in range(spec.pointer_depth):
        base = PointerType(base)
    return base


def _resolve_base(spec: TypeSpec, scope: _ScopeLike) -> Type:
    if spec.base != "struct":
        return PrimitiveType(spec.base)
    if spec.struct_name is None:
        return UnknownType()
    symbol = scope.lookup(spec.struct_name)
    if symbol is None:
        return UnknownType()
    return symbol.type

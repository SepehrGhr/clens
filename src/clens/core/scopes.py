"""Scope and ScopeKind — the scope tree (S1.2). Lookup walks inner to outer;
struct scopes are the one deliberate exception (see `Scope.lookup`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from clens.core.symbols import Symbol
from clens.core.token import Span

if TYPE_CHECKING:
    from clens.core.ast_nodes import Node

__all__ = ["Scope", "ScopeKind"]


class ScopeKind(Enum):
    """The five scope-creation points in C (see the symbol-table skill's
    table): the file, a function's parameters, a block body, a struct's
    fields, and a for-loop's init clause."""

    GLOBAL = "global"
    FUNCTION = "function"
    BLOCK = "block"
    STRUCT = "struct"
    FOR_INIT = "for_init"


@dataclass(slots=True)
class Scope:
    """One node of the scope tree. `symbols` is a plain `dict`, which is
    insertion-ordered in Python — that ordering is what `clens symbols`
    renders.
    """

    kind: ScopeKind
    parent: Scope | None
    span: Span
    children: list[Scope] = field(default_factory=list)
    symbols: dict[str, Symbol] = field(default_factory=dict)
    #: The FuncDecl / Block / StructDecl this scope belongs to. Typed as
    #: the generic core Node, not a C-specific node, since core must never
    #: import a language module.
    owner: Node | None = None

    def declare(self, symbol: Symbol) -> Symbol | None:
        """Register `symbol` in this scope.

        Returns the *existing* symbol on a name collision, so the caller
        can report a duplicate-declaration error naming both locations,
        rather than a bare bool that would throw away the first one.
        Returns `None` on a clean declaration.
        """
        existing = self.symbols.get(symbol.name)
        if existing is not None:
            return existing
        self.symbols[symbol.name] = symbol
        return None

    def lookup_local(self, name: str) -> Symbol | None:
        """Search this scope only — no outward walk."""
        return self.symbols.get(name)

    def lookup(self, name: str) -> Symbol | None:
        """Walk outward from this scope to global (S3.1).

        Struct scopes are not part of the lexical chain: a struct's fields
        are reachable only through member access, never by bare name. A
        struct scope's own symbols are still visible via `lookup_local` (or
        `lookup` called directly on it, which member-access resolution
        does), but the walk never *escalates past* one to a parent's
        siblings, and no executable scope is ever parented under one.
        """
        found = self.lookup_with_scope(name)
        return found[0] if found is not None else None

    def lookup_with_scope(self, name: str) -> tuple[Symbol, Scope] | None:
        """Like `lookup`, but also returns the scope the hit was found in
        — needed to decide whether a hit is shadowing something."""
        scope: Scope | None = self
        while scope is not None:
            hit = scope.symbols.get(name)
            if hit is not None:
                return hit, scope
            if scope.kind is ScopeKind.STRUCT:
                return None
            scope = scope.parent
        return None

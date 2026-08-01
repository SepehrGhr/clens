"""Safe rename by symbol identity (A5.1-A5.3).

The course document: *"A simple text-substitution approach is not
acceptable and will receive zero credit for this feature."* Every span
this module ever edits comes from `Symbol.definition_loc` and
`Symbol.references` -- the scope tree Phase 2 already built -- never from
scanning source text for a name. If this file ever grows a `str.replace`
or a regex over source text, that is a bug, not an optimization.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from clens.core.scopes import Scope, ScopeKind
from clens.core.symbols import Symbol, SymbolKind
from clens.core.token import Span
from clens.core.types import PointerType, StructType
from clens.core.visitor import walk
from clens.languages.c.ast_nodes import MemberExpr
from clens.languages.c.queries import goto_definition_at

if TYPE_CHECKING:
    from clens.core.source import SourceFile
    from clens.languages.c.semantic import SemanticModel

__all__ = ["RenameResult", "rename_symbol", "rename_symbol_at"]


@dataclass(slots=True, frozen=True)
class RenameResult:
    """`ok=False` means refused (a conflict, a shadow, or no symbol at the
    given position) -- `error` explains why and names the conflicting
    location where relevant. `ok=True` carries the unified diff (A5.1 step
    4) and the fully rewritten source text, ready to write out in one
    shot (step 5): every occurrence renamed, or nothing is returned at all.
    """

    ok: bool
    error: str | None = None
    diff: str = ""
    new_text: str | None = None


def rename_symbol_at(
    model: SemanticModel, source: SourceFile, offset: int, new_name: str
) -> RenameResult:
    """The cursor-driven entry point: resolve `offset` to a `Symbol` (the
    same resolution `goto_definition_at` uses) and rename it."""
    info = goto_definition_at(model, offset)
    if info is None:
        return RenameResult(ok=False, error="no symbol at the given position")
    return rename_symbol(model, source, info.symbol, new_name)


def rename_symbol(
    model: SemanticModel, source: SourceFile, symbol: Symbol, new_name: str
) -> RenameResult:
    """A5.1: conflict check, both shadow directions, then the diff. Step 1
    (resolving the cursor) is the caller's job via `rename_symbol_at` or a
    symbol already in hand from another query.
    """
    error = _check_conflict(symbol, new_name) or _check_shadowing(symbol, new_name)
    if error is not None:
        return RenameResult(ok=False, error=error)

    spans = _all_spans(model, symbol)
    new_text = _apply_renames(source.text, spans, new_name)
    diff = "".join(
        difflib.unified_diff(
            source.text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=source.filename,
            tofile=source.filename,
        )
    )
    return RenameResult(ok=True, diff=diff, new_text=new_text)


def _check_conflict(symbol: Symbol, new_name: str) -> str | None:
    """A5.1 step 2: the new name must not already exist in the *same*
    scope as `symbol`."""
    if new_name == symbol.name:
        return f"'{new_name}' is already the current name"
    existing = symbol.scope.lookup_local(new_name)
    if existing is not None and existing is not symbol:
        loc = existing.definition_loc
        return (
            f"cannot rename to '{new_name}': already declared in this scope "
            f"at {loc.line}:{loc.column}"
        )
    return None


def _check_shadowing(symbol: Symbol, new_name: str) -> str | None:
    """A5.1 step 3, both directions (A5.2 -- both are mandatory, not just
    the common half-implementation that only checks one).
    """
    would_shadow = _check_would_shadow(symbol, new_name)
    if would_shadow is not None:
        return would_shadow
    return _check_would_be_shadowed(symbol, new_name)


def _check_would_shadow(symbol: Symbol, new_name: str) -> str | None:
    """Would an *enclosing* scope's declaration of `new_name` get shadowed
    by our renamed symbol -- silently changing what an outer reference
    resolves to? Walk outward, same as `Scope.lookup`, stopping at a
    struct scope (fields are never reached by bare-name lookup).
    """
    scope: Scope | None = symbol.scope.parent
    while scope is not None:
        hit = scope.symbols.get(new_name)
        if hit is not None:
            loc = hit.definition_loc
            return (
                f"renaming to '{new_name}' would shadow the declaration at {loc.line}:{loc.column}"
            )
        if scope.kind is ScopeKind.STRUCT:
            break
        scope = scope.parent
    return None


def _check_would_be_shadowed(symbol: Symbol, new_name: str) -> str | None:
    """Would a scope *nested inside* ours already declare `new_name` --
    meaning our own renamed references inside that inner region would
    start resolving to that inner declaration instead of us? Struct
    scopes are excluded: a field is never reached by the bare-name lookup
    a rename's references go through.
    """
    for scope in _descendant_scopes(symbol.scope):
        hit = scope.symbols.get(new_name)
        if hit is not None:
            loc = hit.definition_loc
            return (
                f"renaming to '{new_name}' would be shadowed by the declaration at "
                f"{loc.line}:{loc.column}"
            )
    return None


def _descendant_scopes(scope: Scope):
    for child in scope.children:
        if child.kind is ScopeKind.STRUCT:
            continue
        yield child
        yield from _descendant_scopes(child)


def _all_spans(model: SemanticModel, symbol: Symbol) -> list[Span]:
    """Every span that must change: the declaration, plus every recorded
    reference, deduplicated by offset. A global's own declaration can
    appear as *both* `definition_loc` and a `Reference` (the initializer
    walk records a write at the same span the declaration already used),
    so applying every span blindly would rename that one spot twice.

    `Symbol.references` is never populated for a `FIELD` symbol -- member
    access resolves through type-checking against the struct's field list,
    not through the general scope-lookup path Phase 2 records references
    from (see `typecheck._member_type`) -- so a field additionally needs
    its own structural scan of `MemberExpr` sites naming it. This is not
    re-deriving read/write data that already exists; it is the one
    genuine gap Phase 2 left, and it is scoped to fields only.
    """
    spans = [symbol.definition_loc, *(r.span for r in symbol.references)]
    if symbol.kind is SymbolKind.FIELD:
        spans.extend(_field_reference_spans(model, symbol))
    seen: set[tuple[int, int]] = set()
    unique: list[Span] = []
    for span in spans:
        key = (span.start_offset, span.end_offset)
        if key not in seen:
            seen.add(key)
            unique.append(span)
    return unique


def _field_reference_spans(model: SemanticModel, symbol: Symbol) -> list[Span]:
    spans: list[Span] = []
    for node in walk(model.program):
        if not isinstance(node, MemberExpr) or node.member != symbol.name:
            continue
        obj_type = node.obj.type_annotation
        if isinstance(obj_type, PointerType):
            obj_type = obj_type.pointee
        if not isinstance(obj_type, StructType):
            continue
        struct_scope = _struct_scope_for(model, obj_type)
        if struct_scope is not None and struct_scope.lookup_local(symbol.name) is symbol:
            spans.append(node.member_span)
    return spans


def _struct_scope_for(model: SemanticModel, struct_type: StructType) -> Scope | None:
    for scope in model.all_scopes:
        if scope.kind is ScopeKind.STRUCT and scope.owner is struct_type.decl:
            return scope
    return None


def _apply_renames(text: str, spans: list[Span], new_name: str) -> str:
    """A5.1 step 5: apply right-to-left by offset so earlier spans stay
    valid as later ones change length, building the whole new text in
    memory rather than writing incrementally.
    """
    for span in sorted(spans, key=lambda s: s.start_offset, reverse=True):
        text = text[: span.start_offset] + new_name + text[span.end_offset :]
    return text

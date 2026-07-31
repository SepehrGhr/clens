"""S6.3's two crude usage diagnostics: use-before-initialization (row 12,
warning) and unused variable (row 13, info). Both are deliberately cheap
approximations — proper versions need Phase 3's CFG and definite-assignment
analysis / liveness. Documented as such in `docs/known-limitations.md`.

Runs after name resolution: everything here reads `Symbol.references` /
`is_used` / `is_initialized`, already fully populated by
`languages/c/resolver.py`. Nothing here re-walks the AST.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from clens.core.diagnostics import (
    DiagnosticCollector,
    SemanticCode,
    Severity,
    diagnostic_from_span,
)
from clens.core.scopes import ScopeKind
from clens.core.symbols import Symbol, SymbolKind
from clens.core.types import PrimitiveType

if TYPE_CHECKING:
    from clens.languages.c.semantic import SemanticModel

__all__ = ["check_usage"]


def check_usage(model: SemanticModel, diagnostics: DiagnosticCollector) -> None:
    """Row 12 and row 13 for every local variable in `model`. Parameters
    and globals are skipped for both: unused parameters are normal in C,
    and neither row is meaningful outside a function body.
    """
    for scope in model.all_scopes:
        if scope.kind is ScopeKind.GLOBAL or scope.kind is ScopeKind.STRUCT:
            continue
        for symbol in scope.symbols.values():
            if symbol.kind is not SymbolKind.VARIABLE:
                continue
            _check_unused(symbol, model, diagnostics)
            _check_use_before_init(symbol, model, diagnostics)


def _check_unused(symbol: Symbol, model: SemanticModel, diagnostics: DiagnosticCollector) -> None:
    """Row 13: no read anywhere. `is_used` is set only by a read reference
    (S3.3), so this is exactly "references contains no reads" without
    re-scanning the list.
    """
    if symbol.is_used:
        return
    diagnostics.add(
        diagnostic_from_span(
            Severity.INFO,
            f"unused variable '{symbol.name}'",
            model.source.filename,
            symbol.definition_loc,
            model.source,
            code=SemanticCode.UNUSED_VARIABLE,
        )
    )


def _check_use_before_init(
    symbol: Symbol, model: SemanticModel, diagnostics: DiagnosticCollector
) -> None:
    """Row 12: a read with no prior write in `references`' recorded order.

    References are appended in the order Pass 2 walked the AST (S3.3),
    which matches source order for straight-line code. This is exactly
    where the crude approximation shows: a write inside an `if` branch
    counts as "prior" here even though it might not execute at runtime
    (`if (c) { x = 42; } printf(x);` is the course document's own example
    of what this misses — see docs/known-limitations.md).

    Scoped to scalar primitives (`char`/`int`/`float`/`double`) only.
    Pointers, arrays, and structs are routinely "initialized" through a
    declaration with no `=` at all (`struct Point p;` then `p.x = ...`, or
    `int *p;` then `p = &n;`) — a single Reference.is_write never captures
    that for a composite type the way it does for `int x; x = 1;`, so
    flagging them here would be noise the crude approximation was never
    meant to produce.
    """
    if not isinstance(symbol.type, PrimitiveType):
        return
    seen_write = False
    for reference in symbol.references:
        if reference.is_write:
            seen_write = True
        if reference.is_read and not seen_write:
            diagnostics.add(
                diagnostic_from_span(
                    Severity.WARNING,
                    f"'{symbol.name}' may be used before being initialized",
                    model.source.filename,
                    reference.span,
                    model.source,
                    code=SemanticCode.USE_BEFORE_INITIALIZATION,
                )
            )
            return  # one diagnostic per symbol, not one per later read too

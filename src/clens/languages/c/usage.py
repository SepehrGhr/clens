"""S6.3's two usage diagnostics: use-before-initialization (row 12,
warning) and unused variable (row 13, info).

Row 12 is Phase 3's real definite-assignment analysis (A2.1, D27): a CFG is
built per function and `languages/c/analyses.find_uninitialized_uses` walks
it, replacing Phase 2's crude "no prior write anywhere earlier in
`Symbol.references`' list order" approximation, which could not tell
whether a write inside an `if` branch actually ran. Row 13 needs no CFG --
`Symbol.is_used` is already exactly "read at least once, anywhere" -- so it
is unchanged from Phase 2. See `docs/known-limitations.md`'s rewritten
entry.
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
from clens.languages.c.analyses import collect_local_symbols, find_uninitialized_uses
from clens.languages.c.ast_nodes import FuncDecl
from clens.languages.c.cfg_builder import build_cfg

if TYPE_CHECKING:
    from clens.languages.c.semantic import SemanticModel

__all__ = ["check_usage"]


def check_usage(model: SemanticModel, diagnostics: DiagnosticCollector) -> None:
    """Row 13 for every local variable in `model`, plus row 12 via a real
    definite-assignment pass over each function's CFG. Parameters and
    globals are skipped for row 13: unused parameters are normal in C, and
    it is not meaningful outside a function body.
    """
    for scope in model.all_scopes:
        if scope.kind is ScopeKind.GLOBAL or scope.kind is ScopeKind.STRUCT:
            continue
        for symbol in scope.symbols.values():
            if symbol.kind is not SymbolKind.VARIABLE:
                continue
            _check_unused(symbol, model, diagnostics)

    for decl in model.program.declarations:
        if isinstance(decl, FuncDecl) and decl.body is not None:
            _check_use_before_init(decl, model, diagnostics)


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
    func: FuncDecl, model: SemanticModel, diagnostics: DiagnosticCollector
) -> None:
    """Row 12: a read of a scalar-primitive local with no definite prior
    write on *every* path from ENTRY to that read (A2.1's real
    definite-assignment analysis), not just "somewhere earlier in
    `Symbol.references`' recorded order" -- the fix for the course
    document's own example, `if (c) { x = 42; } printf(x);`, which the
    text-order approximation could not see (docs/known-limitations.md).

    Still scoped to scalar primitives (`char`/`int`/`float`/`double`):
    pointers, arrays, and structs are routinely "initialized" through a
    declaration with no `=` at all (`struct Point p;` then `p.x = ...`, or
    `int *p;` then `p = &n;`) -- a single Reference.is_write never captures
    that for a composite type the way it does for `int x; x = 1;`, so
    flagging them would be noise this diagnostic was never meant to
    produce. That scoping choice is independent of crude-vs-real analysis
    underneath it and is kept as-is.
    """
    cfg = build_cfg(func)
    if cfg is None:
        return
    symbols = collect_local_symbols(model, func)
    violations = find_uninitialized_uses(cfg, symbols)

    reported: set[int] = set()
    for violation in violations:
        symbol = violation.symbol
        if not isinstance(symbol.type, PrimitiveType) or id(symbol) in reported:
            continue
        reported.add(id(symbol))  # one diagnostic per symbol, not one per later read too
        diagnostics.add(
            diagnostic_from_span(
                Severity.WARNING,
                f"'{symbol.name}' may be used before being initialized",
                model.source.filename,
                violation.reference.span,
                model.source,
                code=SemanticCode.USE_BEFORE_INITIALIZATION,
            )
        )

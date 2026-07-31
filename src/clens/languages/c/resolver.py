"""Two-pass name resolution (S2). Pass 1 (this file, for now) is the
declaration scan: every top-level `FuncDecl` (prototype or definition),
`StructDecl`, and `VarDecl` goes into the global scope before anything looks
at a function body. This is what makes forward calls and mutual recursion
resolve (S2.3) — Pass 2 (added next) walks bodies against an already-complete
global scope.
"""

from __future__ import annotations

from clens.core.diagnostics import (
    DiagnosticCollector,
    SemanticCode,
    Severity,
    diagnostic_from_span,
)
from clens.core.scopes import Scope, ScopeKind
from clens.core.source import SourceFile
from clens.core.symbols import Reference, Symbol, SymbolKind
from clens.core.token import Span
from clens.core.types import ArrayType, FunctionType, StructType, Type
from clens.languages.c import ast_nodes as ast
from clens.languages.c.typecheck import resolve_type_spec

__all__ = ["scan_declarations"]


def scan_declarations(
    program: ast.Program, source: SourceFile, diagnostics: DiagnosticCollector
) -> tuple[Scope, list[Scope]]:
    """Pass 1 (S2.1): populate the global scope from top-level declarations
    only. Returns the global scope and every scope created so far (struct
    scopes are created here too, since a struct's fields don't depend on any
    function body having been walked).
    """
    return _Pass1(diagnostics, source).run(program)


class _Pass1:
    def __init__(self, diagnostics: DiagnosticCollector, source: SourceFile) -> None:
        self.diagnostics = diagnostics
        self.source = source
        self.all_scopes: list[Scope] = []
        #: Function name -> name_span of the declaration that first supplied
        #: a body, so a second full definition is caught as a duplicate even
        #: when its signature matches the first (S2.1/row 8).
        self._defined_functions: dict[str, Span] = {}

    def run(self, program: ast.Program) -> tuple[Scope, list[Scope]]:
        global_scope = Scope(kind=ScopeKind.GLOBAL, parent=None, span=program.span, owner=program)
        self.all_scopes.append(global_scope)
        for decl in program.declarations:
            if isinstance(decl, ast.StructDecl):
                self._declare_struct(decl, global_scope)
            elif isinstance(decl, ast.FuncDecl):
                self._declare_func(decl, global_scope)
            elif isinstance(decl, ast.VarDecl):
                self._declare_global_var(decl, global_scope)
        return global_scope, self.all_scopes

    # ---- Declarations ---------------------------------------------------

    def _declare_struct(self, decl: ast.StructDecl, global_scope: Scope) -> None:
        struct_type = StructType(name=decl.name, decl=decl)
        symbol = Symbol(
            name=decl.name,
            kind=SymbolKind.TYPE,
            type=struct_type,
            scope=global_scope,
            definition_loc=decl.name_span,
        )
        existing = global_scope.declare(symbol)
        if existing is not None:
            self._report_duplicate(decl.name, decl.name_span, existing.definition_loc)
            return

        struct_scope = Scope(kind=ScopeKind.STRUCT, parent=global_scope, span=decl.span, owner=decl)
        global_scope.children.append(struct_scope)
        self.all_scopes.append(struct_scope)
        for f in decl.fields:
            field_type = self._resolve_type(f.type, global_scope)
            field_symbol = Symbol(
                name=f.name,
                kind=SymbolKind.FIELD,
                type=field_type,
                scope=struct_scope,
                definition_loc=f.name_span,
            )
            existing_field = struct_scope.declare(field_symbol)
            if existing_field is not None:
                self._report_duplicate(f.name, f.name_span, existing_field.definition_loc)

    def _declare_func(self, decl: ast.FuncDecl, global_scope: Scope) -> None:
        signature = FunctionType(
            params=tuple(self._param_type(p, global_scope) for p in decl.params),
            ret=self._resolve_type(decl.return_type, global_scope),
        )

        existing = global_scope.lookup_local(decl.name)
        if existing is None:
            symbol = Symbol(
                name=decl.name,
                kind=SymbolKind.FUNCTION,
                type=signature,
                scope=global_scope,
                definition_loc=decl.name_span,
                signature=signature,
            )
            global_scope.declare(symbol)
            if decl.body is not None:
                self._defined_functions[decl.name] = decl.name_span
            return

        if existing.kind is not SymbolKind.FUNCTION:
            self._report_duplicate(decl.name, decl.name_span, existing.definition_loc)
            return

        if decl.body is not None and decl.name in self._defined_functions:
            # Two full bodies for the same name - a real duplicate
            # definition, regardless of whether the signatures match.
            self._report_duplicate(decl.name, decl.name_span, self._defined_functions[decl.name])
            return

        if existing.signature != signature:
            self.diagnostics.add(
                diagnostic_from_span(
                    Severity.ERROR,
                    f"signature of '{decl.name}' does not match its prototype at "
                    f"{existing.definition_loc.line}:{existing.definition_loc.column}",
                    self.source.filename,
                    decl.name_span,
                    self.source,
                    code=SemanticCode.DUPLICATE_DECLARATION,
                )
            )
            if decl.body is not None:
                self._defined_functions[decl.name] = decl.name_span
            return

        # Matching signature: a legitimate prototype-then-definition merge,
        # or a repeated prototype. Keep the first symbol (and its
        # definition_loc) as the canonical one.
        if decl.body is not None:
            self._defined_functions[decl.name] = decl.name_span

    def _declare_global_var(self, decl: ast.VarDecl, global_scope: Scope) -> None:
        var_type = self._resolve_type(decl.type, global_scope)
        if decl.array:
            var_type = ArrayType(var_type, size=_array_size(decl.array_size))
        symbol = Symbol(
            name=decl.name,
            kind=SymbolKind.VARIABLE,
            type=var_type,
            scope=global_scope,
            definition_loc=decl.name_span,
        )
        existing = global_scope.declare(symbol)
        if existing is not None:
            self._report_duplicate(decl.name, decl.name_span, existing.definition_loc)

    # ---- Helpers ----------------------------------------------------------

    def _param_type(self, param: ast.Param, scope: Scope) -> Type:
        param_type = self._resolve_type(param.type, scope)
        if param.array:
            param_type = ArrayType(param_type, size=_array_size(param.array_size))
        return param_type

    def _resolve_type(self, spec: ast.TypeSpec, scope: Scope) -> Type:
        """`resolve_type_spec` (core, pure) for the `Type` value, plus the
        reference-recording `resolve_type_spec` deliberately leaves out
        (S3.3's "struct tag in a TypeSpec" row) — it stays a pure query so
        hover and completion can reuse it without side effects.
        """
        resolved = resolve_type_spec(spec, scope)
        if spec.base == "struct" and spec.struct_name is not None:
            span = spec.struct_name_span or spec.span
            found = scope.lookup_with_scope(spec.struct_name)
            if found is None:
                self._report_undefined(spec.struct_name, span)
            else:
                symbol, _ = found
                symbol.references.append(Reference(span=span, is_read=True))
                symbol.is_used = True
        return resolved

    def _report_duplicate(self, name: str, span: Span, existing_loc: Span) -> None:
        self.diagnostics.add(
            diagnostic_from_span(
                Severity.ERROR,
                f"'{name}' is already declared at {existing_loc.line}:{existing_loc.column}",
                self.source.filename,
                span,
                self.source,
                code=SemanticCode.DUPLICATE_DECLARATION,
            )
        )

    def _report_undefined(self, name: str, span: Span) -> None:
        self.diagnostics.add(
            diagnostic_from_span(
                Severity.ERROR,
                f"undefined symbol '{name}'",
                self.source.filename,
                span,
                self.source,
                code=SemanticCode.UNDEFINED_SYMBOL,
            )
        )


def _array_size(expr: ast.Expr | None) -> int | None:
    """Best-effort constant array size: only a bare integer literal is
    recognized. Anything else (a name, an expression) yields `None` — an
    unknown size, not a crash; this subset does no constant folding.
    """
    if isinstance(expr, ast.IntLiteral):
        return expr.value
    return None

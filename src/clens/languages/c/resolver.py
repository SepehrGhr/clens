"""Two-pass name resolution (S2). Pass 1 is the declaration scan: every
top-level `FuncDecl` (prototype or definition), `StructDecl`, and `VarDecl`
goes into the global scope before anything looks at a function body. This is
what makes forward calls and mutual recursion resolve (S2.3). Pass 2 then
walks bodies (and global initializers) against that already-complete global
scope, building the rest of the scope tree and resolving every reference.
"""

from __future__ import annotations

from clens.core.ast_nodes import ErrorExpr, ErrorStmt
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

__all__ = ["resolve", "scan_declarations"]


def scan_declarations(
    program: ast.Program, source: SourceFile, diagnostics: DiagnosticCollector
) -> tuple[Scope, list[Scope]]:
    """Pass 1 (S2.1): populate the global scope from top-level declarations
    only. Returns the global scope and every scope created so far (struct
    scopes are created here too, since a struct's fields don't depend on any
    function body having been walked).
    """
    return _Pass1(diagnostics, source).run(program)


def resolve(
    program: ast.Program, source: SourceFile, diagnostics: DiagnosticCollector
) -> tuple[Scope, list[Scope], dict[str, list[Symbol]]]:
    """Both passes (S2): the declaration scan, then the body walk that
    builds the rest of the scope tree and resolves every reference.
    Returns the global scope, every scope created, and a flat name index
    over all of them.
    """
    global_scope, all_scopes = scan_declarations(program, source, diagnostics)
    _Pass2(diagnostics, source, all_scopes).run(program, global_scope)
    return global_scope, all_scopes, _index_by_name(all_scopes)


def _index_by_name(all_scopes: list[Scope]) -> dict[str, list[Symbol]]:
    index: dict[str, list[Symbol]] = {}
    for scope in all_scopes:
        for symbol in scope.symbols.values():
            index.setdefault(symbol.name, []).append(symbol)
    return index


class _ResolverBase:
    """Shared machinery between the two passes: diagnostics/source, the
    struct-tag-aware type resolver, and the duplicate/undefined reporters.
    """

    def __init__(self, diagnostics: DiagnosticCollector, source: SourceFile) -> None:
        self.diagnostics = diagnostics
        self.source = source
        #: (id(scope), name) pairs already reported undefined, so a name
        #: used repeatedly in one scope is still exactly one diagnostic
        #: (S9.2's no-cascade rule).
        self._reported_undefined: set[tuple[int, str]] = set()

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
                self._report_undefined(spec.struct_name, span, scope)
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

    def _report_undefined(self, name: str, span: Span, scope: Scope) -> None:
        key = (id(scope), name)
        if key in self._reported_undefined:
            return
        self._reported_undefined.add(key)
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


class _Pass1(_ResolverBase):
    def __init__(self, diagnostics: DiagnosticCollector, source: SourceFile) -> None:
        super().__init__(diagnostics, source)
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


class _Pass2(_ResolverBase):
    """S2.2/S3.1-S3.3: walk function bodies and global initializers against
    the already-complete global scope from Pass 1, building the rest of the
    scope tree (function, block, for-init, and struct scopes already exist)
    and resolving every reference as it's encountered.
    """

    def __init__(
        self, diagnostics: DiagnosticCollector, source: SourceFile, all_scopes: list[Scope]
    ) -> None:
        super().__init__(diagnostics, source)
        self.all_scopes = all_scopes

    def run(self, program: ast.Program, global_scope: Scope) -> None:
        for decl in program.declarations:
            if isinstance(decl, ast.FuncDecl):
                self._resolve_func_decl(decl, global_scope)
            elif isinstance(decl, ast.VarDecl):
                self._resolve_global_var_init(decl, global_scope)
            # StructDecl: nothing left to walk - fields carry no expressions
            # in this subset.

    # ---- Declarations that open scopes -----------------------------------

    def _resolve_func_decl(self, decl: ast.FuncDecl, global_scope: Scope) -> None:
        if decl.body is None:
            return  # a prototype: nothing to walk
        function_scope = Scope(
            kind=ScopeKind.FUNCTION, parent=global_scope, span=decl.span, owner=decl
        )
        global_scope.children.append(function_scope)
        self.all_scopes.append(function_scope)
        for param in decl.params:
            self._declare_param(param, function_scope)
        # The function scope and its body Block are two scopes (a param
        # shadowed by a top-level local in the body must still warn).
        self._stmt(decl.body, function_scope)

    def _declare_param(self, param: ast.Param, function_scope: Scope) -> None:
        symbol = Symbol(
            name=param.name,
            kind=SymbolKind.PARAMETER,
            type=self._param_type(param, function_scope),
            scope=function_scope,
            definition_loc=param.name_span,
            is_initialized=True,
        )
        existing = function_scope.declare(symbol)
        if existing is not None:
            self._report_duplicate(param.name, param.name_span, existing.definition_loc)
        # No shadowing check: a parameter's only possible outer scope is
        # global, and "parameter shadows a global" is deliberately excluded.

    def _resolve_global_var_init(self, decl: ast.VarDecl, global_scope: Scope) -> None:
        if decl.init is None:
            return
        self._expr(decl.init, global_scope)
        symbol = global_scope.lookup_local(decl.name)
        if symbol is not None:
            symbol.references.append(Reference(span=decl.name_span, is_write=True))
            symbol.is_initialized = True

    def _resolve_block(self, block: ast.Block, parent_scope: Scope) -> Scope:
        scope = Scope(kind=ScopeKind.BLOCK, parent=parent_scope, span=block.span, owner=block)
        parent_scope.children.append(scope)
        self.all_scopes.append(scope)
        for item in block.body:
            self._stmt(item, scope)
        return scope

    def _resolve_for(self, node: ast.ForStmt, parent_scope: Scope) -> None:
        for_scope = Scope(kind=ScopeKind.FOR_INIT, parent=parent_scope, span=node.span, owner=node)
        parent_scope.children.append(for_scope)
        self.all_scopes.append(for_scope)
        if isinstance(node.init, list):
            for var_decl in node.init:
                self._declare_local_var(var_decl, for_scope)
        elif node.init is not None:
            self._stmt(node.init, for_scope)
        if node.condition is not None:
            self._expr(node.condition, for_scope)
        if node.update is not None:
            self._expr(node.update, for_scope)
        self._stmt(node.body, for_scope)

    def _declare_local_var(self, decl: ast.VarDecl, scope: Scope) -> None:
        # Resolve the initializer against the *current* scope before the
        # new name is declared: `int x = x;` sees the outer x, matching
        # real C scoping (a name is visible starting after its declarator).
        if decl.init is not None:
            self._expr(decl.init, scope)

        var_type = self._resolve_type(decl.type, scope)
        if decl.array:
            var_type = ArrayType(var_type, size=_array_size(decl.array_size))
        symbol = Symbol(
            name=decl.name,
            kind=SymbolKind.VARIABLE,
            type=var_type,
            scope=scope,
            definition_loc=decl.name_span,
        )
        existing = scope.declare(symbol)
        if existing is not None:
            self._report_duplicate(decl.name, decl.name_span, existing.definition_loc)
            target = existing
        else:
            self._check_shadowing(symbol, scope)
            target = symbol

        if decl.init is not None:
            target.references.append(Reference(span=decl.name_span, is_write=True))
            target.is_initialized = True

    def _check_shadowing(self, symbol: Symbol, scope: Scope) -> None:
        if symbol.kind is SymbolKind.PARAMETER or scope.parent is None:
            return
        found = scope.parent.lookup_with_scope(symbol.name)
        if found is None:
            return
        outer_symbol, _ = found
        self.diagnostics.add(
            diagnostic_from_span(
                Severity.WARNING,
                f"declaration of '{symbol.name}' shadows an outer declaration at "
                f"{outer_symbol.definition_loc.line}:{outer_symbol.definition_loc.column}",
                self.source.filename,
                symbol.definition_loc,
                self.source,
                code=SemanticCode.SHADOWED_DECLARATION,
            )
        )

    # ---- Statements ---------------------------------------------------

    def _stmt(self, stmt: ast.Stmt | ast.Decl, scope: Scope) -> None:
        if isinstance(stmt, ErrorStmt):
            return
        if isinstance(stmt, ast.Block):
            self._resolve_block(stmt, scope)
        elif isinstance(stmt, ast.VarDecl):
            self._declare_local_var(stmt, scope)
        elif isinstance(stmt, ast.IfStmt):
            self._expr(stmt.condition, scope)
            self._stmt(stmt.then_branch, scope)
            if stmt.else_branch is not None:
                self._stmt(stmt.else_branch, scope)
        elif isinstance(stmt, ast.WhileStmt):
            self._expr(stmt.condition, scope)
            self._stmt(stmt.body, scope)
        elif isinstance(stmt, ast.ForStmt):
            self._resolve_for(stmt, scope)
        elif isinstance(stmt, ast.ReturnStmt):
            if stmt.value is not None:
                self._expr(stmt.value, scope)
        elif isinstance(stmt, ast.ExprStmt):
            self._expr(stmt.expr, scope)
        # BreakStmt, ContinueStmt, EmptyStmt: nothing to resolve.

    # ---- Expressions ----------------------------------------------------

    def _expr(self, expr: ast.Expr, scope: Scope) -> None:
        if isinstance(expr, ErrorExpr):
            return
        if isinstance(expr, ast.Identifier):
            self._use(expr, scope, is_read=True, is_write=False)
        elif isinstance(expr, ast.BinaryExpr):
            self._expr(expr.left, scope)
            self._expr(expr.right, scope)
        elif isinstance(expr, ast.UnaryExpr):
            self._resolve_unary(expr, scope)
        elif isinstance(expr, ast.AssignExpr):
            self._resolve_assign(expr, scope)
        elif isinstance(expr, ast.TernaryExpr):
            self._expr(expr.condition, scope)
            self._expr(expr.then_expr, scope)
            self._expr(expr.else_expr, scope)
        elif isinstance(expr, ast.CallExpr):
            self._resolve_call(expr, scope)
        elif isinstance(expr, ast.IndexExpr):
            self._expr(expr.array, scope)
            self._expr(expr.index, scope)
        elif isinstance(expr, ast.MemberExpr):
            self._expr(expr.obj, scope)
        elif isinstance(expr, ast.SizeofExpr):
            self._resolve_sizeof(expr, scope)
        # Int/Float/String/CharLiteral: leaves, nothing to resolve.

    def _resolve_unary(self, expr: ast.UnaryExpr, scope: Scope) -> None:
        if expr.op in ("++", "--") and isinstance(expr.operand, ast.Identifier):
            self._use(expr.operand, scope, is_read=True, is_write=True)
            return
        if expr.op == "&" and isinstance(expr.operand, ast.Identifier):
            # The address escapes; treated conservatively as a write (S3.3).
            self._use(expr.operand, scope, is_read=False, is_write=True)
            return
        self._expr(expr.operand, scope)

    def _resolve_assign(self, expr: ast.AssignExpr, scope: Scope) -> None:
        self._expr(expr.value, scope)
        is_compound = expr.op != "="
        if isinstance(expr.target, ast.Identifier):
            self._use(expr.target, scope, is_read=is_compound, is_write=True)
        else:
            self._expr(expr.target, scope)

    def _resolve_call(self, expr: ast.CallExpr, scope: Scope) -> None:
        for arg in expr.args:
            self._expr(arg, scope)
        found = scope.lookup_with_scope(expr.callee)
        if found is None:
            self._report_undefined(expr.callee, expr.callee_span, scope)
            return
        symbol, _ = found
        symbol.references.append(Reference(span=expr.callee_span, is_read=True))
        symbol.is_used = True

    def _resolve_sizeof(self, expr: ast.SizeofExpr, scope: Scope) -> None:
        if isinstance(expr.target, ast.TypeSpec):
            self._resolve_type(expr.target, scope)
        else:
            self._expr(expr.target, scope)

    def _use(self, ident: ast.Identifier, scope: Scope, *, is_read: bool, is_write: bool) -> None:
        found = scope.lookup_with_scope(ident.name)
        if found is None:
            self._report_undefined(ident.name, ident.span, scope)
            return
        symbol, _ = found
        symbol.references.append(Reference(span=ident.span, is_read=is_read, is_write=is_write))
        if is_read:
            symbol.is_used = True
        if is_write:
            symbol.is_initialized = True


def _array_size(expr: ast.Expr | None) -> int | None:
    """Best-effort constant array size: only a bare integer literal is
    recognized. Anything else (a name, an expression) yields `None` — an
    unknown size, not a crash; this subset does no constant folding.
    """
    if isinstance(expr, ast.IntLiteral):
        return expr.value
    return None

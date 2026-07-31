"""Bridges syntactic `TypeSpec` (what was written) to semantic `Type` (what
the checker reasons about) — D15 — and, below that, the expression-typing
walk itself (S4.1-S4.8): `type_check()` annotates every `Expr.type_annotation`
in an already name-resolved `SemanticModel` and emits the type diagnostics.
Both live in `languages/c/`, not `core/types.py`, because they work with
C-specific nodes (`TypeSpec`, the C AST) and core must never import from a
language module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from clens.core.ast_nodes import ErrorExpr, ErrorStmt
from clens.core.diagnostics import (
    DiagnosticCollector,
    SemanticCode,
    Severity,
    diagnostic_from_span,
)
from clens.core.scopes import Scope
from clens.core.symbols import SymbolKind
from clens.core.token import Span
from clens.core.types import (
    ArrayType,
    AssignResult,
    PointerType,
    PrimitiveType,
    StructType,
    Type,
    UnknownType,
    is_assignable,
    usual_arithmetic_conversion,
)
from clens.languages.c import ast_nodes as ast
from clens.languages.c.ast_nodes import TypeSpec

if TYPE_CHECKING:
    from clens.core.source import SourceFile
    from clens.languages.c.semantic import SemanticModel

__all__ = ["resolve_type_spec", "type_check"]


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


# --- Expression typing (S4.1-S4.8) ------------------------------------------

_COMPARISON_OPS = frozenset({"==", "!=", "<", ">", "<=", ">="})
_LOGICAL_OPS = frozenset({"&&", "||"})


def type_check(model: SemanticModel, source: SourceFile, diagnostics: DiagnosticCollector) -> None:
    """Annotate every `Expr.type_annotation` in `model.program` and emit the
    S4 type diagnostics, on top of an already name-resolved `SemanticModel`
    (Stage 3's scope tree and symbols are read, never rebuilt).
    """
    _TypeChecker(model, source, diagnostics).run()


class _TypeChecker:
    def __init__(
        self, model: SemanticModel, source: SourceFile, diagnostics: DiagnosticCollector
    ) -> None:
        self.model = model
        self.source = source
        self.diagnostics = diagnostics
        #: Every scope Stage 3 built, indexed by the AST node it belongs to
        #: (a FuncDecl, a Block, a ForStmt), so this pass can find the
        #: right scope for a node without rebuilding the tree.
        self._owner_to_scope: dict[int, Scope] = {
            id(scope.owner): scope for scope in model.all_scopes if scope.owner is not None
        }

    def run(self) -> None:
        for decl in self.model.program.declarations:
            if isinstance(decl, ast.FuncDecl):
                self._check_func_decl(decl)
            elif isinstance(decl, ast.VarDecl):
                self._check_var_decl(decl, self.model.global_scope)

    # ---- Declarations -----------------------------------------------------

    def _check_func_decl(self, decl: ast.FuncDecl) -> None:
        if decl.body is None:
            return
        function_scope = self._owner_to_scope[id(decl)]
        symbol = self.model.global_scope.lookup_local(decl.name)
        return_type = (
            symbol.signature.ret if symbol is not None and symbol.signature else UnknownType()
        )
        self._stmt(decl.body, function_scope, return_type)

    def _check_var_decl(self, decl: ast.VarDecl, scope: Scope) -> None:
        if decl.init is None:
            return
        init_type = self._expr(decl.init, scope)
        symbol = scope.lookup_local(decl.name)
        if symbol is None:
            return
        self._check_assignment(symbol.type, init_type, decl.init.span)

    # ---- Statements ---------------------------------------------------

    def _stmt(self, stmt: ast.Stmt | ast.Decl, scope: Scope, return_type: Type) -> None:
        if isinstance(stmt, ErrorStmt):
            return
        if isinstance(stmt, ast.Block):
            block_scope = self._owner_to_scope[id(stmt)]
            for item in stmt.body:
                self._stmt(item, block_scope, return_type)
        elif isinstance(stmt, ast.VarDecl):
            self._check_var_decl(stmt, scope)
        elif isinstance(stmt, ast.IfStmt):
            self._expr(stmt.condition, scope)
            self._stmt(stmt.then_branch, scope, return_type)
            if stmt.else_branch is not None:
                self._stmt(stmt.else_branch, scope, return_type)
        elif isinstance(stmt, ast.WhileStmt):
            self._expr(stmt.condition, scope)
            self._stmt(stmt.body, scope, return_type)
        elif isinstance(stmt, ast.ForStmt):
            self._check_for(stmt, scope, return_type)
        elif isinstance(stmt, ast.ReturnStmt):
            self._check_return(stmt, scope, return_type)
        elif isinstance(stmt, ast.ExprStmt):
            self._expr(stmt.expr, scope)
        # BreakStmt, ContinueStmt, EmptyStmt: nothing to type.

    def _check_for(self, node: ast.ForStmt, parent_scope: Scope, return_type: Type) -> None:
        for_scope = self._owner_to_scope[id(node)]
        if isinstance(node.init, list):
            for var_decl in node.init:
                self._check_var_decl(var_decl, for_scope)
        elif node.init is not None:
            self._stmt(node.init, for_scope, return_type)
        if node.condition is not None:
            self._expr(node.condition, for_scope)
        if node.update is not None:
            self._expr(node.update, for_scope)
        self._stmt(node.body, for_scope, return_type)

    def _check_return(self, node: ast.ReturnStmt, scope: Scope, return_type: Type) -> None:
        is_void = isinstance(return_type, PrimitiveType) and return_type.name == "void"
        if node.value is None:
            if not is_void:
                self._report_error(
                    SemanticCode.RETURN_TYPE_MISMATCH,
                    "non-void function must return a value",
                    node.span,
                )
            return
        value_type = self._expr(node.value, scope)
        if is_void:
            self._report_error(
                SemanticCode.RETURN_TYPE_MISMATCH,
                "void function should not return a value",
                node.span,
            )
            return
        result = is_assignable(return_type, value_type)
        if result is AssignResult.INCOMPATIBLE:
            self._report_error(
                SemanticCode.RETURN_TYPE_MISMATCH,
                f"cannot return '{value_type}' from a function returning '{return_type}'",
                node.span,
            )
        elif result is AssignResult.NARROWING:
            self._report_warning(
                SemanticCode.NARROWING_CONVERSION,
                f"conversion from '{value_type}' to '{return_type}' may lose precision",
                node.span,
            )

    # ---- Expressions ------------------------------------------------------

    def _expr(self, expr: ast.Expr, scope: Scope) -> Type:
        result = self._compute_expr_type(expr, scope)
        expr.type_annotation = result
        return result

    def _compute_expr_type(self, expr: ast.Expr, scope: Scope) -> Type:
        if isinstance(expr, ErrorExpr):
            return UnknownType()
        if isinstance(expr, ast.IntLiteral):
            return PrimitiveType("int")
        if isinstance(expr, ast.FloatLiteral):
            return PrimitiveType("double")
        if isinstance(expr, ast.StringLiteral):
            return PointerType(PrimitiveType("char"))
        if isinstance(expr, ast.CharLiteral):
            return PrimitiveType("char")
        if isinstance(expr, ast.Identifier):
            found = scope.lookup(expr.name)
            return found.type if found is not None else UnknownType()
        if isinstance(expr, ast.BinaryExpr):
            left = self._expr(expr.left, scope)
            right = self._expr(expr.right, scope)
            return self._binary_type(expr, left, right)
        if isinstance(expr, ast.UnaryExpr):
            return self._unary_type(expr, scope)
        if isinstance(expr, ast.AssignExpr):
            return self._assign_type(expr, scope)
        if isinstance(expr, ast.TernaryExpr):
            return self._ternary_type(expr, scope)
        if isinstance(expr, ast.CallExpr):
            return self._call_type(expr, scope)
        if isinstance(expr, ast.IndexExpr):
            array_type = self._expr(expr.array, scope)
            self._expr(expr.index, scope)
            return self._index_type(array_type)
        if isinstance(expr, ast.MemberExpr):
            obj_type = self._expr(expr.obj, scope)
            return self._member_type(expr, obj_type)
        if isinstance(expr, ast.SizeofExpr):
            return self._sizeof_type(expr, scope)
        return UnknownType()  # unreachable: every Expr subtype is above

    def _binary_type(self, expr: ast.BinaryExpr, left: Type, right: Type) -> Type:
        if isinstance(left, UnknownType) or isinstance(right, UnknownType):
            return UnknownType()
        op = expr.op
        if op in _COMPARISON_OPS or op in _LOGICAL_OPS:
            return PrimitiveType("int")
        if op in ("+", "-"):
            if op == "-" and isinstance(left, PointerType) and isinstance(right, PointerType):
                return PrimitiveType("int")
            if isinstance(left, PointerType) and _is_integral(right):
                return left
            if op == "+" and isinstance(right, PointerType) and _is_integral(left):
                return right
            if _is_numeric(left) and _is_numeric(right):
                return usual_arithmetic_conversion(left, right)
            return UnknownType()
        if op in ("*", "/", "%") and _is_numeric(left) and _is_numeric(right):
            return usual_arithmetic_conversion(left, right)
        return UnknownType()

    def _unary_type(self, expr: ast.UnaryExpr, scope: Scope) -> Type:
        operand_type = self._expr(expr.operand, scope)
        if isinstance(operand_type, UnknownType):
            return UnknownType()
        if expr.op == "&":
            return PointerType(operand_type)
        if expr.op == "*":
            return operand_type.pointee if isinstance(operand_type, PointerType) else UnknownType()
        if expr.op == "!":
            return PrimitiveType("int")
        if expr.op in ("-", "~", "++", "--"):
            return operand_type
        return UnknownType()  # unreachable: every unary op is above

    def _assign_type(self, expr: ast.AssignExpr, scope: Scope) -> Type:
        target_type = self._expr(expr.target, scope)
        value_type = self._expr(expr.value, scope)
        self._check_assignment(target_type, value_type, expr.span)
        return target_type

    def _ternary_type(self, expr: ast.TernaryExpr, scope: Scope) -> Type:
        self._expr(expr.condition, scope)
        then_type = self._expr(expr.then_expr, scope)
        else_type = self._expr(expr.else_expr, scope)
        if isinstance(then_type, UnknownType) or isinstance(else_type, UnknownType):
            return UnknownType()
        if then_type == else_type:
            return then_type
        if _is_numeric(then_type) and _is_numeric(else_type):
            return usual_arithmetic_conversion(then_type, else_type)
        self._report_error(
            SemanticCode.TERNARY_TYPE_MISMATCH,
            f"mismatched types in conditional expression: '{then_type}' and '{else_type}'",
            expr.span,
        )
        return UnknownType()

    def _call_type(self, expr: ast.CallExpr, scope: Scope) -> Type:
        arg_types = [self._expr(arg, scope) for arg in expr.args]
        found = scope.lookup(expr.callee)
        if found is None:
            return UnknownType()  # already reported undefined in Stage 3
        if found.kind is not SymbolKind.FUNCTION or found.signature is None:
            self._report_error(
                SemanticCode.NOT_CALLABLE, f"'{expr.callee}' is not a function", expr.callee_span
            )
            return UnknownType()
        signature = found.signature
        if len(arg_types) != len(signature.params):
            self._report_error(
                SemanticCode.ARGUMENT_COUNT_MISMATCH,
                f"expected {len(signature.params)} argument(s), got {len(arg_types)}",
                expr.span,
            )
            return signature.ret  # arity is wrong; skip per-argument checks (no cascade)
        for i, (arg_type, param_type, arg_node) in enumerate(
            zip(arg_types, signature.params, expr.args, strict=True), start=1
        ):
            result = is_assignable(param_type, arg_type)
            if result is AssignResult.INCOMPATIBLE:
                self._report_error(
                    SemanticCode.CALL_TYPE_MISMATCH,
                    f"argument {i}: expected '{param_type}', got '{arg_type}'",
                    arg_node.span,
                )
            elif result is AssignResult.NARROWING:
                self._report_warning(
                    SemanticCode.NARROWING_CONVERSION,
                    f"argument {i}: conversion from '{arg_type}' to '{param_type}' may lose"
                    " precision",
                    arg_node.span,
                )
        return signature.ret

    def _index_type(self, array_type: Type) -> Type:
        if isinstance(array_type, UnknownType):
            return UnknownType()
        if isinstance(array_type, ArrayType):
            return array_type.element
        if isinstance(array_type, PointerType):
            return array_type.pointee
        # Indexing something that is neither: not one of S4's required
        # rows, so this degrades to unknown rather than inventing a
        # diagnostic beyond what was asked for.
        return UnknownType()

    def _member_type(self, expr: ast.MemberExpr, obj_type: Type) -> Type:
        if isinstance(obj_type, UnknownType):
            return UnknownType()
        if expr.arrow:
            if not isinstance(obj_type, PointerType):
                self._report_error(
                    SemanticCode.BAD_MEMBER_ACCESS,
                    "arrow on non-pointer; did you mean '.'?",
                    expr.member_span,
                )
                return UnknownType()
            target = obj_type.pointee
        else:
            if isinstance(obj_type, PointerType):
                self._report_error(
                    SemanticCode.BAD_MEMBER_ACCESS,
                    "member access on pointer; did you mean '->'?",
                    expr.member_span,
                )
                return UnknownType()
            target = obj_type
        if not isinstance(target, StructType):
            return UnknownType()
        field_type = self._field_type(target, expr.member)
        if field_type is None:
            self._report_error(
                SemanticCode.BAD_MEMBER_ACCESS,
                f"struct '{target.name}' has no field '{expr.member}'",
                expr.member_span,
            )
            return UnknownType()
        return field_type

    def _field_type(self, struct_type: StructType, name: str) -> Type | None:
        struct_scope = self._owner_to_scope.get(id(struct_type.decl))
        if struct_scope is None:
            return None
        field_symbol = struct_scope.lookup_local(name)
        return field_symbol.type if field_symbol is not None else None

    def _sizeof_type(self, expr: ast.SizeofExpr, scope: Scope) -> Type:
        if isinstance(expr.target, ast.Expr):
            self._expr(expr.target, scope)
        return PrimitiveType("int")

    # ---- Shared assignability check ----------------------------------------

    def _check_assignment(self, target: Type, source: Type, span: Span) -> None:
        result = is_assignable(target, source)
        if result is AssignResult.INCOMPATIBLE:
            self._report_error(
                SemanticCode.ASSIGNMENT_TYPE_MISMATCH,
                f"cannot assign '{source}' to '{target}'",
                span,
            )
        elif result is AssignResult.NARROWING:
            self._report_warning(
                SemanticCode.NARROWING_CONVERSION,
                f"conversion from '{source}' to '{target}' may lose precision",
                span,
            )

    # ---- Diagnostics --------------------------------------------------

    def _report_error(self, code: str, message: str, span: Span) -> None:
        self.diagnostics.add(
            diagnostic_from_span(
                Severity.ERROR, message, self.source.filename, span, self.source, code=code
            )
        )

    def _report_warning(self, code: str, message: str, span: Span) -> None:
        self.diagnostics.add(
            diagnostic_from_span(
                Severity.WARNING, message, self.source.filename, span, self.source, code=code
            )
        )


def _is_numeric(t: Type) -> bool:
    return isinstance(t, PrimitiveType) and t.name != "void"


def _is_integral(t: Type) -> bool:
    return isinstance(t, PrimitiveType) and t.name in ("char", "int")

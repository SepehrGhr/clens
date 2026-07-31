"""C AST node inventory (R4.1): one dataclass per grammar production in
`docs/grammar.ebnf`. Node names that the course document names explicitly —
`BinaryExpr`, `IfStmt`, `FuncDecl`, `CallExpr`, `ReturnStmt` — use exactly
those names. The rest follow the same convention, cross-checked against the
node inventory in pycparser's `_c_ast.cfg` (adapted, not copied — see
`.agents/skills/pycparser-reference/SKILL.md`).

All subclasses use `kw_only=True`: `Expr` already gives every expression a
`type_annotation` field with a default (`None`), and Python dataclasses
require every field after a defaulted one to also have a default *unless* it
is keyword-only. Keyword-only construction also reads better at call sites
with four or five fields (`BinaryExpr(span=s, op="+", left=a, right=b)`).

`CallExpr.callee` is a plain `str`, not a nested `Identifier` node: this
subset only allows calling a bare identifier (`f(...)`, never `(*fp)(...)`),
so there is no callee sub-expression to model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

from clens.core.ast_nodes import Decl, Expr, Node, Stmt
from clens.core.token import Span

__all__ = [
    "AssignExpr",
    "Block",
    "BinaryExpr",
    "BreakStmt",
    "CallExpr",
    "CharLiteral",
    "ContinueStmt",
    "EmptyStmt",
    "ExprStmt",
    "Field",
    "FloatLiteral",
    "ForStmt",
    "FuncDecl",
    "Identifier",
    "IfStmt",
    "IndexExpr",
    "IntLiteral",
    "MemberExpr",
    "Param",
    "Program",
    "ReturnStmt",
    "SizeofExpr",
    "StringLiteral",
    "StructDecl",
    "TernaryExpr",
    "TypeSpec",
    "UnaryExpr",
    "VarDecl",
    "WhileStmt",
]


# --- Types and program structure --------------------------------------------


@dataclass(slots=True, kw_only=True)
class TypeSpec(Node):
    """A syntactic type as written in source: base type, pointer depth,
    `struct` tag, `const`, and storage-class keyword. Not a semantic type —
    that is Phase 2's `Type`, referenced by `Expr.type_annotation`.
    """

    base: str  # "void" | "char" | "int" | "float" | "double" | "struct"
    struct_name: str | None = None
    #: Span of just the struct tag token (e.g. 'Point' in 'struct Point');
    #: None unless base == "struct". The highlighter needs this to color
    #: the tag as a type reference — to the lexer it's a plain IDENT.
    struct_name_span: Span | None = None
    pointer_depth: int = 0
    is_const: bool = False
    storage: str | None = None  # "static" | "extern" | "volatile" | "register"

    INLINE_FIELDS: ClassVar[tuple[str, ...]] = (
        "base",
        "struct_name",
        "pointer_depth",
        "is_const",
        "storage",
    )


@dataclass(slots=True, kw_only=True)
class Field(Node):
    """One member of a `struct` field list."""

    type: TypeSpec
    name: str
    #: Span of just the `name` token, distinct from `span` (the whole
    #: field declaration) — the highlighter needs to color the name alone.
    name_span: Span

    INLINE_FIELDS: ClassVar[tuple[str, ...]] = ("name",)


@dataclass(slots=True, kw_only=True)
class Program(Node):
    """The whole translation unit: top-level declarations in source order."""

    declarations: list[Decl] = field(default_factory=list)


# --- Declarations ------------------------------------------------------------


@dataclass(slots=True, kw_only=True)
class FuncDecl(Decl):
    """A function prototype (`body is None`) or definition."""

    return_type: TypeSpec
    name: str
    #: Span of just the `name` token — see `Field.name_span`.
    name_span: Span
    params: list[Param] = field(default_factory=list)
    body: Block | None = None

    INLINE_FIELDS: ClassVar[tuple[str, ...]] = ("name",)


@dataclass(slots=True, kw_only=True)
class Param(Decl):
    """One function parameter."""

    type: TypeSpec
    name: str
    name_span: Span
    array: bool = False
    array_size: Expr | None = None

    INLINE_FIELDS: ClassVar[tuple[str, ...]] = ("name",)


@dataclass(slots=True, kw_only=True)
class VarDecl(Decl):
    """One variable declarator. `int a = 1, b, c = 3;` is three sibling
    `VarDecl` nodes sharing no wrapper node — see `Block.body`.
    """

    type: TypeSpec
    name: str
    name_span: Span
    array: bool = False
    array_size: Expr | None = None
    init: Expr | None = None

    INLINE_FIELDS: ClassVar[tuple[str, ...]] = ("name",)


@dataclass(slots=True, kw_only=True)
class StructDecl(Decl):
    """A `struct` type declaration with its field list."""

    name: str
    name_span: Span
    fields: list[Field] = field(default_factory=list)

    INLINE_FIELDS: ClassVar[tuple[str, ...]] = ("name",)


# --- Statements ---------------------------------------------------------------


@dataclass(slots=True, kw_only=True)
class Block(Stmt):
    """A `{ ... }` compound statement. Declarations and statements may be
    interleaved, so `body` holds both.
    """

    body: list[Stmt | Decl] = field(default_factory=list)


@dataclass(slots=True, kw_only=True)
class IfStmt(Stmt):
    condition: Expr
    then_branch: Stmt
    else_branch: Stmt | None = None


@dataclass(slots=True, kw_only=True)
class WhileStmt(Stmt):
    condition: Expr
    body: Stmt


@dataclass(slots=True, kw_only=True)
class ForStmt(Stmt):
    # A declaration init clause (`for (int i = 0, j = 9; ...)`) can expand
    # to more than one sibling VarDecl, same as any other declarator list.
    init: Stmt | list[VarDecl] | None = None
    condition: Expr | None = None
    update: Expr | None = None
    body: Stmt


@dataclass(slots=True, kw_only=True)
class ReturnStmt(Stmt):
    value: Expr | None = None


@dataclass(slots=True, kw_only=True)
class BreakStmt(Stmt):
    pass


@dataclass(slots=True, kw_only=True)
class ContinueStmt(Stmt):
    pass


@dataclass(slots=True, kw_only=True)
class ExprStmt(Stmt):
    expr: Expr


@dataclass(slots=True, kw_only=True)
class EmptyStmt(Stmt):
    """The bare `;` statement."""


# --- Expressions ---------------------------------------------------------------


@dataclass(slots=True, kw_only=True)
class Identifier(Expr):
    name: str

    INLINE_FIELDS: ClassVar[tuple[str, ...]] = ("name",)
    SHOW_LOC: ClassVar[bool] = True


@dataclass(slots=True, kw_only=True)
class IntLiteral(Expr):
    value: int

    INLINE_FIELDS: ClassVar[tuple[str, ...]] = ("value",)
    SHOW_LOC: ClassVar[bool] = True


@dataclass(slots=True, kw_only=True)
class FloatLiteral(Expr):
    value: float

    INLINE_FIELDS: ClassVar[tuple[str, ...]] = ("value",)
    SHOW_LOC: ClassVar[bool] = True


@dataclass(slots=True, kw_only=True)
class StringLiteral(Expr):
    value: str

    INLINE_FIELDS: ClassVar[tuple[str, ...]] = ("value",)
    SHOW_LOC: ClassVar[bool] = True


@dataclass(slots=True, kw_only=True)
class CharLiteral(Expr):
    value: str

    INLINE_FIELDS: ClassVar[tuple[str, ...]] = ("value",)
    SHOW_LOC: ClassVar[bool] = True


@dataclass(slots=True, kw_only=True)
class BinaryExpr(Expr):
    op: str
    left: Expr
    right: Expr

    INLINE_FIELDS: ClassVar[tuple[str, ...]] = ("op",)


@dataclass(slots=True, kw_only=True)
class UnaryExpr(Expr):
    """Covers `-x !x &x *x ~x ++x --x` (`prefix=True`) and postfix `x++ x--`
    (`prefix=False`) — one node, since they differ only in fixity, not
    structure.
    """

    op: str
    operand: Expr
    prefix: bool = True

    INLINE_FIELDS: ClassVar[tuple[str, ...]] = ("op", "prefix")


@dataclass(slots=True, kw_only=True)
class AssignExpr(Expr):
    op: str  # "=" | "+=" | "-=" | "*=" | "/=" | "%="
    target: Expr
    value: Expr

    INLINE_FIELDS: ClassVar[tuple[str, ...]] = ("op",)


@dataclass(slots=True, kw_only=True)
class TernaryExpr(Expr):
    condition: Expr
    then_expr: Expr
    else_expr: Expr


@dataclass(slots=True, kw_only=True)
class CallExpr(Expr):
    callee: str
    args: list[Expr] = field(default_factory=list)

    INLINE_FIELDS: ClassVar[tuple[str, ...]] = ("callee",)
    SHOW_LOC: ClassVar[bool] = True


@dataclass(slots=True, kw_only=True)
class IndexExpr(Expr):
    """`array[index]`."""

    array: Expr
    index: Expr


@dataclass(slots=True, kw_only=True)
class MemberExpr(Expr):
    """`obj.member` (`arrow=False`) or `obj->member` (`arrow=True`)."""

    obj: Expr
    member: str
    arrow: bool = False

    INLINE_FIELDS: ClassVar[tuple[str, ...]] = ("member", "arrow")


@dataclass(slots=True, kw_only=True)
class SizeofExpr(Expr):
    """`sizeof(type)` or `sizeof expr` — exactly one of the two is set."""

    target: TypeSpec | Expr

"""AST-driven syntax highlighter for C (R5.1). Two passes:

**Pass 1** (`_default_categories`) assigns an obvious category from each
token's own type/lexeme — this is everything a token-only highlighter could
ever do, and by itself is *not* sufficient (R5.1): it cannot tell a function
call's callee from a bare variable reference, since both are just IDENT
tokens to the lexer. `factorial(n)` and `int x = factorial;` lex identically
at the callee/variable position.

**Pass 2** (`_UpgradeVisitor`) walks the AST and upgrades specific identifier
tokens using context only the parse tree has: a `CallExpr`'s callee is a
function reference, a `FuncDecl`'s name is being defined as a function, a
`struct` tag is a type reference. Pass 2 only ever overwrites Pass 1, never
the reverse.
"""

from __future__ import annotations

from clens.core.highlight import Category, HighlightMap
from clens.core.token import Span, Token, TokenType
from clens.core.visitor import NodeVisitor
from clens.languages.c import ast_nodes as ast
from clens.languages.c.parser import BASE_TYPE_KEYWORDS

__all__ = ["highlight"]


def highlight(tokens: list[Token], program: ast.Program) -> HighlightMap:
    """Build the `token_index -> Category` map for `tokens`/`program`, which
    must come from the same parse of the same `SourceFile`. `tokens` is the
    *full* list including trivia (comments, whitespace) — see
    `core.token.iter_significant` for the filtered view the parser uses.

    Never raises: a program with parse errors still highlights everything
    that did parse, via Pass 1 defaults for the rest (see
    `.agents/skills/highlighter/SKILL.md`, "a file that fails to parse still
    highlights").
    """
    highlight_map = _default_categories(tokens)
    offset_index = {token.start_offset: index for index, token in enumerate(tokens)}
    _UpgradeVisitor(highlight_map, offset_index).visit(program)
    return highlight_map


def _default_categories(tokens: list[Token]) -> HighlightMap:
    """Pass 1: category from token type/lexeme alone."""
    highlight_map: HighlightMap = {}
    for index, token in enumerate(tokens):
        category = _default_category(token)
        if category is not None:
            highlight_map[index] = category
    return highlight_map


def _default_category(token: Token) -> Category | None:
    if token.type is TokenType.KEYWORD:
        # Base-type keywords (int, float, ...) are Category.TYPE; every
        # other keyword (if, return, static, sizeof, ...) is Category.KEYWORD.
        return Category.TYPE if token.lexeme in BASE_TYPE_KEYWORDS else Category.KEYWORD
    if token.type is TokenType.IDENT:
        return Category.VARIABLE  # neutral default; Pass 2 upgrades some
    if token.type is TokenType.INT_LIT or token.type is TokenType.FLOAT_LIT:
        return Category.NUMBER
    if token.type is TokenType.STRING_LIT or token.type is TokenType.CHAR_LIT:
        return Category.STRING
    if token.type is TokenType.OPERATOR:
        return Category.OPERATOR
    if token.type is TokenType.LINE_COMMENT or token.type is TokenType.BLOCK_COMMENT:
        return Category.COMMENT
    if token.type is TokenType.PREPROC:
        return Category.PREPROCESSOR
    if token.type is TokenType.INVALID:
        return Category.ERROR
    return None  # DELIMITER, WHITESPACE, EOF: no styling needed


class _UpgradeVisitor(NodeVisitor):
    """Pass 2. Every `visit_*` here ends with `generic_visit` so the walk
    still reaches every descendant — upgrading a node's own tokens must
    never stop its children from being visited.
    """

    def __init__(self, highlight_map: HighlightMap, offset_index: dict[int, int]) -> None:
        self._map = highlight_map
        self._offset_index = offset_index

    def _upgrade(self, span: Span, category: Category) -> None:
        index = self._offset_index.get(span.start_offset)
        if index is not None:
            self._map[index] = category

    def _upgrade_type_spec(self, type_spec: ast.TypeSpec) -> None:
        # Plain base types (int, float, ...) are already Category.TYPE from
        # Pass 1, since they're KEYWORD tokens in BASE_TYPE_KEYWORDS. Only
        # struct tags need AST context: to the lexer, 'Point' in
        # 'struct Point' is just another IDENT.
        if type_spec.base == "struct" and type_spec.struct_name_span is not None:
            self._upgrade(type_spec.struct_name_span, Category.TYPE_NAME)

    def visit_CallExpr(self, node: ast.CallExpr) -> None:
        self._upgrade(node.span, Category.FUNCTION)  # span starts at the callee token
        self.generic_visit(node)

    def visit_FuncDecl(self, node: ast.FuncDecl) -> None:
        self._upgrade(node.name_span, Category.FUNCTION)
        self._upgrade_type_spec(node.return_type)
        self.generic_visit(node)

    def visit_VarDecl(self, node: ast.VarDecl) -> None:
        self._upgrade_type_spec(node.type)
        self.generic_visit(node)

    def visit_Param(self, node: ast.Param) -> None:
        self._upgrade_type_spec(node.type)
        self.generic_visit(node)

    def visit_Field(self, node: ast.Field) -> None:
        self._upgrade_type_spec(node.type)
        self.generic_visit(node)

    def visit_StructDecl(self, node: ast.StructDecl) -> None:
        self._upgrade(node.name_span, Category.TYPE_NAME)
        self.generic_visit(node)

    def visit_SizeofExpr(self, node: ast.SizeofExpr) -> None:
        if isinstance(node.target, ast.TypeSpec):
            self._upgrade_type_spec(node.target)
        self.generic_visit(node)

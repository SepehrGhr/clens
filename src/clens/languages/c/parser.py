"""Recursive-descent parser for the C subset (R3.1-R3.5): one function per
non-terminal in `docs/grammar.ebnf`, named identically (`parse_<name>` for
`<name>`). Built bottom-up in the same order as the grammar file: expressions
first (this commit), then statements, then declarations and the program
entry point.

Expression precedence cascade, lowest to highest binding, exactly matching
`docs/grammar.ebnf`:

    assignment -> ternary -> logical_or -> logical_and -> equality
    -> relational -> additive -> multiplicative -> unary -> postfix -> primary

Every binary level is a loop (`_parse_left_assoc_binary`), not recursion on
the left — that is what keeps the grammar left-recursion-free (R2.2) and
gives left associativity. Assignment and the ternary recurse on the
right-hand side instead, for right associativity.
"""

from __future__ import annotations

from clens.core.ast_nodes import join
from clens.core.parser_base import ParserBase
from clens.core.token import TokenType
from clens.languages.c import ast_nodes as ast

_ASSIGN_OPS = frozenset({"=", "+=", "-=", "*=", "/=", "%="})
_EQUALITY_OPS = frozenset({"==", "!="})
_RELATIONAL_OPS = frozenset({"<", ">", "<=", ">="})
_ADDITIVE_OPS = frozenset({"+", "-"})
_MULTIPLICATIVE_OPS = frozenset({"*", "/", "%"})
_UNARY_PREFIX_OPS = frozenset({"-", "!", "&", "*", "~", "++", "--"})
_POSTFIX_INCDEC_OPS = frozenset({"++", "--"})
_MEMBER_OPS = frozenset({".", "->"})

#: Keywords that start a type-spec — shared with declaration parsing (added
#: in a later commit) and with sizeof's type-vs-expression disambiguation.
BASE_TYPE_KEYWORDS = frozenset({"void", "char", "int", "float", "double"})
STORAGE_KEYWORDS = frozenset({"static", "extern", "volatile", "register"})
_TYPE_START_KEYWORDS = BASE_TYPE_KEYWORDS | STORAGE_KEYWORDS | {"struct", "const"}


def _is_type_start(token) -> bool:
    return token.type is TokenType.KEYWORD and token.lexeme in _TYPE_START_KEYWORDS


def _parse_int_literal(lexeme: str) -> int:
    text = lexeme.rstrip("uUlL")
    if text[:2] in ("0x", "0X"):
        return int(text, 16)
    if text[:2] in ("0b", "0B"):
        return int(text[2:], 2)
    if text.startswith("0") and len(text) > 1:
        return int(text, 8)
    return int(text, 10)


def _parse_float_literal(lexeme: str) -> float:
    return float(lexeme.rstrip("FfLl"))


def _unquote(lexeme: str, quote: str) -> str:
    """Strip the surrounding quote characters. Tolerates an unterminated
    literal (from lexer recovery, R1.6) missing its closing quote.
    """
    body = lexeme[1:]
    if body.endswith(quote) and body != quote:
        body = body[:-1]
    return body


class Parser(ParserBase):
    """Parses a significant-token view (see `core.token.iter_significant`)
    of a C source file. Statement and declaration parsing, and the
    `parse()` entry point, are added by later commits in this same class.
    """

    # ---- Expressions (lowest to highest precedence) -----------------------

    def parse_expression(self) -> ast.Expr:
        return self.parse_assignment_expr()

    def parse_assignment_expr(self) -> ast.Expr:
        left = self.parse_ternary_expr()
        if self.check(TokenType.OPERATOR) and self.peek().lexeme in _ASSIGN_OPS:
            op_token = self.advance()
            value = self.parse_assignment_expr()  # right-associative
            return ast.AssignExpr(
                span=join(left.span, value.span), op=op_token.lexeme, target=left, value=value
            )
        return left

    def parse_ternary_expr(self) -> ast.Expr:
        condition = self.parse_logical_or_expr()
        if self.match_lexeme("?"):
            then_expr = self.parse_expression()
            self.expect(TokenType.OPERATOR, ":", "in ternary expression")
            else_expr = self.parse_assignment_expr()  # right-associative
            return ast.TernaryExpr(
                span=join(condition.span, else_expr.span),
                condition=condition,
                then_expr=then_expr,
                else_expr=else_expr,
            )
        return condition

    def _parse_left_assoc_binary(self, operand, ops: frozenset[str]) -> ast.Expr:
        left = operand()
        while self.check(TokenType.OPERATOR) and self.peek().lexeme in ops:
            op_token = self.advance()
            right = operand()
            left = ast.BinaryExpr(
                span=join(left.span, right.span), op=op_token.lexeme, left=left, right=right
            )
        return left

    def parse_logical_or_expr(self) -> ast.Expr:
        return self._parse_left_assoc_binary(self.parse_logical_and_expr, frozenset({"||"}))

    def parse_logical_and_expr(self) -> ast.Expr:
        return self._parse_left_assoc_binary(self.parse_equality_expr, frozenset({"&&"}))

    def parse_equality_expr(self) -> ast.Expr:
        return self._parse_left_assoc_binary(self.parse_relational_expr, _EQUALITY_OPS)

    def parse_relational_expr(self) -> ast.Expr:
        return self._parse_left_assoc_binary(self.parse_additive_expr, _RELATIONAL_OPS)

    def parse_additive_expr(self) -> ast.Expr:
        return self._parse_left_assoc_binary(self.parse_multiplicative_expr, _ADDITIVE_OPS)

    def parse_multiplicative_expr(self) -> ast.Expr:
        return self._parse_left_assoc_binary(self.parse_unary_expr, _MULTIPLICATIVE_OPS)

    def parse_unary_expr(self) -> ast.Expr:
        if self.check(TokenType.KEYWORD) and self.peek().lexeme == "sizeof":
            return self._parse_sizeof_expr()
        if self.check(TokenType.OPERATOR) and self.peek().lexeme in _UNARY_PREFIX_OPS:
            op_token = self.advance()
            operand = self.parse_unary_expr()
            return ast.UnaryExpr(
                span=join(op_token.span, operand.span),
                op=op_token.lexeme,
                operand=operand,
                prefix=True,
            )
        return self.parse_postfix_expr()

    def _parse_sizeof_expr(self) -> ast.Expr:
        sizeof_token = self.advance()  # "sizeof"
        if (
            self.check(TokenType.DELIMITER)
            and self.peek().lexeme == "("
            and _is_type_start(self.peek(1))
        ):
            self.advance()  # "("
            type_spec = self.parse_type_spec()
            close = self.expect(TokenType.DELIMITER, ")", "to close sizeof type")
            return ast.SizeofExpr(span=join(sizeof_token.span, close.span), target=type_spec)
        operand = self.parse_unary_expr()
        return ast.SizeofExpr(span=join(sizeof_token.span, operand.span), target=operand)

    def parse_postfix_expr(self) -> ast.Expr:
        expr = self.parse_primary_expr()
        while True:
            if (
                self.check(TokenType.DELIMITER)
                and self.peek().lexeme == "("
                and isinstance(expr, ast.Identifier)
            ):
                expr = self._parse_call(expr)
            elif self.check(TokenType.DELIMITER) and self.peek().lexeme == "[":
                expr = self._parse_index(expr)
            elif self.check(TokenType.OPERATOR) and self.peek().lexeme in _MEMBER_OPS:
                expr = self._parse_member(expr)
            elif self.check(TokenType.OPERATOR) and self.peek().lexeme in _POSTFIX_INCDEC_OPS:
                op_token = self.advance()
                expr = ast.UnaryExpr(
                    span=join(expr.span, op_token.span),
                    op=op_token.lexeme,
                    operand=expr,
                    prefix=False,
                )
            else:
                return expr

    def _parse_call(self, callee: ast.Identifier) -> ast.CallExpr:
        self.advance()  # "("
        args: list[ast.Expr] = []
        if not (self.check(TokenType.DELIMITER) and self.peek().lexeme == ")"):
            args.append(self.parse_assignment_expr())
            while self.match_lexeme(","):
                args.append(self.parse_assignment_expr())
        close = self.expect(TokenType.DELIMITER, ")", "to close argument list")
        return ast.CallExpr(span=join(callee.span, close.span), callee=callee.name, args=args)

    def _parse_index(self, array_expr: ast.Expr) -> ast.IndexExpr:
        self.advance()  # "["
        index = self.parse_expression()
        close = self.expect(TokenType.DELIMITER, "]", "to close index expression")
        return ast.IndexExpr(span=join(array_expr.span, close.span), array=array_expr, index=index)

    def _parse_member(self, obj_expr: ast.Expr) -> ast.MemberExpr:
        op_token = self.advance()  # "." or "->"
        name_token = self.expect_type(TokenType.IDENT, "member name")
        return ast.MemberExpr(
            span=join(obj_expr.span, name_token.span),
            obj=obj_expr,
            member=name_token.lexeme,
            arrow=(op_token.lexeme == "->"),
        )

    def parse_primary_expr(self) -> ast.Expr:
        token = self.peek()
        if token.type is TokenType.INT_LIT:
            self.advance()
            return ast.IntLiteral(span=token.span, value=_parse_int_literal(token.lexeme))
        if token.type is TokenType.FLOAT_LIT:
            self.advance()
            return ast.FloatLiteral(span=token.span, value=_parse_float_literal(token.lexeme))
        if token.type is TokenType.STRING_LIT:
            self.advance()
            return ast.StringLiteral(span=token.span, value=_unquote(token.lexeme, '"'))
        if token.type is TokenType.CHAR_LIT:
            self.advance()
            return ast.CharLiteral(span=token.span, value=_unquote(token.lexeme, "'"))
        if token.type is TokenType.IDENT:
            self.advance()
            return ast.Identifier(span=token.span, name=token.lexeme)
        if token.type is TokenType.DELIMITER and token.lexeme == "(":
            self.advance()
            inner = self.parse_expression()
            self.expect(TokenType.DELIMITER, ")", "to close parenthesized expression")
            return inner
        self.fail(f"expected expression, got {self._describe_current()}")

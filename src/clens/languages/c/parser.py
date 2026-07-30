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
from clens.core.parser_base import ParseError, ParserBase
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

#: Statement-leading keywords (parser skill's synchronization set) plus the
#: type-start keywords: anything that legitimately opens a new statement or
#: declaration, so panic-mode recovery (R3.3) can resume there.
_STATEMENT_KEYWORDS = frozenset({"if", "while", "for", "return", "break", "continue"})
SYNC_LEXEMES = _STATEMENT_KEYWORDS | _TYPE_START_KEYWORDS

#: Real C keywords this subset deliberately excludes (project/03-c-subset.md).
#: Seeing one is a clear diagnostic and a synchronize(), never a crash.
_UNSUPPORTED_KEYWORDS = frozenset(
    {"typedef", "union", "enum", "switch", "case", "goto", "default", "do"}
)


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
    of a C source file. Declaration parsing and the `parse()` entry point
    are added by a later commit in this same class; `parse_block_item()`
    below is provisional until then (statements only, no local
    declarations) and is widened once `parse_var_decl_stmt` exists.
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

    # ---- Statements ---------------------------------------------------

    def parse_block(self) -> ast.Block:
        open_brace = self.expect(TokenType.DELIMITER, "{", "to open block")
        body: list[ast.Stmt | ast.Decl] = []
        while not self.check_lexeme("}") and not self.at_end():
            pos_before = self.pos
            start_token = self.peek()
            try:
                body.append(self.parse_block_item())
            except ParseError:
                body.append(ast.ErrorStmt(span=start_token.span, message=self._last_error()))
                self.synchronize(SYNC_LEXEMES)
            self.guard_progress(pos_before)
        close = self.expect(TokenType.DELIMITER, "}", "to close block")
        return ast.Block(span=join(open_brace.span, close.span), body=body)

    def parse_block_item(self) -> ast.Stmt | ast.Decl:
        # Widened to `var_decl_stmt | statement` once parse_var_decl_stmt
        # exists (declarations commit); statement-only for now.
        return self.parse_statement()

    def parse_statement(self) -> ast.Stmt:
        token = self.peek()
        if token.type is TokenType.KEYWORD and token.lexeme in _UNSUPPORTED_KEYWORDS:
            self.fail(f"unsupported construct: '{token.lexeme}' (see docs/known-limitations.md)")
        if token.type is TokenType.DELIMITER and token.lexeme == "{":
            return self.parse_block()
        if token.type is TokenType.KEYWORD and token.lexeme == "if":
            return self.parse_if_stmt()
        if token.type is TokenType.KEYWORD and token.lexeme == "while":
            return self.parse_while_stmt()
        if token.type is TokenType.KEYWORD and token.lexeme == "for":
            return self.parse_for_stmt()
        if token.type is TokenType.KEYWORD and token.lexeme == "return":
            return self.parse_return_stmt()
        if token.type is TokenType.KEYWORD and token.lexeme == "break":
            self.advance()
            semi = self.expect(TokenType.DELIMITER, ";", "after 'break'")
            return ast.BreakStmt(span=join(token.span, semi.span))
        if token.type is TokenType.KEYWORD and token.lexeme == "continue":
            self.advance()
            semi = self.expect(TokenType.DELIMITER, ";", "after 'continue'")
            return ast.ContinueStmt(span=join(token.span, semi.span))
        if token.type is TokenType.DELIMITER and token.lexeme == ";":
            self.advance()
            return ast.EmptyStmt(span=token.span)
        return self.parse_expr_stmt()

    def parse_if_stmt(self) -> ast.Stmt:
        if_token = self.advance()  # "if"
        self.expect(TokenType.DELIMITER, "(", "after 'if'")
        condition = self.parse_expression()
        self.expect(TokenType.DELIMITER, ")", "to close 'if' condition")
        then_branch = self.parse_statement()
        else_branch: ast.Stmt | None = None
        # Dangling else: binds to the nearest still-open 'if' simply because
        # that 'if' is the one whose recursive parse_statement() call is on
        # top of the stack when the 'else' token is reached.
        if self.check_lexeme("else"):
            self.advance()
            else_branch = self.parse_statement()
        end_span = (else_branch or then_branch).span
        return ast.IfStmt(
            span=join(if_token.span, end_span),
            condition=condition,
            then_branch=then_branch,
            else_branch=else_branch,
        )

    def parse_while_stmt(self) -> ast.Stmt:
        while_token = self.advance()  # "while"
        self.expect(TokenType.DELIMITER, "(", "after 'while'")
        condition = self.parse_expression()
        self.expect(TokenType.DELIMITER, ")", "to close 'while' condition")
        body = self.parse_statement()
        return ast.WhileStmt(span=join(while_token.span, body.span), condition=condition, body=body)

    def parse_for_stmt(self) -> ast.Stmt:
        for_token = self.advance()  # "for"
        self.expect(TokenType.DELIMITER, "(", "after 'for'")

        init: ast.Stmt | ast.Decl | None = None
        if _is_type_start(self.peek()):
            init = self.parse_var_decl_stmt()  # consumes its own ';'
        else:
            if not self.check_lexeme(";"):
                init_expr = self.parse_expression()
                init = ast.ExprStmt(span=init_expr.span, expr=init_expr)
            self.expect(TokenType.DELIMITER, ";", "after 'for' initializer")

        condition: ast.Expr | None = None
        if not self.check_lexeme(";"):
            condition = self.parse_expression()
        self.expect(TokenType.DELIMITER, ";", "after 'for' condition")

        update: ast.Expr | None = None
        if not self.check_lexeme(")"):
            update = self.parse_expression()
        self.expect(TokenType.DELIMITER, ")", "to close 'for' clauses")

        body = self.parse_statement()
        return ast.ForStmt(
            span=join(for_token.span, body.span),
            init=init,
            condition=condition,
            update=update,
            body=body,
        )

    def parse_return_stmt(self) -> ast.Stmt:
        return_token = self.advance()  # "return"
        value: ast.Expr | None = None
        if not self.check_lexeme(";"):
            value = self.parse_expression()
        semi = self.expect(TokenType.DELIMITER, ";", "after 'return'")
        return ast.ReturnStmt(span=join(return_token.span, semi.span), value=value)

    def parse_expr_stmt(self) -> ast.Stmt:
        expr = self.parse_expression()
        semi = self.expect(TokenType.DELIMITER, ";", "after expression statement")
        return ast.ExprStmt(span=join(expr.span, semi.span), expr=expr)

    def _last_error(self) -> str:
        if self.diagnostics.diagnostics:
            return self.diagnostics.diagnostics[-1].message
        raise AssertionError("unreachable: fail() always logs a diagnostic before raising")

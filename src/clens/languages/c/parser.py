"""Recursive-descent parser for the C subset (R3.1-R3.5): one function per
non-terminal in `docs/grammar.ebnf`, named identically (`parse_<name>` for
`<name>`). Call the module-level `parse()` to get a `Program` from a
`SourceFile`; it never raises (R3.4) — panic-mode recovery (`ParseError`,
caught at statement/declaration granularity, see `SYNC_LEXEMES`) keeps any
one broken construct from taking down the rest of the file.

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
from clens.core.diagnostics import DiagnosticCollector
from clens.core.parser_base import ParseError, ParserBase
from clens.core.source import SourceFile
from clens.core.token import Token, TokenType, iter_significant
from clens.languages.c import ast_nodes as ast
from clens.languages.c.lexer import tokenize

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


def _is_type_start(token: Token) -> bool:
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
    of a C source file into a `Program` — see the module-level `parse()`
    for the usual entry point.
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
                body.extend(self.parse_block_item())
            except ParseError:
                body.append(ast.ErrorStmt(span=start_token.span, message=self._last_error()))
                self.synchronize(SYNC_LEXEMES)
            self.guard_progress(pos_before)
        close = self.expect(TokenType.DELIMITER, "}", "to close block")
        return ast.Block(span=join(open_brace.span, close.span), body=body)

    def parse_block_item(self) -> list[ast.Stmt | ast.Decl]:
        """`block_item = var_decl_stmt | statement`. Returns a list because
        one `var_decl_stmt` line can expand to several sibling `VarDecl`s
        (`int a = 1, b, c = 3;`).
        """
        if _is_type_start(self.peek()):
            return list(self.parse_var_decl_stmt())
        return [self.parse_statement()]

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

        init: ast.Stmt | list[ast.VarDecl] | None = None
        if _is_type_start(self.peek()):
            init = self.parse_var_decl_stmt()  # list[VarDecl]; consumes its own ';'
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

    # ---- Types ----------------------------------------------------------

    def parse_type_spec(self) -> ast.TypeSpec:
        start_token = self.peek()
        storage: str | None = None
        while self.check(TokenType.KEYWORD) and self.peek().lexeme in STORAGE_KEYWORDS:
            storage = self.advance().lexeme

        is_const = False
        if self.check_lexeme("const"):
            self.advance()
            is_const = True

        if self.check_lexeme("struct"):
            self.advance()
            name_token = self.expect_type(TokenType.IDENT, "struct tag name")
            base, struct_name, end_token = "struct", name_token.lexeme, name_token
        elif self.check(TokenType.KEYWORD) and self.peek().lexeme in BASE_TYPE_KEYWORDS:
            base_token = self.advance()
            base, struct_name, end_token = base_token.lexeme, None, base_token
        else:
            self.fail(f"expected a type, got {self._describe_current()}")

        pointer_depth = 0
        while self.check_lexeme("*"):
            end_token = self.advance()
            pointer_depth += 1

        return ast.TypeSpec(
            span=join(start_token.span, end_token.span),
            base=base,
            struct_name=struct_name,
            pointer_depth=pointer_depth,
            is_const=is_const,
            storage=storage,
        )

    def _parse_array_suffix(self) -> tuple[ast.Expr | None, Token]:
        """`"[" [int_lit] "]"`, given the '[' has already been checked (not
        consumed). Returns the optional size literal and the closing ']'.
        """
        self.advance()  # "["
        size: ast.Expr | None = None
        if self.check(TokenType.INT_LIT):
            size_token = self.advance()
            size = ast.IntLiteral(span=size_token.span, value=_parse_int_literal(size_token.lexeme))
        close = self.expect(TokenType.DELIMITER, "]", "to close array size")
        return size, close

    # ---- Declarations -----------------------------------------------------

    def parse_param(self) -> ast.Param:
        type_spec = self.parse_type_spec()
        name_token = self.expect_type(TokenType.IDENT, "parameter name")
        array = False
        array_size: ast.Expr | None = None
        end_token = name_token
        if self.check_lexeme("["):
            array = True
            array_size, end_token = self._parse_array_suffix()
        return ast.Param(
            span=join(type_spec.span, end_token.span),
            type=type_spec,
            name=name_token.lexeme,
            array=array,
            array_size=array_size,
        )

    def parse_param_list(self) -> list[ast.Param]:
        params = [self.parse_param()]
        while self.match_lexeme(","):
            params.append(self.parse_param())
        return params

    def _finish_declarator(self, base_type: ast.TypeSpec, name_token: Token) -> ast.VarDecl:
        array = False
        array_size: ast.Expr | None = None
        last_span = name_token.span
        if self.check_lexeme("["):
            array = True
            array_size, close = self._parse_array_suffix()
            last_span = close.span
        init: ast.Expr | None = None
        if self.match_lexeme("="):
            init = self.parse_assignment_expr()
            last_span = init.span
        return ast.VarDecl(
            span=join(base_type.span, last_span),
            type=base_type,
            name=name_token.lexeme,
            array=array,
            array_size=array_size,
            init=init,
        )

    def parse_var_decl_list(self, base_type: ast.TypeSpec, first_name: Token) -> list[ast.VarDecl]:
        """The rest of `declarator , { "," , declarator } , ";"`, given
        `base_type` and the first declarator's name already parsed.
        """
        decls = [self._finish_declarator(base_type, first_name)]
        while self.match_lexeme(","):
            name_token = self.expect_type(TokenType.IDENT, "declarator name")
            decls.append(self._finish_declarator(base_type, name_token))
        self.expect(TokenType.DELIMITER, ";", "after variable declaration")
        return decls

    def parse_var_decl_stmt(self) -> list[ast.VarDecl]:
        type_spec = self.parse_type_spec()
        name_token = self.expect_type(TokenType.IDENT, "declarator name")
        return self.parse_var_decl_list(type_spec, name_token)

    def _finish_func_decl(self, return_type: ast.TypeSpec, name_token: Token) -> ast.FuncDecl:
        self.advance()  # "("
        params: list[ast.Param] = []
        if self.check_lexeme("void") and self.peek(1).lexeme == ")":
            self.advance()  # "void" meaning "no parameters", not a param named nothing
        elif not self.check_lexeme(")"):
            params = self.parse_param_list()
        self.expect(TokenType.DELIMITER, ")", "to close parameter list")
        if self.check_lexeme("{"):
            body = self.parse_block()
            end_span = body.span
        else:
            semi = self.expect(TokenType.DELIMITER, ";", "after function prototype")
            body = None
            end_span = semi.span
        return ast.FuncDecl(
            span=join(return_type.span, end_span),
            return_type=return_type,
            name=name_token.lexeme,
            params=params,
            body=body,
        )

    def parse_field_decl(self) -> ast.Field:
        type_spec = self.parse_type_spec()
        name_token = self.expect_type(TokenType.IDENT, "field name")
        semi = self.expect(TokenType.DELIMITER, ";", "after struct field")
        return ast.Field(
            span=join(type_spec.span, semi.span), type=type_spec, name=name_token.lexeme
        )

    def parse_struct_decl(self) -> ast.StructDecl:
        struct_token = self.advance()  # "struct"
        name_token = self.expect_type(TokenType.IDENT, "struct tag name")
        self.expect(TokenType.DELIMITER, "{", "to open struct body")
        fields: list[ast.Field] = []
        while not self.check_lexeme("}") and not self.at_end():
            pos_before = self.pos
            try:
                fields.append(self.parse_field_decl())
            except ParseError:
                self.synchronize(SYNC_LEXEMES)
            self.guard_progress(pos_before)
        self.expect(TokenType.DELIMITER, "}", "to close struct body")
        semi = self.expect(TokenType.DELIMITER, ";", "after struct declaration")
        return ast.StructDecl(
            span=join(struct_token.span, semi.span), name=name_token.lexeme, fields=fields
        )

    def parse_external_decl(self) -> list[ast.Decl]:
        """`external_decl = func_decl | struct_decl | var_decl_stmt`.
        Returns a list because a var_decl_stmt line can expand to several
        sibling VarDecls, same as `parse_block_item`.
        """
        token = self.peek()
        if token.type is TokenType.KEYWORD and token.lexeme in _UNSUPPORTED_KEYWORDS:
            self.fail(f"unsupported construct: '{token.lexeme}' (see docs/known-limitations.md)")
        if self.check_lexeme("struct") and self.peek(2).lexeme == "{":
            return [self.parse_struct_decl()]
        type_spec = self.parse_type_spec()
        name_token = self.expect_type(TokenType.IDENT, "declared name")
        if self.check_lexeme("("):
            return [self._finish_func_decl(type_spec, name_token)]
        return list(self.parse_var_decl_list(type_spec, name_token))

    # ---- Program (entry production) ----------------------------------

    def parse_program(self) -> ast.Program:
        start_token = self.peek()
        declarations: list[ast.Decl] = []
        while not self.at_end():
            pos_before = self.pos
            try:
                declarations.extend(self.parse_external_decl())
            except ParseError:
                self.synchronize(SYNC_LEXEMES)
            self.guard_progress(pos_before)
        return ast.Program(span=join(start_token.span, self.peek().span), declarations=declarations)


def parse(source: SourceFile, diagnostics: DiagnosticCollector) -> ast.Program:
    """Parse a C `SourceFile` into a `Program`. Never returns `None` and
    never raises (R3.4): every `ParseError` is caught internally by panic-
    mode recovery, and the best partial tree is returned alongside whatever
    diagnostics were recorded.
    """
    tokens = list(iter_significant(tokenize(source, diagnostics)))
    parser = Parser(tokens, diagnostics)
    return parser.parse_program()

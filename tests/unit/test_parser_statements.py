"""R3.1-R3.3 — statement parsing: block, if/else (dangling-else), while,
for, return, break, continue, expression and empty statements.
"""

from clens.core.diagnostics import DiagnosticCollector
from clens.core.source import SourceFile
from clens.core.token import iter_significant
from clens.languages.c import ast_nodes as ast
from clens.languages.c.lexer import tokenize
from clens.languages.c.parser import Parser


def parse_stmt(text: str) -> tuple[ast.Stmt, DiagnosticCollector]:
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    tokens = list(iter_significant(tokenize(source, diagnostics)))
    parser = Parser(tokens, diagnostics)
    return parser.parse_statement(), diagnostics


def test_empty_statement():
    stmt, diags = parse_stmt(";")
    assert isinstance(stmt, ast.EmptyStmt)
    assert not diags.diagnostics


def test_expr_statement():
    stmt, diags = parse_stmt("x = 1;")
    assert isinstance(stmt, ast.ExprStmt)
    assert isinstance(stmt.expr, ast.AssignExpr)
    assert not diags.diagnostics


def test_break_and_continue():
    brk, _ = parse_stmt("break;")
    cont, _ = parse_stmt("continue;")
    assert isinstance(brk, ast.BreakStmt)
    assert isinstance(cont, ast.ContinueStmt)


def test_return_with_and_without_value():
    bare, _ = parse_stmt("return;")
    assert isinstance(bare, ast.ReturnStmt) and bare.value is None
    with_value, _ = parse_stmt("return n * 2;")
    assert isinstance(with_value, ast.ReturnStmt)
    assert isinstance(with_value.value, ast.BinaryExpr)


def test_block_of_statements():
    block, diags = parse_stmt("{ x = 1; y = 2; }")
    assert isinstance(block, ast.Block)
    assert len(block.body) == 2
    assert all(isinstance(item, ast.ExprStmt) for item in block.body)
    assert not diags.diagnostics


def test_empty_block():
    block, _ = parse_stmt("{}")
    assert isinstance(block, ast.Block)
    assert block.body == []


def test_if_without_else():
    stmt, _ = parse_stmt("if (x) return 1;")
    assert isinstance(stmt, ast.IfStmt)
    assert stmt.else_branch is None
    assert isinstance(stmt.then_branch, ast.ReturnStmt)


def test_if_with_else():
    stmt, _ = parse_stmt("if (x) return 1; else return 2;")
    assert isinstance(stmt, ast.IfStmt)
    assert isinstance(stmt.else_branch, ast.ReturnStmt)


def test_dangling_else_binds_to_nearest_if():
    """if (a) if (b) return 1; else return 2; -- else attaches to the inner if."""
    stmt, _ = parse_stmt("if (a) if (b) return 1; else return 2;")
    assert isinstance(stmt, ast.IfStmt)
    assert stmt.else_branch is None  # outer if has no else
    inner = stmt.then_branch
    assert isinstance(inner, ast.IfStmt)
    assert inner.else_branch is not None  # else bound to the inner if


def test_while_loop():
    stmt, _ = parse_stmt("while (x < 10) x = x + 1;")
    assert isinstance(stmt, ast.WhileStmt)
    assert isinstance(stmt.condition, ast.BinaryExpr)


def test_for_loop_all_clauses():
    stmt, _ = parse_stmt("for (i = 0; i < 10; i = i + 1) x = i;")
    assert isinstance(stmt, ast.ForStmt)
    assert isinstance(stmt.init, ast.ExprStmt)
    assert isinstance(stmt.condition, ast.BinaryExpr)
    assert isinstance(stmt.update, ast.AssignExpr)


def test_for_loop_all_clauses_omitted():
    stmt, _ = parse_stmt("for (;;) break;")
    assert isinstance(stmt, ast.ForStmt)
    assert stmt.init is None
    assert stmt.condition is None
    assert stmt.update is None


def test_statement_span_covers_whole_construct():
    stmt, _ = parse_stmt("return 1;")
    assert stmt.span.start_offset == 0
    assert stmt.span.end_offset == len("return 1;")

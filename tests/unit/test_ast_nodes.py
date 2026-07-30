"""R4.2, R4.3 — Node/Expr/Stmt/Decl bases, ErrorExpr/ErrorStmt, join()."""

from clens.core.ast_nodes import Decl, ErrorExpr, ErrorStmt, Expr, Node, Stmt, join
from clens.core.token import Span


def make_span(start: int, end: int, line: int = 1, column: int = 1) -> Span:
    return Span(start_offset=start, end_offset=end, line=line, column=column)


def test_node_carries_span():
    node = Node(span=make_span(0, 3))
    assert node.span == make_span(0, 3)


def test_expr_type_annotation_defaults_to_none():
    expr = Expr(span=make_span(0, 1))
    assert expr.type_annotation is None


def test_stmt_and_decl_carry_span_with_no_extra_fields():
    stmt = Stmt(span=make_span(0, 1))
    decl = Decl(span=make_span(0, 1))
    assert stmt.span == decl.span == make_span(0, 1)


def test_error_expr_carries_message_and_span():
    error = ErrorExpr(span=make_span(5, 6, line=1, column=6), message="expected expression")
    assert error.message == "expected expression"
    assert error.span.line == 1 and error.span.column == 6
    assert error.SHOW_LOC is True
    assert error.INLINE_FIELDS == ("message",)


def test_error_stmt_carries_message_and_span():
    error = ErrorStmt(span=make_span(0, 1), message="expected statement")
    assert error.message == "expected statement"


def test_join_spans_start_from_first_end_from_last():
    left = make_span(10, 11, line=3, column=12)
    right = make_span(20, 22, line=3, column=22)
    joined = join(left, right)
    assert joined == Span(start_offset=10, end_offset=22, line=3, column=12)

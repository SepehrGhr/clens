"""R4.2 — the AST pretty-printer, including the course document §4.3.2 golden
case for `return n * factorial(n - 1);` on line 3 of valid/factorial.c.
"""

from pathlib import Path

from clens.core.ast_printer import format_ast
from clens.core.token import Span
from clens.languages.c import ast_nodes as c


def _load_golden_ast() -> str:
    """The golden file has a '#'-comment header (attribution, not content)
    above the actual AST dump; strip it before comparing.
    """
    raw = (Path(__file__).parent.parent / "fixtures" / "golden" / "factorial_ast.txt").read_text()
    content_lines = [line for line in raw.splitlines() if not line.startswith("#")]
    return "\n".join(content_lines).strip("\n")


GOLDEN_AST = _load_golden_ast()


def span(line: int, column: int, length: int = 1) -> Span:
    # Offsets are not exercised by this test; only line/column feed the
    # golden `loc=` output, so any consistent offsets are fine here.
    return Span(start_offset=0, end_offset=length, line=line, column=column)


def test_golden_factorial_line_3_ast():
    """R4.2 golden positions: n@3:12, factorial@3:16, n@3:26, 1@3:30."""
    inner_left = c.Identifier(span=span(3, 26), name="n")
    inner_right = c.IntLiteral(span=span(3, 30), value=1)
    inner_binary = c.BinaryExpr(span=span(3, 26), op="-", left=inner_left, right=inner_right)

    call = c.CallExpr(
        span=span(3, 16), callee="factorial", callee_span=span(3, 16), args=[inner_binary]
    )
    outer_left = c.Identifier(span=span(3, 12), name="n")
    outer_binary = c.BinaryExpr(span=span(3, 12), op="*", left=outer_left, right=call)

    return_stmt = c.ReturnStmt(span=span(3, 5), value=outer_binary)

    rendered = format_ast(return_stmt)
    assert rendered == GOLDEN_AST


def test_leaf_with_no_inline_fields_prints_bare_class_name():
    node = c.BreakStmt(span=span(1, 1))
    assert format_ast(node) == "BreakStmt"


def test_node_with_inline_fields_and_no_children():
    node = c.Identifier(span=span(1, 1), name="x")
    assert format_ast(node) == "Identifier(name='x', loc=1:1)"


def test_none_optional_child_is_omitted():
    if_stmt = c.IfStmt(
        span=span(1, 1),
        condition=c.Identifier(span=span(1, 4), name="c"),
        then_branch=c.BreakStmt(span=span(1, 10)),
        else_branch=None,
    )
    rendered = format_ast(if_stmt)
    assert "else_branch" not in rendered
    assert rendered == (
        "IfStmt\n  condition:   Identifier(name='c', loc=1:4)\n  then_branch: BreakStmt"
    )


def test_list_of_node_fields_expand_with_index_labels():
    call = c.CallExpr(
        span=span(1, 1),
        callee="f",
        callee_span=span(1, 1),
        args=[
            c.IntLiteral(span=span(1, 3), value=1),
            c.IntLiteral(span=span(1, 6), value=2),
        ],
    )
    rendered = format_ast(call)
    assert rendered == (
        "CallExpr(callee='f', loc=1:1)\n"
        "  args[0]: IntLiteral(value=1, loc=1:3)\n"
        "  args[1]: IntLiteral(value=2, loc=1:6)"
    )

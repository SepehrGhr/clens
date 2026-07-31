"""R2.1-R2.2, R3.1 — expression parsing: precedence, associativity, postfix
chains, and primary literals.
"""

from clens.core.diagnostics import DiagnosticCollector
from clens.core.source import SourceFile
from clens.core.token import iter_significant
from clens.languages.c import ast_nodes as ast
from clens.languages.c.lexer import tokenize
from clens.languages.c.parser import Parser


def parse_expr(text: str) -> tuple[ast.Expr, DiagnosticCollector]:
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    tokens = list(iter_significant(tokenize(source, diagnostics)))
    parser = Parser(tokens, diagnostics)
    return parser.parse_expression(), diagnostics


def dump(node: ast.Expr) -> object:
    """A structure-only view (no spans) for concise assertions."""
    if isinstance(node, ast.Identifier):
        return node.name
    if isinstance(node, ast.IntLiteral | ast.FloatLiteral):
        return node.value
    if isinstance(node, ast.StringLiteral | ast.CharLiteral):
        return node.value
    if isinstance(node, ast.BinaryExpr):
        return (node.op, dump(node.left), dump(node.right))
    if isinstance(node, ast.AssignExpr):
        return (node.op, dump(node.target), dump(node.value))
    if isinstance(node, ast.UnaryExpr):
        return ("prefix" if node.prefix else "postfix", node.op, dump(node.operand))
    if isinstance(node, ast.TernaryExpr):
        return ("?:", dump(node.condition), dump(node.then_expr), dump(node.else_expr))
    if isinstance(node, ast.CallExpr):
        return ("call", node.callee, [dump(a) for a in node.args])
    if isinstance(node, ast.IndexExpr):
        return ("index", dump(node.array), dump(node.index))
    if isinstance(node, ast.MemberExpr):
        return ("->" if node.arrow else ".", dump(node.obj), node.member)
    if isinstance(node, ast.SizeofExpr):
        return ("sizeof", dump(node.target) if isinstance(node.target, ast.Expr) else node.target)
    raise TypeError(f"dump() doesn't know {type(node).__name__}")


def test_primary_literals():
    assert dump(parse_expr("42")[0]) == 42
    assert dump(parse_expr("3.14")[0]) == 3.14
    assert dump(parse_expr('"hi"')[0]) == "hi"
    assert dump(parse_expr("'a'")[0]) == "a"
    assert dump(parse_expr("n")[0]) == "n"


def test_parenthesized_expression_unwraps():
    assert dump(parse_expr("(1 + 2)")[0]) == ("+", 1, 2)


def test_precedence_mult_binds_tighter_than_add():
    assert dump(parse_expr("a + b * c")[0]) == ("+", "a", ("*", "b", "c"))


def test_precedence_relational_binds_tighter_than_equality():
    assert dump(parse_expr("a == b < c")[0]) == ("==", "a", ("<", "b", "c"))


def test_associativity_additive_is_left():
    """R3.5 associativity: a - b - c -> (a - b) - c."""
    assert dump(parse_expr("a - b - c")[0]) == ("-", ("-", "a", "b"), "c")


def test_associativity_assignment_is_right():
    """a = b = c -> a = (b = c)."""
    assert dump(parse_expr("a = b = c")[0]) == ("=", "a", ("=", "b", "c"))


def test_ternary_is_right_associative_and_lowest_but_assignment():
    assert dump(parse_expr("a ? b : c ? d : e")[0]) == ("?:", "a", "b", ("?:", "c", "d", "e"))


def test_logical_and_binds_tighter_than_logical_or():
    assert dump(parse_expr("a || b && c")[0]) == ("||", "a", ("&&", "b", "c"))


def test_unary_prefix_operators():
    assert dump(parse_expr("-x")[0]) == ("prefix", "-", "x")
    assert dump(parse_expr("!x")[0]) == ("prefix", "!", "x")
    assert dump(parse_expr("&x")[0]) == ("prefix", "&", "x")
    assert dump(parse_expr("*x")[0]) == ("prefix", "*", "x")
    assert dump(parse_expr("~x")[0]) == ("prefix", "~", "x")
    assert dump(parse_expr("++x")[0]) == ("prefix", "++", "x")


def test_postfix_increment_decrement():
    assert dump(parse_expr("x++")[0]) == ("postfix", "++", "x")
    assert dump(parse_expr("x--")[0]) == ("postfix", "--", "x")


def test_postfix_chain_call_index_member_arrow():
    """f(x)[0].field->next is one postfix expression, suffixes applied left
    to right."""
    node, _ = parse_expr("f(x)[0].field->next")
    assert dump(node) == (
        "->",
        (".", ("index", ("call", "f", ["x"]), 0), "field"),
        "next",
    )


def test_member_expr_member_span_is_just_the_name():
    """member_span must cover only the field name, not the whole expression —
    this has to hold even with whitespace/comments between '.' and the name,
    where end_offset - len(member) would silently give the wrong answer."""
    node, _ = parse_expr("p.x")
    assert isinstance(node, ast.MemberExpr)
    assert (node.member_span.start_offset, node.member_span.end_offset) == (2, 3)

    spaced, _ = parse_expr("p /*c*/ . x")
    assert isinstance(spaced, ast.MemberExpr)
    start = spaced.member_span.start_offset
    end = spaced.member_span.end_offset
    assert spaced.member == "x"
    assert (start, end) == (10, 11)


def test_call_with_multiple_args():
    assert dump(parse_expr("f(1, 2, 3)")[0]) == ("call", "f", [1, 2, 3])


def test_call_with_no_args():
    assert dump(parse_expr("f()")[0]) == ("call", "f", [])


def test_sizeof_expr_form():
    assert dump(parse_expr("sizeof x")[0]) == ("sizeof", "x")
    assert dump(parse_expr("sizeof(x)")[0]) == ("sizeof", "x")


def test_golden_factorial_call_vs_variable_line_reuse():
    """The exact right-hand side from factorial.c line 3."""
    node, diagnostics = parse_expr("n * factorial(n - 1)")
    assert dump(node) == ("*", "n", ("call", "factorial", [("-", "n", 1)]))
    assert not diagnostics.diagnostics


def test_spans_cover_the_whole_construct():
    node, _ = parse_expr("a + b")
    assert node.span.start_offset == 0
    assert node.span.end_offset == 5  # end of 'b'


def test_int_literal_bases_and_suffixes():
    assert dump(parse_expr("0xFF")[0]) == 255
    assert dump(parse_expr("0b1010")[0]) == 10
    assert dump(parse_expr("0755")[0]) == 493
    assert dump(parse_expr("10u")[0]) == 10
    assert dump(parse_expr("10UL")[0]) == 10

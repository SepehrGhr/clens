"""R4.1 — the C AST node inventory: construction, defaults, and the
"course-document-named" nodes matching exactly."""

from clens.core.ast_nodes import Decl, Expr, Stmt
from clens.core.token import Span
from clens.languages.c import ast_nodes as c_ast

SPAN = Span(start_offset=0, end_offset=1, line=1, column=1)


def test_course_document_named_nodes_exist_with_exact_names():
    """R4.1 — 'The document names: BinaryExpr, IfStmt, FuncDecl, CallExpr,
    ReturnStmt.'"""
    for name in ("BinaryExpr", "IfStmt", "FuncDecl", "CallExpr", "ReturnStmt"):
        assert hasattr(c_ast, name), f"missing course-document node: {name}"


def test_all_exports_are_node_subclasses_and_carry_span():
    for name in c_ast.__all__:
        cls = getattr(c_ast, name)
        assert issubclass(cls, Decl | Expr | Stmt | c_ast.Node) or hasattr(cls, "span")


def test_func_decl_prototype_has_no_body():
    proto = c_ast.FuncDecl(
        span=SPAN,
        return_type=c_ast.TypeSpec(span=SPAN, base="int"),
        name="factorial",
        name_span=SPAN,
        params=[],
    )
    assert proto.body is None


def test_func_decl_definition_has_a_block_body():
    body = c_ast.Block(span=SPAN, body=[])
    func = c_ast.FuncDecl(
        span=SPAN,
        return_type=c_ast.TypeSpec(span=SPAN, base="int"),
        name="factorial",
        name_span=SPAN,
        params=[
            c_ast.Param(
                span=SPAN, type=c_ast.TypeSpec(span=SPAN, base="int"), name="n", name_span=SPAN
            )
        ],
        body=body,
    )
    assert func.body is body
    assert func.params[0].name == "n"


def test_multiple_declarators_are_sibling_var_decls_not_wrapped():
    """'int a = 1, b, c = 3;' -> three sibling VarDecl nodes, no wrapper node
    (D9-style flattening, matching pycparser's own Decl handling)."""
    int_type = c_ast.TypeSpec(span=SPAN, base="int")
    a = c_ast.VarDecl(
        span=SPAN,
        type=int_type,
        name="a",
        name_span=SPAN,
        init=c_ast.IntLiteral(span=SPAN, value=1),
    )
    b = c_ast.VarDecl(span=SPAN, type=int_type, name="b", name_span=SPAN)
    c = c_ast.VarDecl(
        span=SPAN,
        type=int_type,
        name="c",
        name_span=SPAN,
        init=c_ast.IntLiteral(span=SPAN, value=3),
    )
    block = c_ast.Block(span=SPAN, body=[a, b, c])
    assert [d.name for d in block.body] == ["a", "b", "c"]
    assert b.init is None


def test_call_expr_callee_is_a_plain_string_not_a_node():
    call = c_ast.CallExpr(
        span=SPAN,
        callee="factorial",
        callee_span=SPAN,
        args=[c_ast.IntLiteral(span=SPAN, value=1)],
    )
    assert call.callee == "factorial"
    assert isinstance(call.args[0], Expr)


def test_unary_expr_prefix_and_postfix_share_one_node_type():
    prefix = c_ast.UnaryExpr(span=SPAN, op="++", operand=c_ast.Identifier(span=SPAN, name="x"))
    postfix = c_ast.UnaryExpr(
        span=SPAN, op="++", operand=c_ast.Identifier(span=SPAN, name="x"), prefix=False
    )
    assert prefix.prefix is True
    assert postfix.prefix is False


def test_member_expr_dot_vs_arrow():
    dot = c_ast.MemberExpr(
        span=SPAN, obj=c_ast.Identifier(span=SPAN, name="p"), member="x", member_span=SPAN
    )
    arrow = c_ast.MemberExpr(
        span=SPAN,
        obj=c_ast.Identifier(span=SPAN, name="p"),
        member="x",
        member_span=SPAN,
        arrow=True,
    )
    assert dot.arrow is False
    assert arrow.arrow is True


def test_struct_decl_holds_field_list():
    point = c_ast.StructDecl(
        span=SPAN,
        name="Point",
        name_span=SPAN,
        fields=[
            c_ast.Field(
                span=SPAN, type=c_ast.TypeSpec(span=SPAN, base="int"), name="x", name_span=SPAN
            ),
            c_ast.Field(
                span=SPAN, type=c_ast.TypeSpec(span=SPAN, base="int"), name="y", name_span=SPAN
            ),
        ],
    )
    assert [f.name for f in point.fields] == ["x", "y"]


def test_type_spec_pointer_and_const():
    t = c_ast.TypeSpec(span=SPAN, base="char", pointer_depth=2, is_const=True)
    assert (t.base, t.pointer_depth, t.is_const) == ("char", 2, True)


def test_expr_nodes_inherit_type_annotation_none_by_default():
    ident = c_ast.Identifier(span=SPAN, name="n")
    assert ident.type_annotation is None

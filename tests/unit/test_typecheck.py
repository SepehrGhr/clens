"""D15 — resolve_type_spec bridges syntactic TypeSpec to semantic Type.
S4.1-S4.6 — the expression-typing walk built on top of it: literals,
identifiers, unary, binary, ternary, assignment, index, sizeof, member
access, calls, and return checking.
"""

from dataclasses import dataclass

from clens.core.ast_nodes import Node
from clens.core.diagnostics import DiagnosticCollector, SemanticCode, Severity
from clens.core.source import SourceFile
from clens.core.token import Span
from clens.core.types import (
    ArrayType,
    PointerType,
    PrimitiveType,
    StructType,
    Type,
    UnknownType,
)
from clens.core.visitor import walk
from clens.languages.c import ast_nodes as ast
from clens.languages.c.ast_nodes import TypeSpec
from clens.languages.c.parser import parse
from clens.languages.c.semantic import analyze
from clens.languages.c.typecheck import resolve_type_spec

SPAN = Span(start_offset=0, end_offset=1, line=1, column=1)


# --- resolve_type_spec (D15) -------------------------------------------------


@dataclass
class _FakeSymbol:
    type: Type


class _FakeScope:
    def __init__(self, symbols: dict[str, Type]) -> None:
        self._symbols = {name: _FakeSymbol(type=t) for name, t in symbols.items()}

    def lookup(self, name: str):
        return self._symbols.get(name)


def spec(base: str, *, struct_name: str | None = None, pointer_depth: int = 0) -> TypeSpec:
    return TypeSpec(span=SPAN, base=base, struct_name=struct_name, pointer_depth=pointer_depth)


def test_primitive_bases_resolve_directly():
    scope = _FakeScope({})
    for base in ("void", "char", "int", "float", "double"):
        assert resolve_type_spec(spec(base), scope) == PrimitiveType(base)


def test_pointer_depth_wraps_in_pointer_type():
    scope = _FakeScope({})
    assert resolve_type_spec(spec("char", pointer_depth=1), scope) == PointerType(
        PrimitiveType("char")
    )
    assert resolve_type_spec(spec("int", pointer_depth=2), scope) == PointerType(
        PointerType(PrimitiveType("int"))
    )


def test_struct_tag_resolves_against_scope():
    decl = Node(span=SPAN)
    point_type = StructType("Point", decl)
    scope = _FakeScope({"Point": point_type})

    resolved = resolve_type_spec(spec("struct", struct_name="Point"), scope)

    assert resolved == point_type


def test_struct_pointer_wraps_the_resolved_struct_type():
    decl = Node(span=SPAN)
    point_type = StructType("Point", decl)
    scope = _FakeScope({"Point": point_type})

    resolved = resolve_type_spec(spec("struct", struct_name="Point", pointer_depth=1), scope)

    assert resolved == PointerType(point_type)


def test_undeclared_struct_tag_yields_unknown_not_a_crash():
    scope = _FakeScope({})
    assert resolve_type_spec(spec("struct", struct_name="Missing"), scope) == UnknownType()


def test_struct_spec_with_no_name_yields_unknown():
    """Defensive: a malformed TypeSpec (struct_name=None) must not crash."""
    scope = _FakeScope({})
    assert resolve_type_spec(spec("struct", struct_name=None), scope) == UnknownType()


# --- the expression-typing walk (S4.1-S4.6) ---------------------------------


def analyze_text(text: str, filename: str = "a.c"):
    source = SourceFile(text, filename)
    diagnostics = DiagnosticCollector()
    program = parse(source, diagnostics)
    model = analyze(program, source, diagnostics)
    return model, diagnostics


def find(root, node_type, **attrs):
    for node in walk(root):
        if isinstance(node, node_type) and all(getattr(node, k) == v for k, v in attrs.items()):
            return node
    raise AssertionError(f"no {node_type.__name__} matching {attrs} found")


# --- literals (S4.2) ---------------------------------------------------------


def test_literal_types():
    model, diagnostics = analyze_text("void f(void) { 1; 3.14; \"hi\"; 'c'; }\n")
    body = find(model.program, ast.FuncDecl).body
    int_lit = find(body, ast.IntLiteral)
    float_lit = find(body, ast.FloatLiteral)
    str_lit = find(body, ast.StringLiteral)
    char_lit = find(body, ast.CharLiteral)
    assert int_lit.type_annotation == PrimitiveType("int")
    assert float_lit.type_annotation == PrimitiveType("double")
    assert str_lit.type_annotation == PointerType(PrimitiveType("char"))
    assert char_lit.type_annotation == PrimitiveType("char")
    assert not diagnostics.diagnostics


# --- identifiers ---------------------------------------------------------


def test_identifier_types_from_its_declaration():
    model, diagnostics = analyze_text("int g = 1;\nvoid f(void) { g; }\n")
    ident = find(find(model.program, ast.FuncDecl).body, ast.Identifier, name="g")
    assert ident.type_annotation == PrimitiveType("int")
    assert not diagnostics.diagnostics


def test_unresolved_identifier_types_as_unknown_no_extra_diagnostic():
    """Stage 3 already reported the undefined symbol; typing must not add
    a second diagnostic on top."""
    model, diagnostics = analyze_text("void f(void) { missing; }\n")
    ident = find(model.program, ast.Identifier, name="missing")
    assert ident.type_annotation is not None
    assert str(ident.type_annotation) == "unknown"
    assert len(diagnostics.diagnostics) == 1
    assert diagnostics.diagnostics[0].code == SemanticCode.UNDEFINED_SYMBOL


# --- binary expressions (S4.3) --------------------------------------------


def test_binary_numeric_widening_int_plus_double_is_double():
    model, _ = analyze_text("void f(void) { int a; double b; a + b; }\n")
    add = find(find(model.program, ast.FuncDecl).body, ast.BinaryExpr, op="+")
    assert add.type_annotation == PrimitiveType("double")


def test_comparison_operators_yield_int():
    model, _ = analyze_text("void f(void) { int a; int b; a < b; }\n")
    cmp = find(find(model.program, ast.FuncDecl).body, ast.BinaryExpr, op="<")
    assert cmp.type_annotation == PrimitiveType("int")


def test_logical_operators_yield_int():
    model, _ = analyze_text("void f(void) { int a; int b; a && b; }\n")
    logical = find(find(model.program, ast.FuncDecl).body, ast.BinaryExpr, op="&&")
    assert logical.type_annotation == PrimitiveType("int")


def test_pointer_plus_int_is_the_same_pointer_type():
    model, diagnostics = analyze_text("void f(void) { int *p; int n; p + n; }\n")
    add = find(find(model.program, ast.FuncDecl).body, ast.BinaryExpr, op="+")
    assert add.type_annotation == PointerType(PrimitiveType("int"))
    assert not diagnostics.diagnostics


def test_pointer_minus_pointer_is_int():
    model, diagnostics = analyze_text("void f(void) { int *p; int *q; p - q; }\n")
    sub = find(find(model.program, ast.FuncDecl).body, ast.BinaryExpr, op="-")
    assert sub.type_annotation == PrimitiveType("int")
    assert not diagnostics.diagnostics


# --- unary expressions -----------------------------------------------------


def test_address_of_yields_pointer_to_operand_type():
    model, _ = analyze_text("void f(void) { int x; &x; }\n")
    addr = find(find(model.program, ast.FuncDecl).body, ast.UnaryExpr, op="&")
    assert addr.type_annotation == PointerType(PrimitiveType("int"))


def test_dereference_yields_pointee_type():
    model, diagnostics = analyze_text("void f(void) { int *p; *p; }\n")
    deref = find(find(model.program, ast.FuncDecl).body, ast.UnaryExpr, op="*")
    assert deref.type_annotation == PrimitiveType("int")
    assert not diagnostics.diagnostics


def test_logical_not_yields_int():
    model, _ = analyze_text("void f(void) { int x; !x; }\n")
    node = find(find(model.program, ast.FuncDecl).body, ast.UnaryExpr, op="!")
    assert node.type_annotation == PrimitiveType("int")


def test_increment_keeps_operand_type():
    model, _ = analyze_text("void f(void) { int x; x++; }\n")
    node = find(find(model.program, ast.FuncDecl).body, ast.UnaryExpr, op="++")
    assert node.type_annotation == PrimitiveType("int")


# --- ternary -----------------------------------------------------------


def test_ternary_matching_branch_types():
    model, diagnostics = analyze_text("void f(void) { int c; int a; int b; c ? a : b; }\n")
    node = find(model.program, ast.TernaryExpr)
    assert node.type_annotation == PrimitiveType("int")
    assert not diagnostics.diagnostics


def test_ternary_numeric_promotion():
    model, _ = analyze_text("void f(void) { int c; int a; double b; c ? a : b; }\n")
    node = find(model.program, ast.TernaryExpr)
    assert node.type_annotation == PrimitiveType("double")


def test_ternary_mismatch_is_an_error():
    model, diagnostics = analyze_text(
        "struct P { int x; };\nvoid f(void) { int c; struct P p; int a; c ? p : a; }\n"
    )
    node = find(model.program, ast.TernaryExpr)
    assert str(node.type_annotation) == "unknown"
    assert len(diagnostics.diagnostics) == 1
    assert diagnostics.diagnostics[0].code == SemanticCode.TERNARY_TYPE_MISMATCH
    assert diagnostics.diagnostics[0].severity is Severity.ERROR


# --- index and sizeof --------------------------------------------------


def test_index_on_array_yields_element_type():
    model, diagnostics = analyze_text("void f(void) { int arr[3]; arr[0]; }\n")
    node = find(model.program, ast.IndexExpr)
    assert node.type_annotation == PrimitiveType("int")
    assert not diagnostics.diagnostics


def test_index_on_pointer_yields_pointee_type():
    model, diagnostics = analyze_text("void f(void) { int *p; p[0]; }\n")
    node = find(model.program, ast.IndexExpr)
    assert node.type_annotation == PrimitiveType("int")
    assert not diagnostics.diagnostics


def test_sizeof_is_always_int():
    model, diagnostics = analyze_text("void f(void) { sizeof(int); int x; sizeof x; }\n")
    for node in walk(model.program):
        if isinstance(node, ast.SizeofExpr):
            assert node.type_annotation == PrimitiveType("int")
    assert not diagnostics.diagnostics


# --- array-typed declarations -------------------------------------------


def test_array_var_decl_records_array_and_size_on_the_ast_node():
    model, _ = analyze_text("void f(void) { int arr[5]; }\n")
    func = find(model.program, ast.FuncDecl)
    var_decl = find(func.body, ast.VarDecl, name="arr")
    # VarDecl itself has no type_annotation (only Expr nodes do); the
    # computed Type lives on the Symbol instead - see the next test.
    assert var_decl.array is True
    assert var_decl.array_size.value == 5


def test_array_symbol_type_is_array_type_via_model():
    model, _ = analyze_text("void f(void) { int arr[5]; arr[0]; }\n")
    func_decl = find(model.program, ast.FuncDecl)
    function_scope = next(s for s in model.all_scopes if s.owner is func_decl)
    body_scope = next(s for s in model.all_scopes if s.owner is func_decl.body)
    symbol = body_scope.lookup_local("arr") or function_scope.lookup_local("arr")
    assert symbol.type == ArrayType(PrimitiveType("int"), size=5)

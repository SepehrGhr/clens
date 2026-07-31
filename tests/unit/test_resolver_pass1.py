"""S2.1 — Pass 1: the declaration scan. Only top-level names; never
descends into a function body.
"""

from clens.core.diagnostics import DiagnosticCollector, SemanticCode, Severity
from clens.core.scopes import ScopeKind
from clens.core.source import SourceFile
from clens.core.symbols import SymbolKind
from clens.core.types import ArrayType, FunctionType, PrimitiveType
from clens.languages.c.parser import parse
from clens.languages.c.resolver import scan_declarations


def scan(text: str):
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    program = parse(source, diagnostics)
    global_scope, all_scopes = scan_declarations(program, source, diagnostics)
    return global_scope, all_scopes, diagnostics


def test_global_var_registered_with_its_type():
    global_scope, _, diagnostics = scan("int g = 1;\n")
    symbol = global_scope.lookup_local("g")
    assert symbol.kind is SymbolKind.VARIABLE
    assert symbol.type == PrimitiveType("int")
    assert not diagnostics.diagnostics


def test_array_var_gets_array_type_with_known_size():
    global_scope, _, _ = scan("int arr[10];\n")
    symbol = global_scope.lookup_local("arr")
    assert symbol.type == ArrayType(PrimitiveType("int"), size=10)


def test_prototype_registers_a_function_signature():
    global_scope, _, diagnostics = scan("int later(int n);\n")
    symbol = global_scope.lookup_local("later")
    assert symbol.kind is SymbolKind.FUNCTION
    expected = FunctionType(params=(PrimitiveType("int"),), ret=PrimitiveType("int"))
    assert symbol.signature == expected
    assert not diagnostics.diagnostics


def test_function_body_is_not_descended_into_during_pass1():
    """Pass 1 must not resolve names inside a function body - an undefined
    reference in a body must not be reported here (that's Pass 2's job)."""
    global_scope, _, diagnostics = scan("int f(void) { return undeclared_name; }\n")
    assert global_scope.lookup_local("f") is not None
    assert not diagnostics.diagnostics


def test_struct_declares_a_type_symbol_and_a_field_scope():
    global_scope, all_scopes, diagnostics = scan("struct Point { int x; int y; };\n")
    symbol = global_scope.lookup_local("Point")
    assert symbol.kind is SymbolKind.TYPE
    assert str(symbol.type) == "struct Point"

    struct_scopes = [s for s in all_scopes if s.kind is ScopeKind.STRUCT]
    assert len(struct_scopes) == 1
    field_names = set(struct_scopes[0].symbols)
    assert field_names == {"x", "y"}
    assert not diagnostics.diagnostics


def test_struct_field_type_resolves_through_the_field_scope():
    _, all_scopes, _ = scan("struct Point { int x; };\n")
    struct_scope = next(s for s in all_scopes if s.kind is ScopeKind.STRUCT)
    assert struct_scope.symbols["x"].type == PrimitiveType("int")


def test_duplicate_global_var_reports_row_8():
    _, _, diagnostics = scan("int a = 1;\nint a = 2;\n")
    assert len(diagnostics.diagnostics) == 1
    d = diagnostics.diagnostics[0]
    assert d.severity is Severity.ERROR
    assert d.code == SemanticCode.DUPLICATE_DECLARATION
    assert "already declared" in d.message


def test_duplicate_struct_tag_reports_row_8():
    _, _, diagnostics = scan("struct P { int x; };\nstruct P { int y; };\n")
    assert len(diagnostics.diagnostics) == 1
    assert diagnostics.diagnostics[0].code == SemanticCode.DUPLICATE_DECLARATION


def test_name_collision_across_kinds_is_a_duplicate():
    """A function name colliding with an existing variable name (or vice
    versa) is still a duplicate declaration, not a silent overwrite."""
    _, _, diagnostics = scan("int foo;\nint foo(void);\n")
    assert len(diagnostics.diagnostics) == 1
    assert diagnostics.diagnostics[0].code == SemanticCode.DUPLICATE_DECLARATION

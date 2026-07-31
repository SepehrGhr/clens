"""R2.1, R3.1 — declaration parsing: type specs, pointers, function
definitions/prototypes, parameter lists, multi-declarator variable
declarations, struct declarations, and the full program entry point.
"""

from pathlib import Path

from clens.core.diagnostics import DiagnosticCollector
from clens.core.source import SourceFile
from clens.languages.c import ast_nodes as ast
from clens.languages.c.parser import parse

FIXTURES = Path(__file__).parent.parent / "fixtures"


def parse_program(text: str) -> tuple[ast.Program, DiagnosticCollector]:
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    return parse(source, diagnostics), diagnostics


def test_empty_file_parses_to_empty_program():
    program, diagnostics = parse_program("")
    assert isinstance(program, ast.Program)
    assert program.declarations == []
    assert not diagnostics.diagnostics


def test_function_prototype_has_no_body():
    program, diagnostics = parse_program("int factorial(int n);")
    assert not diagnostics.diagnostics
    (decl,) = program.declarations
    assert isinstance(decl, ast.FuncDecl)
    assert decl.name == "factorial"
    assert decl.body is None
    assert [p.name for p in decl.params] == ["n"]


def test_function_definition_has_a_body():
    program, diagnostics = parse_program("int f(void) { return 0; }")
    assert not diagnostics.diagnostics
    (decl,) = program.declarations
    assert isinstance(decl, ast.FuncDecl)
    assert isinstance(decl.body, ast.Block)
    assert len(decl.body.body) == 1


def test_function_with_no_params_and_void():
    program, _ = parse_program("void f(void) {}")
    (decl,) = program.declarations
    assert decl.params == []


def test_multiple_parameters():
    program, _ = parse_program("int add(int a, int b) { return a + b; }")
    (decl,) = program.declarations
    assert [p.name for p in decl.params] == ["a", "b"]
    assert all(p.type.base == "int" for p in decl.params)


def test_pointer_type_spec():
    program, _ = parse_program("char* p;")
    (decl,) = program.declarations
    assert isinstance(decl, ast.VarDecl)
    assert decl.type.base == "char"
    assert decl.type.pointer_depth == 1


def test_multi_level_pointer():
    program, _ = parse_program("int** pp;")
    (decl,) = program.declarations
    assert decl.type.pointer_depth == 2


def test_const_and_storage_qualifiers():
    program, _ = parse_program("static const int x = 5;")
    (decl,) = program.declarations
    assert decl.type.is_const is True
    assert decl.type.storage == "static"


def test_array_declarator_with_and_without_size():
    program, _ = parse_program("int a[10]; int b[];")
    a, b = program.declarations
    assert a.array is True and a.array_size.value == 10
    assert b.array is True and b.array_size is None


def test_array_parameter_with_and_without_size():
    """'int a[10]' and 'int a[]' are also valid in a parameter list
    (project/03-c-subset.md), not just in a variable declaration."""
    program, diagnostics = parse_program("void f(int a[10], int b[]) {}")
    assert not diagnostics.diagnostics
    (decl,) = program.declarations
    sized, unsized = decl.params
    assert sized.array is True and sized.array_size.value == 10
    assert unsized.array is True and unsized.array_size is None


def test_multiple_declarators_share_type_no_wrapper_node():
    """int a = 1, b, c = 3; -> three sibling VarDecl nodes."""
    program, diagnostics = parse_program("int a = 1, b, c = 3;")
    assert not diagnostics.diagnostics
    assert len(program.declarations) == 3
    a, b, c = program.declarations
    assert all(isinstance(d, ast.VarDecl) for d in (a, b, c))
    assert (a.name, a.init.value) == ("a", 1)
    assert (b.name, b.init) == ("b", None)
    assert (c.name, c.init.value) == ("c", 3)
    assert a.type is b.type is c.type  # one shared TypeSpec, not copies


def test_global_var_decl_no_init():
    program, _ = parse_program("int x;")
    (decl,) = program.declarations
    assert decl.init is None


def test_struct_decl_with_fields():
    program, diagnostics = parse_program("struct Point { int x; int y; };")
    assert not diagnostics.diagnostics
    (decl,) = program.declarations
    assert isinstance(decl, ast.StructDecl)
    assert decl.name == "Point"
    assert [f.name for f in decl.fields] == ["x", "y"]


def test_struct_typed_variable():
    program, diagnostics = parse_program("struct Point { int x; int y; }; struct Point origin;")
    assert not diagnostics.diagnostics
    struct_decl, var_decl = program.declarations
    assert isinstance(struct_decl, ast.StructDecl)
    assert isinstance(var_decl, ast.VarDecl)
    assert var_decl.type.base == "struct"
    assert var_decl.type.struct_name == "Point"


def test_sizeof_of_a_type():
    program, diagnostics = parse_program("int x = sizeof(int);")
    assert not diagnostics.diagnostics
    (decl,) = program.declarations
    assert isinstance(decl.init, ast.SizeofExpr)
    assert isinstance(decl.init.target, ast.TypeSpec)
    assert decl.init.target.base == "int"


def test_for_loop_with_declaration_init():
    program, diagnostics = parse_program(
        "int f(void) { for (int i = 0; i < 10; i = i + 1) { } return 0; }"
    )
    assert not diagnostics.diagnostics
    (func,) = program.declarations
    for_stmt = func.body.body[0]
    assert isinstance(for_stmt, ast.ForStmt)
    assert isinstance(for_stmt.init, list)
    assert for_stmt.init[0].name == "i"


def test_local_multi_declarator_inside_block():
    program, diagnostics = parse_program("int f(void) { int a = 1, b = 2; return a + b; }")
    assert not diagnostics.diagnostics
    (func,) = program.declarations
    a, b, ret = func.body.body
    assert (a.name, b.name) == ("a", "b")
    assert isinstance(ret, ast.ReturnStmt)


def test_golden_factorial_file_parses_cleanly():
    text = (FIXTURES / "valid" / "factorial.c").read_text()
    program, diagnostics = parse_program(text)
    assert not diagnostics.errors
    (func,) = program.declarations
    assert isinstance(func, ast.FuncDecl)
    assert func.name == "factorial"
    assert isinstance(func.body, ast.Block)
    if_stmt, return_stmt = func.body.body
    assert isinstance(if_stmt, ast.IfStmt)
    assert isinstance(return_stmt, ast.ReturnStmt)
    # The exact golden fragment checked in test_ast_printer.py:
    binary = return_stmt.value
    assert isinstance(binary, ast.BinaryExpr) and binary.op == "*"
    assert binary.left.name == "n"
    assert (binary.left.span.line, binary.left.span.column) == (3, 12)
    call = binary.right
    assert isinstance(call, ast.CallExpr) and call.callee == "factorial"
    assert (call.span.line, call.span.column) == (3, 16)


def test_program_span_covers_whole_file():
    program, _ = parse_program("int x;\nint y;\n")
    assert program.span.start_offset == 0
    assert program.span.end_offset == len("int x;\nint y;\n")

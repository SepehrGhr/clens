"""S2.2, S3.1-S3.3 — Pass 2: scope construction and reference resolution."""

from clens.core.diagnostics import DiagnosticCollector, SemanticCode, Severity
from clens.core.scopes import ScopeKind
from clens.core.source import SourceFile
from clens.languages.c.parser import parse
from clens.languages.c.resolver import resolve


def run(text: str):
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    program = parse(source, diagnostics)
    global_scope, all_scopes, symbols_by_name = resolve(program, source, diagnostics)
    return global_scope, all_scopes, symbols_by_name, diagnostics


def test_function_and_body_block_are_two_separate_scopes():
    _, all_scopes, _, diagnostics = run("int f(int x) { return x; }\n")
    kinds = [s.kind for s in all_scopes]
    assert kinds.count(ScopeKind.FUNCTION) == 1
    assert kinds.count(ScopeKind.BLOCK) == 1
    assert not diagnostics.diagnostics


def test_parameter_is_visible_and_read_inside_the_body():
    _, all_scopes, _, diagnostics = run("int f(int x) { return x; }\n")
    function_scope = next(s for s in all_scopes if s.kind is ScopeKind.FUNCTION)
    param_symbol = function_scope.symbols["x"]
    assert param_symbol.is_used is True
    assert len(param_symbol.references) == 1
    assert param_symbol.references[0].is_read is True
    assert not diagnostics.diagnostics


def test_call_resolves_and_records_a_reference_on_the_callee():
    global_scope, _, _, diagnostics = run(
        "int g(void) { return 1; }\nint f(void) { return g(); }\n"
    )
    g_symbol = global_scope.lookup_local("g")
    assert len(g_symbol.references) == 1
    assert g_symbol.references[0].is_read is True
    assert g_symbol.is_used is True
    assert not diagnostics.diagnostics


def test_undefined_identifier_reports_row_5_once_for_five_uses():
    """S9.2 no-cascade: one undefined name used five times is one diagnostic."""
    text = (
        "int use(void) {\n"
        "    counter = 1;\n"
        "    counter = counter + 1;\n"
        "    return counter * counter;\n"
        "}\n"
    )
    _, _, _, diagnostics = run(text)
    assert len(diagnostics.diagnostics) == 1
    d = diagnostics.diagnostics[0]
    assert d.code == SemanticCode.UNDEFINED_SYMBOL
    assert d.severity is Severity.ERROR
    assert "counter" in d.message


def test_assignment_target_is_write_only_plain_assign():
    global_scope, _, _, _ = run("int x; void f(void) { x = 1; }\n")
    x_symbol = global_scope.lookup_local("x")
    assert len(x_symbol.references) == 1
    ref = x_symbol.references[0]
    assert ref.is_write is True
    assert ref.is_read is False
    assert x_symbol.is_initialized is True


def test_compound_assignment_is_read_and_write():
    global_scope, _, _, _ = run("int x = 0; void f(void) { x += 1; }\n")
    x_symbol = global_scope.lookup_local("x")
    # First reference: the initializer's write. Second: the += read+write.
    compound_ref = x_symbol.references[-1]
    assert compound_ref.is_read is True
    assert compound_ref.is_write is True


def test_address_of_is_treated_as_a_conservative_write():
    global_scope, _, _, _ = run("int x; void f(void) { int *p; p = &x; }\n")
    x_symbol = global_scope.lookup_local("x")
    ref = x_symbol.references[0]
    assert ref.is_write is True
    assert ref.is_read is False


def test_increment_is_read_and_write():
    global_scope, _, _, _ = run("int x = 0; void f(void) { x++; }\n")
    x_symbol = global_scope.lookup_local("x")
    inc_ref = x_symbol.references[-1]
    assert inc_ref.is_read is True
    assert inc_ref.is_write is True


def test_var_decl_with_init_sets_is_initialized_and_write_reference():
    global_scope, _, _, _ = run("int g = 5;\n")
    symbol = global_scope.lookup_local("g")
    assert symbol.is_initialized is True
    assert any(r.is_write for r in symbol.references)


def test_for_init_declares_two_names_and_body_uses_them():
    text = "void f(void) { for (int i = 0, j = 9; i < j; i++) { j = i; } }\n"
    _, all_scopes, _, diagnostics = run(text)
    for_scopes = [s for s in all_scopes if s.kind is ScopeKind.FOR_INIT]
    assert len(for_scopes) == 1
    assert set(for_scopes[0].symbols) == {"i", "j"}
    assert not diagnostics.diagnostics


def test_error_stmt_region_is_skipped_without_crashing_or_extra_diagnostics():
    """A syntax error inside a body produces exactly the parser's own
    diagnostic; name resolution must not also report on the ErrorStmt
    region, and must not crash walking it."""
    text = "int f(void) { int x = ; return 0; }\n"
    _, _, _, diagnostics = run(text)
    # Whatever the parser reported, resolution added nothing extra to it,
    # and in particular never mentions "undefined" from inside the hole.
    assert not any(d.code == SemanticCode.UNDEFINED_SYMBOL for d in diagnostics.diagnostics)


def test_member_expr_resolves_the_object_but_not_the_member_name():
    """The member name itself is not scope-resolved (Stage 4's job); only
    `.obj` is walked, so an undefined `.obj` still reports."""
    text = "struct P { int x; }; void f(void) { struct P p; missing.x; }\n"
    _, _, _, diagnostics = run(text)
    undefined = [d for d in diagnostics.diagnostics if d.code == SemanticCode.UNDEFINED_SYMBOL]
    assert len(undefined) == 1
    assert "missing" in undefined[0].message

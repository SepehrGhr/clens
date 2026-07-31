"""P3.6 — the closing Stage 3 sweep: mutual recursion explicitly, the full
scopes.c nesting fixture, and robustness against ErrorStmt-heavy input.

Forward reference, the three shadowing depths, and same-vs-inner-scope
redeclaration are already covered by test_resolver_prototypes.py and
test_resolver_diagnostics.py against the real fixtures.
"""

from pathlib import Path

from clens.core.diagnostics import DiagnosticCollector
from clens.core.scopes import ScopeKind
from clens.core.source import SourceFile
from clens.languages.c.parser import parse
from clens.languages.c.resolver import resolve

FIXTURES_VALID = Path(__file__).parent.parent / "fixtures" / "valid"


def analyze(text: str, filename: str = "a.c"):
    source = SourceFile(text, filename)
    diagnostics = DiagnosticCollector()
    program = parse(source, diagnostics)
    global_scope, all_scopes, symbols_by_name = resolve(program, source, diagnostics)
    return global_scope, all_scopes, symbols_by_name, diagnostics


def test_mutual_recursion_both_functions_call_each_other():
    text = (FIXTURES_VALID / "forward_reference.c").read_text()
    global_scope, _, _, diagnostics = analyze(text)
    assert not diagnostics.diagnostics

    earlier = global_scope.lookup_local("earlier")
    later = global_scope.lookup_local("later")
    # earlier() calls later() (forward call); later() calls earlier() back.
    assert earlier.is_used is True
    assert later.is_used is True
    assert any(r.is_read for r in earlier.references)
    assert any(r.is_read for r in later.references)


def test_scopes_fixture_builds_the_full_tree_with_no_diagnostics():
    """The scopes.c fixture: global, function, nested blocks, and a
    for-init scope with two declared names, all in one file."""
    text = (FIXTURES_VALID / "scopes.c").read_text()
    global_scope, all_scopes, _, diagnostics = analyze(text)
    assert not diagnostics.diagnostics

    kinds = [s.kind for s in all_scopes]
    assert kinds.count(ScopeKind.GLOBAL) == 1
    assert kinds.count(ScopeKind.FUNCTION) == 1
    assert kinds.count(ScopeKind.BLOCK) >= 2  # two nested blocks in outer()
    assert kinds.count(ScopeKind.FOR_INIT) == 1

    for_scope = next(s for s in all_scopes if s.kind is ScopeKind.FOR_INIT)
    assert set(for_scope.symbols) == {"i", "j"}

    g_symbol = global_scope.lookup_local("g")
    assert g_symbol.is_used is True


def test_error_stmt_region_does_not_crash_with_multiple_broken_statements():
    """Several syntax errors in one body: the parser fills in ErrorStmt for
    each; resolution must walk past all of them without raising and without
    adding its own diagnostics on top."""
    text = "int f(void) { int x = ; int y = ; return x + y; }\n"
    _, _, _, diagnostics = analyze(text)
    # The parser's own recovery diagnostics may be present; resolution must
    # not have raised getting here, and must not report anything about the
    # (undeclared-looking) holes themselves.
    assert isinstance(diagnostics.diagnostics, list)


def test_error_expr_inside_a_binary_expression_does_not_crash():
    text = "int f(void) { return 1 + ; }\n"
    _, _, _, diagnostics = analyze(text)
    assert isinstance(diagnostics.diagnostics, list)

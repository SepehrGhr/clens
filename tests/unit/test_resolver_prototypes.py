"""P3.5 — prototype-then-definition must not fire duplicate-declaration;
mismatched signatures between them must.
"""

from pathlib import Path

from clens.core.diagnostics import DiagnosticCollector, SemanticCode, Severity
from clens.core.source import SourceFile
from clens.core.symbols import SymbolKind
from clens.languages.c.parser import parse
from clens.languages.c.resolver import resolve, scan_declarations


def scan(text: str):
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    program = parse(source, diagnostics)
    global_scope, all_scopes = scan_declarations(program, source, diagnostics)
    return global_scope, all_scopes, diagnostics


def test_matching_prototype_then_definition_is_not_a_duplicate():
    text = "int later(int n);\nint later(int n) { return n; }\n"
    global_scope, _, diagnostics = scan(text)
    assert not diagnostics.diagnostics
    symbol = global_scope.lookup_local("later")
    assert symbol.kind is SymbolKind.FUNCTION


def test_repeated_identical_prototype_is_not_a_duplicate():
    text = "int later(int n);\nint later(int n);\n"
    _, _, diagnostics = scan(text)
    assert not diagnostics.diagnostics


def test_mismatched_signature_between_prototype_and_definition_errors():
    """Different return type: the prototype says int, the definition says
    void - an error at the definition, naming the prototype's location."""
    text = "int later(int n);\nvoid later(int n) { }\n"
    _, _, diagnostics = scan(text)
    assert len(diagnostics.diagnostics) == 1
    d = diagnostics.diagnostics[0]
    assert d.severity is Severity.ERROR
    assert d.code == SemanticCode.DUPLICATE_DECLARATION
    assert "does not match its prototype" in d.message
    assert d.start.line == 2  # reported at the definition, not the prototype


def test_mismatched_parameter_type_between_prototype_and_definition_errors():
    text = "int later(int n);\nint later(char n) { return n; }\n"
    _, _, diagnostics = scan(text)
    assert len(diagnostics.diagnostics) == 1
    assert diagnostics.diagnostics[0].code == SemanticCode.DUPLICATE_DECLARATION


def test_two_full_definitions_is_a_duplicate_even_with_matching_signatures():
    text = "int f(void) { return 1; }\nint f(void) { return 2; }\n"
    _, _, diagnostics = scan(text)
    assert len(diagnostics.diagnostics) == 1
    d = diagnostics.diagnostics[0]
    assert d.severity is Severity.ERROR
    assert d.code == SemanticCode.DUPLICATE_DECLARATION
    assert "already declared" in d.message


def test_forward_reference_fixture_has_no_diagnostics():
    """tests/fixtures/valid/forward_reference.c: a prototype, a forward
    call through it, and a mutually-recursive definition - all clean. Uses
    full resolve() (both passes), since the calls being checked live in
    function bodies, which Pass 1 alone never looks at."""
    path = Path(__file__).parent.parent / "fixtures" / "valid" / "forward_reference.c"
    source = SourceFile(path.read_text(), "forward_reference.c")
    diagnostics = DiagnosticCollector()
    program = parse(source, diagnostics)
    resolve(program, source, diagnostics)
    assert not diagnostics.diagnostics

"""D19, S1.3 — SemanticModel is the returned artifact, not a byproduct."""

from clens.core.diagnostics import DiagnosticCollector
from clens.core.scopes import Scope, ScopeKind
from clens.core.source import SourceFile
from clens.core.token import Span
from clens.languages.c.ast_nodes import Program
from clens.languages.c.parser import parse
from clens.languages.c.semantic import SemanticModel, analyze

SPAN = Span(start_offset=0, end_offset=1, line=1, column=1)


def test_semantic_model_holds_program_scope_and_source():
    program = Program(span=SPAN)
    global_scope = Scope(kind=ScopeKind.GLOBAL, parent=None, span=SPAN)
    source = SourceFile("int main() { return 0; }\n", "a.c")

    model = SemanticModel(
        program=program,
        global_scope=global_scope,
        source=source,
        diagnostics=DiagnosticCollector(),
    )

    assert model.program is program
    assert model.global_scope is global_scope
    assert model.source is source
    assert model.all_scopes == []
    assert model.symbols_by_name == {}
    assert model.tokens == []


def test_semantic_model_all_scopes_and_symbols_by_name_are_independent_per_instance():
    """Mutable defaults must not be shared across instances."""
    program = Program(span=SPAN)
    source = SourceFile("", "a.c")

    a = SemanticModel(
        program=program,
        global_scope=Scope(kind=ScopeKind.GLOBAL, parent=None, span=SPAN),
        source=source,
        diagnostics=DiagnosticCollector(),
    )
    b = SemanticModel(
        program=program,
        global_scope=Scope(kind=ScopeKind.GLOBAL, parent=None, span=SPAN),
        source=source,
        diagnostics=DiagnosticCollector(),
    )

    a.all_scopes.append(a.global_scope)
    assert b.all_scopes == []


def test_analyze_runs_resolution_and_assembles_the_model():
    source = SourceFile("int g = 1;\nint f(void) { return g; }\n", "a.c")
    diagnostics = DiagnosticCollector()
    program = parse(source, diagnostics)

    model = analyze(program, source, diagnostics)

    assert model.program is program
    assert model.source is source
    assert model.global_scope.lookup_local("g") is not None
    assert "g" in model.symbols_by_name
    assert len(model.all_scopes) >= 2  # global + at least one function scope
    assert not diagnostics.diagnostics
    assert model.diagnostics is diagnostics
    assert model.tokens == []


def test_analyze_stores_tokens_when_given_them():
    from clens.languages.c.lexer import tokenize

    text = "int g = 1;\n"
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    tokens = tokenize(source, diagnostics)
    program = parse(source, diagnostics)

    model = analyze(program, source, diagnostics, tokens=tokens)

    assert model.tokens is tokens

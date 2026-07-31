"""D19, S1.3 — SemanticModel is the returned artifact, not a byproduct."""

from clens.core.scopes import Scope, ScopeKind
from clens.core.source import SourceFile
from clens.core.token import Span
from clens.languages.c.ast_nodes import Program
from clens.languages.c.semantic import SemanticModel

SPAN = Span(start_offset=0, end_offset=1, line=1, column=1)


def test_semantic_model_holds_program_scope_and_source():
    program = Program(span=SPAN)
    global_scope = Scope(kind=ScopeKind.GLOBAL, parent=None, span=SPAN)
    source = SourceFile("int main() { return 0; }\n", "a.c")

    model = SemanticModel(program=program, global_scope=global_scope, source=source)

    assert model.program is program
    assert model.global_scope is global_scope
    assert model.source is source
    assert model.all_scopes == []
    assert model.symbols_by_name == {}


def test_semantic_model_all_scopes_and_symbols_by_name_are_independent_per_instance():
    """Mutable defaults must not be shared across instances."""
    program = Program(span=SPAN)
    source = SourceFile("", "a.c")

    a = SemanticModel(
        program=program,
        global_scope=Scope(kind=ScopeKind.GLOBAL, parent=None, span=SPAN),
        source=source,
    )
    b = SemanticModel(
        program=program,
        global_scope=Scope(kind=ScopeKind.GLOBAL, parent=None, span=SPAN),
        source=source,
    )

    a.all_scopes.append(a.global_scope)
    assert b.all_scopes == []

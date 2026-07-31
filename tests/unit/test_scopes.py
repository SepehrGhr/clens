"""S1.2 — the scope tree: nesting, shadowing lookups, and the struct-scope
exclusion from the lexical chain.
"""

from clens.core.scopes import Scope, ScopeKind
from clens.core.symbols import Symbol, SymbolKind
from clens.core.token import Span
from clens.core.types import PrimitiveType

SPAN = Span(start_offset=0, end_offset=100, line=1, column=1)


def make_symbol(name: str, scope: Scope) -> Symbol:
    return Symbol(
        name=name,
        kind=SymbolKind.VARIABLE,
        type=PrimitiveType("int"),
        scope=scope,
        definition_loc=SPAN,
    )


def test_declare_returns_none_on_clean_declaration():
    scope = Scope(kind=ScopeKind.GLOBAL, parent=None, span=SPAN)
    result = scope.declare(make_symbol("x", scope))
    assert result is None
    assert scope.lookup_local("x") is not None


def test_declare_returns_existing_symbol_on_collision():
    scope = Scope(kind=ScopeKind.GLOBAL, parent=None, span=SPAN)
    first = make_symbol("x", scope)
    scope.declare(first)
    collision = scope.declare(make_symbol("x", scope))
    assert collision is first


def test_lookup_local_does_not_walk_outward():
    global_scope = Scope(kind=ScopeKind.GLOBAL, parent=None, span=SPAN)
    global_scope.declare(make_symbol("g", global_scope))
    block = Scope(kind=ScopeKind.BLOCK, parent=global_scope, span=SPAN)
    assert block.lookup_local("g") is None
    assert global_scope.lookup_local("g") is not None


def test_lookup_walks_outward_to_global():
    global_scope = Scope(kind=ScopeKind.GLOBAL, parent=None, span=SPAN)
    g_symbol = make_symbol("g", global_scope)
    global_scope.declare(g_symbol)

    function_scope = Scope(kind=ScopeKind.FUNCTION, parent=global_scope, span=SPAN)
    block = Scope(kind=ScopeKind.BLOCK, parent=function_scope, span=SPAN)

    assert block.lookup("g") is g_symbol


def test_lookup_returns_none_when_not_found_anywhere():
    global_scope = Scope(kind=ScopeKind.GLOBAL, parent=None, span=SPAN)
    block = Scope(kind=ScopeKind.BLOCK, parent=global_scope, span=SPAN)
    assert block.lookup("missing") is None


def test_lookup_finds_inner_shadow_before_outer():
    global_scope = Scope(kind=ScopeKind.GLOBAL, parent=None, span=SPAN)
    outer_x = make_symbol("x", global_scope)
    global_scope.declare(outer_x)

    block = Scope(kind=ScopeKind.BLOCK, parent=global_scope, span=SPAN)
    inner_x = make_symbol("x", block)
    block.declare(inner_x)

    assert block.lookup("x") is inner_x
    assert block.lookup("x") is not outer_x


def test_lookup_with_scope_returns_the_defining_scope():
    global_scope = Scope(kind=ScopeKind.GLOBAL, parent=None, span=SPAN)
    g_symbol = make_symbol("g", global_scope)
    global_scope.declare(g_symbol)
    block = Scope(kind=ScopeKind.BLOCK, parent=global_scope, span=SPAN)

    found = block.lookup_with_scope("g")

    assert found == (g_symbol, global_scope)


def test_lookup_with_scope_none_when_missing():
    global_scope = Scope(kind=ScopeKind.GLOBAL, parent=None, span=SPAN)
    assert global_scope.lookup_with_scope("missing") is None


def test_three_levels_of_nesting_resolve_correctly():
    """global -> function -> block, a name declared at each level."""
    global_scope = Scope(kind=ScopeKind.GLOBAL, parent=None, span=SPAN)
    global_scope.declare(make_symbol("g", global_scope))

    function_scope = Scope(kind=ScopeKind.FUNCTION, parent=global_scope, span=SPAN)
    function_scope.declare(make_symbol("param", function_scope))

    block = Scope(kind=ScopeKind.BLOCK, parent=function_scope, span=SPAN)
    local = make_symbol("local", block)
    block.declare(local)

    assert block.lookup("local") is local
    assert block.lookup("param") is not None
    assert block.lookup("g") is not None


def test_struct_scope_fields_are_visible_locally():
    global_scope = Scope(kind=ScopeKind.GLOBAL, parent=None, span=SPAN)
    struct_scope = Scope(kind=ScopeKind.STRUCT, parent=global_scope, span=SPAN)
    field_symbol = Symbol(
        name="x",
        kind=SymbolKind.FIELD,
        type=PrimitiveType("int"),
        scope=struct_scope,
        definition_loc=SPAN,
    )
    struct_scope.declare(field_symbol)

    assert struct_scope.lookup("x") is field_symbol


def test_struct_scope_lookup_never_escalates_to_parent():
    """A struct's fields are reachable only through member access, never by
    bare name — lookup() on a struct scope must not fall through to global
    for a name it doesn't itself declare."""
    global_scope = Scope(kind=ScopeKind.GLOBAL, parent=None, span=SPAN)
    global_scope.declare(make_symbol("g", global_scope))
    struct_scope = Scope(kind=ScopeKind.STRUCT, parent=global_scope, span=SPAN)

    assert struct_scope.lookup("g") is None


def test_struct_scope_parented_for_tree_display_only():
    """Struct scopes still show up as children for tree rendering (clens
    symbols), even though lookup never routes through them."""
    global_scope = Scope(kind=ScopeKind.GLOBAL, parent=None, span=SPAN)
    struct_scope = Scope(kind=ScopeKind.STRUCT, parent=global_scope, span=SPAN)
    global_scope.children.append(struct_scope)

    assert struct_scope in global_scope.children
    assert struct_scope.parent is global_scope

"""D15 — resolve_type_spec bridges syntactic TypeSpec to semantic Type.

Stage 2's real Scope/Symbol don't exist yet, so these tests use a minimal
stand-in that satisfies the _ScopeLike/_HasType protocols structurally
(a plain dict of name -> object-with-a-.type-attribute).
"""

from dataclasses import dataclass

from clens.core.ast_nodes import Node
from clens.core.token import Span
from clens.core.types import PointerType, PrimitiveType, StructType, Type, UnknownType
from clens.languages.c.ast_nodes import TypeSpec
from clens.languages.c.typecheck import resolve_type_spec

SPAN = Span(start_offset=0, end_offset=1, line=1, column=1)


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

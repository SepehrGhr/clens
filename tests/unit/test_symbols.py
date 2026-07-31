"""S1.1 — Symbol's nine required fields, SymbolKind, and Reference."""

from clens.core.symbols import Reference, Symbol, SymbolKind
from clens.core.token import Span
from clens.core.types import FunctionType, PrimitiveType

SPAN = Span(start_offset=0, end_offset=1, line=1, column=1)


def test_symbol_kind_has_the_five_c_relevant_kinds():
    assert {k.value for k in SymbolKind} == {
        "variable",
        "function",
        "parameter",
        "type",
        "field",
    }


def test_reference_defaults_to_neither_read_nor_write():
    ref = Reference(span=SPAN)
    assert ref.is_read is False
    assert ref.is_write is False


def test_reference_can_be_both_read_and_write():
    """x += 1 is both a read and a write of x."""
    ref = Reference(span=SPAN, is_read=True, is_write=True)
    assert ref.is_read is True
    assert ref.is_write is True


def test_symbol_has_all_nine_fields_with_sane_defaults():
    symbol = Symbol(
        name="x",
        kind=SymbolKind.VARIABLE,
        type=PrimitiveType("int"),
        scope=None,
        definition_loc=SPAN,
    )
    assert symbol.name == "x"
    assert symbol.kind is SymbolKind.VARIABLE
    assert symbol.type == PrimitiveType("int")
    assert symbol.scope is None
    assert symbol.definition_loc == SPAN
    assert symbol.references == []
    assert symbol.signature is None
    assert symbol.is_initialized is False
    assert symbol.is_used is False


def test_symbol_references_accumulate():
    symbol = Symbol(
        name="x",
        kind=SymbolKind.VARIABLE,
        type=PrimitiveType("int"),
        scope=None,
        definition_loc=SPAN,
    )
    symbol.references.append(Reference(span=SPAN, is_write=True))
    symbol.references.append(Reference(span=SPAN, is_read=True))
    symbol.is_used = True
    assert len(symbol.references) == 2
    assert symbol.is_used is True


def test_function_symbol_carries_a_signature():
    signature = FunctionType(params=(PrimitiveType("int"),), ret=PrimitiveType("int"))
    symbol = Symbol(
        name="factorial",
        kind=SymbolKind.FUNCTION,
        type=signature,
        scope=None,
        definition_loc=SPAN,
        signature=signature,
    )
    assert symbol.signature == signature
    assert str(symbol.signature) == "(int) -> int"

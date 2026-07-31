"""S4.1, D15-D18 — the semantic Type hierarchy: variants, __str__, numeric
conversion, and assignability.
"""

import itertools

import pytest

from clens.core.ast_nodes import Node
from clens.core.token import Span
from clens.core.types import (
    ArrayType,
    FunctionType,
    PointerType,
    PrimitiveType,
    StructType,
    UnknownType,
    usual_arithmetic_conversion,
)

SPAN = Span(start_offset=0, end_offset=1, line=1, column=1)

_RANK_ORDER = ["char", "int", "float", "double"]


def test_primitive_str_is_bare_name():
    assert str(PrimitiveType("int")) == "int"
    assert str(PrimitiveType("void")) == "void"


def test_pointer_str_appends_star():
    assert str(PointerType(PrimitiveType("char"))) == "char*"


def test_pointer_nests_for_double_star():
    assert str(PointerType(PointerType(PrimitiveType("char")))) == "char**"


def test_array_str_with_and_without_known_size():
    assert str(ArrayType(PrimitiveType("int"), size=10)) == "int[10]"
    assert str(ArrayType(PrimitiveType("int"), size=None)) == "int[]"


def test_struct_str_is_struct_plus_name():
    decl = Node(span=SPAN)
    assert str(StructType("Point", decl)) == "struct Point"


def test_function_str_matches_course_document_shape():
    fn = FunctionType(params=(PrimitiveType("int"),), ret=PrimitiveType("int"))
    assert str(fn) == "(int) -> int"


def test_function_str_with_no_params():
    fn = FunctionType(params=(), ret=PrimitiveType("void"))
    assert str(fn) == "() -> void"


def test_unknown_str():
    assert str(UnknownType()) == "unknown"


def test_primitive_types_compare_structurally():
    assert PrimitiveType("int") == PrimitiveType("int")
    assert PrimitiveType("int") != PrimitiveType("char")


def test_struct_types_compare_by_name_and_decl():
    decl = Node(span=SPAN)
    other_decl = Node(span=Span(start_offset=10, end_offset=11, line=2, column=1))
    assert StructType("Point", decl) == StructType("Point", decl)
    assert StructType("Point", decl) != StructType("Point", other_decl)


def test_unknown_type_instances_are_all_equal():
    assert UnknownType() == UnknownType()


def test_types_are_hashable():
    seen = {PrimitiveType("int"), PointerType(PrimitiveType("int")), UnknownType()}
    assert len(seen) == 3


@pytest.mark.parametrize("a_name,b_name", list(itertools.product(_RANK_ORDER, repeat=2)))
def test_usual_arithmetic_conversion_every_rank_pair(a_name, b_name):
    """D18: the operand with the higher rank wins, e.g. int + double -> double."""
    a, b = PrimitiveType(a_name), PrimitiveType(b_name)
    winner = a_name if _RANK_ORDER.index(a_name) >= _RANK_ORDER.index(b_name) else b_name
    assert str(usual_arithmetic_conversion(a, b)) == winner


def test_usual_arithmetic_conversion_unknown_absorbs_left():
    assert usual_arithmetic_conversion(UnknownType(), PrimitiveType("int")) == UnknownType()


def test_usual_arithmetic_conversion_unknown_absorbs_right():
    assert usual_arithmetic_conversion(PrimitiveType("int"), UnknownType()) == UnknownType()


def test_usual_arithmetic_conversion_non_numeric_yields_unknown():
    assert usual_arithmetic_conversion(PrimitiveType("void"), PrimitiveType("int")) == UnknownType()

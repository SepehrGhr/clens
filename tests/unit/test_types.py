"""S4.1, D15-D18 — the semantic Type hierarchy: variants, __str__, numeric
conversion, and assignability.
"""

import itertools

import pytest

from clens.core.ast_nodes import Node
from clens.core.token import Span
from clens.core.types import (
    ArrayType,
    AssignResult,
    FunctionType,
    PointerType,
    PrimitiveType,
    StructType,
    UnknownType,
    is_assignable,
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


@pytest.mark.parametrize("a_name,b_name", list(itertools.product(_RANK_ORDER, repeat=2)))
def test_is_assignable_every_rank_pair(a_name, b_name):
    """Widening (source rank <= target rank) is OK; narrowing is a warning,
    never an error — S4.7's `int x = 3.14;` needs exactly this."""
    target, source = PrimitiveType(a_name), PrimitiveType(b_name)
    expected = (
        AssignResult.OK
        if _RANK_ORDER.index(b_name) <= _RANK_ORDER.index(a_name)
        else AssignResult.NARROWING
    )
    assert is_assignable(target, source) is expected


def test_is_assignable_identical_types_ok():
    assert is_assignable(PrimitiveType("int"), PrimitiveType("int")) is AssignResult.OK
    p = PointerType(PrimitiveType("char"))
    assert is_assignable(p, PointerType(PrimitiveType("char"))) is AssignResult.OK


def test_is_assignable_unknown_absorbs_both_directions():
    assert is_assignable(UnknownType(), PrimitiveType("int")) is AssignResult.OK
    assert is_assignable(PrimitiveType("int"), UnknownType()) is AssignResult.OK


def test_is_assignable_pointer_int_mixing_is_incompatible():
    """S4.7 golden example 2: char *s = 42; is an error, not a warning."""
    target = PointerType(PrimitiveType("char"))
    assert is_assignable(target, PrimitiveType("int")) is AssignResult.INCOMPATIBLE


def test_is_assignable_int_to_pointer_is_incompatible_symmetrically():
    assert (
        is_assignable(PrimitiveType("int"), PointerType(PrimitiveType("char")))
        is AssignResult.INCOMPATIBLE
    )


def test_is_assignable_struct_mismatch_is_incompatible():
    decl_a = Node(span=SPAN)
    decl_b = Node(span=Span(start_offset=10, end_offset=11, line=2, column=1))
    assert is_assignable(StructType("Point", decl_a), StructType("Line", decl_b)) is (
        AssignResult.INCOMPATIBLE
    )


def test_is_assignable_narrowing_golden_example():
    """S4.7 golden example 1: int x = 3.14; is a warning."""
    assert is_assignable(PrimitiveType("int"), PrimitiveType("double")) is AssignResult.NARROWING


def test_is_assignable_mismatched_pointee_is_incompatible():
    """int* and char* are not the same type, even though both are pointers."""
    target = PointerType(PrimitiveType("int"))
    source = PointerType(PrimitiveType("char"))
    assert is_assignable(target, source) is AssignResult.INCOMPATIBLE


def test_is_assignable_matching_pointee_is_ok():
    target = PointerType(PrimitiveType("int"))
    source = PointerType(PrimitiveType("int"))
    assert is_assignable(target, source) is AssignResult.OK


def test_is_assignable_matching_struct_is_ok():
    decl = Node(span=SPAN)
    assert is_assignable(StructType("Point", decl), StructType("Point", decl)) is AssignResult.OK


def test_is_assignable_array_to_pointer_is_incompatible():
    """Arrays and pointers are distinct Type variants in this subset, even
    though C itself decays one to the other; no ArrayType/PointerType
    special-casing is implemented, so this is INCOMPATIBLE."""
    target = PointerType(PrimitiveType("int"))
    source = ArrayType(PrimitiveType("int"), size=10)
    assert is_assignable(target, source) is AssignResult.INCOMPATIBLE

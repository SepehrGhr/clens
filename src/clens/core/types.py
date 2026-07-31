"""The semantic `Type` hierarchy (S4.1-S4.8, D15-D16).

`Type` is what the checker reasons about — distinct from `TypeSpec`
(`languages/c/ast_nodes.py`), which is only what was *written* in source.
`resolve_type_spec` bridges the two and lives in `languages/c/typecheck.py`,
not here, since `TypeSpec` is a C-specific node and core must never import
from a language module.

All variants are frozen and structurally compared, and each has a readable
`__str__` — that string is exactly what hover and completion `detail` show,
so it is user-facing output, not debug output.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clens.core.ast_nodes import Node

__all__ = [
    "ArrayType",
    "AssignResult",
    "FunctionType",
    "PointerType",
    "PrimitiveType",
    "StructType",
    "Type",
    "UnknownType",
    "is_assignable",
    "usual_arithmetic_conversion",
]


@dataclass(frozen=True, slots=True)
class Type:
    """Base of the semantic type hierarchy. Never instantiated directly."""

    def __str__(self) -> str:  # pragma: no cover - overridden by every variant
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class PrimitiveType(Type):
    """`void`, `char`, `int`, `float`, or `double`. `void` is a `PrimitiveType`,
    not a separate variant (D16)."""

    name: str

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class PointerType(Type):
    """`pointee*`. Nests for `char**` etc."""

    pointee: Type

    def __str__(self) -> str:
        return f"{self.pointee}*"


@dataclass(frozen=True, slots=True)
class ArrayType(Type):
    """`element[size]`, or `element[]` when the size is unknown (e.g. an
    unsized `extern` array)."""

    element: Type
    size: int | None = None

    def __str__(self) -> str:
        size_str = "" if self.size is None else str(self.size)
        return f"{self.element}[{size_str}]"


@dataclass(frozen=True, slots=True)
class StructType(Type):
    """A named struct type. `decl` links back to the `StructDecl` so field
    lookup has something to walk — typed as the generic core `Node` rather
    than the C-specific `StructDecl`, since core must never import a
    language module.
    """

    name: str
    decl: Node

    def __str__(self) -> str:
        return f"struct {self.name}"


@dataclass(frozen=True, slots=True)
class FunctionType(Type):
    """A function's signature: parameter types in declared order, plus the
    return type."""

    params: tuple[Type, ...]
    ret: Type

    def __str__(self) -> str:
        param_str = ", ".join(str(p) for p in self.params)
        return f"({param_str}) -> {self.ret}"


@dataclass(frozen=True, slots=True)
class UnknownType(Type):
    """The error-suppression device (D17). Compatible with everything in
    both directions; every operation involving it yields `unknown` and emits
    no diagnostic. Every `ErrorExpr` and every unresolved name types as this.
    """

    def __str__(self) -> str:
        return "unknown"


# --- Conversion rank (D18) ---------------------------------------------------

_NUMERIC_RANK: dict[str, int] = {"char": 0, "int": 1, "float": 2, "double": 3}


def usual_arithmetic_conversion(a: Type, b: Type) -> Type:
    """The type a binary numeric operation promotes `a` and `b` to.

    Defined for the four numeric primitives (`char < int < float < double`):
    the operand with the higher rank wins, e.g. `int + double` -> `double`.
    `unknown` absorbs either operand (D17). Any other combination (a pointer,
    a struct, `void`) is not this function's call to make — the caller
    classifies those itself (pointer arithmetic, `void`-in-operand errors,
    etc.) before ever reaching here; this returns `unknown` for them rather
    than raising, so a caller that gets the classification wrong fails safe
    instead of crashing.
    """
    if isinstance(a, UnknownType) or isinstance(b, UnknownType):
        return UnknownType()
    rank_a = _NUMERIC_RANK.get(a.name) if isinstance(a, PrimitiveType) else None
    rank_b = _NUMERIC_RANK.get(b.name) if isinstance(b, PrimitiveType) else None
    if rank_a is None or rank_b is None:
        return UnknownType()
    return a if rank_a >= rank_b else b


class AssignResult(Enum):
    """The outcome of `is_assignable`, so callers do not each re-derive the
    severity from a bare bool."""

    OK = "ok"
    NARROWING = "narrowing"
    INCOMPATIBLE = "incompatible"


def is_assignable(target: Type, source: Type) -> AssignResult:
    """Can a value of type `source` be assigned to a variable of type
    `target`?

    - `unknown` on either side is always `OK` (D17).
    - Identical types are always `OK`.
    - Numeric widening (`source` rank <= `target` rank) is `OK`; numeric
      narrowing (e.g. `double` into `int`) is a `NARROWING` warning, not an
      error — that is what `int x = 3.14;` requires (D18).
    - Everything else (pointer/integer mixing, struct/pointer mismatches,
      ...) is `INCOMPATIBLE`.
    """
    if isinstance(target, UnknownType) or isinstance(source, UnknownType):
        return AssignResult.OK
    if target == source:
        return AssignResult.OK
    if isinstance(target, PrimitiveType) and isinstance(source, PrimitiveType):
        target_rank = _NUMERIC_RANK.get(target.name)
        source_rank = _NUMERIC_RANK.get(source.name)
        if target_rank is not None and source_rank is not None:
            if source_rank <= target_rank:
                return AssignResult.OK
            return AssignResult.NARROWING
    return AssignResult.INCOMPATIBLE

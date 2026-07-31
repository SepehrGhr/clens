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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clens.core.ast_nodes import Node

__all__ = [
    "ArrayType",
    "FunctionType",
    "PointerType",
    "PrimitiveType",
    "StructType",
    "Type",
    "UnknownType",
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

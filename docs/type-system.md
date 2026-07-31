# Type System

## `Type` is not `TypeSpec` (D15)

`languages/c/ast_nodes.py::TypeSpec` is **syntax** — exactly what appears in
the source: a base keyword (`int`, `struct`, ...), a pointer-star count, an
optional `struct` tag, `const`, a storage-class keyword. Two different
`TypeSpec` nodes can describe the same real type (`struct Point` written in
two different declarations), and a `TypeSpec` cannot express "this name
didn't resolve to anything" at all.

`core/types.py::Type` is **semantics** — what the checker actually reasons
about. It is a closed hierarchy of six frozen, structurally-compared
variants:

```python
PrimitiveType(name)  # "void" | "char" | "int" | "float" | "double"
PointerType(pointee)
ArrayType(element, size)  # size: int | None
StructType(name, decl)  # decl links to the real StructDecl, for field lookup
FunctionType(params, ret)  # params: tuple[Type, ...]
UnknownType()  # the error-suppression device — see below
```

`void` is a `PrimitiveType`, not its own variant (D16) — it behaves like any
other primitive for the rules below except that it is never numeric.

`resolve_type_spec(spec, scope) -> Type` (`languages/c/typecheck.py`) is the
bridge: it resolves `struct Point` against the scope to the real
`StructType` (canonicalising two textually-identical `struct Point` specs to
the *same* semantic type) and wraps `pointer_depth` levels of `PointerType`.
It is a pure query — no diagnostics, no side effects — precisely so hover
and completion can reuse it for display without accidentally re-reporting
an undefined struct tag that name resolution already reported once.

Every variant has a `__str__` that is the exact string hover and completion
`detail` show: `"int"`, `"char*"`, `"int[10]"`, `"struct Point"`,
`"(int, int) -> int"`, `"unknown"`.

## Conversion rank and the usual arithmetic conversion (D18)

```
char (0)  <  int (1)  <  float (2)  <  double (3)
```

`usual_arithmetic_conversion(a, b)` (`core/types.py`) is the rule for a
binary numeric operation: the operand with the higher rank wins —
`int + double` types as `double`. Pointer arithmetic is handled separately
by the type checker itself, not by this function: `ptr + int` (or
`int + ptr`) keeps the pointer's type, `ptr - ptr` yields `int`, and mixing
a pointer with anything else in an arithmetic operator degrades to
`unknown` rather than raising, since operand misclassification here isn't
one of S6's required diagnostics.

## Assignability (S4.5)

`is_assignable(target, source) -> AssignResult` returns one of three
outcomes, so every caller (a `VarDecl` initializer, an `AssignExpr`, a
function argument, a `return` value) asks the type system once instead of
re-deriving the severity itself:

| `AssignResult` | Meaning | Severity |
|---|---|---|
| `OK` | Identical types, or `source`'s rank ≤ `target`'s rank (a widening numeric conversion) | — |
| `NARROWING` | `source`'s rank > `target`'s rank (e.g. `double` into `int`) | **Warning** (`S010`) |
| `INCOMPATIBLE` | Anything else — pointer/integer mixing, mismatched pointees, mismatched structs, a struct against a scalar | **Error** (`S002` for assignment, `S003` for a call argument, `S006` for a `return`) |

`unknown` on either side is always `OK`, in both directions (D17 — see
below). This is exactly what `int x = 3.14;` (warning) versus
`char *s = 42;` (error) need, and it is the same check reused unchanged for
call arguments and `return` values, not three separate implementations.

## Per-node typing rules (S4.1–S4.3)

| Node | Type |
|---|---|
| `IntLiteral` | `int` |
| `FloatLiteral` | `double` |
| `StringLiteral` | `char*` |
| `CharLiteral` | `char` |
| `Identifier` | the resolved symbol's declared type, or `unknown` if it never resolved |
| `BinaryExpr` | comparisons (`== != < > <= >=`) and logicals (`&& \|\|`) always yield `int`; arithmetic yields the usual arithmetic conversion (or the pointer-arithmetic rules above) |
| `UnaryExpr` | `&x` → `PointerType(operand)`; `*p` → the pointee (or `unknown` if `p` isn't a pointer); `!x` → `int`; `- ~ ++ --` → the operand's own type |
| `AssignExpr` | the **target's** type; checks assignability against the value |
| `TernaryExpr` | the two branches' common type if identical, their usual arithmetic conversion if both numeric, otherwise an error (`S013`) |
| `CallExpr` | the callee's return type, or `unknown` if the callee never resolved |
| `IndexExpr` | the array's element type, or the pointer's pointee type |
| `MemberExpr` | the field's declared type — see below |
| `SizeofExpr` | always `int` (see `docs/known-limitations.md` — real C says `size_t`, which this subset has no type for) |

### `MemberExpr` (S4.2, the swapped-operator messages)

The type checker (`typecheck.py`) is strict about the operator:

1. Resolve `.obj`'s type.
2. `.` used where the object is actually a pointer: **error**, `"member
   access on pointer; did you mean '->'?"`.
3. `->` used where the object is not a pointer: **error**, `"arrow on
   non-pointer; did you mean '.'?"`.
4. Otherwise, deref one pointer level for `->`, then look the field up. An
   unknown field name: **error**, naming the struct:
   `"struct 'Point' has no field 'z'"`.

All three are code `S011` — one diagnostic *class* ("bad member access"),
three distinct messages for the three distinct mistakes.

Completion and hover (`languages/c/queries.py`) deliberately do **not**
reuse this strictness: their base-expression resolver derefs a pointer
regardless of which operator was typed, so `p.` still offers useful field
completions even mid-typing, before the user has necessarily typed the
"correct" operator. Being helpful during editing and being correct during
type checking are different jobs.

### Function calls (S4.4)

Arity is checked **first**. A wrong argument count is reported once
(`S005`, `"expected N argument(s), got M"`) and per-argument type checking
is skipped entirely for that call — checking argument types against a
parameter list that's already known to be the wrong length would just be
noise on top of the one real problem. Only once the arity matches does each
argument go through `is_assignable` against its parameter's type (`S003`
for a mismatch, or a narrowing warning). Calling a name that resolved to
something other than a function is its own error (`S012`,
`"'g' is not a function"`); calling a name that never resolved at all is
just an undefined-symbol error from name resolution — the call itself
types as `unknown` and is not reported a second time.

## `UnknownType` and no-cascade (D17, S9.2)

This is the single mechanism behind "one undefined symbol used five times
produces one diagnostic," and it is worth stating precisely because it is
the answer to *every* no-cascade question at the defense:

> Any operation with an `unknown` operand yields `unknown` and emits **no**
> diagnostic of its own. Every `ErrorExpr` (a parser recovery placeholder)
> types as `unknown`. Every identifier that name resolution could not
> resolve types as `unknown`.

So the *first* time a name fails to resolve, name resolution reports it
once and the identifier types as `unknown`. Every later use of that same
broken subtree — as a binary operand, a call argument, an assignment
target, a `return` value — inherits `unknown` and every check downstream
(`is_assignable`, `usual_arithmetic_conversion`, arity checking) is defined
to treat `unknown` as compatible with anything, so none of them add a
second, third, fourth diagnostic about the same root cause. The
alternative — every pass independently deciding whether to suppress a
report for a name it already knows is broken — would mean N passes each
needing their own suppression bookkeeping. One absorbing value, checked in
one place per operation, does the same job for free.

## S4.8: dynamically typed languages — N/A

The course document's S4.8 asks for flow-sensitive type inference for
dynamically typed target languages (Python, JavaScript). C is statically
typed (every declaration states its type; D1), so there is no inference to
perform here — every `Type` in this project comes from a declaration
(`resolve_type_spec`) or is computed structurally from already-typed
subexpressions. This is recorded as N/A rather than silently skipped; see
`docs/known-limitations.md`.

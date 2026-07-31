---
name: type-system
description: The semantic Type hierarchy, C conversion rules, and expression type checking for c-lens Phase 2 — Type vs TypeSpec, the rank table, assignability, and UnknownType error suppression. Use whenever touching core/types.py, languages/c/typecheck.py, or any Expr.type_annotation work.
---

# Type system

Requirements: S4.1–S4.8. Decisions: D15–D18.

## Type is not TypeSpec

`TypeSpec` (Phase 1) is **syntax**: what was written, including `const`, storage
class, and pointer stars. `Type` (Phase 2) is **semantics**: what the checker
reasons about. Phase 1's `TypeSpec` docstring already says this — it was designed
for it.

`resolve_type_spec(spec, scope) -> Type` bridges them. It resolves `struct Point`
against the scope to a `StructType` pointing at the real declaration, and wraps
`pointer_depth` levels of `PointerType`.

## The variants

```python
PrimitiveType(name)          # "void" | "char" | "int" | "float" | "double"
PointerType(pointee)
ArrayType(element, size)     # size: int | None
StructType(name, decl)       # decl links to the StructDecl for field lookup
FunctionType(params, ret)    # params: tuple[Type, ...]
UnknownType()                # the error-suppression device
```

All frozen, structurally compared. Give each a readable `__str__` — `"int"`,
`"char*"`, `"int[10]"`, `"struct Point"`, `"(int) -> int"`. That string is exactly
what hover and completion `detail` display, so it is user-facing, not debug output.

## UnknownType absorbs everything

This is the whole no-cascade mechanism (S9.2, D17):

- Any operation with an `unknown` operand yields `unknown` and emits **no**
  diagnostic.
- `is_assignable(unknown, T)` and `is_assignable(T, unknown)` are both ok.
- Every `ErrorExpr` types as `unknown`.
- Every unresolved identifier types as `unknown`.

Result: one undefined symbol produces one message, not a flood. Test that
explicitly — a file using an undefined name five times must produce exactly one
diagnostic.

## Conversion rank (D18)

```
char = 0  <  int = 1  <  float = 2  <  double = 3
```

- **Binary numeric operands** promote to the higher rank. `int + double` → `double`
  (S4.3).
- **Assignment to a lower rank** is a **warning**: "conversion from double to int
  may lose precision". This is what `int x = 3.14;` requires — warning, not error.
- **Pointer and integer mixed** in assignment is an **error**: `char *s = 42;`.
- **`void` in an operand position** is an error.
- Pointer arithmetic: `ptr + int` → same pointer type; `ptr - ptr` → `int`.
- Comparison operators always yield `int` (C has no bool in this subset).
- Logical `&&` `||` `!` yield `int` and accept any scalar.

Return an `AssignResult` (ok / narrowing / incompatible) from `is_assignable`
rather than a bool, so callers do not each re-derive the severity.

## Per-node rules

| Node | Type |
|---|---|
| `IntLiteral` | `int` |
| `FloatLiteral` | `double` |
| `StringLiteral` | `char*` |
| `CharLiteral` | `char` |
| `Identifier` | the symbol's type, or `unknown` if unresolved |
| `BinaryExpr` | per operator; comparisons and logicals yield `int` |
| `UnaryExpr` | `&x` → `PointerType(T)`; `*p` → pointee, error if not a pointer; `-x !x ~x` → numeric rules; `++`/`--` → operand type |
| `AssignExpr` | the **target's** type; checks assignability |
| `TernaryExpr` | conversion of the two branch types; mismatch is an error |
| `CallExpr` | the function's return type, or `unknown` |
| `IndexExpr` | element type; error if the base is neither array nor pointer |
| `MemberExpr` | the field's type; see below |
| `SizeofExpr` | `int` (C says `size_t`; this subset has none — document it) |

## MemberExpr rules

- `.` on a `StructType` → look the field up in that struct's field list.
- `->` on a `PointerType(StructType)` → same, through one level.
- `.` used on a pointer → error: "member access on pointer; did you mean `->`?"
- `->` used on a non-pointer → error: "arrow on non-pointer; did you mean `.`?"
- Unknown field name → error naming the struct.

Those two swapped-operator messages cost nothing and read very well in a demo.

## Function calls

Check **arity first**, then per-argument assignability. If arity is wrong, report
once and do not also report argument mismatches — that is cascading.

Calling something that is not a function is its own error. Calling an undefined
name is an undefined-symbol error from resolution, and the call types as `unknown`.

Prototype and definition must agree; a mismatch is an error at the definition site,
pointing back at the prototype's location.

## The four golden examples (S4.7)

```c
int x = 3.14;                  /* WARNING: narrowing */
char *s = 42;                  /* ERROR: int to char* */
int y = factorial("hello");    /* ERROR: argument type mismatch */
void foo() { return 5; }       /* ERROR: void function returns a value */
```

One test file, asserting exact severities. Get these right before anything else in
Stage 4 — they are the course document's own worked examples and are the most
likely thing to be tried by hand at the defense.

## Definition of done

- [ ] Every `Expr` node in every valid fixture has a non-`None` `type_annotation`
- [ ] Every conversion pair in the rank table tested
- [ ] `unknown` absorption tested in both directions
- [ ] Both swapped-member-operator messages tested
- [ ] The four golden examples pass with exact severities
- [ ] No-cascade test passes
- [ ] `__str__` tested for every variant, including nested (`char**`, `(int) -> int`)

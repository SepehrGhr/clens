---
name: name-resolution
description: Two-pass name resolution for c-lens Phase 2 — declaration scan then resolution, shadowing warnings, duplicate declarations, prototype-vs-definition, and reference recording. Use whenever touching languages/c/resolver.py or debugging an undefined-symbol or shadowing diagnostic.
---

# Name resolution

Requirements: S2.1–S2.3, S3.1–S3.3.

## Why two passes (S2.3)

C allows calling a function declared later in the file, and mutual recursion. A
single pass reports false "undefined symbol" errors. The course document names C
prototypes as the motivating case.

**Pass 1 — declaration scan.** Walk `Program.declarations` only. Enter every
`FuncDecl` (prototype or definition), `StructDecl`, and top-level `VarDecl` into the
global scope. Do not descend into bodies.

**Pass 2 — resolution.** Walk everything, building scopes and resolving each name
against the now-complete chain.

Locals are still strictly declare-before-use — that is C. Only the global scope gets
the forward-reference treatment. Test both: a forward function call resolves; a
forward local reference does not.

## Resolution algorithm (S3.1)

1. Innermost scope first.
2. Walk outward to global.
3. (Class scope and superclass chain — N/A for C. One line in the docs.)
4. Not found → **error**, "undefined symbol 'x'", one per unique name per scope.
5. Found in an outer scope while an inner declaration shadows it → **warning**.

## Shadowing (S3.2)

Fires when a declaration in an inner scope has the same name as one visible from an
enclosing scope. It is a **warning**, on the *inner declaration*, and the message
should name both locations: "declaration of 'x' shadows an outer declaration at
3:9".

Do not fire it for:
- A parameter shadowing a global — arguably correct, but noisy; the course document
  does not require it. Pick one behaviour and document it.
- A struct field with the same name as a variable. Different namespace entirely.

## Duplicate declaration (row 8)

Same name declared twice in the **same** scope. Report at the second declaration,
naming the first's location. Remember `int a = 1, a = 2;` is two sibling `VarDecl`
nodes in one scope — it must fire.

**Prototype then definition is not a duplicate.** Same name, same signature →
merge into one symbol, keeping the prototype's `definition_loc` and adding the
definition. Same name, *different* signature → error at the definition, pointing at
the prototype.

## Reference recording (S3.3)

Every resolved use appends a `Reference` and updates flags:

| Context | Records |
|---|---|
| `Identifier` in an r-value position | read; sets `is_used` |
| `AssignExpr.target` being a plain `Identifier` | write; sets `is_initialized` |
| `x += 1` | read **and** write |
| `&x` | write (conservatively — the address escapes) |
| `CallExpr.callee` | read on the function symbol |
| `VarDecl` with an `init` | write; sets `is_initialized` |
| Struct tag in a `TypeSpec` | read on the type symbol |

Use `CallExpr.callee_span` and `MemberExpr.member_span` (added in Stage 0) for
reference spans — do not compute them from the parent span.

## Error-recovery regions

The AST can contain `ErrorExpr` / `ErrorStmt` anywhere. **Skip them silently.** Do
not resolve inside them, do not report anything about them — the parser already
reported the syntax error. Re-reporting is cascading.

## Definition of done

- [ ] Forward function call resolves; forward local reference errors
- [ ] Mutual recursion resolves
- [ ] Shadowing warning at three nesting depths, naming both locations
- [ ] Duplicate declaration fires in the same scope, not in an inner one
- [ ] `int a = 1, a = 2;` fires
- [ ] Prototype + matching definition does not fire; mismatched signature does
- [ ] Every reference kind above recorded, with a test each
- [ ] A file full of `ErrorStmt` regions resolves without a crash or extra diagnostics

# Semantic Analysis

## Why this phase has to exist

The course document frames a language's specification as an attribute
grammar: a context-free grammar (`docs/grammar.ebnf`) plus attributes and
semantic rules layered on top of it. The CFG alone can decide whether
`n * factorial(n - 1)` is *syntactically* a valid expression. It cannot
decide any of the following, because each one is a **context-sensitive**
property — its answer depends on something declared somewhere else in the
program, not on the local shape of the parse tree:

- Is `n` even declared here? (depends on every enclosing scope)
- Is `n` declared *twice* in the same scope? (depends on every other
  declaration in that scope)
- Does `factorial(n - 1)`'s argument type match the declared parameter type?
  (depends on `factorial`'s signature, declared elsewhere)
- Does the `return` statement's value match the enclosing function's
  declared return type? (depends on the function header, which may be many
  lines above)

None of these can be expressed as a production `A -> α` in a CFG, because a
CFG production has no notion of "the same name declared elsewhere" or "the
type computed for a different subtree." They are exactly the *inherited*
and *synthesized* attributes the course document's attribute-grammar
framing is pointing at: a name's binding is inherited from the enclosing
scope; an expression's type is synthesized from its subexpressions' types
and then checked against an inherited expectation (a parameter type, a
return type, an assignment target's type). `languages/c/resolver.py` and
`languages/c/typecheck.py` are literally an evaluator for those attribute
rules, run as two more passes after the CFG's own pass (parsing) has
already built the tree.

## The scope model

Five constructs open a scope (`core/scopes.py::ScopeKind`):

| Construct | `ScopeKind` | Holds |
|---|---|---|
| The whole file | `GLOBAL` | Every top-level function, struct, and global variable |
| A function *with a body* | `FUNCTION` | Its parameters |
| Any `{ ... }` block | `BLOCK` | Locals declared directly in it |
| A `for` loop | `FOR_INIT` | The names declared in its `init` clause |
| A `struct` declaration | `STRUCT` | Its fields |

A function's parameter scope and its body's block scope are **two separate
scopes**, not one — `int f(int x) { int x; }` is legal in this subset's
model (the inner `x` shadows the parameter, it does not collide with it),
which matches real C block scoping and is exactly what makes the
`shadowing.c` fixture's "a local shadows the parameter" case fire as a
*warning*, not row 8's duplicate-declaration *error*.

### Struct scopes are off the lexical chain

Every other scope kind is reachable by walking `.parent` outward from
wherever the cursor or reference sits — that walk is `Scope.lookup()`. A
`STRUCT` scope is deliberately excluded from it: `Scope.lookup()` never
escalates past a struct scope to its parent, and no executable scope
(`FUNCTION`/`BLOCK`/`FOR_INIT`) is ever parented under one. This mirrors C
itself — `struct Point { int x; };` does not put `x` in scope as a bare
name anywhere; `x` is only reachable through `p.x` or `p->x`, i.e. through
*member access*, which is a completely different resolution path
(`languages/c/queries.py`'s member-completion/hover code walks the token
stream back to the base expression and looks the field up directly in the
struct's own scope — it never goes through `Scope.lookup()` at all). A
struct scope still gets a `.parent` pointer, purely so `clens symbols` can
render it in the right place in the tree; that pointer is never consulted
by name resolution.

## Why two passes (S2.3)

C allows a function to be called before its declaration appears, as long as
a prototype (or the definition itself) exists somewhere in the file, and it
allows mutual recursion between two functions that each call the other:

```c
int later(int n);              /* prototype: 'later' now exists */

int earlier(int n) {
    return later(n);            /* forward call, resolves via the prototype */
}

int later(int n) {
    if (n <= 0) return 0;
    return earlier(n - 1);      /* backward call to an already-resolved name */
}
```

A single top-to-bottom pass would report `later` as undefined inside
`earlier` (it has not been seen yet, in a naive left-to-right walk) — a
false positive on completely legal C. Two passes fix this:

1. **Pass 1 — declaration scan** (`resolver.py::scan_declarations`, `_Pass1`).
   Walks `Program.declarations` **only** — every top-level `FuncDecl`
   (prototype or definition), `StructDecl`, and `VarDecl` goes into the
   global scope. Function bodies are not looked at yet.
2. **Pass 2 — resolution** (`resolver.py::resolve`, `_Pass2`). Walks every
   function body (and every global initializer) against the now-complete
   global scope, building the rest of the scope tree (function, block,
   for-init) as it goes and resolving every reference.

By the time Pass 2 looks inside `earlier`'s body, Pass 1 has already put
`later` into the global scope — regardless of which function's *text*
comes first. Locals do **not** get this treatment: they are still strictly
declare-before-use, because Pass 2 only ever creates a local's `Symbol`
at the point in the walk where its declaration statement is reached, and a
read earlier in the same block simply will not find it in scope yet (which
is also what row 12's crude use-before-initialization check leans on — see
`docs/known-limitations.md`).

## Symbol table structure (S1.1)

`core/symbols.py::Symbol` has all nine required fields:

| Field | Type | What it's for |
|---|---|---|
| `name` | `str` | The identifier text |
| `kind` | `SymbolKind` | `VARIABLE` / `FUNCTION` / `PARAMETER` / `TYPE` / `FIELD` — the five of the course document's seven kinds this subset has classes for (no `class`/`method`) |
| `type` | `Type` | The declared or resolved semantic type — see `docs/type-system.md` |
| `scope` | `Scope` | Back-reference to the scope this symbol lives in |
| `definition_loc` | `Span` | Where it was declared (the name token's span) |
| `references` | `list[Reference]` | Every use, in source order, each carrying its own span and whether it's a read, a write, or both |
| `signature` | `FunctionType \| None` | Set for `FUNCTION`-kind symbols; `None` otherwise |
| `is_initialized` | `bool` | Whether any write reference has been recorded |
| `is_used` | `bool` | Whether any read reference has been recorded |

`references` and `is_used` are the two fields the course document calls out
as easy to skip. They are populated *as* Pass 2 resolves each use, not in a
later sweep — this is what row 12 (use-before-initialization) and row 13
(unused variable) read directly, and it's also the data Phase 3's
find-all-references, go-to-definition, and safe rename are built on
(`project/04-future-phases.md`), so getting it right now is not optional
scaffolding.

`Reference.is_read` and `.is_write` are independent flags, not an enum,
because `x += 1` is both at once. The table below is S3.3's reference-kind
list exactly as implemented:

| Context | Records |
|---|---|
| `Identifier` in a normal (r-value) position | read |
| `AssignExpr.target`, plain `=` | write only |
| `AssignExpr.target`, compound (`+=` etc.) | read **and** write |
| `x++` / `x--` | read **and** write |
| `&x` | write (conservative — the address escapes) |
| `CallExpr.callee` | read, on the function's own symbol |
| `VarDecl` with an initializer | write, on the declared symbol itself |
| A struct tag in a `TypeSpec` (`struct Point p;`) | read, on the type symbol |

## Duplicate declaration vs. shadowing

These are two different diagnostics (rows 8 and 11) with one dividing line:
**same scope is a duplicate (error); an enclosing scope is shadowing
(warning).**

- **Duplicate** (`Scope.declare()` returns the colliding symbol instead of
  `None`): `int a = 1, a = 2;` is two sibling `VarDecl` nodes from one
  declaration statement, in the same scope — it fires. A prototype
  followed by a matching-signature definition does **not** fire; they
  merge into one symbol, keeping the prototype's `definition_loc`. A
  mismatched signature between them *does* fire, at the definition,
  naming the prototype's location. Two full bodies for the same function
  name fire regardless of whether their signatures match — you cannot
  define a function twice.
- **Shadowing** (checked once, at declaration time, against
  `scope.parent.lookup()`): an inner declaration with the same name as one
  visible from an enclosing scope. Fired for a block-local shadowing a
  parameter, or a nested block shadowing an outer local — **not** fired
  for a parameter shadowing a global (an explicit, documented exclusion;
  see `shadowing.c`'s own comment) and not fired for a struct field with
  the same name as a variable, since fields are never in the lexical chain
  at all.

## Worked example: `factorial.c`'s scope chain

```c
int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}
```

`clens symbols tests/fixtures/valid/factorial.c` (this is the tool's real
output, not a hand-drawn approximation):

```
GLOBAL
  factorial: function (int) -> int
  FUNCTION
    n: parameter int
    BLOCK
```

Three scopes, nested left-to-right as drawn: `GLOBAL` is `factorial`'s
declaring scope (Pass 1); `FUNCTION` is opened for the parameter list and
holds `n`; `BLOCK` is `factorial`'s body — empty in this rendering because
it declares no locals of its own (`if`'s `then_branch` here is a bare
`return`, not a `{ ... }` block, so it opens no scope of its own). Resolving
the recursive call `factorial(n - 1)` walks outward from `BLOCK` to
`FUNCTION` to `GLOBAL`, finds `factorial` in `GLOBAL` (declared by Pass 1
before Pass 2 ever looked at the body), and records a read reference on it
— the same mechanism that makes the mutually-recursive `earlier`/`later`
example above resolve regardless of order.

---
name: symbol-table
description: Symbol and Scope data structures for c-lens Phase 2 — the nine required entry fields, the scope tree, offset-based cursor queries, and the SemanticModel that survives analysis. Use whenever touching core/symbols.py, core/scopes.py, or anything that looks up a name or a cursor position.
---

# Symbol table and scopes

Requirements: S1.1–S1.4. Decisions: D19, D20.

## Symbol — all nine fields

The course document specifies nine fields exactly. Missing one is a visible rubric
gap:

```python
@dataclass(slots=True)
class Symbol:
    name: str
    kind: SymbolKind              # VARIABLE FUNCTION PARAMETER TYPE FIELD
    type: Type
    scope: "Scope"                # enclosing scope, back-reference
    definition_loc: Span          # declaration site
    references: list[Reference]   # every usage location
    signature: FunctionType | None = None
    is_initialized: bool = False
    is_used: bool = False
```

`references` and `is_used` are the two that get skipped. Phase 3's
find-all-references, go-to-definition, and safe rename are all built on
`references` — a bug here fails three features at once. Populate it as you resolve,
not in a later sweep.

`Reference` records the span **and** whether the use is a read, a write, or both
(`x += 1` is both). Phase 3 liveness needs the distinction; recording it now is free.

## Scope

```python
@dataclass(slots=True)
class Scope:
    kind: ScopeKind               # GLOBAL FUNCTION BLOCK STRUCT FOR_INIT
    parent: "Scope | None"
    children: list["Scope"]
    symbols: dict[str, Symbol]    # insertion-ordered
    span: Span                    # the source range this scope covers
    owner: Node | None = None     # the FuncDecl / Block / StructDecl it belongs to
```

- `declare(symbol)` → returns the existing symbol on collision so the caller can
  report a duplicate-declaration error with **both** locations.
- `lookup_local(name)` → this scope only.
- `lookup(name)` → walks outward to global.
- `lookup_with_scope(name)` → returns `(symbol, scope)`, needed to decide whether a
  hit is shadowing something.

**Struct scopes are not in the lexical chain.** A struct's fields are reachable only
through member access, never by bare name. Parent them for tree display, but never
let `lookup()` walk into or out of them.

## Scope creation points in C

| Construct | Scope |
|---|---|
| The file | `GLOBAL` |
| `FuncDecl` with a body | `FUNCTION` — holds the parameters |
| `Block` | `BLOCK` |
| `ForStmt` | `FOR_INIT` — holds init declarations, wraps the body |
| `StructDecl` | `STRUCT` — fields only, off the lexical chain |

⚠️ `ForStmt.init` can be a `list[VarDecl]`: `for (int i = 0, j = 9; ...)` declares
two names. Handle the list case — see `project/07-phase1-interfaces.md`.

⚠️ The function scope and its body `Block` are two scopes. That means a parameter
shadowed by a top-level local in the body correctly produces a shadowing warning.

## Offset queries (D20)

Every scope records the span it covers, so:

```python
def scope_at(model, offset) -> Scope     # innermost scope whose span contains offset
def symbols_visible_at(model, offset) -> list[Symbol]
```

Descend the tree picking the innermost containing child. O(depth), no AST walk, and
it still works on a file that failed to parse cleanly.

Test the boundaries explicitly: the first character of a scope, the last character,
and one past the end. Off-by-one here silently breaks completion.

## SemanticModel (D19)

```python
@dataclass(slots=True)
class SemanticModel:
    program: ast.Program          # now annotated with types
    global_scope: Scope
    all_scopes: list[Scope]
    symbols_by_name: dict[str, list[Symbol]]
    source: SourceFile
```

Returned by `analyze()`, never discarded. Completion, hover, and every Phase 3
feature read this object. It is the deliverable, not a byproduct.

## Definition of done

- [ ] All nine S1.1 fields present and populated
- [ ] `references` correct, with read/write distinction
- [ ] Scope tree shape tested for nesting, function-vs-body, for-init, struct
- [ ] Struct scopes excluded from lexical lookup, with a test
- [ ] `scope_at` boundary tests at first char, last char, one past the end
- [ ] `SemanticModel` returned and queryable after analysis
- [ ] `clens symbols` renders the tree readably and as JSON

---
name: completion-engine
description: The auto-completion and hover engine for c-lens Phase 2 — the course document calls completion the central deliverable. Covers cursor context detection, symbol querying, prefix-then-fuzzy ranking, and doc-comment hover. Use whenever touching core/queries.py or languages/c/completion.py.
---

# Completion and hover

Requirements: S5.1–S5.6, S7. Decisions: D21, D23, D24.

The course document calls the completion engine **"the central deliverable of
Phase 2."** Budget accordingly.

## One query layer (D23)

`core/queries.py` holds pure functions over a `SemanticModel`:

```python
def completions_at(model, offset) -> list[CompletionItem]
def hover_at(model, offset) -> HoverInfo | None
def symbols_of(model) -> list[Symbol]
def diagnostics_of(model) -> list[Diagnostic]
```

The CLI, the web server, and any future LSP server are **thin adapters** over these.
No feature logic lives in an adapter. This is what makes the LSP bonus cheap later.

Take an **offset**, not line/column, at this layer — adapters convert via
`SourceFile`. One conversion point, one place for off-by-one bugs to live.

## Context detection (S5.2)

Look at the last significant token at or before the cursor:

| Preceding | Context |
|---|---|
| `.` or `->` | `MEMBER` — complete fields of the left-hand expression's type |
| `::` | N/A for C. Document it; costs one line |
| Statement start, or after an operator or `(` `,` `;` `{` | `GENERAL` — everything visible |
| Inside a call's argument list | `ARGUMENT` — general, but re-ranked by the expected parameter type |
| Inside a comment or a string literal | **no completions** — return empty |

That last row matters and is easy to forget. Completions popping up inside a string
looks broken in the demo.

A partially typed prefix (`fac|`) means the cursor sits inside or just after an
`IDENT`; take that lexeme as the filter prefix, and take the context from the token
*before* it.

## Member completion (S5.6)

1. Find the `MemberExpr` containing the cursor, or the expression immediately left
   of the `.` / `->` if the parse is incomplete.
2. Read its `type_annotation`. Deref one level for `->`.
3. If it is a `StructType`, list the fields from the linked `StructDecl`.
4. Fields become items: `label` = name, `kind` = Field, `detail` = the field's type
   string.

Golden case from the document — `p.` on a `struct Point { int x; int y; }` offers
exactly `x : int` and `y : int`.

⚠️ The document's fixture uses `struct Point p = {1, 2};`, an initializer list,
which is **out of our subset**. Use `struct Point p;` in the fixture and note the
deviation in `docs/known-limitations.md`. Do not widen the subset for this.

**Incomplete parses are the normal case here.** `p.` with nothing after it is a
syntax error — the user is mid-typing. Do not rely on a clean AST: fall back to the
token stream, walk left from the `.` to find the base expression's tokens, and
resolve that. Make this a test; it is the single most common real-world path
through this code.

## Ranking (D24)

Score, lowest sorts first:

1. Exact prefix match, case-sensitive
2. Prefix match, case-insensitive
3. Subsequence fuzzy match (`fct` matches `factorial`)
4. No match → excluded entirely

Tie-breaks: **scope distance** (a local beats a global — this is what real IDEs do
and it demos well), then alphabetically.

Use any standard fzf-style subsequence scorer, ~40 lines. Do not invent one.

## CompletionItem (S5.5)

```python
@dataclass(slots=True, frozen=True)
class CompletionItem:
    label: str          # "factorial"
    kind: str           # "function" | "variable" | "parameter" | "field" | "type" | "keyword"
    detail: str         # "(int) -> int"   <- Type.__str__ from the type system
    sort_order: float
```

Include C keywords in `GENERAL` context, ranked below real symbols. Cheap, and its
absence is noticeable.

## Hover (S7)

Listed under Phase 3 in the course document, but it is the same query. Build it here.

Returns: the symbol's full type signature, its enclosing scope description
("function `factorial`", "global scope"), and its attached doc comment.

**Doc comments** are why Phase 1 retained comment tokens (R1.8). Attach the nearest
preceding comment token to a declaration when only whitespace separates them. Handle
both `/* */` and `//`, and a run of consecutive `//` lines as one block. Strip the
comment markers and leading `*` decoration before displaying.

## Definition of done

- [ ] All four contexts detected, plus the comment/string suppression case
- [ ] Member completion works on a **complete** parse and on `p.` mid-typing
- [ ] The S5.6 golden case returns exactly `x` and `y` with `int` details
- [ ] Argument-list completion re-ranks by the expected parameter type
- [ ] Ranking: exact prefix beats case-insensitive beats fuzzy; local beats global
- [ ] Keywords appear in general context, ranked below symbols
- [ ] Hover returns signature, scope, and doc comment for each symbol kind
- [ ] `completions_at` takes an offset and is pure over `SemanticModel`

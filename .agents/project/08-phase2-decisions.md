# Phase 2 Decisions (D15 – D24)

Continues `02-decisions.md`. Settled — do not revisit without asking the user.

---

**D15 — Semantic `Type` is a separate hierarchy from syntactic `TypeSpec`.**
`TypeSpec` is what was written in source. `Type` is what the checker reasons about.
The Phase 1 code already anticipated this in `TypeSpec`'s docstring. A
`resolve_type_spec(spec, scope) -> Type` function bridges them. Rejected: annotating
with `TypeSpec` directly — it cannot express "unknown", cannot canonicalise
`struct Point` to its declaration, and cannot represent a function type.

**D16 — `Type` variants: `PrimitiveType`, `PointerType`, `ArrayType`, `StructType`,
`FunctionType`, `UnknownType`.** Frozen dataclasses, structurally compared.
`UnknownType` is the error-suppression device (see D17). `void` is a
`PrimitiveType`, not a separate variant.

**D17 — `UnknownType` is compatible with everything, in both directions.**
Any operation involving `unknown` yields `unknown` and emits no diagnostic. This is
the mechanism for S9.2 (no cascading errors): one root cause, one message. Every
`ErrorExpr` types as `unknown`, and every unresolved name types as `unknown`.

**D18 — Numeric conversions use a rank table.**
`char(0) < int(1) < float(2) < double(3)`. Binary numeric operands promote to the
higher rank. Assignment to a lower rank is a **warning** ("loses precision"), which
is what the course document's `int x = 3.14;` example requires. Pointer/int mixing
is an **error**. `void` in an operand position is an error.

**D19 — The scope tree is the returned artifact.**
`analyze()` returns a `SemanticModel` holding the global scope, the scope tree, a
flat symbol index, and the AST (now annotated). Nothing is discarded. Completion,
hover, and all of Phase 3 read this object.

**D20 — Scopes are found by offset range, not by re-walking the AST.**
Each `Scope` records the span it covers. `scope_at(offset)` descends the tree
choosing the innermost scope whose span contains the offset. O(depth), no AST
traversal, and it works on a partially broken file.

**D21 — Completion is answered from a fresh analysis of the buffer, not an
incremental update.** Files are small and this is a course project; correctness
beats latency. Incremental re-parsing is a listed *bonus* and stays out of scope
unless everything else is done.

**D22 — The interactive interface is a Web UI, not an LSP server.**
Rationale: it screenshots well for the README, needs no editor setup for the
graders, reuses the existing theme and HTML rendering, and — decisively — the
course document lists Web UI as one of the three acceptable Phase 3 interfaces
(§6.6), so this is Phase 3 work pulled forward rather than extra work.

Constraints that keep it cheap:
- **stdlib `http.server` only.** The zero-runtime-dependency claim survives.
- **Vanilla JS, no build step, no framework, no CDN.**
- **Side-by-side panes** — a plain `<textarea>` editor beside a rendered pane. Do
  **not** attempt a contenteditable overlay with highlighting behind the caret;
  that trick is where web editors get expensive, and it buys nothing here.

An LSP server remains a later bonus. Diagnostics are already LSP-shaped (D11) and
the query layer in D23 is designed to be LSP-compatible, so it stays cheap.

**D23 — One query layer serves CLI, web, and any future LSP.**
`core/queries.py` exposes pure functions over a `SemanticModel`:
`completions_at(model, offset)`, `hover_at(model, offset)`,
`symbols_of(model)`, `diagnostics_of(model)`. The CLI, the web server, and a future
LSP server are all thin adapters over these. No feature logic lives in an adapter.

**D24 — Completion ranking: exact prefix, then case-insensitive prefix, then
subsequence fuzzy, then everything else; ties broken by scope distance then
alphabetically.** Scope distance means a local beats a global with the same name
quality, which is what a real IDE does. `sortOrder` is a float; lower sorts first.

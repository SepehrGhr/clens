# Future Phases — Why Certain Hooks Exist

**Do not implement anything in this file.** It exists so you understand why some
Phase 1 structures look over-engineered, and so you don't optimize them away.

If a Phase 1 change would break something listed here, don't make it.

---

## Phase 2 will need (semantic analysis, intellisense)

| Phase 2 need | Phase 1 obligation |
|---|---|
| Symbol table entries with a `references` list | Token/AST spans must be exact and stable — three Phase 3 features depend on this list being right |
| Type annotation on every expression | `type_annotation: Type \| None = None` field on expression nodes (R4.3) |
| Scope tree queried by cursor position | AST nodes need **end** offsets, not just start, so "which node contains this cursor" is answerable |
| Diagnostics with a `length` to underline the span | Diagnostics are LSP-shaped with full start/end ranges from day one (D11) |
| Member-access completion `p.` → fields | `struct` and `.`/`->` must be **in** the Phase 1 subset. They are. Do not drop them |
| Two-pass resolution for forward references | Parser must produce a complete top-level declaration list even when a function body fails to parse |
| Unified lexer + parser + semantic diagnostics | One `Diagnostic` type, one collector, from Phase 1 |

## Phase 3 will need (CFG, call graph, navigation, refactoring)

| Phase 3 need | Phase 1 obligation |
|---|---|
| CFG built from statement structure | Statement nodes must be distinct types with their sub-statements as named fields, not flattened lists |
| Hover showing doc comments | **Comment tokens must be retained with positions** (R1.8). This is the single hook most likely to be "cleaned up" by mistake |
| Go-to-definition / find-all-references | Exact identifier spans |
| Safe rename, scope-aware | Rename operates on symbol identity, which requires stable node identity. Do not rebuild AST nodes during traversal |
| Unified diff output for rename | Byte-faithful source reconstruction — already required by R5.3 |
| Dead code detection | Nothing in Phase 1 |
| Generic data-flow solver | Nothing in Phase 1, but `NodeVisitor` will be reused |

## Multi-language bonus (very end, Java)

The only Phase 1 obligation is D12: `core/` never imports from `languages/`.
Concretely, a new language should require adding one directory containing keyword
set, token rules, grammar, AST-construction, and later type rules — and changing
nothing in `core/`.

Do **not** build a plugin registry, an abstract base class hierarchy, or a
configuration format for this now. One language, clean boundary, done. Premature
abstraction here costs more than it saves.

## What NOT to build in Phase 1

Explicitly out, even if it seems easy:
- Symbol table, scope resolution, name binding
- Any type checking or inference
- Completion, hover, signature help
- CFG, call graph, data-flow, dead code
- Rename, go-to-definition, find-references
- LSP server
- The Java language module

If a task seems to require one of these to proceed, you have misread the task. Ask.

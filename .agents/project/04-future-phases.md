# Future Phases — Phase 3 Hooks

**Do not implement anything in this file.** It exists so you understand why some
Phase 2 structures look over-built, and so you do not optimize them away.

Phase 2's own needs are no longer listed here — they are live requirements now, in
`06-phase2-requirements.md`.

---

## Phase 3 will need (CFG, call graph, navigation, refactoring)

| Phase 3 need | Phase 2 obligation |
|---|---|
| CFG built from statement structure | Statement nodes keep sub-statements as named fields. Already true; do not flatten |
| Definite-assignment analysis | `Reference` records read vs write. Record it now — Phase 3 cannot recover the distinction |
| Live-variable analysis | Same. Also why `is_used` must be accurate, not approximate |
| Call graph | `CallExpr.callee_span` plus the resolved function `Symbol`. Store the resolution result on the symbol's `references`, not just as a local variable during checking |
| Go-to-definition | `Symbol.definition_loc`, exact |
| Find-all-references | `Symbol.references`, complete. Three features fail together if this is wrong |
| Safe rename, scope-aware | Symbol identity anchored to node identity. Do not rebuild AST nodes during any pass — annotate in place |
| Rename conflict and shadow checks | The scope tree surviving analysis (D19), and `lookup_with_scope` |
| Hover with doc comments | Built in Phase 2 (S7). Phase 3 claims it |
| Dead function detection | The call graph, built on resolved call references |
| LSP server (optional bonus) | `core/queries.py` staying adapter-free (D23), and LSP-shaped diagnostics (D11) |
| The required Phase 3 interface | The web UI (D22) already satisfies §6.6. Phase 3 extends it rather than starting one |

## Multi-language bonus (Java, at the very end)

Unchanged: `core/` never imports from `languages/`. Phase 2 splits the same way —
generic machinery (`Type` bases, `Scope`, `Symbol`, queries) in `core/`, C-specific
rules (conversion table, C scope kinds, C completion contexts) in `languages/c/`.

Do **not** build a plugin registry or an abstract language interface now. One
language, clean boundary.

## What NOT to build in Phase 2

Explicitly out, even if it seems easy while you are in the neighbourhood:

- Control flow graphs, basic blocks
- Call graphs
- Data-flow analysis of any kind, including proper definite-assignment and liveness
- Dead code detection
- Go-to-definition, find-all-references
- Rename refactoring
- An LSP server
- The Java language module
- Incremental re-parsing (a listed bonus; D21 defers it)

Hover (S7) is the one deliberate exception: it is a Phase 3 item built in Phase 2
because it is the same query as completion `detail`.

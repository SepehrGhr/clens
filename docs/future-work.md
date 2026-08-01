# Future work

Items deliberately scoped out of this project, each with what it is, why
it was deferred, a rough effort estimate, and where it plugs into the
existing architecture. This is scoping, not apology: every item below has
a concrete entry point because the layering (`core/` never imports
`languages/`; `languages/c/queries.py` is adapter-free; the CLI and web UI
are both thin shells over the same functions) was built to make adding
each of these a bounded, local change rather than a rewrite. Delivered
bonus items are documented separately in `docs/bonus/`.

## Dominator and post-dominator trees

Node `d` dominates node `n` iff every path from `ENTRY` to `n` in the CFG
passes through `d`. The course document names the Lengauer-Tarjan
algorithm; at the function sizes this project's CFGs reach, the naive
iterative dataflow formulation (initialize `dom(n) = all nodes`, then
iterate `dom(n) = {n} ∪ ⋂ dom(p) for p in preds(n)` to a fixed point) is
~20 lines and gives identical results, so Lengauer-Tarjan's added
complexity buys nothing here. Post-dominators are the same algorithm run
on the CFG with edges reversed and `ENTRY`/`EXIT` swapped.

- **Why deferred**: not required by the course document's core or bonus
  lists; its main value in this project is as a prerequisite for SSA
  (below), which was itself judged lower priority than finishing the
  required Phase 3 surface (CFG, three data-flow analyses, call graph,
  navigation, rename, dead code) to a polished state.
- **Effort**: small — half a day, mostly reusing `core/graph.py`'s
  existing BFS/reverse-adjacency machinery.
- **Plugs into**: `core/cfg.py`, as a function over `ControlFlowGraph`
  parallel to the existing `unreachable_blocks` helper.

## Dominance frontier and SSA form

The dominance frontier of `n` is the set of blocks where `n`'s dominance
"stops" — where φ-functions get placed in SSA construction. Once
dominators exist, the frontier itself is ~15 lines (Cytron et al.'s
formulation); the real work is φ-placement and the renaming pass that
turns ordinary assignments into fresh SSA variables. SSA is the
intermediate representation LLVM and GCC actually use, which is what
makes it the most conceptually valuable remaining bonus — and also the
one most likely to overrun a course project's timeline if attempted
alongside everything else.

- **Why deferred**: highest effort-to-course-credit ratio of anything on
  this list; needs dominators first, so it inherits that deferral too.
- **Effort**: large — multiple days: dominance frontier, φ-insertion,
  and a renaming pass that must interact correctly with the existing
  scope tree (`core/scopes.py`) for variables that already shadow.
- **Plugs into**: a new `core/ssa.py` sitting on top of `core/cfg.py` and
  the dominator tree above; would reuse `core/dataflow.py`'s solver for
  the liveness computation SSA renaming needs.

## Java as a second language

The `core/` package (lexer/parser base classes, `NodeVisitor`, the
dataflow solver, the graph types, the SVG renderer) was designed
specifically so that `core/` never imports anything from `languages/` —
Phase 1's own bonus-language pitch relied on this boundary being real.
A second language today, however, needs its own token rules, grammar,
recursive-descent parser, AST node set, type rules, and scope rules, plus
something C never required: a class-scope model with virtual dispatch
for the call graph and dead-function analysis to stay meaningful (a
"dead" virtual method may still be reachable through an override).
It was the cheapest bonus available in Phase 1, before name resolution,
type checking, data-flow, and call-graph analysis all existed to be
reimplemented against; it is the most expensive one now.

- **Why deferred**: cost grew with every later phase; by Phase 3 it is a
  second full language front end, not a lexer-and-parser exercise.
- **Effort**: very large — comparable to redoing Phases 1–3 for a second
  grammar, plus a dispatch model C never needed.
- **Plugs into**: `src/clens/languages/java/`, mirroring
  `src/clens/languages/c/` module-for-module.

## LSP server

`languages/c/queries.py` was kept deliberately adapter-free — it takes a
`SemanticModel` and a cursor position or symbol, and returns plain data,
with no knowledge of the CLI or the web UI that calls it. An LSP server
would be a third such adapter: a thin `pygls`-based layer translating
`textDocument/completion`, `textDocument/hover`,
`textDocument/definition`, and `textDocument/references` requests into
the exact same `queries.py` calls the CLI and web UI already make.

- **Why deferred**: the web UI (`docs/bonus/web-ui.md`) already satisfies
  the course document's interface requirement, including the Phase 3
  navigation/CFG/call-graph features via A7.1/§6.6. `pygls` would also be
  clens's first third-party runtime dependency, breaking a property held
  since Phase 1.
- **Effort**: small to medium — the query layer already does the work;
  this is protocol translation and JSON-RPC plumbing.
- **Plugs into**: `src/clens/lsp/`, calling straight into
  `languages/c/queries.py`.

## Incremental re-parsing

Re-parse only the source region a keystroke actually changed, plus
whatever syntactically depends on it — the core Tree-sitter technique —
instead of re-tokenizing and re-parsing the whole file. The web UI
currently rebuilds the full model (`_build_model` in
`web/server.py:_build_model`) from scratch on every `/api/*` request.

- **Why deferred**: decision D21 — at the file sizes this project
  actually handles (single translation units, not multi-thousand-line
  codebases), a full re-parse is fast enough that correctness beats
  latency. Incremental re-parsing adds real complexity (invalidation
  tracking, partial-AST splicing) for a performance win that isn't
  currently needed.
- **Effort**: large — this is close to a parser architecture change, not
  a bolt-on.
- **Plugs into**: `core/parser_base.py` and the web server's
  `_build_model`, which is the one place that would need to start caching
  and diffing instead of rebuilding.

## C preprocessor pass

`#define`, `#include`, `#ifdef`/`#ifndef`/`#endif`, with macro expansion
and error locations mapped back through expansion to the original
pre-expansion source position (the hard part — a naive implementation
that reports errors at *expanded* positions is nearly useless to a user).
Currently, preprocessor directives are tokenized (so the lexer doesn't
choke on them) but never expanded or acted on.

- **Why deferred**: out of scope for the course document's C subset, and
  position-mapping through macro expansion is a substantial project on
  its own — every diagnostic, every navigation query, and every rename
  would need to reason about expanded vs. original spans.
- **Effort**: large.
- **Plugs into**: a new pass between `languages/c/lexer.py` and
  `languages/c/parser.py`, needing its own source-position mapping
  layer that every downstream consumer of `Span`/`Location` would have
  to go through.

## Multi-file support

Resolve symbols and build call graphs across multiple translation units —
`#include`d headers, or several `.c` files analyzed together — rather
than clens's current single-file scope.

- **Why deferred**: every A4 navigation result already carries a `file`
  field in its JSON shape (`docs/bonus`'s navigation doc and
  `languages/c/queries.py`'s §6.3 output), specifically so this extension
  wouldn't require a breaking format change later. But the actual
  cross-file work — a translation-unit model, merging multiple symbol
  tables, and resolving an external declaration to its defining file —
  is new and was judged lower priority than deepening the single-file
  feature set the course document actually grades.
- **Effort**: medium to large — mostly in `core/symbols.py` and the
  resolver (`languages/c/resolver.py`), which currently assume one
  `SemanticModel` per file.
- **Plugs into**: a new coordinating layer above today's per-file
  `analyze()`, likely `languages/c/project.py`, holding several
  `SemanticModel`s and a cross-file symbol index.

# Program analysis

The Phase 3 analysis layer: control-flow graph construction, the three
required data-flow analyses (plus one bonus), and the call graph's seven
required queries. Each analysis states its **direction, lattice,
transfer, and join** explicitly (A2.4). See `docs/architecture.md` for
where these modules sit in the overall pipeline, and `docs/bonus/` for
the bonus items called out inline below.

## Control-flow graph construction (A1)

`core/cfg.py` defines the language-agnostic structures — `BasicBlock`
(id, statements, successors with an `EdgeLabel`, predecessors kept in
sync via `add_successor`), `ControlFlowGraph` (one `entry`, one `exit`,
the block list), and four edge labels: `true`, `false`, `fallthrough`,
`back`.

`languages/c/cfg_builder.py` builds one CFG per function *definition*
(A1.1) — a prototype (`body is None`) has no body to graph and yields
`None` (A8.1), not an empty graph. Because `switch`/`goto`/labels are
outside this C subset, every construct is structured (`if`, `while`,
`for`, `return`, `break`, `continue`), so the graph is always reducible —
no arbitrary jump target ever needs resolving.

**The recursive recipe**: `_build_stmt(stmt, current) -> BasicBlock | None`
returns the block control falls out the bottom into, or `None` if control
never falls through (a `return`, `break`, or `continue` always jumps
somewhere else first). A `None` result with more statements left in the
enclosing block is exactly a post-jump unreachable region (A2.3): the
next statement is built into a fresh, disconnected block, so "no
incoming edges" catches it structurally rather than as a special case.

- **`if`/`else`**: the condition is appended to the current block; `true`
  and `false` edges lead to fresh then/else-entry blocks; both tails (if
  they fall through) rejoin at a new join block. No `else`: the `false`
  edge goes directly from the head to the join block.
- **`while`**: a header block holds the condition; `true` enters the
  body, `false` exits to `after`. The body's tail (if any) adds a `back`
  edge to the header. `break` targets `after`; `continue` targets the
  header directly (nothing needs to run before re-testing the
  condition).
- **`for`**: the same shape as `while`, but with a separate `latch` block
  holding the update expression between the body and the header —
  `continue` targets the `latch`, not the header, since the update must
  run before the condition is re-tested.
- **`while(1)` / `for(;;)`** (A8.1): `_condition_always_true` recognizes
  the literal non-zero-constant idiom and *omits* the `false` edge
  entirely, rather than wiring it to a block nothing can reach. With no
  `break` inside, `after` — and therefore `EXIT` — is genuinely
  unreachable, which is correct, not a bug (see "Unreachable code"
  below for why this forced a BFS-based reachability check rather than a
  naive one).
- **Loop context stack**: `break`/`continue` targets come from a stack of
  `(continue_target, after)` pairs, one push per loop nesting level.
  `break`/`continue` outside any loop is a parse-level concern, but the
  builder still guards against an empty stack (falling through to
  `EXIT`) in case a recovered, malformed AST reaches it (A8.1) — the
  builder must never crash on such input.

A single `EXIT` node (rather than one per `return`) is simpler and still
satisfies A1.4 ("one or more exit nodes"): every `return` and the
function's implicit final fallthrough all flow into it.

## Data-flow analysis (A2)

`core/dataflow.py`'s `solve(cfg, analysis)` is one generic worklist
fixed-point solver, parameterized by an `Analysis` bundling `direction`
(`FORWARD`/`BACKWARD`), `join`, `transfer`, `boundary` (the value fixed
at the direction's entry point — `ENTRY` for forward, `EXIT` for
backward), and `initial` (the starting value at every other block).
Standard worklist: seed every block, pop, recompute `in` from
neighbours' `out` via `join`, recompute `out` via `transfer`, and
re-enqueue affected neighbours only when `out` actually changes.

All three analyses below configure this one solver — none of them run
their own loop. Gen/kill sets come entirely from `Reference.is_read`/
`is_write`, recorded once during Phase 2 name resolution and reused here
verbatim (D27) — nothing re-walks the AST to rediscover which
identifiers are reads or writes.

### A2.1 Definite assignment

Backs the real S6.3 row-12 diagnostic (`S008`), replacing Phase 2's
block-local approximation.

| | |
|---|---|
| Direction | Forward |
| Lattice | `(2^Vars, ⊇)` — a "must" analysis: more assigned is "higher" |
| Boundary (ENTRY) | Parameters only — bound by the call, not by any write `Reference` in the body |
| Initial (elsewhere) | The full variable universe — optimistic until proven otherwise; **critical**: seeding with the empty set instead collapses everything to "unassigned" on the first intersection, the classic must-analysis bug |
| Transfer | `out(b) = in(b) ∪ defs(b)` |
| Join | Intersection — a variable counts only if assigned on *every* incoming path |

A read is flagged only when the enclosing block's running assigned-set
(walked statement-by-statement from that block's `in`, not just checked
at block granularity) doesn't yet contain the variable. This is what
correctly warns on the course document's own example —
`int x; if (c) { x = 42; } printf(x);` — on exactly the path where `c`
is falsy, while a single top-to-bottom AST walk (Phase 2's old
approximation) could not distinguish that path from one where `c` was
always true. Scoped to scalar primitives only (`char`/`int`/`float`/
`double`) — see `docs/known-limitations.md` for why pointers/structs are
excluded.

### A2.2 Live variables

Backward "may" analysis: a variable is live at a point if its current
value may be read on *some* path forward from there. Powers the dead-
assignment detector (A6) and is the natural backward counterpart to
definite assignment.

| | |
|---|---|
| Direction | Backward |
| Lattice | `(2^Vars, ⊆)` — a "may" analysis: more live is "higher" |
| Boundary (EXIT) | Empty — nothing is live after the function returns |
| Initial (elsewhere) | Empty |
| Transfer | `in(b) = use(b) ∪ (out(b) − def(b))` |
| Join | Union |

A write with no live variable expecting it afterward (checked at
statement granularity, walking each block backward from its `out`) is a
dead assignment.

### A2.3 Unreachable code

Structural, not a data-flow problem: every block not reachable from
`ENTRY` by a plain BFS over successor edges.

A naive "zero predecessors" check is **not** sufficient — a block can
have a predecessor that is itself unreachable. The canonical case is
`while(1)` with no `break`: the loop's `false` edge is never wired (see
above), so the block after the loop still has zero predecessors and is
trivially caught, but a more complex shape (a predecessor chain hanging
off that same dead branch) would not be. BFS from `ENTRY` is the
transitive closure that gets this right in general, including correctly
reporting `EXIT` itself as unreachable in the no-break `while(1)` case
(A8.1) rather than silently treating "has one static edge pointing at
it" as proof of reachability.

Post-jump statements (code textually following a `return`/`break`/
`continue` inside the same block) are caught for free by the same check:
`cfg_builder` deliberately builds them into a fresh, disconnected block
rather than special-casing "trailing dead code" separately.

## Bonus: reaching definitions

Documented in full in [`docs/bonus/reaching-definitions.md`](bonus/reaching-definitions.md);
summarized here for A2.4 completeness since it is a fourth solver
configuration.

| | |
|---|---|
| Direction | Forward |
| Lattice | `(2^Defs, ⊆)`, where a "definition" is `(id(symbol), id(defining_block))` at block granularity |
| Boundary / Initial | Empty |
| Transfer | `out(b) = gen(b) ∪ (in(b) − kill(b))`, `kill(b)` = every *other* block's definition of a variable `b` redefines |
| Join | Union — a "may" analysis: a definition reaches a point if it reaches along *any* incoming path |

## Call graph (A3)

`core/graph.py`'s `DirectedGraph[N]` is a small, language-agnostic
directed graph: forward and reverse adjacency (so callers/callees are
both O(1) lookups, never a re-scan), BFS reachability in both
directions, and Tarjan's SCC algorithm. `languages/c/call_graph.py`
builds one `CallGraph` per program: one node per `FuncDecl` with a body
(A3.1), one edge per call site whose callee resolves (via Phase 2's own
symbol resolution — matching a `CallExpr.callee_span` against the
resolved symbol's recorded reference spans, not a fresh lookup) to
another defined function (A3.2-A3.3). A call to a declared-but-never-
defined function is recorded separately as `UnresolvedCall`, not
silently dropped.

**Virtual dispatch (A3.4) is not applicable**: this C subset has no
methods, classes, or inheritance, so every call site names exactly one
syntactically fixed candidate — there is no "callable set given the
declared receiver type and class hierarchy" to compute. See
`docs/known-limitations.md`.

### The seven A3.5 queries

| # | Query | Algorithm |
|---|---|---|
| 1 | Direct callees | `DirectedGraph.successors(name)` — forward adjacency, O(1) |
| 2 | Direct callers | `DirectedGraph.predecessors(name)` — reverse adjacency, O(1) |
| 3 | Transitive callees | `DirectedGraph.reachable_from(name)` — BFS over forward adjacency |
| 4 | Transitive callers | `DirectedGraph.reachable_to(name)` — BFS over reverse adjacency (same BFS helper, walked backward) |
| 5 | Recursive functions | DFS with white/grey/black colour marking (`recursive_functions`) |
| 6 | Dead functions | Every node not in `{main} ∪ reachable_from(main)` (`dead_functions`) |
| 7 | Strongly connected components | Tarjan's algorithm (`DirectedGraph.strongly_connected_components`) |

**Row 5 vs. row 7**: recursion detection is a genuinely separate DFS,
not just "read off Tarjan's output," because a single-node SCC is only
*actually* recursive if it has a self-edge — an ordinary acyclic
function is also its own trivial one-node SCC. The DFS closes a cycle
whenever it re-reaches a grey (currently-on-the-DFS-stack) node, and
marks *every* node from that ancestor onward as recursive — not just the
two endpoints of the closing edge — which is what makes a 3-function
mutual-recursion cycle report all three members, not two.

**Row 6, no `main`**: if the program defines no `main`, there is no
principled entry point to measure reachability from. Rather than
declaring every function dead (the file may genuinely be library code,
not a mistake), `dead_functions` returns an empty set — equivalent to
treating every function as its own root. `call_graph_layout` (the SVG
rendering entry point) makes the same choice: it ranks from `main` when
present, or an arbitrary node otherwise.

## Seeing it work

```bash
clens show-cfg tests/fixtures/valid/factorial.c factorial
clens show-cfg tests/fixtures/valid/factorial.c factorial --format svg -o factorial.svg
clens callgraph tests/fixtures/valid/factorial.c --json
clens dead-code tests/fixtures/valid/factorial.c
pytest tests/unit/test_cfg_builder.py tests/unit/test_dataflow_solver.py \
       tests/unit/test_analyses.py tests/unit/test_call_graph.py tests/unit/test_graph.py -v
```

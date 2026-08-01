---
name: call-graph
description: Program-wide call graph construction and the seven required queries for c-lens Phase 3 — including Tarjan SCC, recursion detection, and dead function analysis. Use whenever touching core/graph.py or languages/c/call_graph.py.
---

# Call graph

Requirements: A3.1–A3.5.

## Construction

- **Nodes**: every `FuncDecl` with a body. Prototypes without definitions are not
  nodes, but a call to one is not an error — record it as an unresolved edge target
  and note it.
- **Edges**: `f -> g` iff `f` contains a `CallExpr` resolving to `g`.
- **Resolution**: through the symbol table, not by name matching. The Phase 2
  resolver already resolved every call site; reuse that.
- **Virtual dispatch** (A3.4): N/A for C — no methods, no inheritance. One line in
  the docs.

Store the call site's span on each edge. The web UI's click-to-navigate wants it,
and it costs nothing now.

## The seven queries (A3.5)

All are explicit table rows in the course document. Put a generic directed graph in
`core/graph.py` (adjacency, reverse adjacency, BFS/DFS) and these become thin:

| Query | Implementation |
|---|---|
| Direct callees of `f` | Adjacency lookup |
| Direct callers of `f` | Reverse adjacency lookup |
| Transitively reachable callees | DFS from `f` |
| All functions that can reach `f` | DFS on the reversed graph |
| Recursive functions | DFS with colour marking (white/grey/black); a grey→grey edge is a cycle |
| Dead functions | Not reachable from `main` |
| Strongly connected components | **Tarjan's algorithm** |

**SCC is not optional** — it is a named row. Tarjan is ~40 lines and standard;
copy a reference implementation and adapt naming. Direct recursion shows up as a
single-node SCC with a self-loop; mutual recursion as a multi-node SCC. Point that
out in the docs — it connects the two rows and reads well.

⚠️ Recursion detection and SCC overlap but are not the same. A single-node SCC is
only recursive if it has a self-edge. Handle that.

## Dead functions

Reachability from `main`. If there is no `main`, report that and treat every
function as a root instead of declaring everything dead — the file may be a library.
Say which behaviour you chose in the docs.

## Test fixture

One file exercising: direct recursion, mutual recursion (a 2-cycle), a 3-cycle, a
dead function, a function only reachable through another dead function, and a leaf.
Assert every query against it.

## Definition of done

- [ ] Nodes and edges correct, with call-site spans
- [ ] All seven queries implemented and individually tested
- [ ] Tarjan SCC correct for self-loops, 2-cycles, and 3-cycles
- [ ] Recursion vs single-node-SCC distinction handled
- [ ] No-`main` behaviour chosen, implemented, and documented
- [ ] `clens callgraph` with `--json`

# Phase 3 Requirements

Every Phase 3 requirement from the course document, with stable IDs. Phase 1 used
`R`, Phase 2 used `S`; Phase 3 uses **`A`** (analysis).

Source: course document §6 (Phase Three), plus §8–§9.

---

## A1 — Control Flow Graph

### A1.1 One CFG per function
Built for every `FuncDecl` with a body.

### A1.2 Basic blocks
A maximal sequence of statements with no branches: control enters at the top and
exits at the bottom. Exactly one entry point, at most two successors.

### A1.3 Edges
Possible execution paths: true and false branches of conditionals, loop back-edges,
and exits via `return` / `break` / `continue`. (`throw` is in the document but C has
no exceptions — document as N/A.)

### A1.4 Unique ENTRY, one or more EXIT
Every CFG has one `ENTRY` node and at least one `EXIT`.

### A1.5 Golden example
Course document §6.1, for `factorial`:

```
ENTRY -> B1: evaluate n <= 1
B1 --true--> B2: return 1
B1 --false-> B3: return n * factorial(n-1)
B2 -> EXIT ; B3 -> EXIT
```

This is a golden test.

---

## A2 — Data-flow analyses

All three run on the CFG. Write **one** generic worklist solver parameterized by
(direction, join, transfer); each analysis is then ~15 lines. Do not write three
solvers — see D26.

### A2.1 Definite assignment (forward must-analysis)
For each variable use, verify the variable is definitely assigned on **every** path
from ENTRY to that use. Lattice ⟨2^Vars, ⊇⟩. Transfer sets the assigned variable.
Join is **intersection**.

Golden example (§6.1.1):
```c
int x;
if (condition) { x = 42; }
printf("%d\n", x);   /* Error: x uninitialized on the false path */
```

### A2.2 Live variables (backward may-analysis)
A variable is live at a point if its current value may be used on some future path.
Lattice ⟨2^Vars, ⊆⟩. Transfer removes defined variables, adds used ones. Join is
**union**. Used to detect dead assignments.

### A2.3 Unreachable code
A basic block with no incoming edges (other than ENTRY) is unreachable — report as a
**warning**. Also detect statements following an unconditional
`return`/`break`/`continue` within a block.

Golden example (§6.1.1):
```c
int foo() { return 42; printf("never\n"); }        /* after unconditional return */
void bar(int x) { if (x > 0) { return; x++; } }    /* after return in if-branch */
```

### A2.4 Document the lattice
For each analysis, state direction, lattice, transfer function, and join operator in
the docs. The course document spells these out, so they are clearly assessed.

---

## A3 — Call graph

### A3.1 Nodes
Every function definition in the program.

### A3.2 Edges
Directed: `f -> g` iff `f` contains a call site resolving to `g`.

### A3.3 Resolution
Use the symbol table to resolve each direct call site.

### A3.4 Virtual calls
For polymorphic dispatch (Java/C++), add edges to all methods callable given the
declared receiver type and class hierarchy. **N/A for C** — document it, one line.

### A3.5 The seven required queries
All of §6.2.1's table:

| Query | Algorithm |
|---|---|
| Direct callees of `f` | Adjacency list lookup |
| Direct callers of `f` | Reverse adjacency |
| All transitively reachable callees from `f` | BFS / DFS |
| All functions that can reach `f` | BFS on the reversed graph |
| Detect recursive functions | Cycle detection (DFS with color marking) |
| Dead functions (unreachable from entry) | Reachability from `main` |
| Strongly connected components | Tarjan's or Kosaraju's |

SCC is a real algorithm and an explicit table row. Do not skip it.

---

## A4 — Navigation

### A4.1 Go-to-definition
Given a cursor over a symbol usage, return the exact (file, line, column) of its
declaration. (Overridden methods — N/A for C.)

### A4.2 Find all references
Given a symbol's definition site, return every (file, line, column) where it is read
or written.

### A4.3 Hover
**Already delivered in Phase 2 (S7).** Verify it still works and claim it here.

### A4.4 JSON response shape
Course document §6.3 specifies it exactly:

```json
{
  "symbol": "factorial",
  "kind": "function",
  "type": "(int) -> int",
  "defined_at": { "file": "main.c", "line": 1, "col": 5 },
  "references": [ { "file": "main.c", "line": 15, "col": 12 } ]
}
```

Note the key is `col`, not `column`. Match it exactly.

---

## A5 — Safe rename

### A5.1 The five steps
1. Accept a symbol (identified by source location) and a new name.
2. **Conflict check**: the new name must not already exist in the same scope.
3. **Shadow check**: the rename must not cause shadowing in any inner or outer scope.
4. Produce a **unified diff** of every line that would change.
5. Apply atomically: every occurrence renamed, or none.

### A5.2 Scope-awareness is mandatory
The course document: *"A simple text-substitution approach is not acceptable and
will receive zero credit for this feature."*

Rename by symbol identity from the scope tree, never by string matching.

### A5.3 Golden example
§6.4 — renaming `n` to `number` inside `factorial` changes only that function's `n`.
Variables named `n` in other functions are untouched. This is the test they will run.

---

## A6 — Dead code detection

All five categories from §6.5, using the CFG and call graph together:

| Category | Source |
|---|---|
| Unreachable functions | Call graph reachability from entry |
| Unreachable basic blocks | CFG, no incoming edges |
| Post-jump statements | Code after `return`/`break`/`continue` |
| Unused variables | Liveness |
| Dead assignments | A value written then overwritten before being read |

§6.5's example contains all five in one file. Make it a fixture.

---

## A7 — Interactive output

### A7.1 The requirement
The document requires **at least one** of: interactive CLI REPL, Web UI, or LSP
server.

**Already satisfied** — the Phase 2 web UI is the Web UI option. Phase 3 extends it
with new panels rather than building a new interface. Record this explicitly in the
docs; it is a requirement that is met, not skipped.

### A7.2 CLI commands
The document names these; add them to the existing CLI:
`goto-def <file> <line> <col>`, `find-refs <file> <symbol>`,
`rename <file> <line> <col> <new-name>`, `show-cfg <function>`, `callgraph`,
`dead-code`.

### A7.3 Web UI additions
CFG visualization, call-graph visualization, click-to-navigate, dead-code panel.
See `skills/cfg` for the rendering approach (SVG generated server-side; **no new
runtime dependency**).

---

## A8 — Always-on

### A8.1 Never crash
Unchanged. The CFG builder must handle `ErrorStmt` regions, functions with no body
(prototypes), empty bodies, and infinite loops (`while(1)` with no exit — the CFG
then has an unreachable EXIT, which is correct, not a bug).

### A8.2 Phases 1 and 2 stay green
Both acceptance checklists are regression gates.

### A8.3 Coverage ≥80%.

### A8.4 Commits
Target 35–45 for Phase 3.

---

## A9 — Bonus documentation (user requirement, not from the course document)

Every bonus feature — already delivered or added in Phase 3 — gets its own file in
`docs/bonus/`, covering: the goal, why it was implemented, how it was implemented,
and how to see the output. See `skills/bonus-docs` and D29.

Already-delivered bonuses needing retroactive write-ups: Docker, CI/CD with Pages
publishing, the test suite with coverage, and the Web UI.

## A10 — Future work document (user requirement)

`docs/future-work.md` — everything deliberately deferred past Phase 3, each with
scope, effort estimate, and where it would plug in. See D30 for the contents.

---
name: cfg
description: Control flow graph construction and rendering for c-lens Phase 3 — basic blocks, edges, loop handling, and the layered SVG layout used by both CFG and call graph panes. Use whenever touching core/cfg.py, languages/c/cfg_builder.py, core/graph_layout.py, or render/svg.py.
---

# Control Flow Graph

Requirements: A1.1–A1.5, A2.3. Decision: D28.

## Why this one is tractable

`switch`, `goto`, and labels are out of subset. That means control transfer is
always structured, every CFG is reducible, and the recursive builder below always
terminates with a single well-formed graph. Say this out loud in the docs and at the
defense — it is the direct payoff of a Phase 1 scoping decision.

## Data structures (`core/cfg.py`, language-agnostic)

```python
class BlockKind(Enum): ENTRY, EXIT, NORMAL
class EdgeLabel(Enum): TRUE, FALSE, FALLTHROUGH, BACK

@dataclass(slots=True)
class BasicBlock:
    id: int
    kind: BlockKind
    statements: list[Node]                     # empty for ENTRY/EXIT
    successors: list[tuple["BasicBlock", EdgeLabel]]
    predecessors: list["BasicBlock"]

@dataclass(slots=True)
class ControlFlowGraph:
    function_name: str
    entry: BasicBlock
    exit: BasicBlock
    blocks: list[BasicBlock]
```

Keep `predecessors` maintained as edges are added — unreachable-block detection
(A2.3) and every backward analysis read it.

One `EXIT` node is simpler than several and satisfies A1.4 ("one or more"). All
`return`s and the fallthrough end both flow into it.

## Construction: the recursive shape

The clean recipe for structured code is a function that takes the current block and
returns the block control leaves through:

```python
def build_stmt(stmt, current: BasicBlock) -> BasicBlock | None
```

Returning `None` means control does not continue (the statement was a `return`,
`break`, or `continue`). That `None` is exactly what makes post-jump statements
detectable: if a sequence's builder gets `None` back and there are statements left,
those statements are unreachable (A2.3).

Per construct:

- **Straight-line** (`ExprStmt`, `VarDecl`) — append to `current`, return `current`.
- **`Block`** — fold over `body`, threading the current block.
- **`IfStmt`** — terminate `current`; create `then_block`, build into it; same for
  `else`; create a `join` block; wire true/false edges from `current`; connect each
  surviving branch tail to `join`. If both branches return `None`, return `None`.
- **`WhileStmt`** — create a `header` block for the condition; `current` → header;
  body built from a fresh block, its tail → header as a `BACK` edge; header →
  `after` on false. Return `after`.
- **`ForStmt`** — init into `current`; then identical to `while`, with the update
  appended to the body's tail before the back-edge. Remember `init` can be a
  `list[VarDecl]`.
- **`ReturnStmt`** — append, edge to EXIT, return `None`.
- **`BreakStmt` / `ContinueStmt`** — edge to the loop context's `after` / `header`,
  return `None`.

Keep a stack of `(header, after)` loop contexts for break/continue.

## Edge cases that must not crash (A8.1)

- **Prototype** (`body is None`) → no CFG. Skip, do not build an empty one.
- **Empty body** → ENTRY → EXIT, one edge.
- **`while(1)`** with no `break` → EXIT is genuinely unreachable. That is correct,
  not a bug. Do not "fix" it by adding a fake edge; do note it in the docs.
- **`ErrorStmt` / `ErrorExpr`** → treat as a straight-line statement with no control
  effect. Never inspect inside them.
- **`break`/`continue` with no enclosing loop** → the loop stack is empty; edge to
  EXIT and move on. Do not raise.

## Golden test (A1.5)

The course document's §6.1 `factorial` CFG:

```
ENTRY -> B1                       B1: evaluate n <= 1
B1 --true--> B2                   B2: return 1
B1 --false-> B3                   B3: return n * factorial(n-1)
B2 -> EXIT ; B3 -> EXIT
```

Assert block count, statements per block, and every labelled edge.

---

# Rendering (D28)

## No new dependencies

No Graphviz binary, no `networkx`, no JS graph library. All would break the
zero-runtime-dependency claim that is stated in the README and is itself a talking
point.

## Layered layout (`core/graph_layout.py`)

Pure geometry, no I/O, fully unit-testable:

1. **Rank** each block by BFS depth from ENTRY. Back-edges do not contribute to
   rank — detect them first (a successor already visited at a lower-or-equal rank).
2. **Order** within a rank by first-visit order; keeps the true branch left.
3. **Position**: `y = rank * row_height`, `x` centered within the rank.
4. **Route**: forward edges straight or with one bend; back-edges as a curve to the
   left of the node column so they read as loops.

CFGs here have single-digit block counts. Do not build a crossing-minimisation pass;
it will not be visible.

## SVG (`render/svg.py`)

Emit text. Take colors from `core/theme.py` so the CFG matches the highlighter's
palette — same "one theme table, many renderers" pattern as Phase 1's ANSI/HTML
split. Nodes are rounded rects with the block id and its statements; edges are paths
with `TRUE`/`FALSE` labels.

The same layout and renderer serve the call graph — different node contents, same
geometry.

## Definition of done

- [ ] `factorial` golden CFG matches §6.1 exactly
- [ ] `if`/`else`/`while`/`for`/`break`/`continue`/`return` each tested
- [ ] Prototype, empty body, `while(1)`, and `ErrorStmt` all handled without a crash
- [ ] `predecessors` maintained and correct
- [ ] Layout is pure and unit-tested independently of SVG output
- [ ] SVG uses theme colors, embeds no external references
- [ ] Zero runtime dependencies added

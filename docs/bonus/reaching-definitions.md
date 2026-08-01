# Reaching Definitions

## Goal

A fourth data-flow analysis alongside the three the course document
requires (definite assignment, live variables, unreachable code): for
every point in a function, which assignments to a variable could possibly
be the one whose value is read there. This is the classical
"reaching-definitions" problem from the course document's data-flow
material — not on the required list, but built with the same machinery.

## Motivation

Once `core/dataflow.py`'s generic worklist solver exists (D26), reaching
definitions is one more `Analysis` configuration, not a new algorithm.
Doing it "now while the machinery is fresh" (as the task plan puts it) is
the cheapest possible bonus point: it is direct evidence that the solver
is genuinely generic and not secretly specialized to definite assignment,
and reaching definitions is itself the textbook prerequisite for
optimizations like constant propagation and the SSA form recorded in
`docs/future-work.md`.

## Implementation

`languages/c/analyses.reaching_definitions(cfg, symbols)`:

- **Direction**: forward.
- **Lattice**: `(2^Defs, ⊆)` — a "definition" is identified by
  `(id(symbol), id(defining_block))`, at the CFG's own block granularity
  rather than per-statement, since that is the granularity every other
  analysis in this module already works at.
- **Transfer**: `out(b) = gen(b) ∪ (in(b) − kill(b))`, where `gen(b)` is
  every variable this block writes, tagged with `b` itself as the
  defining block, and `kill(b)` is every *other* block's definition of a
  variable this block redefines.
- **Join**: union (a "may" analysis — a definition reaches a point if it
  reaches along *any* incoming path).

This is the same shape as `live_variables` and `definite_assignment` in
the same file, configured through the identical `core.dataflow.solve()`.
Gen/kill still comes from `Reference.is_write` via the shared
`_references_by_block` helper — no new AST walk.

## Seeing it work

```python
from clens.core.diagnostics import DiagnosticCollector
from clens.core.source import SourceFile
from clens.languages.c.parser import parse
from clens.languages.c.semantic import analyze
from clens.languages.c.program_analysis import analyze_program

text = """
int use(int v);
int f(int c) {
    int x;
    if (c) { x = 1; } else { x = 2; }
    return use(x);
}
"""
source = SourceFile(text, "a.c")
diagnostics = DiagnosticCollector()
program = parse(source, diagnostics)
model = analyze(program, source, diagnostics)
analysis = analyze_program(model)

results = analysis.dataflow["f"].reaching_definitions
# Both branches' definitions of `x` reach the `return use(x);` block.
```

Or run the test directly:

```
pytest tests/unit/test_analyses.py -k reaching_definitions -v
```

`test_reaching_definitions_distinguishes_branches` asserts exactly the
scenario above: the block holding `return use(x);` has two distinct
reaching definitions of `x` — one from each branch of the `if`.

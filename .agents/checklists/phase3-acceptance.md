# Phase 3 Acceptance Checklist

Walk top to bottom, then re-walk `checklists/phase1-acceptance.md` and
`checklists/phase2-acceptance.md` — both are regression gates.

## Regression

- [ ] Every item in the Phase 1 and Phase 2 checklists still passes
- [ ] `clens highlight --format html` byte-identical; golden green; no JavaScript
- [ ] Coverage still ≥ 80%
- [ ] Zero runtime dependencies still true

## Robustness

- [ ] No crash on: prototype without body, empty function body, `while(1)` with no
      exit, `ErrorStmt` inside a function, a file with no `main`, a file that fails
      to parse entirely, an empty file
- [ ] Unreachable EXIT from `while(1)` is reported correctly, not "fixed"
- [ ] `break` / `continue` with no enclosing loop does not raise

## CFG

- [ ] `factorial` golden CFG matches course document §6.1 exactly, including the
      labelled true/false edges
- [ ] `if`/`else`, `while`, `for`, `break`, `continue`, `return` each tested
- [ ] Loop back-edges present and labelled
- [ ] `predecessors` maintained and correct
- [ ] One ENTRY, at least one EXIT (A1.4)

## Data-flow

- [ ] One generic solver; all analyses configured through it
- [ ] Solver tested standalone on a toy lattice, both directions, both joins
- [ ] Must-analysis initial value is the **full** set, not empty
- [ ] Definite assignment: `int x; if (c) { x = 42; } printf(x);` warns
- [ ] Live variables produce dead assignments
- [ ] Unreachable blocks and post-jump statements both warn
- [ ] Gen/kill built from `Reference.is_read`/`is_write`, not re-derived from the AST
- [ ] `usage.py` rewired to real results; codes `S008`/`S009` and severities unchanged
- [ ] `known-limitations.md` row-12/13 entry **rewritten**, not appended
- [ ] Direction, lattice, transfer, and join documented for each analysis (A2.4)

## Call graph

- [ ] Nodes and edges correct, with call-site spans
- [ ] All seven A3.5 queries implemented and individually tested
- [ ] Tarjan SCC correct for self-loops, 2-cycles, 3-cycles
- [ ] Recursion vs single-node-SCC distinction handled
- [ ] No-`main` behaviour chosen, implemented, documented

## Navigation

- [ ] Go-to-definition for variables, parameters, functions, struct tags, fields
- [ ] Cursor on a definition returns that definition
- [ ] References include the definition site, flagged, sorted by offset
- [ ] JSON matches course document §6.3 exactly — including **`col`**, not `column`
- [ ] Hover (Phase 2's S7) still works

## Rename

- [ ] **No string substitution anywhere in the rename path**
- [ ] Conflict check names the conflicting declaration's location
- [ ] Both shadow directions checked (would-shadow, would-be-shadowed)
- [ ] Unified diff produced
- [ ] Edits applied right-to-left, atomically
- [ ] §6.4 golden test passes, **including the untouched second function using the
      same name**
- [ ] Refusal cases tested

## Dead code

- [ ] All five A6 categories fire on the §6.5 fixture, each exactly once
- [ ] Severities: unreachable and dead assignments warn; unused variables info

## Interfaces

- [ ] `show-cfg`, `callgraph`, `dead-code`, `goto-def`, `find-refs`, `rename` all
      work, all support `--json`
- [ ] SVG rendering for CFG and call graph, theme colors, no external references
- [ ] Graph layout is pure and unit-tested independently of SVG output
- [ ] Web endpoints `/api/cfg` and `/api/callgraph` follow the `handle_*` +
      `_POST_ROUTES` + `dispatch_post` pattern; tested without a socket
- [ ] Web UI: CFG pane, call-graph pane, dead-code panel, click-to-navigate
- [ ] A7.1 explicitly recorded as satisfied by the Web UI

## Documentation

- [ ] `docs/program-analysis.md` — CFG algorithm, three analyses with all four
      lattice properties each, call-graph queries with algorithms
- [ ] `docs/known-limitations.md` — row-12/13 rewritten; `throw` N/A; virtual calls
      N/A; single-file scope
- [ ] `docs/architecture.md` and README pipeline updated for the analysis layer
- [ ] `docs/testing.md` — every new command verified copy-pasteable
- [ ] `docs/bonus/README.md` + a four-section file per delivered bonus
      (docker, ci-cd, test-suite-coverage, web-ui, reaching-definitions)
- [ ] Every command in every "Seeing it work" section actually runs
- [ ] `docs/future-work.md` — all seven deferred items with effort and plug-in points
- [ ] Both linked from the README

## Defense readiness

- [ ] Both members can explain why the CFG is tractable here (no `goto`/`switch`)
- [ ] Both can state direction, lattice, transfer, and join for each analysis
- [ ] Both can explain why one generic solver rather than three loops
- [ ] Both can explain why a must-analysis initialises to the full set
- [ ] Both can explain why text-substitution rename is wrong and what we do instead
- [ ] Both can trace `int x; if (c) { x = 42; } printf(x);` from CFG construction
      through definite-assignment to the warning
- [ ] Both can demo the web UI's CFG and call-graph panes without notes

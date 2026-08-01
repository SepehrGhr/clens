# Phase 3 Acceptance Checklist

Walk top to bottom, then re-walk `checklists/phase1-acceptance.md` and
`checklists/phase2-acceptance.md` — both are regression gates.

## Regression

- [x] Every item in the Phase 1 and Phase 2 checklists still passes
- [x] `clens highlight --format html` byte-identical; golden green; no JavaScript
- [x] Coverage still ≥ 80% (96.83% as of this pass — `pytest --cov=src/clens`)
- [x] Zero runtime dependencies still true (`pyproject.toml`'s `dependencies = []`)

## Robustness

- [x] No crash on: prototype without body, empty function body, `while(1)` with no
      exit, `ErrorStmt` inside a function, a file with no `main`, a file that fails
      to parse entirely, an empty file
- [x] Unreachable EXIT from `while(1)` is reported correctly, not "fixed"
- [x] `break` / `continue` with no enclosing loop does not raise

## CFG

- [x] `factorial` golden CFG matches course document §6.1 exactly, including the
      labelled true/false edges
- [x] `if`/`else`, `while`, `for`, `break`, `continue`, `return` each tested
- [x] Loop back-edges present and labelled
- [x] `predecessors` maintained and correct
- [x] One ENTRY, at least one EXIT (A1.4)

## Data-flow

- [x] One generic solver; all analyses configured through it
- [x] Solver tested standalone on a toy lattice, both directions, both joins
- [x] Must-analysis initial value is the **full** set, not empty
- [x] Definite assignment: `int x; if (c) { x = 42; } printf(x);` warns
- [x] Live variables produce dead assignments
- [x] Unreachable blocks and post-jump statements both warn
- [x] Gen/kill built from `Reference.is_read`/`is_write`, not re-derived from the AST
- [x] `usage.py` rewired to real results; codes `S008`/`S009` and severities unchanged
- [x] `known-limitations.md` row-12/13 entry **rewritten**, not appended
- [x] Direction, lattice, transfer, and join documented for each analysis (A2.4)

## Call graph

- [x] Nodes and edges correct, with call-site spans
- [x] All seven A3.5 queries implemented and individually tested
- [x] Tarjan SCC correct for self-loops, 2-cycles, 3-cycles
- [x] Recursion vs single-node-SCC distinction handled
- [x] No-`main` behaviour chosen, implemented, documented

## Navigation

- [x] Go-to-definition for variables, parameters, functions, struct tags, fields
- [x] Cursor on a definition returns that definition
- [x] References include the definition site, flagged, sorted by offset
- [x] JSON matches course document §6.3 exactly — including **`col`**, not `column`
- [x] Hover (Phase 2's S7) still works

## Rename

- [x] **No string substitution anywhere in the rename path**
- [x] Conflict check names the conflicting declaration's location
- [x] Both shadow directions checked (would-shadow, would-be-shadowed)
- [x] Unified diff produced
- [x] Edits applied right-to-left, atomically
- [x] §6.4 golden test passes, **including the untouched second function using the
      same name**
- [x] Refusal cases tested

## Dead code

- [x] All five A6 categories fire on the §6.5 fixture, each exactly once
- [x] Severities: unreachable and dead assignments warn; unused variables info

## Interfaces

- [x] `show-cfg`, `callgraph`, `dead-code`, `goto-def`, `find-refs`, `rename` all
      work, all support `--json`
- [x] SVG rendering for CFG and call graph, theme colors, no external references
- [x] Graph layout is pure and unit-tested independently of SVG output
- [x] Web endpoints `/api/cfg` and `/api/callgraph` follow the `handle_*` +
      `_POST_ROUTES` + `dispatch_post` pattern; tested without a socket
- [x] Web UI: CFG pane, call-graph pane, dead-code panel, click-to-navigate
- [x] A7.1 explicitly recorded as satisfied by the Web UI

## Documentation

- [x] `docs/program-analysis.md` — CFG algorithm, three analyses with all four
      lattice properties each, call-graph queries with algorithms
- [x] `docs/known-limitations.md` — row-12/13 rewritten; `throw` N/A; virtual calls
      N/A; single-file scope
- [x] `docs/architecture.md` and README pipeline updated for the analysis layer
- [x] `docs/testing.md` — every new command verified copy-pasteable
- [x] `docs/bonus/README.md` + a four-section file per delivered bonus
      (docker, ci-cd, test-suite-coverage, web-ui, reaching-definitions)
- [x] Every command in every "Seeing it work" section actually runs
- [x] `docs/future-work.md` — all seven deferred items with effort and plug-in points
- [x] Both linked from the README

## Defense readiness

- [ ] Both members can explain why the CFG is tractable here (no `goto`/`switch`)
- [ ] Both can state direction, lattice, transfer, and join for each analysis
- [ ] Both can explain why one generic solver rather than three loops
- [ ] Both can explain why a must-analysis initialises to the full set
- [ ] Both can explain why text-substitution rename is wrong and what we do instead
- [ ] Both can trace `int x; if (c) { x = 42; } printf(x);` from CFG construction
      through definite-assignment to the warning
- [ ] Both can demo the web UI's CFG and call-graph panes without notes

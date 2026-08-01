# Phase 3 Task Plan

Same discipline: top to bottom, one or two commits per task, tick the box in the
same commit. Target **35–45 commits**.

Legend: `→ skill` = read first. `→ A#` = requirement IDs.

Before Stage 0: read `project/10-phase2-interfaces.md`. Phase 3 consumes every
structure in it.

---

## Stage 0 — Carry-over (≈3 commits)

- [x] **Q0.1** Drop in the Phase 3 agent environment; commit it.
- [x] **Q0.2** Run `pytest`; walk both `checklists/phase1-acceptance.md` and
      `checklists/phase2-acceptance.md`. Green before any Phase 3 code.
- [x] **Q0.3** `languages/c/program_analysis.py` skeleton: `ProgramAnalysis` and
      `analyze_program(model) -> ProgramAnalysis` returning empty structures, wired
      into the CLI and a test. Everything else fills it in. → D25

## Stage 1 — CFG (≈7 commits)

→ `skills/cfg`.

- [x] **Q1.1** `core/cfg.py`: `BasicBlock` (id, statements, successors,
      predecessors, kind), `ControlFlowGraph` (entry, exit(s), blocks), and edge
      labels (`true`/`false`/`fallthrough`/`back`). Language-agnostic. → A1.2–A1.4
- [x] **Q1.2** `languages/c/cfg_builder.py`: straight-line statements, `Block`,
      `ExprStmt`, `VarDecl`. → A1.1
- [x] **Q1.3** `if`/`else` with true/false edges; `return` terminating a block into
      EXIT.
- [x] **Q1.4** `while` and `for`, including the loop back-edge, and `break` /
      `continue` targeting the enclosing loop's exit / header. Keep a loop-context
      stack; `break` outside a loop is already a parse-level concern, but the
      builder must not crash on a recovered AST.
- [x] **Q1.5** Edge cases: prototypes (no body → no CFG), empty bodies, `while(1)`
      with no exit (unreachable EXIT is correct), `ErrorStmt` regions. → A8.1
- [x] **Q1.6** Golden test: the `factorial` CFG matches §6.1 exactly — ENTRY, B1,
      B2, B3, EXIT with the labelled true/false edges. → A1.5
- [x] **Q1.7** `clens show-cfg <file> <function>` — text form first (blocks,
      statements, successors). SVG comes in Stage 5. → A7.2

## Stage 2 — Data-flow (≈7 commits)

→ `skills/dataflow`.

- [x] **Q2.1** `core/dataflow.py`: the generic worklist solver, parameterized by
      direction, join, transfer, and initial value. Tested standalone on a toy
      lattice before any real analysis uses it. → D26
- [x] **Q2.2** Per-block gen/kill sets from `Reference.is_read` / `is_write`.
      **Reuse Phase 2's reference data; do not re-derive read/write from the AST.**
- [x] **Q2.3** Definite assignment: forward, intersection, must. Produces the real
      row-12 diagnostic. Golden case: `int x; if (c) { x = 42; } printf(x);` →
      warning. → A2.1
- [x] **Q2.4** Live variables: backward, union, may. → A2.2
- [x] **Q2.5** Unreachable code: blocks with no incoming edges, plus post-jump
      statements. Warning severity. → A2.3
- [x] **Q2.6** Replace `usage.py`'s crude row-12/13 logic with the real results.
      Same codes (`S008`, `S009`), same severities. **Rewrite** the corresponding
      `docs/known-limitations.md` entry. → D27
- [x] **Q2.7** **Bonus — reaching definitions.** One more solver configuration,
      ~15 lines. Do it now while the machinery is fresh. Write
      `docs/bonus/reaching-definitions.md` in the same commit. → D29

## Stage 3 — Call graph (≈5 commits)

→ `skills/call-graph`.

- [x] **Q3.1** `core/graph.py`: a small directed-graph type with adjacency and
      reverse adjacency, plus BFS/DFS reachability. Language-agnostic and reused by
      the CFG renderer.
- [x] **Q3.2** `languages/c/call_graph.py`: nodes from `FuncDecl`s, edges from
      resolved `CallExpr` sites via the symbol table. → A3.1–A3.3
- [x] **Q3.3** Queries 1–4: direct callees, direct callers, transitive callees,
      transitive callers. → A3.5
- [x] **Q3.4** Queries 5–7: recursion detection (DFS colour marking), dead functions
      (unreachable from `main`), **SCC via Tarjan**. → A3.5
- [x] **Q3.5** `clens callgraph <file>` with `--json`. Test against a fixture with
      direct recursion, mutual recursion, a dead function, and a 3-cycle. → A7.2

## Stage 4 — Navigation, rename, dead code (≈8 commits)

→ `skills/navigation`, then `skills/refactoring`.

- [x] **Q4.1** `goto_definition_at(model, offset)` in `languages/c/queries.py`.
      Nearly free — it is `Symbol.definition_loc`. → A4.1
- [x] **Q4.2** `find_references(model, symbol)` — `Symbol.references`. Include the
      definition site itself in the result, flagged. → A4.2
- [x] **Q4.3** The §6.3 JSON shape, exactly — note the key is `col`, not `column`.
      Golden test. → A4.4
- [x] **Q4.4** `clens goto-def` and `clens find-refs` CLI commands. → A7.2
- [x] **Q4.5** Rename: conflict check and shadow check against the scope tree.
      → A5.1 steps 2–3
- [x] **Q4.6** Rename: unified diff via `difflib.unified_diff`, and atomic
      application. → A5.1 steps 4–5
- [x] **Q4.7** **The A5.3 golden test**: renaming `n` in `factorial` leaves every
      other function's `n` untouched. Plus: renaming to an existing name in the same
      scope is refused; renaming to a name that would shadow is refused.
      → A5.2, A5.3
- [x] **Q4.8** Dead code report: all five categories, combining CFG, call graph, and
      liveness. `clens dead-code`. Fixture containing all five. → A6

## Stage 5 — Visualization and web UI (≈6 commits)

→ `skills/cfg` (rendering section).

- [x] **Q5.1** `core/graph_layout.py`: layered layout — rank by BFS depth, center
      each rank, route edges orthogonally, curve back-edges. Pure geometry, no I/O,
      unit-testable. → D28
- [x] **Q5.2** `render/svg.py`: emit SVG from a laid-out graph, using
      `core/theme.py` colors. Serves both CFG and call graph.
- [x] **Q5.3** `clens show-cfg --format svg -o out.svg` and
      `clens callgraph --format svg`.
- [x] **Q5.4** Web endpoints `/api/cfg` and `/api/callgraph`, following the existing
      `handle_*` + `_POST_ROUTES` + `dispatch_post` pattern exactly. Tested via
      `dispatch_post`, no socket. → A7.3
- [x] **Q5.5** Web UI panels: a function picker driving a CFG pane, a call-graph
      pane, and a dead-code panel. Click a symbol → go to definition; a
      references list in the sidebar.
- [x] **Q5.6** Screenshots of the CFG and call-graph panes into `docs/images/`.

## Stage 6 — Bonus and future-work documentation (≈6 commits)

→ `skills/bonus-docs`. → A9, A10, D29, D30

- [x] **Q6.1** `docs/bonus/README.md` — index and status table.
- [x] **Q6.2** Retroactive: `docker.md`, `ci-cd.md`.
- [x] **Q6.3** Retroactive: `test-suite-coverage.md`, `web-ui.md`.
- [x] **Q6.4** `reaching-definitions.md` if not already written in Q2.7.
- [x] **Q6.5** `docs/future-work.md` — dominator trees, dominance frontier + SSA,
      Java, LSP, incremental re-parsing, preprocessor, multi-file. Each with scope,
      effort, and plug-in point. → D30
- [x] **Q6.6** Link `docs/bonus/` and `docs/future-work.md` from the README.

## Stage 7 — Docs and gate (≈5 commits)

- [ ] **Q7.1** `docs/program-analysis.md` — CFG construction algorithm, the three
      data-flow analyses with **direction, lattice, transfer, and join stated
      explicitly for each** (A2.4), and the call-graph queries with their algorithms.
- [ ] **Q7.2** `docs/known-limitations.md` — rewrite the row-12/13 entry (D27); add
      `throw` N/A, virtual calls N/A, single-file scope.
- [ ] **Q7.3** `docs/architecture.md` and the README pipeline diagram updated for
      the analysis layer. Note explicitly that A7.1's interface requirement is
      satisfied by the web UI.
- [ ] **Q7.4** `docs/testing.md` — every new command, verified copy-pasteable.
- [ ] **Q7.5** Coverage ≥80%; walk `checklists/phase3-acceptance.md`, then re-walk
      the Phase 1 and Phase 2 checklists. Only then report Phase 3 complete.

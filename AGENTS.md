# AGENTS.md

Agent instructions for this repository live in **`.agents/`**.

Read `.agents/AGENTS.md` first, then `.agents/project/10-phase2-interfaces.md`,
then `.agents/tasks/phase3-plan.md`.

Quick facts:
- Project: **c-lens** — compiler front-end and IDE feature set for a subset of C.
- **Phases 1 and 2 are complete and delivered.** Current scope: **Phase 3** —
  control flow graphs, data-flow analysis, call graph, navigation, safe rename,
  dead code detection, and the bonus/future-work documentation.
- Language: Python 3.11+, **zero runtime dependencies** — this is stated in the
  README and is load-bearing. Graph rendering is hand-emitted SVG for this reason.

Six rules that override anything else:
1. The tool must never crash on any input. Errors become diagnostics.
2. Phases 1 and 2 stay green. Both acceptance checklists are regression gates.
   `clens highlight --format html` must stay byte-identical and JavaScript-free.
3. Rename by symbol identity, never by text substitution — the course document
   assigns zero credit to a string-replacement rename.
4. No new runtime dependencies. No Graphviz, no networkx, no JS graph library,
   no pygls.
5. Reuse Phase 2's recorded data (`Reference.is_read`/`is_write`,
   `Symbol.references`, `definition_loc`) rather than re-deriving it from the AST.
6. Never credit yourself in a commit message, comment, or document.

Two documentation deliverables carry real weight and are easy to forget:
`docs/bonus/` (one four-section file per bonus, including retroactive write-ups for
Docker, CI/CD, the test suite, and the Web UI) and `docs/future-work.md`.

# AGENTS.md

Agent instructions for this repository live in **`.agents/`**.

Read `.agents/AGENTS.md` first, then `.agents/project/07-phase1-interfaces.md`,
then `.agents/tasks/phase2-plan.md`.

Quick facts:
- Project: **c-lens** — compiler front-end and IDE feature set for a subset of C.
- **Phase 1 is complete and delivered.** Current scope: **Phase 2** — semantic
  analysis, symbol table, type system, intellisense, and the web UI.
- Language: Python 3.11+, zero runtime dependencies (the web UI uses stdlib
  `http.server` and vanilla JavaScript specifically to keep it that way).
- Reference clone at `../pycparser` — read
  `.agents/skills/pycparser-reference/SKILL.md` before opening it. Note it does no
  semantic analysis at all, so it is far less useful in Phase 2 than in Phase 1.

Five rules that override anything else:
1. The tool must never crash on any input. Errors become diagnostics.
2. Phase 1 stays green. `.agents/checklists/phase1-acceptance.md` is a regression
   gate. In particular `clens highlight --format html` must keep producing
   byte-identical, JavaScript-free output — the web UI is a *separate* renderer.
3. Do not implement Phase 3 features (CFG, call graph, data-flow, rename,
   go-to-definition, find-all-references). Hover is the one deliberate exception.
4. One diagnostic per root cause. No cascading error floods.
5. Never credit yourself in a commit message, comment, or document.

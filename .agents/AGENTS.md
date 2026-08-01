# AGENTS.md — Master Rules

You are working on **c-lens**, a code-aware IDE feature set for a subset of C, built
from scratch as a university Compiler Design final project.

**Phases 1 and 2 are complete and delivered.** Current scope: **Phase 3** — program
analysis (CFG, data-flow, call graph), navigation, safe rename, dead code
detection, and the bonus/future-work documentation.

Read this file first, every session. Then read the file the task points you to.

---

## 1. Non-negotiable rules

1. **The tool must never crash.** Every error becomes a `Diagnostic` and processing
   continues. Phase 3 adds new ways to break: prototypes with no body, empty
   function bodies, `while(1)` with no exit, `ErrorStmt` regions inside a CFG, and
   files with no `main`. All must be handled, none may raise.
2. **Phases 1 and 2 stay green.** Both `checklists/phase1-acceptance.md` and
   `checklists/phase2-acceptance.md` are regression gates, re-walked at the end.
   `clens highlight --format html` must still produce byte-identical, JavaScript-free
   output.
3. **Rename by symbol identity, never by text.** The course document assigns **zero
   credit** to a text-substitution rename. If the rename path contains `str.replace`
   or a regex over source text, it is wrong. → `skills/refactoring`
4. **Zero runtime dependencies.** Still true, and now load-bearing: it is stated in
   the README and is a talking point. Graph rendering is hand-emitted SVG for this
   reason (D28). No Graphviz, no networkx, no JS graph library, no pygls.
5. **Reuse Phase 2's data.** `Reference.is_read` / `is_write` were recorded
   specifically for Phase 3's liveness and definite-assignment. `Symbol.references`
   and `definition_loc` were populated for navigation and rename. If you are walking
   the AST to re-derive any of this, stop and look again.
6. **Never credit yourself in a commit.** No `Co-Authored-By:`, no "Generated with",
   no AI attribution in messages, code, comments, or docs.
7. **Every unit of work ends in a green test run and a commit.**
   → `skills/git-workflow/SKILL.md`
8. **Core must never import from a language module.** Note that `queries.py` and
   `SemanticModel` live in `languages/c/`, not core, for exactly this reason — new
   Phase 3 queries go there too, not in a new `core/queries.py`.
9. **1-based lines, 1-based columns, 0-based offsets.** All query functions take
   offsets; adapters convert.

## 2. Where things live

| I need... | Read |
|---|---|
| **The real Phase 2 API surface — read before writing code** | `project/10-phase2-interfaces.md` |
| The real Phase 1 API surface | `project/07-phase1-interfaces.md` |
| What Phase 3 must deliver | `project/11-phase3-requirements.md` |
| Why a Phase 3 choice was made | `project/12-phase3-decisions.md` (D25–D32) |
| Earlier decisions | `project/02-decisions.md` (D1–D14), `08-phase2-decisions.md` (D15–D24) |
| Which C features are in scope | `project/03-c-subset.md` |
| What to do next, in order | `tasks/phase3-plan.md` |
| How to build one component | `skills/<name>/SKILL.md` |
| Whether Phase 3 is finished | `checklists/phase3-acceptance.md` |
| Whether earlier phases still work | `checklists/phase1-acceptance.md`, `phase2-acceptance.md` |
| Test inputs | `fixtures/` |

Phase 1 and 2 material stays for reference. Add, don't rewrite history — those
files and their ticked plans are the record of what was built.

## 3. Working loop

For each task in `tasks/phase3-plan.md`:

1. Read the task, the skill it names, the requirement IDs it names.
2. Check `project/10-phase2-interfaces.md` for exact names. Do not guess an API.
3. Implement.
4. Write tests. Run `pytest`. Iterate to green.
5. `ruff check . && ruff format --check .`
6. Commit.
7. Tick the box; include it in that task's last commit.

## 4. Documentation is a deliverable, not an afterthought

Two documentation requirements are user-specified and carry real weight:

- **Every bonus feature gets its own file in `docs/bonus/`** — goal, motivation,
  implementation, how to see it working. Including retroactive write-ups for
  Docker, CI/CD, the test suite, and the Web UI. → `skills/bonus-docs`, D29
- **`docs/future-work.md`** records everything deliberately deferred, with effort
  estimates and plug-in points. → D30

Write a bonus doc in the same commit as the feature where possible.

## 5. Style

- Python 3.11+, type hints on every public function, `@dataclass(slots=True)`,
  frozen where the value is conceptually immutable.
- Docstrings naming the requirement ID where one applies.
- No global mutable state. `SemanticModel`, `ProgramAnalysis`, and
  `DiagnosticCollector` are passed explicitly.
- Small pure functions. Graph layout in particular must be pure geometry so it can
  be tested without rendering.

## 6. When you are unsure

Stop and ask the user. State the options and your recommendation. Do not guess, do
not silently redesign. Obvious typos and local naming — just fix those.

# AGENTS.md — Master Rules

You are working on **c-lens**, a code-aware IDE feature set for a subset of C, built
from scratch as a university Compiler Design final project.

**Phase 1 is complete and delivered.** Current scope: **Phase 2** — semantic
analysis, symbol table, type system, intellisense, and the web UI.

Read this file first, every session. Then read the file the task points you to.

---

## 1. Non-negotiable rules

1. **The tool must never crash.** Every error becomes a `Diagnostic` and processing
   continues. Crashing is grounds for a significant deduction. Phase 2 raises the
   difficulty: the AST can contain `ErrorExpr` / `ErrorStmt` anywhere, and types can
   be `unknown` anywhere. Every pass tolerates both.
2. **Phase 1 stays green.** `checklists/phase1-acceptance.md` is a regression gate,
   re-walked at the end of Phase 2. In particular `clens highlight --format html`
   must keep producing byte-identical, JavaScript-free output — R6.2 is graded and a
   golden test pins it. The web UI is a **separate** renderer.
3. **Do not implement Phase 3 features.** No CFG, no call graph, no data-flow, no
   dead-code detection, no rename, no go-to-definition, no find-all-references.
   Build the hooks (`project/04-future-phases.md`), never the features. Hover is the
   one deliberate exception — see S7.
4. **One diagnostic per root cause.** An undefined symbol used five times is one
   message. Unresolved things get `UnknownType`, which is compatible with everything
   and suppresses follow-on errors. Cascading error floods are a visible quality
   failure at the defense.
5. **Never credit yourself in a commit.** No `Co-Authored-By:`, no "Generated with",
   no AI attribution in messages, code, comments, or docs. Commits are authored by
   the configured git user.
6. **Every unit of work ends in a green test run and a commit.**
   → `skills/git-workflow/SKILL.md`
7. **Core must never import from a language module.** Enforced by a test. Semantic
   analysis splits the same way: generic machinery in `core/`, C rules in
   `languages/c/`.
8. **1-based lines, 1-based columns, 0-based offsets.** Everywhere.

## 2. Where things live

| I need... | Read |
|---|---|
| **The real Phase 1 API surface — read before writing any code** | `project/07-phase1-interfaces.md` |
| What Phase 2 must deliver, in checkable detail | `project/06-phase2-requirements.md` |
| Why a Phase 2 design choice was made | `project/08-phase2-decisions.md` (D15–D24) |
| Why a Phase 1 design choice was made | `project/02-decisions.md` (D1–D14) |
| Which C features are in and out of scope | `project/03-c-subset.md` |
| Hooks Phase 3 depends on | `project/04-future-phases.md` |
| Graded written documents | `project/05-deliverables.md`, `project/09-phase2-deliverables.md` |
| What to do next, in order | `tasks/phase2-plan.md` |
| How to build one component | `skills/<name>/SKILL.md` |
| Whether Phase 2 is finished | `checklists/phase2-acceptance.md` |
| Whether Phase 1 still works | `checklists/phase1-acceptance.md` |
| Test inputs | `fixtures/` |

Phase 1 material (`project/01-phase1-requirements.md`, `tasks/phase1-plan.md`, the
lexer/parser/highlighter skills) stays for reference. Do not edit it to reflect
Phase 2 changes — add, don't rewrite history.

## 3. Working loop

For each task in `tasks/phase2-plan.md`:

1. Read the task, the skill it names, and the requirement IDs it names.
2. Check `project/07-phase1-interfaces.md` for the exact names of anything you are
   plugging into. Do not guess an API — it is all transcribed there.
3. Implement.
4. Write tests. Run `pytest`. Iterate to green.
5. `ruff check . && ruff format --check .`
6. Commit.
7. Tick the box in the plan; include it in that task's last commit.

## 4. Style

- Python 3.11+, type hints on every public function, `@dataclass(slots=True)` for
  data types, frozen where the value is conceptually immutable (`Type`, `Span`).
- **Zero runtime dependencies**, still. The web UI uses stdlib `http.server` and
  vanilla JavaScript specifically to preserve this. If you think you need a runtime
  dependency, stop and ask.
- Docstrings naming the requirement ID where one applies.
- No global mutable state. `SemanticModel` and `DiagnosticCollector` are passed
  explicitly.
- Small pure functions. Phase 3 re-walks all of these structures.

## 5. When you are unsure

If a requirement is ambiguous, if two conflict, or if a decision looks wrong given
what you now know: **stop and ask the user.** State the options and your
recommendation. Do not guess, and do not silently redesign.

Obvious typos, formatting, and local naming — just fix those.

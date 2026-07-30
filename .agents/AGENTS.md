# AGENTS.md — Master Rules

You are working on **c-lens**, a code-aware IDE feature set for a subset of C, built
from scratch as a university Compiler Design final project.

Read this file first, every session. Then read the file the task points you to.

---

## 1. Non-negotiable rules

These are graded requirements or hard project constraints. Violating any of them
loses marks or breaks later phases.

1. **The tool must never crash.** Not on malformed input, not on empty files, not
   on binary garbage. Every error becomes a `Diagnostic` and processing continues.
   The course document states that crashing on error is grounds for a significant
   deduction. There is no acceptable uncaught exception path from CLI input to output.
2. **No regex-only highlighting.** Highlighting must consult the AST. A pure
   token/regex highlighter is explicitly worth zero credit. The canonical proof is
   that `factorial` in a call site and `factorial` as a plain variable get
   *different* colors.
3. **Do not implement Phase 2 or Phase 3 features.** No symbol table, no type
   checker, no CFG, no completion. Build the *hooks* for them (see
   `project/04-future-phases.md`), never the features.
4. **Never credit yourself in a commit.** No `Co-Authored-By:` trailer, no
   "Generated with", no AI attribution anywhere in commit messages, code comments,
   file headers, or documentation. Commits are authored by the repo's configured
   git user, full stop.
5. **Every unit of work ends in a green test run and a commit.** See
   `skills/git-workflow/SKILL.md`.
6. **Core must never import from a language module.** `src/clens/core/**` may not
   contain the string `languages.` or any C-specific token name. This boundary is
   what makes the multi-language bonus cheap later; it is checked by a test.
7. **1-based lines, 1-based columns.** Everywhere. Offsets are 0-based. See
   `project/01-phase1-requirements.md` §R1.1.

## 2. Where things live

| I need... | Read |
|---|---|
| What Phase 1 must deliver, in checkable detail | `project/01-phase1-requirements.md` |
| Why a design choice was made (before changing it) | `project/02-decisions.md` |
| Which C features are in and out of scope | `project/03-c-subset.md` |
| Why an odd-looking hook exists | `project/04-future-phases.md` |
| Non-code deliverables (grammar doc, README, defense) | `project/05-deliverables.md` |
| What to do next, in order | `tasks/phase1-plan.md` |
| How to build one specific component | `skills/<name>/SKILL.md` |
| Whether Phase 1 is finished | `checklists/phase1-acceptance.md` |
| Test inputs from the course document | `fixtures/` |

## 3. Working loop

For each task in `tasks/phase1-plan.md`:

1. Read the task. Read the skill file it names. Read the requirement IDs it names.
2. Check `../pycparser/` for reference material if the skill says to
   (see `skills/pycparser-reference/SKILL.md` — read it before you look, there are
   traps in that codebase).
3. Write the implementation.
4. Write tests. Run `pytest`. Iterate until green.
5. Run `ruff check . && ruff format --check .`.
6. Commit (implementation and its tests may be one commit or two — see the git skill).
7. Tick the task off in `tasks/phase1-plan.md` and commit that too.

Do not batch several tasks into one commit. The project requires a traceable,
granular history.

## 4. Style

- Python 3.11+. Type hints on every public function. `@dataclass(slots=True)` for
  data-carrying types.
- The core library has **zero runtime dependencies**. Dev dependencies (pytest,
  ruff) are fine. If you think you need a runtime dependency, stop and ask.
- Docstrings on every public class and function: what it does, and the requirement
  ID it satisfies where one applies.
- Module-level docstring in every file naming that file's responsibility.
- No global mutable state. The course document calls this out explicitly.
- Prefer many small pure functions over long methods. Every later phase re-walks
  these structures; make them boring and inspectable.

## 5. When you are unsure

If a requirement is ambiguous, if two requirements conflict, or if a decision in
`project/02-decisions.md` looks wrong given what you now know:

**Stop and ask the user.** Do not guess and do not silently redesign. Write the
question down, state the options, state which one you would pick and why.

Exception: obvious typos, formatting, and local naming choices — just fix those.

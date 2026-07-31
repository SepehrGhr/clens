# .agents — agent working environment

Everything an agent needs to build this project without re-reading the course PDF.

**Phase 1: complete.** **Phase 2: current scope.**

## Start here

1. `AGENTS.md` — master rules. Read every session.
2. `project/07-phase1-interfaces.md` — the real Phase 1 API surface. Read before
   writing any Phase 2 code; it prevents guessing at names.
3. `tasks/phase2-plan.md` — what to do next, in order.
4. The skill file the task names.

## Contents

```
AGENTS.md                          master rules and hard constraints
project/
  00-overview.md                   what we're building; repo layout
  01-phase1-requirements.md        Phase 1 requirements (R1.1 ...)      [reference]
  02-decisions.md                  decisions D1-D14                     [reference]
  03-c-subset.md                   which C features are in and out
  04-future-phases.md              Phase 3 hooks — do not remove them
  05-deliverables.md               Phase 1 graded documents             [reference]
  06-phase2-requirements.md        Phase 2 requirements (S1.1 ...)      <- current
  07-phase1-interfaces.md          the REAL Phase 1 API surface         <- read first
  08-phase2-decisions.md           decisions D15-D24                    <- current
  09-phase2-deliverables.md        Phase 2 graded documents             <- current
tasks/
  phase1-plan.md                   completed                            [reference]
  phase2-plan.md                   ordered task list                    <- current
skills/
  type-system/                     Type hierarchy, conversions, checking
  symbol-table/                    Symbol, Scope, cursor queries
  name-resolution/                 two-pass resolution, shadowing
  completion-engine/               contexts, ranking, hover
  web-ui/                          the interactive server and front end
  diagnostics/                     one Diagnostic type, the thirteen rows
  lexer/ parser/ ast-and-visitors/ highlighter/     Phase 1             [reference]
  testing/ git-workflow/ devops/ docs-deliverables/ pycparser-reference/
checklists/
  phase1-acceptance.md             regression gate — must stay green
  phase2-acceptance.md             the done gate                        <- current
fixtures/
  valid/ lexical-errors/ syntax-errors/ semantic-errors/ golden/
```

## Using the skills with Claude Code

Standard SKILL.md format. To have them auto-trigger:

```bash
mkdir -p .claude && ln -s ../.agents/skills .claude/skills
```

## Reference clone

`../pycparser` sits beside this repo. `skills/pycparser-reference/SKILL.md` explains
what is safe to take and how it will mislead you. Note that pycparser does **no**
semantic analysis at all — it has no symbol table and no type checker, so it is of
much less use in Phase 2 than it was in Phase 1.

## Keeping this current

When a decision changes, update the decisions file in the same commit. When an
interface changes, update `07-phase1-interfaces.md` in the same commit. Stale agent
docs are worse than none.

# .agents — agent working environment

Everything an agent needs to build this project without re-reading the course PDF.

**Phases 1 and 2: complete.** **Phase 3: current scope.**

## Start here

1. `AGENTS.md` — master rules. Read every session.
2. `project/10-phase2-interfaces.md` — the real Phase 2 API surface. Read before
   writing any Phase 3 code.
3. `tasks/phase3-plan.md` — what to do next, in order.
4. The skill file the task names.

## Contents

```
AGENTS.md                          master rules and hard constraints
project/
  00-overview.md                   what we're building; repo layout
  01-phase1-requirements.md        R1.1 ...                       [reference]
  02-decisions.md                  D1-D14                          [reference]
  03-c-subset.md                   which C features are in scope
  04-future-phases.md              post-project future work
  05-deliverables.md               Phase 1 documents               [reference]
  06-phase2-requirements.md        S1.1 ...                        [reference]
  07-phase1-interfaces.md          Phase 1 API surface
  08-phase2-decisions.md           D15-D24                         [reference]
  09-phase2-deliverables.md        Phase 2 documents               [reference]
  10-phase2-interfaces.md          Phase 2 API surface            <- read first
  11-phase3-requirements.md        A1.1 ...                       <- current
  12-phase3-decisions.md           D25-D32                        <- current
tasks/
  phase1-plan.md  phase2-plan.md   completed                      [reference]
  phase3-plan.md                   ordered task list              <- current
skills/
  cfg/                             CFG construction and SVG rendering
  dataflow/                        generic solver, three analyses
  call-graph/                      construction and the seven queries
  navigation/                      goto-def, find-refs, JSON shape
  refactoring/                     safe rename, dead code
  bonus-docs/                      docs/bonus/ and docs/future-work.md
  lexer/ parser/ ast-and-visitors/ highlighter/                   [reference]
  type-system/ symbol-table/ name-resolution/ completion-engine/  [reference]
  web-ui/ diagnostics/                                            [reference]
  testing/ git-workflow/ devops/ docs-deliverables/ pycparser-reference/
checklists/
  phase1-acceptance.md             regression gate
  phase2-acceptance.md             regression gate
  phase3-acceptance.md             the done gate                  <- current
fixtures/
  valid/ lexical-errors/ syntax-errors/ semantic-errors/ analysis/ golden/
```

## Using the skills with Claude Code

```bash
mkdir -p .claude && ln -s ../.agents/skills .claude/skills
```

## Reference clone

`../pycparser` — see `skills/pycparser-reference/SKILL.md`. Note it has no CFG, no
call graph, and no data-flow analysis, so it is of essentially no use in Phase 3.

## Keeping this current

When a decision changes, update the decisions file in the same commit. When an
interface changes, update the matching `*-interfaces.md` in the same commit.

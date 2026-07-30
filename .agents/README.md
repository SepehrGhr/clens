# .agents — agent working environment

Everything an agent needs to build **Phase 1** of this project without re-reading
the course PDF. Phase 2 and 3 environments get added later.

## Start here

1. `AGENTS.md` — master rules. Read every session.
2. `tasks/phase1-plan.md` — what to do next, in order.
3. The skill file the task names.

## Contents

```
AGENTS.md                       master rules and hard constraints
project/
  00-overview.md                what we're building; target repo layout
  01-phase1-requirements.md     every Phase 1 requirement, with IDs (R1.1 ...)
  02-decisions.md               settled decisions (D1 ... D14) and rejected options
  03-c-subset.md                exactly which C features are in and out
  04-future-phases.md           hooks Phase 2/3 depend on — do not remove them
  05-deliverables.md            the graded written documents
tasks/
  phase1-plan.md                ordered task list with commit points
skills/
  lexer/                        scanning, maximal munch, error recovery
  parser/                       recursive descent, panic-mode recovery
  ast-and-visitors/             node design, spans, NodeVisitor
  highlighter/                  AST-driven categories, ANSI/HTML rendering
  diagnostics/                  the one LSP-shaped Diagnostic type
  testing/                      strategy, golden tests, 80% coverage gate
  git-workflow/                 commit format, cadence, hard rules
  devops/                       pyproject, Docker, CI, Pages
  docs-deliverables/            how to write the graded documents
  pycparser-reference/          using ../pycparser safely — READ BEFORE OPENING IT
checklists/
  phase1-acceptance.md          the done gate
fixtures/
  valid/ lexical-errors/ syntax-errors/ golden/
```

## Using the skills with Claude Code

The `skills/` folders use the standard SKILL.md format (YAML frontmatter with
`name` and `description`, then markdown). To have them auto-trigger:

```bash
mkdir -p .claude && ln -s ../.agents/skills .claude/skills
```

Without that they still work — `AGENTS.md` and the task plan point at them
explicitly.

## Reference clone

`../pycparser` sits beside this repo. `skills/pycparser-reference/SKILL.md`
explains what is safe to take from it and the three specific ways it will mislead
you. Read that before opening it.

## Keeping this current

When a decision changes, update `project/02-decisions.md` in the same commit.
When the subset changes, update `project/03-c-subset.md`, `docs/grammar.ebnf`, and
the parser together. Stale agent docs are worse than none.

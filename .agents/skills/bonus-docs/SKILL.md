---
name: bonus-docs
description: How to write the per-bonus documentation files in docs/bonus/ and docs/future-work.md for c-lens. Every bonus feature gets its own document with goal, motivation, implementation, and how to see it working. Use when writing anything under docs/bonus/ or docs/future-work.md.
---

# Bonus documentation

Requirements: A9, A10. Decisions: D29, D30.

## Why these exist

Bonus credit is only awarded for what a grader can find and verify. A feature that
exists but is undocumented is invisible. These files are also the natural answer to
"so what extra did you do?" at the defense — one index page, one file per item.

## The four-section template

Every file in `docs/bonus/` uses the same structure. Consistency across files is
itself a signal.

```markdown
# <Bonus name>

## Goal
What this is, and which course-document bonus item it satisfies. Quote the
requirement so a grader can match it without re-reading the brief.

## Motivation
Why it was worth doing *in this project*. Connect it to a course concept where
there is one — that is what turns a checkbox into a demonstration of understanding.

## Implementation
How it works. Key design decisions and why. File pointers (`src/clens/...`) so a
grader can go look. Mention what was deliberately *not* done, and why.

## Seeing it work
Exact commands, copy-pasteable, with expected output. Screenshots where visual.
Someone who has never seen the repo must be able to follow this.
```

## Files needed

`docs/bonus/README.md` — index with a status table: bonus, status
(delivered / deferred), link, and the course-document section it maps to.

Retroactive write-ups for what is already built:

| File | Covers |
|---|---|
| `docker.md` | Dockerfile, single `docker run`, non-root user, layer caching |
| `ci-cd.md` | GitHub Actions, lint + tests + coverage gate, Pages publishing of highlighted HTML, the README badge |
| `test-suite-coverage.md` | Per-module suite, valid and erroneous programs, exact expected outputs, the coverage figure |
| `web-ui.md` | The interactive interface — and note it also satisfies the §6.6 Phase 3 interface requirement, which is worth stating plainly |

Plus new Phase 3 items:

| File | Covers |
|---|---|
| `reaching-definitions.md` | The bonus analysis, and how it reuses the generic solver |

Write each in the commit that delivers the feature where possible; retroactive ones
in Stage 6.

## `docs/future-work.md` (A10, D30)

One document, one section per deferred item, each with: **what it is**, **why
deferred**, **rough effort**, **where it plugs in**.

Items:

- **Dominator and post-dominator trees** — node `d` dominates `n` iff every path
  from ENTRY to `n` passes through `d`. The course document names Lengauer-Tarjan;
  the naive iterative algorithm is ~20 lines and gives identical results on graphs
  this size. Post-dominators are the same algorithm on the reversed CFG. Plugs into
  `core/cfg.py`. Prerequisite for SSA.
- **Dominance frontier and SSA form** — frontier is ~15 lines once dominators exist;
  φ-placement via Cytron et al. and variable renaming is the real work. SSA is the
  IR used by LLVM and GCC. The highest-value remaining bonus and the one most likely
  to overrun. Plugs in after dominators.
- **Java as a second language** — `core/` never imports `languages/`, so the
  boundary is ready. But a second language now needs lexer rules, grammar, parser,
  AST, type rules, scope rules, and a class-scope model with virtual dispatch for
  the call graph. It was the cheapest bonus in Phase 1 and is now the most
  expensive. Plugs in as `src/clens/languages/java/`.
- **LSP server** — `queries.py` is deliberately adapter-free, so this is a thin
  layer over existing queries plus `pygls`. Deferred because the web UI already
  satisfies the interface requirement and `pygls` would break the
  zero-runtime-dependency property. Plugs in as `src/clens/lsp/`.
- **Incremental re-parsing** — re-parse only the modified region and its syntactic
  dependents, the core Tree-sitter technique. Deferred per D21: full re-analysis per
  keystroke is fast enough at this file size, and correctness beat latency.
- **C preprocessor pass** — `#define`, `#include`, `#ifdef`, with error locations
  mapped back to pre-expansion positions. Currently directives are tokenized and
  never expanded. Plugs in before the lexer.
- **Multi-file support** — navigation already carries `file` fields throughout.
  Needs a translation-unit model and cross-file symbol resolution.

Frame this as deliberate scoping with a plan, not as apology. Deferred-with-a-plan
demonstrates architectural command; an unexplained absence looks like an oversight.

## Definition of done

- [ ] `docs/bonus/README.md` indexes every bonus with status and mapping
- [ ] Every delivered bonus has a four-section file
- [ ] Every command in a "Seeing it work" section actually runs
- [ ] `docs/future-work.md` covers all seven deferred items with plug-in points
- [ ] Both linked from the README

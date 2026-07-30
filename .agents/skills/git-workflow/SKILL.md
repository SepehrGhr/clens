---
name: git-workflow
description: Commit discipline for c-lens — conventional commit format, when to commit, what must never appear in a commit message, and the graded history requirements. Use before every commit and whenever asked about branching, history, or repository hygiene.
---

# Git workflow

The commit history is **graded**. The course document requires regular, descriptive
commits, at least 20 meaningful ones distributed across both team members, and a
traceable history.

## Hard rules

1. **Never credit yourself.** No `Co-Authored-By:` trailer. No "Generated with", no
   "AI-assisted", no tool name, in commit messages, code comments, file headers,
   docs, or the README. Commits are authored by whatever `user.name` / `user.email`
   git is configured with. Do not touch that configuration.
2. **Never rewrite published history.** No `--amend` on a pushed commit, no
   `push --force`, no rebase of anything already on the remote. A clean-looking
   history that was manufactured is worse than a messy real one.
3. **Never commit red tests.** Run `pytest` before every commit. If it fails, fix it
   or do not commit.
4. **One logical unit per commit.** Do not batch three tasks together to save time —
   granularity is the graded property here.
5. **Never commit generated artifacts**: `__pycache__`, `.pytest_cache`,
   `htmlcov/`, `dist/`, `*.egg-info`, `.coverage`, or generated HTML output.

## Format

Conventional commits, imperative mood, ≤72-character subject:

```
feat(lexer): add maximal-munch handling for multi-char operators
fix(parser): stop consuming '}' during panic-mode recovery
test(lexer): cover unterminated string and block comment recovery
docs(grammar): add struct declarations to EBNF
chore(ci): add coverage gate at 80%
```

Scopes in use: `core`, `lexer`, `parser`, `ast`, `highlight`, `render`, `cli`,
`docs`, `ci`, `docker`, `tests`.

Add a body when the *why* is not obvious from the subject — especially for anything
that looks odd but is deliberate:

```
feat(lexer): retain whitespace and comment tokens as trivia

The course document says whitespace is usually discarded. We keep it so the
highlighter can reproduce the source byte-for-byte and so Phase 3 hover can
attach doc comments to declarations. Parser consumes a filtered view.
```

That body is exactly the kind of thing that is useful at the defense.

## Commit cadence

Per task in `tasks/phase1-plan.md`:

- Implementation → run tests → commit.
- Tests for it (if separate) → run → commit.
- Docs updated by the change → commit with the change, not later.
- Tick the task box in the plan → include in the last commit of that task.

Rough target: **35–45 commits** for Phase 1.

## Authorship across two members

The requirement is ≥20 meaningful commits **distributed across both members**. That
distribution has to be real — each member commits the work they did, under their own
git identity, on the modules they own per `docs/team.md`. Do not attempt to
manufacture a distribution by changing author metadata; a history where one person's
commits all landed in a single burst is visible and is worse than the alternative.

Practical arrangement: each member runs their own sessions for the modules they own.
This also directly serves the defense requirement that each member be able to explain
their partner's components — you have to actually read the other half.

## Branching

`main` plus short-lived feature branches (`feat/lexer-core`) is fine, as is
committing straight to `main` for a two-person project. Pick one, say which in
`docs/team.md`, be consistent. If using branches, merge with `--no-ff` so the
feature grouping stays visible in the history.

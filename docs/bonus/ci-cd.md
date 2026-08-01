# CI/CD

## Goal

Automate lint, test, and coverage checks on every push and pull request,
and publish a live demo of the highlighter to GitHub Pages on every push
to `main`. Satisfies the course document's CI/CD bonus item.

## Motivation

A course project with no CI is graded on "does it work on my machine right
now" — the same failure mode the tool itself is built to avoid for C
source (`.agents/AGENTS.md` rule 1: never crash). CI turns "the tests pass"
into a fact anyone can check without cloning and running anything
locally, and the coverage gate turns the 80% target (`docs/testing.md`,
`.agents/skills/devops`) from an aspiration into an enforced number: a PR
that drops coverage below 80% fails the build, full stop.

## Implementation

`.github/workflows/ci.yml`, two jobs:

**`test`** — matrix over Python 3.11 and 3.12 (the two versions
`pyproject.toml` claims to support):
1. `pip install -e . -r requirements-dev.txt`
2. `ruff check .` and `ruff format --check .` — lint must pass before tests
   run at all.
3. `pytest --cov=src/clens --cov-report=xml --cov-report=term-missing --cov-fail-under=80`
   — `--cov-fail-under=80` is what makes coverage a *gate*, not just a
   report; the job fails if the suite covers less than 80% of
   `src/clens`.
4. Upload the `coverage.xml` as a build artifact per Python version, so a
   reviewer can inspect exactly which lines are uncovered without
   re-running the suite.

**`publish-pages`** — runs only `if: github.ref == 'refs/heads/main' &&
github.event_name == 'push'` (never on a PR, never on a feature branch),
and only `needs: test` (so a broken build is never published):
1. Install `clens` (the real package, not editable-dev extras).
2. `clens highlight tests/fixtures/valid/factorial.c --format html -o site/index.html`
   — the canonical fixture, self-contained HTML, no JS.
3. `actions/upload-pages-artifact` + `actions/deploy-pages` publish
   `site/` to the repo's GitHub Pages environment.

The README's CI badge
(`![CI](https://github.com/SepehrGhr/clens/actions/workflows/ci.yml/badge.svg)`)
reads this workflow's latest status on `main` directly from GitHub, no
separate configuration.

## Seeing it work

Locally, run the same steps CI runs:

```bash
ruff check .
ruff format --check .
pytest --cov=src/clens --cov-report=term-missing --cov-fail-under=80
```

On GitHub: open the repo's **Actions** tab, or look at the badge at the
top of the README — green means the last push to `main` passed lint,
both Python versions' test suites, and the 80% coverage gate.

The published demo (after a push to `main`) is the site under the repo's
**Settings → Pages** URL, showing `factorial.c` fully syntax-highlighted
as static HTML — no server, no JavaScript, exactly what
`clens highlight --format html` produces locally.

---
name: devops
description: Packaging, Docker, and GitHub Actions CI for c-lens — pyproject plus requirements.txt, the coverage gate, and the GitHub Pages publish that the course lists as a bonus. Use when touching pyproject.toml, Dockerfile, .github/workflows/, or the README badge.
---

# Packaging, Docker, CI

The course lists Docker, CI/CD, and an 80%-coverage test suite as bonus credit, and
specifically requires **a passing CI badge in the README** for the CI bonus. Build
all three during Phase 1 — they are near-free now and get skipped when rushed.

## Packaging

Both files, deliberately:

- `pyproject.toml` — real metadata, `src/` layout, console script
  `clens = clens.cli.main:main`, plus `[tool.ruff]`, `[tool.pytest.ini_options]`,
  and `[tool.coverage]` config. Requires Python `>=3.11`.
- `requirements.txt` — a comment stating the core has **zero runtime dependencies**.
  An empty-but-explained file is a better signal than a missing one.
- `requirements-dev.txt` — `pytest`, `pytest-cov`, `ruff`.

Verify `pip install -e .` then `clens --help` works from a clean venv before
committing.

## Dockerfile

Requirement: the system runs with a single `docker run`.

- `python:3.12-slim` base
- Copy dependency manifests first, then source (layer caching)
- `pip install --no-cache-dir .`
- Non-root user
- `ENTRYPOINT ["clens"]`, `CMD ["--help"]`
- `.dockerignore` covering `.git`, `__pycache__`, `tests`, `htmlcov`, `.venv`

Must actually work:

```bash
docker build -t c-lens .
docker run --rm c-lens --help
docker run --rm -v "$PWD/samples:/work" c-lens highlight /work/factorial.c
```

Put those exact commands in the README.

## CI (.github/workflows/ci.yml)

On push and pull request:

1. Checkout; set up Python 3.11 and 3.12 (matrix)
2. `pip install -e . -r requirements-dev.txt`
3. `ruff check .` and `ruff format --check .`
4. `pytest --cov=src/clens --cov-report=xml --cov-report=term-missing --cov-fail-under=80`
5. Upload the coverage report as an artifact

Second job, on `main` only:

6. Run `clens highlight samples/factorial.c --format html -o site/index.html`
7. Publish `site/` to GitHub Pages

That publish step is explicitly part of the bonus description — generate highlighted
HTML for a canonical test file and publish it.

Badge in `README.md`:

```markdown
![CI](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)
```

## Order of operations

Add CI in Stage 0 with a single trivial test so the badge is green from the first
push, then let it tighten as the suite grows. Adding CI at the end means debugging
the workflow and the code at the same time.

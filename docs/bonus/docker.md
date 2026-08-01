# Docker packaging

## Goal

Package `clens` as a container image so it runs with zero local Python
setup — one `docker build`, one `docker run`. This satisfies the course
document's packaging bonus item.

## Motivation

The install instructions in the README already work (`pip install -e .`
in a venv), but a container removes even that dependency: no venv, no
system Python version to match, no `pip` conflicts with other projects
on the grader's machine. It is also the standard way a CLI tool gets
distributed and evaluated outside its own repo, which is the situation a
grader is actually in.

## Implementation

`Dockerfile` (repo root):

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml requirements.txt ./
COPY src/ ./src/
COPY README.md ./

RUN pip install --no-cache-dir .

RUN useradd --create-home --shell /bin/false clens
USER clens

ENTRYPOINT ["clens"]
CMD ["--help"]
```

Key decisions:

- **`python:3.12-slim`**, not `-alpine`: slim is glibc-based so
  `pip install` never needs to compile anything from source (clens has
  zero runtime dependencies per D-series decisions in `.agents/`, but the
  build tooling itself still benefits from a standard glibc base).
- **Layer caching**: `pyproject.toml` and `requirements.txt` are copied
  and installed *before* `src/`, so editing application code doesn't
  invalidate the dependency-install layer on a rebuild.
- **Non-root user**: the image creates and switches to an unprivileged
  `clens` user before running anything. The tool never needs root, so it
  never runs as root.
- **`ENTRYPOINT` + default `CMD`**: `docker run --rm clens` alone prints
  `--help` (a sane default), while `docker run --rm clens <file>.c ast`
  etc. passes straight through to the real CLI without repeating the
  binary name.
- **No dev dependencies in the image**: `requirements-dev.txt` (pytest,
  ruff, coverage) is never copied in — the image is a runtime artifact,
  not a dev environment.

## Seeing it work

```bash
docker build -t clens .
docker run --rm clens --help
docker run --rm -v "$(pwd)/tests/fixtures/valid:/data" clens highlight /data/factorial.c
```

Confirm the non-root user (overriding the entrypoint, since `clens` itself
has no `id`/`whoami` subcommand):

```bash
docker run --rm --entrypoint id clens
# uid=1000(clens) gid=1000(clens) groups=1000(clens)
```

Confirm layer caching: touch a file under `src/` and rebuild — only the
final `COPY src/` layer and everything after it re-executes; the
`pip install` layer from `pyproject.toml`/`requirements.txt` is reused
from cache.

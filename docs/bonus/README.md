# Bonus features

Every bonus item delivered in this project, with a one-file writeup each
(goal, motivation, implementation, and how to see it working). Deferred
items — the ones we chose not to build and why — are in
[`../future-work.md`](../future-work.md), not here.

| Bonus | Status | Course-document section | Doc |
|---|---|---|---|
| Docker packaging | Delivered | §7 Bonus — packaging | [docker.md](docker.md) |
| CI/CD (lint + test + coverage gate + Pages publish) | Delivered | §7 Bonus — CI/CD | [ci-cd.md](ci-cd.md) |
| Test suite depth and coverage gate | Delivered | §7 Bonus — testing | [test-suite-coverage.md](test-suite-coverage.md) |
| Interactive web UI | Delivered | §7 Bonus — interface (also satisfies A7.1/§6.6's Phase 3 interface requirement) | [web-ui.md](web-ui.md) |
| Reaching definitions | Delivered | §7 Bonus — extra data-flow analysis (D29) | [reaching-definitions.md](reaching-definitions.md) |

## How to verify

Each doc below has its own "Seeing it work" section with copy-pasteable
commands. As a single entry point:

```bash
docker build -t clens . && docker run --rm clens --help   # docker.md
clens serve --port 8000                                    # web-ui.md
pytest --cov=src/clens --cov-report=term-missing            # test-suite-coverage.md
pytest tests/unit/test_analyses.py -k reaching_definitions -v  # reaching-definitions.md
```

CI/CD (`ci-cd.md`) runs on every push; see the badge at the top of the
README or the Actions tab on GitHub.

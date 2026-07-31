# Testing

Step-by-step instructions to set up, run, and reproduce every test in this
repository. Written for someone who has never seen this repo before.

## 1. Prerequisites

- Python 3.11 or newer
- git
- Docker (optional, only needed for §10)

## 2. Clone and set up a virtual environment

```bash
git clone <repo-url> clens
cd clens
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

## 3. Install

```bash
pip install -e . -r requirements-dev.txt
```

This installs the `clens` console script (editable) plus `pytest`,
`pytest-cov`, and `ruff`.

## 4. Run the full test suite

```bash
pytest
```

Expect every test to pass, none skipped or expected-to-fail.

## 5. Run with coverage (the CI gate)

```bash
pytest --cov=src/clens --cov-report=term-missing --cov-fail-under=80
```

Coverage must be ≥80%; CI enforces this on every push. A per-file breakdown
prints to the terminal; add `--cov-report=html` for a browsable report in
`htmlcov/index.html`.

## 6. Lint and format check (also enforced by CI)

```bash
ruff check .
ruff format --check .
```

## 7. Run a single test file or test

```bash
pytest tests/unit/test_lexer_c.py
pytest tests/unit/test_lexer_c.py::test_golden_invalid_char_at_1_6_then_clean_line
```

## 8. Regenerate golden snapshots

Only after an intentional rendering change — always eyeball the diff before
committing:

```bash
pytest tests/golden/test_golden.py --regen-golden
git diff tests/golden/expected/
```

## 9. Try the CLI directly

```bash
clens tokens tests/fixtures/valid/factorial.c
clens ast tests/fixtures/valid/factorial.c
clens highlight tests/fixtures/valid/factorial.c                       # ANSI, to your terminal
clens highlight tests/fixtures/valid/factorial.c --format html -o out.html
clens check tests/fixtures/syntax-errors/missing_paren.c; echo "exit: $?"
```

Open `out.html` in a browser — it is a self-contained file, no server or
JavaScript needed. Any subcommand also accepts `--json` for machine-readable
output.

## 10. Docker

```bash
docker build -t clens .
docker run --rm clens --help
docker run --rm -v "$PWD/tests/fixtures/valid:/work" clens highlight /work/factorial.c
```

## 11. What the test suite covers, and where

| Area | Test files |
|---|---|
| Core primitives (`SourceFile`, `Token`, `Diagnostic`) | `test_source.py`, `test_token.py`, `test_diagnostics.py` |
| Lexer engine + C token rules | `test_lexer_base.py`, `test_lexer_c.py` |
| AST base types, C node inventory, visitor, printer | `test_ast_nodes.py`, `test_ast_nodes_c.py`, `test_visitor.py`, `test_ast_printer.py` |
| Parser: expressions, statements, declarations, recovery, robustness | `test_parser_base.py`, `test_parser_expressions.py`, `test_parser_statements.py`, `test_parser_declarations.py`, `test_parser_recovery.py`, `test_parser_robustness.py` |
| Highlighter: categories, theme, two-pass upgrades, R5.1 acceptance | `test_highlight.py`, `test_theme.py`, `test_highlighter_c.py`, `test_highlighter_acceptance.py` |
| Renderers: ANSI, HTML, round-trip fidelity | `test_render_ansi.py`, `test_render_html.py` |
| CLI: all four subcommands, exit codes, robustness | `test_cli.py` |
| Layering guard (`core/` never imports `languages/`) | `test_layering.py` |
| Golden snapshots (course-document AST/tokens, rendered `factorial.c`) | `tests/golden/test_golden.py`, `test_ast_printer.py` |

All tests live under `tests/unit/` except the golden snapshot tests, which
live under `tests/golden/`. `tests/fixtures/` mirrors `.agents/fixtures/` —
valid programs, lexical-error programs, syntax-error programs, and the
course-document golden expectations.

## 12. Requirement traceability

Every requirement ID from `.agents/project/01-phase1-requirements.md` (`R1.1`,
`R3.4`, ...) appears in at least one test's docstring or name:

```bash
grep -rn "R3\.4" tests/
```

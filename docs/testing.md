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

## 9b. Try the Phase 2 commands

```bash
clens symbols tests/fixtures/valid/factorial.c                          # scope tree
clens symbols tests/fixtures/valid/factorial.c --json
clens complete tests/fixtures/valid/member_completion.c 14 7            # p.| -> x, y
clens hover tests/fixtures/valid/doc_comments.c 5 6                     # factorial's signature + doc comment
```

`complete`/`hover` take a 1-based `<line> <col>`, same convention as an
editor's cursor position. All four accept `--json` too.

## 9c. Try the web UI

```bash
clens serve --port 8000
```

Open `http://127.0.0.1:8000/` — a `<textarea>` editor next to the live
AST-highlighted pane, re-analyzed on every keystroke (~300ms debounced).
Type `.` or `->` (or press Ctrl+Space anywhere) for a completion popup;
click a token in the highlighted pane for a hover card; click a row in the
Diagnostics panel to jump the editor to it. No build step — `web/static/`
is served as-is. See the README's "Web UI" section for screenshots.

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
| **Phase 2** — types, symbols, scopes | `test_types.py`, `test_symbols.py`, `test_scopes.py`, `test_semantic_model.py` |
| Name resolution: two-pass, prototypes, diagnostics, `ErrorStmt` robustness | `test_resolver_pass1.py`, `test_resolver_pass2.py`, `test_resolver_prototypes.py`, `test_resolver_diagnostics.py`, `test_resolver_stage3_sweep.py` |
| Type checking: expressions, members/calls, assignment/return, the S4.7 golden four, no-cascade | `test_typecheck.py`, `test_typecheck_member_and_calls.py`, `test_typecheck_assignment_and_return.py`, `test_golden_four.py`, `test_no_cascade.py` |
| Crude use-before-init / unused-variable checks | `test_usage.py` |
| All thirteen S6.1 diagnostic rows, one test each | `test_diagnostics_thirteen_rows.py` |
| Completion and hover: context detection, member/general/argument completion, ranking, hover | `test_queries_context.py`, `test_queries_completion_member.py`, `test_queries_completion_general.py`, `test_queries_ranking.py`, `test_queries_hover.py` |
| Web UI: interactive renderer, HTTP backend (handler-level, no socket, plus one live smoke test) | `test_web_renderer.py`, `test_web_server.py` |

All tests live under `tests/unit/` except the golden snapshot tests, which
live under `tests/golden/`. `tests/fixtures/` mirrors `.agents/fixtures/` —
valid programs, lexical-error programs, syntax-error programs, semantic-error
programs, and the course-document golden expectations.

## 12. Requirement traceability

Every requirement ID from `.agents/project/01-phase1-requirements.md` (`R1.1`,
`R3.4`, ...) and `.agents/project/06-phase2-requirements.md` (`S1.1`, `S4.7`,
`S6.1`, ...) appears in at least one test's docstring or name:

```bash
grep -rn "R3\.4" tests/
grep -rn "S4\.7" tests/
```

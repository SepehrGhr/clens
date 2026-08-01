# Test suite depth and coverage gate

## Goal

A test suite organized per module, exercising both valid and erroneous C
programs against exact expected outputs, with an enforced coverage floor.
Satisfies the course document's testing bonus item.

## Motivation

A tool whose entire premise is "never crash, always produce a diagnostic"
(`.agents/AGENTS.md` rule 1) needs its error paths tested at least as
thoroughly as its happy paths — a lexer test suite with no invalid-input
cases would leave the recovery behavior (unterminated strings, `INVALID`
tokens, panic-mode sync) as the one part of the project nobody actually
verified. Golden/snapshot tests additionally pin down exact output shapes
(the §6.1 CFG text form, the §6.3 navigation JSON, the `factorial` AST
dump) so a refactor that silently changes formatting is caught instead of
discovered by a grader.

## Implementation

- **65 test files under `tests/unit/` and `tests/golden/`**, one file (or
  a small cluster) per module: `test_lexer_base.py`/`test_lexer_c.py`,
  `test_parser_*.py` (declarations, expressions, statements, recovery,
  robustness split out separately), `test_resolver_*.py` per resolver
  pass, `test_typecheck_*.py`, `test_cfg_builder.py`,
  `test_dataflow_solver.py` + `test_analyses.py`, `test_call_graph.py`,
  `test_navigation.py`, `test_rename.py`, `test_dead_code.py`,
  `test_render_svg.py`, `test_web_server.py`, and so on — the module
  layout under `src/clens/` and the test layout under `tests/unit/`
  mirror each other.
- **32 fixture files under `tests/fixtures/`**, split into `valid/`,
  `lexical-errors/`, `syntax-errors/`, `semantic-errors/`, and `golden/` —
  every category of diagnostic the tool can raise has at least one C
  program that triggers it, checked against an exact expected
  diagnostic (code, severity, location), not just "an error was
  raised."
- **Golden-file comparison** (`tests/conftest.py`'s `golden` fixture):
  compares actual output against a checked-in expected file, or
  regenerates it with `pytest --regen-golden` after a deliberate,
  reviewed output-format change — so format changes are a visible diff in
  the PR, not a silent drift.
- **Requirement traceability**: tests reference the course document's
  requirement IDs in names/docstrings where relevant (e.g. `test_analyses.py`
  ties cases to A2.1–A2.3, `test_rename.py`'s golden test is A5.3) so a
  grader can map "is A5.3 tested?" to an actual test without guessing.
- **The 80% coverage gate**: `pytest --cov=src/clens --cov-fail-under=80`,
  enforced identically in CI (`docs/bonus/ci-cd.md`) and locally
  (`docs/testing.md`).

## Seeing it work

```bash
pytest                                                    # full suite, ~700+ tests
pytest --cov=src/clens --cov-report=term-missing --cov-fail-under=80
pytest --regen-golden                                     # regenerate golden files after a reviewed format change
pytest tests/unit/test_analyses.py -k reaching_definitions -v
```

Per-file coverage breakdown is printed by `--cov-report=term-missing`;
add `--cov-report=html` for a browsable `htmlcov/index.html`. See
`docs/testing.md` for the full command reference, including how to run a
single test or a single fixture category.

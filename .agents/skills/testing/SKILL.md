---
name: testing
description: Testing strategy for c-lens — unit tests per module, golden/snapshot tests, requirement-ID traceability, robustness fuzzing, and reaching the 80% coverage bonus gate. Use after writing any implementation code, and whenever coverage, fixtures, or test organization comes up.
---

# Testing

The course document's bonus requires a comprehensive suite covering **every module**,
across **valid and erroneous programs**, where **each test specifies its exact
expected output**, with **≥80% line coverage** and a coverage report.

Write tests as you go. Retrofitting coverage at the end is the single most common way
this bonus gets abandoned.

## Layout

```
tests/
├── conftest.py          # fixture_path(), read_fixture(), lex(), parse() helpers
├── unit/
│   ├── test_source.py
│   ├── test_lexer_*.py
│   ├── test_parser_*.py
│   ├── test_highlighter.py
│   ├── test_render_*.py
│   ├── test_cli.py
│   └── test_layering.py     # core/ must not import languages/
├── golden/
│   ├── test_golden.py       # walks fixtures, diffs against expected/
│   └── expected/
└── fixtures/
    ├── valid/
    ├── lexical-errors/
    └── syntax-errors/
```

Seed `tests/fixtures/` from `.agents/fixtures/`.

## Traceability

Name tests after the requirement they cover, or state it in the docstring:

```python
def test_maximal_munch_le_operator():
    """R1.3 — '<=' scans as one token, not '<' then '='."""
```

At the end of Phase 1 you should be able to grep for every R-ID and find a test.
That grep is also a good slide at the defense.

## Golden / snapshot tests

For token streams, AST dumps, ANSI output, and HTML output: store the expected text
in `tests/golden/expected/` and diff. Cheapest way to satisfy "each test specifies
the exact expected output" and to reach coverage.

Provide a regeneration path (`pytest --regen-golden` via a conftest flag), and
**always eyeball a regenerated file before committing it**. A snapshot test that is
blindly regenerated tests nothing.

## Non-negotiable tests

These map to the rubric and to the ways evaluators will try to break the tool:

- **Round-trip fidelity** (R5.3): strip colors from highlighter output, diff against
  the input, expect zero differences. Run it over every valid fixture.
- **Call-vs-variable** (R5.1): the same identifier used as a call and as a bare
  variable gets different categories. Without this test, R5.1 is not met.
- **Golden positions** (R4.2): the factorial AST matches the course document's
  §4.3.2 locations exactly — `3:12`, `3:16`, `3:26`, `3:30`.
- **Golden lexical error** (R1.5): `int x@ = 5;` → `INVALID('@')` at `1:6`, next
  line lexes clean.
- **Golden syntax recovery** (R3.4): `int x = ;` followed by `int y = 42;` — the
  second one parses.
- **No-crash suite** (R9.5): empty file; whitespace only; comments only; unterminated
  string; unterminated block comment; unbalanced braces; a stray `@`; CRLF line
  endings; no trailing newline; a 1 MB file; random bytes; a nonexistent path; a
  directory passed as a file. Assert diagnostics, assert **no exception**.
- **Truncation fuzz** (R3.5): for each valid fixture, truncate at every Nth token and
  parse. Nothing may raise.
- **Layering** (D12): no file under `src/clens/core/` imports from `languages`.

## Coverage

```bash
pytest --cov=src/clens --cov-report=term-missing --cov-report=html
```

Gate CI at 80%. Close gaps with real tests. Do not use `# pragma: no cover` to hide
untested logic — the honest exceptions are `if TYPE_CHECKING:` blocks and
defensive `raise AssertionError("unreachable")` arms.

## Style

- `pytest` plain functions, `parametrize` for table-driven cases (token categories,
  operator precedence, and error cases are all naturally tabular).
- One assertion concept per test. A failure name should tell you what broke without
  reading the body.
- No network, no clock, no randomness without a fixed seed.

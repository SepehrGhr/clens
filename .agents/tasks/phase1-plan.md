# Phase 1 Task Plan

Work top to bottom. Each task is one or two commits. Tick boxes as you go and
commit the tick with the work.

Target: **35–45 commits** across Phase 1. The course requires ≥20 across the whole
project and both members; overshooting is free.

Legend: `→ skill` = read this skill file first. `→ R#` = requirement IDs this task
must satisfy.

---

## Stage 0 — Scaffold (≈6 commits)

- [x] **T0.1** `git init`, `.gitignore` (Python), `LICENSE`, empty `README.md`.
      → `skills/git-workflow`
- [x] **T0.2** `pyproject.toml` (hatchling or setuptools, `src/` layout, console
      script `clens = clens.cli.main:main`, ruff + pytest config),
      `requirements.txt` (empty / comment: core has zero runtime deps),
      `requirements-dev.txt` (pytest, pytest-cov, ruff). → `skills/devops`
- [x] **T0.3** Package skeleton: `src/clens/` with `core/`, `languages/c/`,
      `render/`, `cli/`, each with `__init__.py` and a module docstring.
- [x] **T0.4** `tests/` skeleton + `conftest.py` with a `fixture_path` helper. One
      trivial passing test so CI is green from the first push.
- [x] **T0.5** `Dockerfile` (slim base, non-root user, `ENTRYPOINT ["clens"]`) +
      `.dockerignore`. Verify `docker build` and `docker run --rm c-lens --help`.
      → `skills/devops`
- [x] **T0.6** `.github/workflows/ci.yml`: install, ruff, pytest with coverage,
      coverage gate at 80%. Badge into `README.md`. → `skills/devops`
      *(Pages publishing comes later in T6.3, once there is HTML to publish.)*

## Stage 1 — Core primitives (≈5 commits)

- [x] **T1.1** `core/source.py`: `SourceFile` — text, filename, line-start index,
      `offset_to_line_col()`, `line_col_to_offset()`, `line_text()`. Handle `\n`,
      `\r\n`, no trailing newline, empty file. Tests first-class here; every
      later position bug traces back to this file. → R1.1
- [x] **T1.2** `core/token.py`: `TokenType` enum, `Token` dataclass, `is_trivia`,
      `Span`. → R1.1, R1.2
- [x] **T1.3** `core/diagnostics.py`: `Severity`, `Diagnostic` (LSP-shaped, full
      start/end range), `DiagnosticCollector` with sorting and JSON export.
      → R1.5, D11
- [x] **T1.4** Tests for T1.1–T1.3 including the CRLF and empty-file edge cases.
- [x] **T1.5** `tests/unit/test_layering.py` — asserts no file under `core/`
      imports from `languages/`. → D12

## Stage 2 — Lexer (≈7 commits)

→ `skills/lexer` before starting.

- [ ] **T2.1** `core/lexer_base.py`: generic master-regex scanner engine, rule
      ordering, position tracking, INVALID emission and single-char recovery.
      Language-agnostic. → R1.3, R1.5
- [ ] **T2.2** `languages/c/keywords.py` + `token_rules.py`: the ordered regex
      table. Cross-check literal regexes against pycparser
      (→ `skills/pycparser-reference`). → R1.2, R1.4
- [ ] **T2.3** `languages/c/lexer.py`: wires the C rules into the engine.
- [ ] **T2.4** Unterminated string and unterminated block comment detection with
      recovery. → R1.6, R1.7
- [ ] **T2.5** Trivia retention + `iter_significant()` view for the parser. → R1.8
- [ ] **T2.6** Lexer tests: one per token category, plus longest-match cases
      (`<=`, `->`, `++`), keyword-vs-identifier, and the `int x@ = 5;` golden case
      asserting `INVALID('@')` at exactly **1:6**. → R1.3–R1.7
- [ ] **T2.7** `docs/lexical-specification.md`. → deliverable D2

## Stage 3 — Grammar and AST (≈5 commits)

→ `skills/ast-and-visitors`.

- [ ] **T3.1** `docs/grammar.ebnf` — full subset, written *before* the parser.
      → R2.1, R2.2
- [ ] **T3.2** `core/ast_nodes.py`: `Node` base with `span`, `Expr`/`Stmt`/`Decl`
      bases, `type_annotation: Type | None = None` on `Expr`. → R4.2, R4.3
- [ ] **T3.3** `languages/c/ast_nodes.py`: one dataclass per production.
      Cross-check the node inventory against pycparser's `_c_ast.cfg`. → R4.1
- [ ] **T3.4** `core/visitor.py`: `NodeVisitor` with `visit_<Type>` dispatch,
      `generic_visit`, and a `walk()` helper. Tested independently. → R4.4
- [ ] **T3.5** AST pretty-printer producing the exact indented shape shown in the
      course document §4.3.2, so `fixtures/golden/factorial_ast.txt` can be
      diffed. → R4.2

## Stage 4 — Parser (≈8 commits)

→ `skills/parser`.

- [ ] **T4.1** `core/parser_base.py`: cursor, `peek/advance/check/match/expect`,
      `at_end`, `synchronize(sync_set)`, diagnostic emission on mismatch. → R3.3
- [ ] **T4.2** Declarations: type specifiers, pointers, function definitions and
      prototypes, parameter lists, variable declarations with multiple declarators.
- [ ] **T4.3** `struct` declarations and struct-typed variables. → subset contract
- [ ] **T4.4** Statements: block, if/else, while, for, return, break, continue,
      expression statement, empty statement.
- [ ] **T4.5** Expressions: full precedence cascade down to primary, including
      postfix chains (`call`, `index`, `.`, `->`, `++`/`--`). Associativity tests
      matter here — `a - b - c` must be `(a - b) - c`.
- [ ] **T4.6** Panic-mode recovery + the two golden error cases from the document
      (`int x = ;` and `if (y > 0 {`), asserting that the *following* declaration
      still parses. → R3.3, R3.4
- [ ] **T4.7** Parser tests: one per production, plus a fuzz-ish robustness test
      that feeds truncated prefixes of every valid fixture and asserts no
      exception escapes. → R3.5, R9.5
- [ ] **T4.8** `docs/first-follow.md` + optional `tools/first_follow.py`.
      → deliverable D3

## Stage 5 — Highlighter and renderers (≈6 commits)

→ `skills/highlighter`.

- [ ] **T5.1** `core/highlight.py`: `Category` enum (all twelve of R5.2),
      `HighlightMap` = `token_index -> Category`.
- [ ] **T5.2** `core/theme.py`: VS Code Dark+ values, category → (ANSI, CSS).
- [ ] **T5.3** `languages/c/highlighter.py`: token-level defaults, then an AST walk
      that *upgrades* categories — call callees to `function`, declared function
      names to `function`, type specifiers to `type`, struct names to `type_name`.
      → R5.1
- [ ] **T5.4** `render/ansi.py` and `render/html.py`, both consuming the same map
      and iterating the original source by offset. HTML: escaping, embedded CSS,
      no JavaScript. → R5.3, R6.1, R6.2, R6.3
- [ ] **T5.5** **The R5.1 acceptance test**: a fixture where the same identifier
      appears as a call and as a bare variable; assert different categories. Plus
      the round-trip test: strip color from output, diff against input, expect zero
      differences.
- [ ] **T5.6** Golden snapshot tests for ANSI and HTML output of `factorial.c`.

## Stage 6 — CLI, docs, polish (≈7 commits)

- [ ] **T6.1** `cli/main.py`: `tokens`, `ast`, `highlight`, `check`; `--format`,
      `-o`, `--json`; exit codes per R7.1. Top-level guard so no traceback ever
      reaches the user.
- [ ] **T6.2** CLI tests including empty file, comments-only file, binary garbage,
      nonexistent path, and a directory passed as a file. → R9.5
- [ ] **T6.3** CI: generate highlighted HTML for the canonical fixture and publish
      to GitHub Pages. → R9.4
- [ ] **T6.4** `docs/architecture.md`, `docs/known-limitations.md`. → D4, D5
- [ ] **T6.5** `docs/testing.md`, `docs/team.md`. → D6, D7
- [ ] **T6.6** `README.md`: summary, pipeline diagram, install, quickstart, usage
      with real output, badge, doc links. → D8
- [ ] **T6.7** Coverage pass to ≥80%; fill the gaps with real tests, never with
      `# pragma: no cover` on untested logic. → R9.4

## Stage 7 — Gate

- [ ] **T7.1** Walk `checklists/phase1-acceptance.md` top to bottom. Fix what
      fails. Only then report Phase 1 complete.

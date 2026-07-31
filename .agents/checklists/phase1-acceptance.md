# Phase 1 Acceptance Checklist

Walk this top to bottom before declaring Phase 1 done. Anything unchecked is not
done. Every line maps to a requirement in `project/01-phase1-requirements.md` or a
stated bonus.

## Robustness — the deduction risks

- [x] No input causes an uncaught exception. Verified against: empty file,
      whitespace only, comments only, unterminated string, unterminated block
      comment, unbalanced braces, stray `@`, CRLF endings, no trailing newline,
      1 MB file, random bytes, nonexistent path, directory as path
- [x] A file with errors still produces highlighted output for its valid regions
- [x] Out-of-scope constructs (`typedef` etc.) produce a clear diagnostic and
      recovery, not a crash

## Lexer

- [x] Every category in R1.2 produced, each with a test
- [x] Maximal munch: `<= >= == != -> ++ -- && || += -= *= /= %=`
- [x] `while` → KEYWORD; `while_count` → IDENT
- [x] `int x@ = 5;` → `INVALID('@')` at exactly **1:6**; line 2 lexes clean
- [x] Unterminated string: one diagnostic, scanning continues on the next line
- [x] Unterminated block comment: exactly one diagnostic, not one per line
- [x] Trivia retained; `iter_significant()` tested
- [x] Token spans tile the source with no gaps or overlaps

## Grammar and parser

- [x] `docs/grammar.ebnf` complete, left-recursion-free, matches the parser
- [x] `docs/first-follow.md` complete; dangling-else stated explicitly
- [x] One parser function per non-terminal, named to match
- [x] Precedence: `a + b * c` → `a + (b * c)`
- [x] Associativity: `a - b - c` → `(a - b) - c`; `a = b = c` → `a = (b = c)`
- [x] `int x = ;` recovers and `int y = 42;` still parses
- [x] `if (y > 0 {` recovers and the block still parses
- [x] `parse()` never returns `None` and never raises
- [x] Truncation fuzz over all valid fixtures: nothing raises

## AST

- [x] Every node carries a span; `type_annotation` present on `Expr`, still `None`
- [x] Golden positions match the course document §4.3.2: `3:12`, `3:16`, `3:26`, `3:30`
- [x] `ErrorExpr` / `ErrorStmt` exist and carry spans
- [x] `NodeVisitor` tested independently

## Highlighter and output

- [x] **Call-vs-variable test passes** — this is the one that fails the phase
- [x] All twelve R5.2 categories reachable and tested
- [x] Round-trip: color-stripped output byte-identical to input, all valid fixtures
- [x] ANSI output correct in a real terminal (look at it)
- [ ] HTML self-contained, embedded CSS, escapes `& < >`, renders with JS disabled
      (actually open it in a browser)
- [x] A third output format would require no highlighter changes

## CLI

- [x] `tokens`, `ast`, `highlight`, `check` all work
- [x] `--format ansi|html`, `-o`, `--json` all work
- [x] Exit codes: 0 clean, 1 errors present, 2 never observed
- [x] No traceback can reach the user

## Engineering and bonuses

- [x] `pytest` green; coverage ≥ 80%; report generated
- [x] `ruff check` and `ruff format --check` clean
- [x] `core/` imports nothing from `languages/` — enforced by a test
- [x] `docker build` then `docker run --rm c-lens --help` works
- [x] CI green on the remote; **badge in the README**
- [x] CI publishes highlighted HTML for the canonical fixture to Pages
- [x] `pip install -e .` then `clens --help` works in a clean venv
- [ ] ≥ 20 meaningful commits, genuinely distributed across both members

## Documentation

- [x] `docs/grammar.ebnf`
- [x] `docs/lexical-specification.md` — regex table **and** the NFA→DFA→minimization
      writeup **and** priority rules **and** a worked conversion example
- [x] `docs/first-follow.md`
- [x] `docs/architecture.md` — modules, pipeline, strategy choice and justification
- [x] `docs/known-limitations.md` — every exclusion with its reason
- [x] `docs/testing.md` — copy-pasteable, actually tried
- [ ] `docs/team.md` — ownership split
- [x] `docs/third-party.md` — pycparser credited as a design reference
- [x] `README.md` — summary, diagram, install, quickstart, real output, badge, links

## Defense readiness

- [ ] Both members can explain the lexer, the parser, and the highlighter
- [ ] Both can answer: why recursive descent and not LALR?
- [ ] Both can answer: why is `typedef` excluded, and what would it take to add?
- [ ] Both can answer: why does token-only highlighting not satisfy the requirement?
- [ ] Both can trace `int x@ = 5;` end to end, through every module
- [ ] Both can point to where each requirement ID is implemented and tested

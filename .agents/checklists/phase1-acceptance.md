# Phase 1 Acceptance Checklist

Walk this top to bottom before declaring Phase 1 done. Anything unchecked is not
done. Every line maps to a requirement in `project/01-phase1-requirements.md` or a
stated bonus.

## Robustness — the deduction risks

- [ ] No input causes an uncaught exception. Verified against: empty file,
      whitespace only, comments only, unterminated string, unterminated block
      comment, unbalanced braces, stray `@`, CRLF endings, no trailing newline,
      1 MB file, random bytes, nonexistent path, directory as path
- [ ] A file with errors still produces highlighted output for its valid regions
- [ ] Out-of-scope constructs (`typedef` etc.) produce a clear diagnostic and
      recovery, not a crash

## Lexer

- [ ] Every category in R1.2 produced, each with a test
- [ ] Maximal munch: `<= >= == != -> ++ -- && || += -= *= /= %=`
- [ ] `while` → KEYWORD; `while_count` → IDENT
- [ ] `int x@ = 5;` → `INVALID('@')` at exactly **1:6**; line 2 lexes clean
- [ ] Unterminated string: one diagnostic, scanning continues on the next line
- [ ] Unterminated block comment: exactly one diagnostic, not one per line
- [ ] Trivia retained; `iter_significant()` tested
- [ ] Token spans tile the source with no gaps or overlaps

## Grammar and parser

- [ ] `docs/grammar.ebnf` complete, left-recursion-free, matches the parser
- [ ] `docs/first-follow.md` complete; dangling-else stated explicitly
- [ ] One parser function per non-terminal, named to match
- [ ] Precedence: `a + b * c` → `a + (b * c)`
- [ ] Associativity: `a - b - c` → `(a - b) - c`; `a = b = c` → `a = (b = c)`
- [ ] `int x = ;` recovers and `int y = 42;` still parses
- [ ] `if (y > 0 {` recovers and the block still parses
- [ ] `parse()` never returns `None` and never raises
- [ ] Truncation fuzz over all valid fixtures: nothing raises

## AST

- [ ] Every node carries a span; `type_annotation` present on `Expr`, still `None`
- [ ] Golden positions match the course document §4.3.2: `3:12`, `3:16`, `3:26`, `3:30`
- [ ] `ErrorExpr` / `ErrorStmt` exist and carry spans
- [ ] `NodeVisitor` tested independently

## Highlighter and output

- [ ] **Call-vs-variable test passes** — this is the one that fails the phase
- [ ] All twelve R5.2 categories reachable and tested
- [ ] Round-trip: color-stripped output byte-identical to input, all valid fixtures
- [ ] ANSI output correct in a real terminal (look at it)
- [ ] HTML self-contained, embedded CSS, escapes `& < >`, renders with JS disabled
      (actually open it in a browser)
- [ ] A third output format would require no highlighter changes

## CLI

- [ ] `tokens`, `ast`, `highlight`, `check` all work
- [ ] `--format ansi|html`, `-o`, `--json` all work
- [ ] Exit codes: 0 clean, 1 errors present, 2 never observed
- [ ] No traceback can reach the user

## Engineering and bonuses

- [ ] `pytest` green; coverage ≥ 80%; report generated
- [ ] `ruff check` and `ruff format --check` clean
- [ ] `core/` imports nothing from `languages/` — enforced by a test
- [ ] `docker build` then `docker run --rm c-lens --help` works
- [ ] CI green on the remote; **badge in the README**
- [ ] CI publishes highlighted HTML for the canonical fixture to Pages
- [ ] `pip install -e .` then `clens --help` works in a clean venv
- [ ] ≥ 20 meaningful commits, genuinely distributed across both members

## Documentation

- [ ] `docs/grammar.ebnf`
- [ ] `docs/lexical-specification.md` — regex table **and** the NFA→DFA→minimization
      writeup **and** priority rules **and** a worked conversion example
- [ ] `docs/first-follow.md`
- [ ] `docs/architecture.md` — modules, pipeline, strategy choice and justification
- [ ] `docs/known-limitations.md` — every exclusion with its reason
- [ ] `docs/testing.md` — copy-pasteable, actually tried
- [ ] `docs/team.md` — ownership split
- [ ] `docs/third-party.md` — pycparser credited as a design reference
- [ ] `README.md` — summary, diagram, install, quickstart, real output, badge, links

## Defense readiness

- [ ] Both members can explain the lexer, the parser, and the highlighter
- [ ] Both can answer: why recursive descent and not LALR?
- [ ] Both can answer: why is `typedef` excluded, and what would it take to add?
- [ ] Both can answer: why does token-only highlighting not satisfy the requirement?
- [ ] Both can trace `int x@ = 5;` end to end, through every module
- [ ] Both can point to where each requirement ID is implemented and tested

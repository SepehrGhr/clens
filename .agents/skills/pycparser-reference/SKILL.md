---
name: pycparser-reference
description: How to use the pycparser clone at ../pycparser as reference material for c-lens without importing it, vendoring it, or copying its mistakes. Read this BEFORE opening anything under ../pycparser. Use whenever looking for reference implementations of C token regexes, C grammar productions, AST node inventories, or recursive-descent structure.
---

# Using pycparser as a reference

A clone sits at `../pycparser`, beside this repository.

## Read this first

pycparser v3.00 dropped its PLY dependency and was rewritten as a **hand-written
lexer plus recursive-descent parser in pure Python**, following the C99 Annex A
grammar, BSD-licensed. Architecturally it is very close to what we are building,
which makes it excellent reference material — and tempting in a way that will cost
us marks.

## Three reasons it cannot be our engine

1. **It has no comments.** pycparser expects input already processed by `cpp`,
   which strips comments. Comments-in-the-AST has been an open request on the
   project for years. Our highlighter needs a `comment` category (R5.2) and Phase 3
   hover needs doc comments (R1.8). Non-starter.
2. **It has no error recovery.** It raises on the first syntax error. Our course
   document requires panic-mode recovery and states that crashing on error is
   grounds for a significant deduction (R3.3, R3.4).
3. **It has no end positions.** Its `Coord` gives file/line/column of a node's
   *start*. We need start **and** end offsets for diagnostic span lengths and for
   offset-based rendering (R1.1, R4.2).

Beyond that: it implements full C99 including `typedef` and the lexer hack, which is
far more than our subset needs, and the project requires each team member to be able
to explain any component at the defense.

## What to take (all safe, all high-value)

| From | Take | Use in |
|---|---|---|
| `pycparser/c_lexer.py` | Keyword tuple; operator/punctuator token names; **literal regexes** — hex/octal/binary ints, float exponent and suffix forms, escape sequences | `languages/c/token_rules.py` |
| `pycparser/c_parser.py` | The decomposition into per-non-terminal functions and the precedence cascade, read as a worked example | `languages/c/parser.py` structure |
| `pycparser/_c_ast.cfg` | The inventory of C AST node types and their child field names — the single most useful file in the repo for us | `languages/c/ast_nodes.py` |
| `pycparser/tests/c_files/`, `examples/` | Real C files to run our tool against | `tests/fixtures/` |

## How to take it

- **Patterns and structure, not files.** Do not copy a source file wholesale, do not
  add pycparser to `requirements.txt`, do not vendor it into `src/`.
- Where a regex is copied close to verbatim, note the origin in a comment above it.
  That is honest, and it is also the right answer when a grader asks where it came
  from.
- pycparser is BSD-licensed; keep its copyright notice with anything substantial
  that is genuinely copied. Add a `docs/third-party.md` note crediting it as a
  design reference. Citing a reference implementation reads as good engineering.
- Adapt names to our conventions. Do not import its `Coord`, `Node`, or token type
  names — ours carry different information.

## What NOT to copy

- Its typedef / lexer-hack machinery. We excluded `typedef` on purpose (decision D3).
- Its scope-tracking callbacks in the lexer (`on_lbrace_func`, `on_rbrace_func`) —
  those exist to serve the lexer hack. Our lexer is context-free and stays that way.
- Its preprocessor expectations, `#line` directive handling, and fake-libc-headers
  approach. We tokenize directives and do not expand them.
- Its error behaviour, obviously.

## Sanity check before using anything from it

Ask: *does this decision survive the fact that we keep comments, recover from
errors, and track spans?* If not, it is one of the three traps above — design our
own and move on.

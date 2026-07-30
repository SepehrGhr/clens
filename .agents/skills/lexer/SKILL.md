---
name: lexer
description: How to build the lexer for c-lens — master-regex scanning, maximal munch, keyword priority, trivia retention, INVALID-token error recovery, and unterminated string/comment handling. Use this whenever touching anything under core/lexer_base.py or languages/*/token_rules.py or languages/*/lexer.py, or when a token, position, or scanning bug is reported.
---

# Lexer

Requirements: R1.1–R1.9. Read them before starting.

## Architecture

Two pieces, cleanly split:

- `core/lexer_base.py` — a **language-agnostic** scanner. Takes an ordered list of
  `(TokenType, compiled_regex)` rules and a `SourceFile`, returns `list[Token]` and
  emits diagnostics. Knows nothing about C.
- `languages/c/token_rules.py` — the ordered rule table. Knows nothing about scanning.

That split is what makes adding Java later a one-directory change.

## The master-regex approach

Build one alternation of named groups, in priority order, and drive it with
`re.compile(...).match(text, pos)` in a loop:

```python
MASTER = re.compile("|".join(f"(?P<{name}>{pattern})" for name, pattern in RULES))
```

Two rules make this correct:

1. **Order the alternation longest-first within each operator family.** Python's
   `re` alternation is leftmost-first, not longest-match. `<=` must appear before
   `<`, `->` before `-`, `++` before `+`, `/*` before `/`. Getting this wrong is the
   single most common bug in this file. Test it explicitly (R1.3).
2. **Keywords are not regex rules.** Match an identifier, then check membership in
   the keyword set and retype the token (R1.4). A `\bwhile\b` style rule looks like
   it works and then mis-lexes `while_count`.

Use `re.VERBOSE` and keep each pattern on its own line with a comment. This file is
also the source material for `docs/lexical-specification.md`, so write it to be read.

## Literal patterns — get these from pycparser

Integer suffixes, hex/octal/binary forms, float exponent-and-suffix combinations,
and string escape sequences are all fiddly and all easy to get subtly wrong.
pycparser's `c_lexer.py` has correct, battle-tested versions. Read
`skills/pycparser-reference/SKILL.md` first, then lift the *patterns* (not the file).

Cases that must be handled, from R1.2:
- `42`, `0xFF`, `0b1010`, `0755`, with `u`/`U`/`l`/`L` suffixes
- `3.14`, `1.0e-5`, `.5f`, `1.`, `1e10`
- `"hello\n"`, `"say \"hi\""`, `""`
- `'a'`, `'\t'`, `'\0'`, `'\''`

Trap: `.5` vs the member-access operator `.`. The float rule must precede the `.`
operator rule, and must require a digit after the dot.

## Error recovery (R1.5)

No character is ever fatal:

```
no rule matched at pos
  -> emit Token(INVALID, source[pos], span=pos..pos+1)
  -> emit Diagnostic(ERROR, "unrecognized character '@'", span)
  -> pos += 1
  -> continue
```

Golden case, must be a test: `int x@ = 5;` yields `INVALID('@')` at **line 1,
column 6**, and `int y = 10;` on the next line lexes cleanly.

## Unterminated string (R1.6)

Do not let a string rule consume to EOF. Terminate the string token at the newline,
emit `"unterminated string literal"` pointing at the **opening quote**, and resume
scanning at the newline. This keeps the rest of the file usable, which is the whole
point of recovery.

## Unterminated block comment (R1.7)

Consume to EOF, emit one diagnostic pointing at the opening `/*`. Do not emit one
diagnostic per remaining line.

Nested block comments: standard C does **not** nest. Do not implement nesting;
record it in `docs/known-limitations.md`.

## Trivia (R1.8)

Whitespace and comment tokens are **kept** in the token list with
`is_trivia == True`. The parser consumes a filtered view; the highlighter and the
renderer consume the full list.

This is a deliberate deviation from "usually discarded" in the course document, and
it is load-bearing: without it there is no comment highlighting and no Phase 3
hover documentation. Note the reasoning in the module docstring so nobody
"optimizes" it away later.

## Position tracking

Do not track line and column incrementally in the scan loop — it is the classic
source of off-by-one drift around `\r\n`. Track **offset only**, and derive line and
column from `SourceFile.offset_to_line_col()`, which owns a precomputed line-start
index. One implementation, one place to test, one place to fix.

Lines and columns are **1-based**. Offsets are **0-based**.

## Definition of done

- [ ] Every category in R1.2 produced, with a test each
- [ ] Maximal munch tested for `<=`, `>=`, `==`, `!=`, `->`, `++`, `--`, `&&`, `||`
- [ ] `while` → KEYWORD, `while_count` → IDENT
- [ ] `int x@ = 5;` golden case passes with position 1:6
- [ ] Unterminated string and block comment each produce exactly one diagnostic
      and leave the lexer able to continue
- [ ] Trivia retained; `iter_significant()` covered by a test
- [ ] Empty file → `[EOF]`, no diagnostics, no exception
- [ ] CRLF file positions identical to the LF equivalent
- [ ] No exception can escape `tokenize()` for any input, including random bytes

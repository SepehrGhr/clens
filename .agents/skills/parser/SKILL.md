---
name: parser
description: How to build the recursive-descent parser for c-lens — one function per non-terminal, precedence cascade, panic-mode error recovery with synchronization sets, and partial-AST-plus-diagnostics contract. Use this whenever touching core/parser_base.py, languages/*/parser.py, docs/grammar.ebnf, or when a syntax-error-recovery or precedence bug is reported.
---

# Parser

Requirements: R2.1–R2.4, R3.1–R3.5. Read them before starting.

## The contract

```python
def parse(tokens: list[Token], diags: DiagnosticCollector) -> TranslationUnit
```

Always returns a node. Never returns `None`. Never raises. On error it emits
diagnostics and produces the best partial tree it can (R3.4). The valid parts of a
broken file must still be highlighted — evaluators test exactly this.

Internally you may use an exception for control flow (`_ParseError`), but it must be
caught at the statement / declaration boundary where synchronization happens. It
never escapes `parse()`.

## Grammar first

Write `docs/grammar.ebnf` **before** writing parser code, and keep them in lockstep:
one function per non-terminal, named identically. If a production changes, the
function and the grammar file change in the same commit. Graders will read both.

## Structure

- `core/parser_base.py` — language-agnostic cursor:
  `peek()`, `peek_type()`, `advance()`, `check(type)`, `match(*types)`,
  `expect(type, context_msg)`, `at_end()`, `synchronize(sync_set)`.
  `expect` on mismatch emits a diagnostic and raises `_ParseError`.
- `languages/c/parser.py` — the grammar functions.

## Expression precedence

Follow the cascade in the course document's EBNF, lowest binding to highest:

```
assignment → ternary → logical_or → logical_and → equality → relational
           → additive → multiplicative → unary → postfix → primary
```

Binary levels are loops, not recursion:

```python
def _additive(self):
    left = self._multiplicative()
    while self.match(PLUS, MINUS):
        op = self.previous()
        right = self._multiplicative()
        left = BinaryExpr(op, left, right, span=join(left.span, right.span))
    return left
```

This gives **left associativity**, which is correct for these operators, and it is
why the grammar needs no left recursion (R2.2). Assignment and the ternary are
**right**-associative — recurse on the right-hand side instead of looping. Test
both: `a - b - c` must parse as `(a - b) - c`, and `a = b = c` as `a = (b = c)`.

Postfix is also a loop, over a chain: `f(x)[0].field->next++` is one postfix
expression with five suffixes applied left to right.

## Panic-mode recovery (R3.3)

On an unexpected token:

1. Emit a diagnostic saying what was expected and what was found, with position.
2. Skip tokens until a synchronization point.
3. Resume.

Synchronization set:
- `;` — **consume it**, then resume. The statement is over.
- `}` — **do not consume**. The enclosing block needs it to close properly.
  Consuming it cascades one error into many.
- Statement-leading keywords (`if while for return break continue struct`) and type
  keywords (`int float char double void`) — do not consume; resume parsing from there.
- EOF — stop.

Recover at **statement and declaration granularity**, not inside expressions. A
failed expression yields an `ErrorExpr` placeholder node (which carries a span, so
the highlighter can still color the region) and the statement-level handler
synchronizes.

Guard against infinite loops: if a recovery attempt leaves the cursor where it
started, force one `advance()`. Add a test that a pathological input terminates.

## Golden recovery cases

Both from the course document; both must be tests asserting the *following*
construct still parses:

```c
int x = ;     /* expected expression, got ';' — recover, continue */
int y = 42;   /* must parse successfully */

if (y > 0     /* missing ')' before '{' — recover */
{
    return y;
}
```

## Error message quality (R3.5)

`expected expression, got ';'` — good.
`expected ')' to close parameter list, got '{'` — better.
`parse error` — not acceptable; it is graded.

Include the construct being parsed in the message where the parser knows it. That
context is free: pass a short string into `expect()`.

## Out-of-scope constructs

When you see `typedef`, `union`, `enum`, `switch`, or `goto` (see
`project/03-c-subset.md`), emit a clear diagnostic naming the unsupported construct,
then synchronize as normal. Do not crash and do not silently skip.

## Definition of done

- [ ] Every production in `docs/grammar.ebnf` has a matching function and a test
- [ ] Associativity tests for `-`, `/`, `=`, and `?:`
- [ ] Precedence test: `a + b * c` groups as `a + (b * c)`
- [ ] Dangling else binds to the nearest unmatched `if`, with a test
- [ ] Both golden recovery cases pass, including the follow-on parse
- [ ] Robustness test: every valid fixture truncated at every 10th token, parsed,
      no exception escapes
- [ ] `docs/first-follow.md` written and consistent with the grammar

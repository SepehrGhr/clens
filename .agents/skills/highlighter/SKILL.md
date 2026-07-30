---
name: highlighter
description: How to build the AST-driven syntax highlighter and the ANSI/HTML renderers for c-lens — category maps, offset-based faithful rendering, and the call-vs-variable requirement that makes token-only highlighting worth zero credit. Use whenever touching core/highlight.py, core/theme.py, languages/*/highlighter.py, or render/.
---

# Highlighter and renderers

Requirements: R5.1–R5.3, R6.1–R6.3.

## The one requirement that fails the phase

The course document states that a pure regex-based highlighter **does not satisfy
the project requirements**, and that token-stream-only highlighting cannot
distinguish a function-call identifier from a variable identifier. The highlighter
must consult the AST.

The proof, and the acceptance test: in a file where `factorial` appears both as a
call target and as a bare variable reference, the two get **different** categories.
Write that test early; it is the thing being checked.

## Two-pass design

**Pass 1 — token defaults.** Walk the flat token list and assign an obvious category
from the token type: keywords to `keyword`, type keywords to `type`, numeric
literals to `number`, strings and chars to `string`, operators to `operator`,
comments to `comment`, preprocessor to `preprocessor`, INVALID to `error`,
identifiers to `variable` (the neutral default).

**Pass 2 — AST upgrades.** Walk the AST with `NodeVisitor` and *upgrade* categories
for identifier tokens where context tells you more:

| AST context | Token upgraded to |
|---|---|
| `CallExpr.callee` identifier | `function` |
| `FuncDecl` name | `function` |
| `StructDecl` name, struct type references | `type_name` |
| Type specifier tokens in a declaration | `type` |
| `true` / `false` if the subset gains them | `boolean` |

Pass 2 only ever overwrites Pass 1, never the reverse. Keep the two passes in
separate functions so a test can assert Pass 2 actually changed something.

## Data flow

```
tokens ---> pass 1 ---+
                      +--> HighlightMap: dict[token_index, Category] ---> renderer
AST ------> pass 2 ---+
```

The map is keyed by **token index**, not by node. That is what lets the renderer
walk the original source in order, including trivia, and produce byte-faithful
output.

## Rendering (R5.3)

Iterate tokens in order; for each, slice `source[token.start_offset:token.end_offset]`
and wrap it in markup. Never reconstruct text from lexemes or from the AST —
reconstruction loses whitespace and is how faithfulness bugs get in.

Assert the invariant: token spans are contiguous and cover the entire source from 0
to `len(source)`. If they do not, the lexer has a gap and the renderer will silently
drop characters. Make that a test.

**ANSI** (`render/ansi.py`): wrap with the category's escape code, reset after each
span. Emit no codes for a category with no styling.

**HTML** (`render/html.py`): a `<pre>` block, one `<span class="...">` per span,
embedded `<style>`, self-contained, **no JavaScript**. HTML-escape `&`, `<`, `>` in
the source text — do this on the sliced text, never on the whole document afterwards.

## Theme (core/theme.py)

One table: `Category -> (ansi_code, css_class, css_rule)`. VS Code Dark+ values.
All twelve categories from R5.2 present. Adding a third output format must not
require touching the highlighter — only reading this table differently.

## Definition of done

- [ ] All twelve R5.2 categories reachable, each with a test
- [ ] Call-vs-variable test passes
- [ ] Round-trip test: color-stripped output is byte-identical to input, over every
      valid fixture
- [ ] Span-coverage test: token spans tile the source with no gaps or overlaps
- [ ] HTML output renders with JavaScript disabled and escapes `<`, `>`, `&`
- [ ] A file that fails to parse still highlights, using Pass 1 categories plus
      `error` spans (this is what evaluators will try)

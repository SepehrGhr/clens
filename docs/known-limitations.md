# Known Limitations

Every exclusion here is a scoping decision with a reason, not an omission — see
`.agents/project/03-c-subset.md` (the authoritative contract between the grammar,
the parser, and the tests) and `.agents/project/02-decisions.md` (D1-D14) for the
full rationale behind each one.

## Excluded C features

| Excluded | Reason |
|---|---|
| `typedef` | Makes C's grammar context-sensitive: the lexer would need to consult a symbol table mid-scan to know whether an identifier names a type (the "lexer hack"). Without it, `IDENT` is unambiguous and the grammar stays clean LL(1) (D3). Detected and reported as `unsupported construct: 'typedef'`, then recovered via the normal panic-mode path — never a crash. |
| `union`, `enum` | New declaration forms with no new compiler-theory content over `struct` |
| `switch` / `case` / `goto` / labels | No new parsing technique over `if`/`while`; Phase 3's CFG cost for arbitrary control transfer is high for the credit available |
| Function pointers | Declarator syntax complexity (`int (*fp)(int)`) disproportionate to the value for this subset |
| Multi-dimensional arrays | Same — 1-D covers the interesting cases (bounds, indexing, `sizeof`) |
| Variadic functions, `...` | Same |
| `#include` / macro expansion | Tokenized only (`PREPROC`, one token per line), never expanded. A real preprocessor is a listed bonus, not base scope |
| Bitfields, designated initializers, compound literals | Out — no new parsing technique, disproportionate grammar cost |
| Multi-file / translation units | Phase 1 is single-file. Phase 3 navigation is designed for multi-file, but Phase 1 need not deliver it |

Every one of these, when encountered, produces a clear diagnostic naming the
construct and recovers via the same panic-mode path as a syntax error — see
`tests/unit/test_parser_recovery.py::test_unsupported_typedef_reports_and_keeps_going`.
The tool never crashes on out-of-scope input; it also never silently ignores it.

## `static` / `extern` / `volatile` / `register` / `const`

The subset document leaves this an open choice ("parsed and ignored, or
rejected — pick one, document it"). **Chosen: parsed and recorded, not
enforced.** All four storage-class keywords and `const` are recognized by the
lexer (`languages/c/keywords.py`), accepted by the parser onto
`TypeSpec.storage` / `TypeSpec.is_const`, and highlighted as `keyword`. Phase 1
does no semantic analysis at all, so "enforced" isn't meaningful yet — there is
no symbol table to check `const`-correctness against, and no linkage model to
apply `static`/`extern` to. Phase 2's semantic analyzer is the natural place to
start acting on these fields; the fields already exist so that work is additive,
not a rewrite.

## Block comments do not nest

Standard C: `/* /* */ */` closes at the first `*/`, leaving a stray `*/` behind.
This is the correct, standards-compliant behavior — not a limitation of our
implementation — but is worth stating explicitly since it surprises people who
expect editor-style nested comments (`.agents/skills/lexer/SKILL.md`).

## Unterminated char literals fall back to generic recovery

R1.6/R1.7 require dedicated recovery for unterminated *strings* and *block
comments*, each with its own diagnostic message. An unterminated char literal
(`'a` with no closing quote) has no such dedicated rule: the `CHAR_LIT` pattern
simply fails to match, and the opening `'` falls through to the lexer's generic
single-character `INVALID` recovery (R1.5) instead of a char-specific message.
This still satisfies "never crash" and still produces a diagnostic — just a
more generic one (`unrecognized character "'"`) than the string/comment cases.

## Calling a non-identifier expression is not modeled

This subset's grammar only allows calling a bare identifier (`f(...)`), matching
the exclusion of function pointers above. `CallExpr.callee` is therefore a plain
`str`, not a sub-expression (`languages/c/ast_nodes.py`). If a postfix `(`
follows something other than an `Identifier` node (which cannot happen through
any construct this grammar accepts, but could appear in adversarial input), the
parser does not build a `CallExpr` there; the stray `(` is left for the
enclosing production to report as an ordinary syntax error. No crash, a
slightly less specific diagnostic than a dedicated check would give.

## String/char literal content is stored raw

`StringLiteral.value` / `CharLiteral.value` hold the literal's source text
between the quotes, with escape sequences (`\n`, `\t`, ...) *not* decoded.
Phase 1 does no constant evaluation, so there is nothing yet that needs the
decoded value; decoding is a small, natural addition when Phase 2 adds constant
folding.

## The `boolean` highlighting category is currently unreachable

R5.2 requires twelve highlighting categories, including `boolean`. This C
subset has no `true`/`false` literals (not in `.agents/project/03-c-subset.md`),
so `Category.BOOLEAN` is fully wired — present in the enum, styled in
`core/theme.py`, tested at the theme layer (`tests/unit/test_theme.py`) — but no
real C source can currently trigger it end-to-end through the highlighter. It
exists for parity with R5.2's category list and so that adding boolean literals
later (or a second language that has them, per D13) requires no changes to
`core/highlight.py` or `core/theme.py`.

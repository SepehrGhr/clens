# The C Subset ("C-lite")

This file is the contract between the grammar, the parser, and the tests. If you
add a feature to one, add it to all three and update this file in the same commit.

## In scope

**Types**
- `int`, `float`, `char`, `double`, `void`
- Pointers: `int*`, `char**` (any depth)
- 1-D arrays: `int a[10]`, `int a[]` in parameters
- `struct` declarations, `struct` variables, field access via `.` and `->`
- `const` accepted and recorded on the type, not enforced in Phase 1

**Declarations**
- Function definitions and prototypes
- Global and local variable declarations, with or without initialiser
- Multiple declarators per declaration: `int a = 1, b, c = 3;`
- Struct declarations with field lists

**Statements**
- `if` / `else` (including `else if` chains)
- `while`
- `for` (all three clauses optional)
- `return` with or without a value
- `break`, `continue`
- Expression statements, empty statements, nested blocks

**Expressions** — full precedence cascade per the grammar
- Assignment: `=`, `+=`, `-=`, `*=`, `/=`, `%=`
- Ternary `?:`
- `||`, `&&`
- `==`, `!=`, `<`, `>`, `<=`, `>=`
- `+`, `-`, `*`, `/`, `%`
- Unary `-`, `!`, `&`, `*`, `~`, prefix `++`/`--`
- Postfix: call `f(...)`, index `a[i]`, member `.`, arrow `->`, postfix `++`/`--`
- Primary: literals, identifiers, parenthesised expressions
- `sizeof(type)` and `sizeof expr`

**Lexical**
- All literal forms in R1.2
- Both comment styles
- Preprocessor directives **tokenized as a single `PREPROC` token per line, never
  expanded**

## Out of scope

Excluded deliberately. Each goes in `docs/known-limitations.md` with its reason.

| Excluded | Reason to record |
|---|---|
| `typedef` | Makes C's grammar context-sensitive; requires the lexer hack. See D3. |
| `union`, `enum` | Adds declaration forms with no new compiler-theory content |
| `switch` / `case` / `goto` / labels | No new parsing technique; Phase 3 CFG cost is high |
| Function pointers | Declarator syntax complexity, disproportionate to value |
| Multi-dimensional arrays | Same |
| Variadic functions, `...` | Same |
| `#include` / macro expansion | Tokenized only. A real preprocessor is a listed *bonus*, not base scope |
| `static`, `extern`, `volatile`, `register` | Parsed and ignored, or rejected — pick one, document it |
| Bitfields, designated initialisers, compound literals | Out |
| Multi-file / translation units | Phase 1 is single-file. Phase 3 navigation is designed for multi-file but Phase 1 need not deliver it |

## Rule for ambiguous cases

If the evaluator hands you a file using an out-of-scope feature, the tool must
still not crash: emit a clear diagnostic naming the unsupported construct, recover
via the normal panic-mode path, and keep processing. "Unsupported construct:
`typedef` (see known limitations)" is a good message and reads far better at the
defense than a stack trace.

# Phase 1 Requirements

Every requirement extracted from the course document, given a stable ID. Tests
should reference these IDs in their names or docstrings so coverage of the rubric
is auditable.

Source: *Compiler Design, Spring 1404–1405, Final Project* — §4 (Phase One), plus
the always-on requirements in §8 and §9.

---

## R1 — Lexer

### R1.1 Token record
Every token carries:

| Field | Notes |
|---|---|
| `type` | Token category enum (see R1.2) |
| `lexeme` | The **exact** matched substring from the source |
| `file` | Source file name |
| `line` | **1-based** |
| `column` | **1-based** |
| `start_offset` | 0-based char offset into the source string |
| `end_offset` | 0-based, exclusive |

The document requires type, lexeme, file, line, column. `start_offset` /
`end_offset` are **our addition** and are mandatory here — Phase 2 diagnostics
require a `length` field to underline the offending span, and the highlighter
renders by offset. Adding them later means touching every construction site.

Column convention is confirmed by the document's own example: in `int x@ = 5;`
the `@` is reported at `1:6`.

### R1.2 Token categories
All of these must be produced:

- `KEYWORD` — finite set, checked before identifiers
- `IDENT` — `[a-zA-Z_][a-zA-Z0-9_]*`
- `INT_LIT` — decimal, hexadecimal (`0xFF`), binary (`0b1010`), octal (`0755`)
- `FLOAT_LIT` — `3.14`, `1.0e-5`, `.5f` — optional exponent, optional suffix
- `STRING_LIT` — quoted, with escape sequence handling
- `CHAR_LIT` — single character or escape
- `OPERATOR` — full set for the language
- `DELIMITER` — structural punctuation `{ } ( ) [ ] ; ,`
- `LINE_COMMENT` — `//` to end of line
- `BLOCK_COMMENT` — `/* ... */`
- `WHITESPACE` — spaces, tabs, newlines
- `PREPROC` — `#include`, `#define` — **a token class, not expanded**
- `INVALID` — see R1.5
- `EOF` — sentinel, carries the end-of-file position

### R1.3 Longest match (maximal munch)
Always consume the longest possible token. `<=` is one token, never `<` then `=`.
`->` is one token. `...` if supported is one token.

### R1.4 Keyword priority
Keywords beat identifiers. `while` produces `KEYWORD(while)`, never `IDENT(while)`.
Implementation: match as identifier, then look up in the keyword set.

### R1.5 Never crash; INVALID token and recovery
On an unrecognized character:
1. Emit an `INVALID` token recording its exact location.
2. Advance past exactly one offending character.
3. Continue scanning.

Golden example from the document:
```c
int x@ = 5;   /* INVALID('@') at 1:6, then scanning resumes */
int y = 10;   /* scanned correctly: INT(10) */
```

### R1.6 Unterminated string literal
Detect and report. Do not run to end of file silently. Recovery: terminate the
token at the newline, emit a diagnostic, resume on the next line.

### R1.7 Unterminated block comment
Detect and report. Recovery: consume to EOF, emit a diagnostic.

### R1.8 Trivia is retained, not discarded
The document says whitespace is "tracked for location; usually discarded."
**We retain it.** Whitespace and comment tokens stay in the token list, flagged as
trivia, and are filtered out by a view function before the parser consumes them.

Reasons: byte-faithful highlighting output (R5.3), the comment color category
(R5.2), and Phase 3 hover, which must attach doc comments to declarations. This is
also the single biggest reason we cannot use pycparser's lexer — see
`skills/pycparser-reference/SKILL.md`.

### R1.9 Formal regex documentation
A documented regular expression for **every** token class, in
`docs/lexical-specification.md`. This is a graded written deliverable independent
of the implementation. See `project/05-deliverables.md` §D2.

---

## R2 — Grammar

### R2.1 EBNF specification
A complete EBNF grammar for the implemented C subset, in `docs/grammar.ebnf`,
covering every construct the parser accepts. This is an explicitly named Phase 1
deliverable. The course document provides a starting fragment; extend it to match
`project/03-c-subset.md` exactly — the grammar and the parser must not drift.

### R2.2 Left-recursion free
Required for recursive descent. Expression levels use iteration (`*`) rather than
left-recursive self-reference.

### R2.3 Ambiguity proof
FIRST and FOLLOW sets for every non-terminal, and a written argument that there are
no FIRST/FIRST or FIRST/FOLLOW conflicts at k=1. In `docs/first-follow.md`.

Known exception to document honestly: the dangling-else ambiguity, resolved by the
conventional "bind `else` to the nearest unmatched `if`" rule. Say so explicitly
rather than pretending the grammar is unambiguous.

### R2.4 Documented parsing strategy
State the choice (LL(1) recursive descent), justify it, and note the alternative
(LALR via generator) and why it was rejected. In `docs/architecture.md`.

---

## R3 — Parser

### R3.1 Recursive descent
One function per non-terminal, named after it. Expression precedence follows the
grammar's cascade. Hand-written; no parser generator.

### R3.2 Produces an AST
Directly, not via a CST. See R4.

### R3.3 Panic-mode error recovery
On an unexpected token: emit a helpful diagnostic, then skip tokens until a
synchronization point, then resume parsing.

Synchronization set: `;` (consume it), `}` (do not consume — let the enclosing
block handle it), and the statement-leading keywords `if while for return break
continue struct` plus type keywords.

### R3.4 Partial results after errors
The parser returns a *partial AST plus diagnostics*, never `None` and never a raised
exception. Valid regions of a file must still be parsed, highlighted, and emitted.
The document is explicit: the system must continue processing the remainder of the
file and produce output for all valid portions.

Golden examples from the document:
```c
int x = ;     /* Error at 1:9: expected expression, got ';'
                 Recovery: skip to ';', continue */
int y = 42;   /* Successfully parsed despite the error above */
if (y > 0     /* Error: missing ')' before '{' --- recovered */
{
    return y;
}
```

### R3.5 Error message quality
Messages state what was expected and what was found, with position:
`expected expression, got ';'`. Not `parse error`.

---

## R4 — AST

### R4.1 Node inventory
Leaves are terminals (literals, identifiers). Internal nodes are grammatical
constructs. The document names: `BinaryExpr`, `IfStmt`, `FuncDecl`, `CallExpr`,
`ReturnStmt`. Full inventory follows from `docs/grammar.ebnf` — one node type per
meaningful production.

### R4.2 Every node carries its source location
Line + column of its **first token**, plus start/end offsets spanning the whole
construct.

Golden example from the document (§4.3.2), for line 3 of the factorial program:

```
ReturnStmt
  value: BinaryExpr(op='*')
    left:  Identifier(name='n', loc=3:12)
    right: CallExpr(callee='factorial', loc=3:16)
      args[0]: BinaryExpr(op='-')
        left:  Identifier(name='n', loc=3:26)
        right: IntLiteral(value=1, loc=3:30)
```

This example is internally consistent with 1-based columns and 4-space indentation
and is used as a golden test — see `fixtures/golden/`.

> ⚠️ **Do not** use the location numbers in the document's §5.1.1 symbol-table
> example as golden data. They are internally inconsistent (`factorial` at `1:5`
> and parameter `n` at `1:23` cannot both be true on a 22-character line). §4.3.2
> is the reliable one.

### R4.3 Type annotation field
Every expression node has a `type_annotation` field, initialised to `None`,
untouched in Phase 1, filled by the Phase 2 semantic analyzer.

### R4.4 Generic visitor
One `NodeVisitor` base class with `visit_<NodeType>` dispatch and a `generic_visit`
fallback. Phase 1 uses it once (the highlighter). Phases 2 and 3 use it four more
times. Write it once, properly.

---

## R5 — Syntax highlighter

### R5.1 AST-level highlighting is mandatory
The highlighter queries AST node types, not just token types. A token-stream-only
highlighter cannot distinguish a function-call identifier from a variable
identifier, and the document states a pure regex-based highlighter does not satisfy
the project requirements.

**Acceptance test:** in a file containing both `factorial(n)` as a call and
`factorial` as a bare variable reference, the two must receive different categories.
If that test does not exist and pass, R5.1 is not met.

### R5.2 Category mapping
Minimum required categories and their intent (colors are the document's
suggestions; exact hex values come from the chosen theme):

| Category | Applies to | Suggested |
|---|---|---|
| `keyword` | `if`, `return`, … | Bold blue |
| `type` | `int`, `float`, … | Teal / cyan |
| `variable` | Variable identifiers | White / default |
| `function` | Function and method names | Yellow / gold |
| `type_name` | Type / class names | Bright green |
| `number` | Integer and float literals | Orange |
| `string` | String and char literals | Warm green |
| `boolean` | Boolean literals | Orange |
| `operator` | Operators | Light gray |
| `comment` | Comments | Dim gray, italic |
| `preprocessor` | Directives, decorators, annotations | Magenta |
| `error` | Invalid tokens | Red underline |

Teams may extend this set. Do not shrink it.

### R5.3 Faithful rendering
Output reproduces the original source exactly — whitespace, blank lines, comments,
line endings — with color markup injected around token spans. Diffing the
color-stripped output against the input must yield zero differences. Make that a test.

---

## R6 — Output formats

### R6.1 ANSI terminal
ANSI escape codes injected into the output, e.g. `\e[34;1m` for bold blue.

### R6.2 HTML / CSS
A self-contained HTML file: a `<pre>` block with `<span class="kw">`-style elements
and an embedded stylesheet. **Must render correctly in any modern browser with no
JavaScript.** HTML-escape `<`, `>`, `&` in source text.

### R6.3 One category map, two renderers
Both renderers consume the same `token_index -> category` map. The theme is a
single data table mapping category to an ANSI code and a CSS rule. Adding a third
output format must not require touching the highlighter.

---

## R7 — User interface

### R7.1 At least one runnable interface
The document requires a runnable UI that accepts input, processes code, and
displays all output relevant to the current phase. Phase 1: a CLI.

Required commands:
- `clens tokens <file>` — dump the token stream
- `clens ast <file>` — pretty-print the AST
- `clens highlight <file> [--format ansi|html] [-o OUT]`
- `clens check <file>` — diagnostics only
- `--json` on any command for machine-readable output

Exit codes: `0` clean, `1` diagnostics with severity error present, `2` internal
failure (which should never happen — see rule 1).

---

## R8 — Documentation deliverables

See `project/05-deliverables.md`. Summary: grammar EBNF, lexical specification with
formal regexes and the NFA→DFA writeup, FIRST/FOLLOW tables, architecture and
algorithm justification, known limitations, and step-by-step test instructions.

---

## R9 — Engineering and process

### R9.1 Version control
Hosted repo. **At least 20 meaningful, descriptive commits**, distributed across
both team members. Traceable history. See `skills/git-workflow/SKILL.md`.

### R9.2 Documented division of responsibilities
Who owns the Lexer, Parser, Semantic Analyzer, etc. In `docs/team.md`. Each member
must be able to explain their partner's components at the defense.

### R9.3 Software engineering practice
Meaningful naming, modular design, separation of concerns, no unnecessary global
mutable state. Explicitly graded.

### R9.4 Bonus items in scope for Phase 1
These are cheap now and expensive later — build them during Phase 1:
- **Docker**: single `docker run` gets a working tool. `Dockerfile` required.
- **CI**: runs all tests on every push, generates highlighted HTML for a canonical
  test file, publishes to GitHub Pages, **passing badge in the README is required
  for the bonus**.
- **Test suite with coverage**: every module, valid and erroneous programs, each
  test specifying exact expected output. **≥80% line coverage**, with a report.

### R9.5 Robustness against evaluator input
Evaluators supply their own files: some valid, some with lexical errors, some with
syntax errors. All must be processed. Assume they will try an empty file, a file of
only comments, a file with CRLF line endings, a file with a stray `@`, and a file
with unbalanced braces.

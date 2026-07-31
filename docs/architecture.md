# Architecture

## Pipeline

```
                 ┌─────────────────────────────────────────────────────────┐
                 │                      DiagnosticCollector                 │
                 └───────────▲───────────────▲───────────────▲─────────────┘
                             │               │               │
SourceFile ──► Lexer ──► tokens ──► Parser ──► AST ──► Highlighter ──► HighlightMap
 (source.py)  (lexer_base +          (parser_base +            (highlight.py +
               token_rules.py,        parser.py)                theme.py +
               lexer.py)                                        highlighter.py)
                                                                       │
                                                                       ▼
                                                          render/ansi.py, render/html.py
                                                                       │
                                                                       ▼
                                                              ANSI text / HTML file
```

Everything produces diagnostics into one `DiagnosticCollector`, passed explicitly
through the pipeline (never a global — see `core/diagnostics.py`). Nothing raises to
the caller; `clens.cli.main.main()` is the only place a truly unexpected exception is
ever caught, and that path is meant to be unreachable (R7.1's exit code `2`).

## Modules

| Module | Responsibility |
|---|---|
| `core/source.py` | `SourceFile`: text plus a precomputed line-start index; the single place offset↔line/column conversion happens |
| `core/token.py` | `TokenType`, `Token`, `Span`, `iter_significant()` (trivia filter) |
| `core/diagnostics.py` | `Severity`, `Position`, `Diagnostic` (LSP-shaped), `DiagnosticCollector` |
| `core/lexer_base.py` | Language-agnostic master-regex scanner engine: rule ordering, position tracking, INVALID recovery, unterminated-literal diagnostics |
| `core/parser_base.py` | Language-agnostic token cursor: `peek`/`advance`/`check`/`match`/`expect`, panic-mode `synchronize()` |
| `core/ast_nodes.py` | `Node`/`Expr`/`Stmt`/`Decl` bases, `ErrorExpr`/`ErrorStmt`, `join()` |
| `core/visitor.py` | `NodeVisitor` (type-dispatch) and `walk()` (flat traversal), generic over any node type |
| `core/ast_printer.py` | Generic AST pretty-printer, driven by two `ClassVar`s each node class declares |
| `core/highlight.py` | `Category` enum (the twelve from R5.2), `HighlightMap` type |
| `core/theme.py` | One `Category -> Style` table; the only place a hex color is written |
| `languages/c/keywords.py`, `token_rules.py` | The C keyword set and the ordered regex rule table |
| `languages/c/lexer.py` | Wires the C rules into `LexerEngine`, applies keyword retyping |
| `languages/c/ast_nodes.py` | One dataclass per grammar production |
| `languages/c/parser.py` | Recursive-descent grammar functions, one per non-terminal; `parse()` entry point |
| `languages/c/highlighter.py` | Two-pass highlighter: token defaults, then AST-context upgrades |
| `render/ansi.py`, `render/html.py` | Consume one `HighlightMap` identically; slice `source.text` by offset, never reconstruct from lexemes |
| `cli/main.py` | `tokens`/`ast`/`highlight`/`check` subcommands, `--json`, `-o`, exit codes |

`src/clens/core/**` never imports from `languages/` — enforced by
`tests/unit/test_layering.py` (D12). This is what makes the multi-language bonus
(Java, planned but not started — D13) a new `languages/java/` directory rather than
a rewrite.

## Why recursive descent, not a parser generator (R2.4)

**Chosen: hand-written LL(1) recursive descent** (D6). One function per
non-terminal, named identically to the grammar production
(`docs/grammar.ebnf` ↔ `Parser.parse_<name>`).

**Rejected: a generated LALR parser** (e.g. a PLY/yacc-style table-driven parser).
Three reasons, all load-bearing for requirements this project actually has:

1. **Error recovery.** A generated parser's error handling is table-driven and
   opaque; panic-mode recovery with a hand-chosen synchronization set (R3.3) is
   naturally expressed in a hand-written parser as "catch `ParseError`, call
   `synchronize()`, keep going" at exactly the granularity we want (statement and
   declaration boundaries — see `.agents/skills/parser/SKILL.md`). Retrofitting
   the same recovery quality onto a generated table is significantly harder to get
   right and to explain.
2. **Custom AST shapes.** A generator naturally builds a parse tree shaped like the
   grammar. We want typed dataclass AST nodes shaped like the *language*
   (`BinaryExpr`, `IfStmt`, `CallExpr`, ...), which recursive descent produces for
   free — each production just builds and returns the node it means.
3. **Defensibility at the defense.** Every team member can read
   `languages/c/parser.py` top to bottom and explain any function. A generated
   parser's actual matching logic lives in a table neither of us wrote by hand.

**Rejected: a hand-written DFA-driven table for the lexer**, for the equivalent
reason on the lexing side (D5) — see `docs/lexical-specification.md` §4 for the
full argument, including the honest note about where our ordered-master-regex
approach diverges from a textbook DFA and why the divergence doesn't matter.

## Data structures

- **AST nodes**: `@dataclass(slots=True, kw_only=True)`, one class per grammar
  production, never dicts (D8). `slots=True` for memory (every node in every
  parsed file is one of these); `kw_only=True` because `Expr.type_annotation`'s
  default (`None`) would otherwise force every subclass field to also have a
  default, which produces meaningless placeholder values for fields that are
  always supposed to be real. See `languages/c/ast_nodes.py`'s module docstring.
- **Highlighting**: an offset map, not an AST-walk-emits-spans-directly design
  (D9). `HighlightMap = dict[token_index, Category]`, built by walking the full
  (trivia-included) token list once for defaults, then the AST once to upgrade
  specific tokens by looking up their start offset. This is what lets the
  renderer reconstruct the source byte-for-byte (R5.3): it walks tokens, not the
  AST, so whitespace and comments — which aren't AST nodes — are never lost.
- **Diagnostics**: `Position` bundles 1-based line/column with the 0-based
  offset in one value, so a `Diagnostic` carries everything both a human-facing
  renderer (line:column) and an offset-based renderer (the highlighter, hover
  spans) need, without either one recomputing the other from raw text.

## Robustness strategy (rule 1: never crash)

Every stage returns a best-effort result plus diagnostics, never raises past its
own boundary:

- **Lexer**: an unrecognized character becomes one `INVALID` token and one
  diagnostic; scanning resumes at the next character. Unterminated strings/block
  comments get dedicated recovery rules (R1.6, R1.7) rather than running to EOF
  silently.
- **Parser**: `ParseError` is an internal control-flow exception, caught at
  statement/declaration granularity (`parse_block`, `parse_program`), never
  escaping `parse()`. A `pos_before`/`guard_progress()` check after every
  recovery attempt forces the cursor forward even if a bug in some future
  production would otherwise leave it stuck (see `core/parser_base.py`).
- **Highlighter**: pure function of tokens + AST, no exceptions possible from
  well-typed input; a program with parse errors still highlights everything that
  *did* parse, via Pass 1 token defaults for the rest.
- **CLI**: `main()`'s outermost `try/except Exception` is the last line of
  defense (exit code `2`), verified by a test that forces it via monkeypatching.
  File loading (missing path, directory, unreadable bytes, non-UTF-8 content)
  never raises either — see `cli/main.py::_load_source`.

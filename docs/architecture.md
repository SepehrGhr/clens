# Architecture

## Pipeline

Phase 1 ends at the highlighter. Phase 2 adds one more stage —
`languages/c/semantic.py::analyze()` — between the parser and everything
that reads a type-annotated, name-resolved program: the highlighter still
only needs the AST (highlighting predates and does not depend on semantic
analysis), but completion, hover, and `clens check`'s semantic diagnostics
all read `analyze()`'s output. Phase 3 adds one further stage —
`languages/c/program_analysis.py::analyze_program()` — built *alongside*
`SemanticModel`, not inside it (D25): a `SemanticModel` consumer that
never asks for CFGs, the call graph, or data-flow results (completion,
hover, `clens check`) never pays for building them.

```
                 ┌───────────────────────────────────────────────────────────────────────┐
                 │                          DiagnosticCollector                          │
                 └──────▲──────────────▲──────────────▲───────────────────▲──────────────┘
                        │              │              │                   │
SourceFile ──► Lexer ──► tokens ──► Parser ──► AST ──┬──► Highlighter ──► HighlightMap
 (source.py)  (lexer_base +      (parser_base +      │        │
               token_rules.py,    parser.py)         │        ▼
               lexer.py)                             │  render/ansi.py, render/html.py,
                                                       │  web/renderer.py
                                                       │        │
                                                       │        ▼
                                                       │  ANSI text / HTML file / interactive HTML
                                                       │
                                                       ▼
                                              analyze() = resolve() + type_check() + check_usage()
                                              (resolver.py, typecheck.py, usage.py)
                                                       │
                                                       ▼
                                                SemanticModel (scope tree, typed AST, diagnostics)
                                                       │
                                            ┌──────────┴──────────────────────────────────┐
                                            ▼                                              ▼
                              languages/c/queries.py: completions_at,           analyze_program(model)
                              hover_at, symbols_of, diagnostics_of,             = build_cfg (per function)
                              goto_definition_at, find_references              + build_call_graph
                                            │                                  + analyze_function (dataflow)
                                            │                                              │
                                            │                                              ▼
                                            │                                     ProgramAnalysis (cfgs,
                                            │                                     call_graph, dataflow)
                                            │                                              │
                                            │                              ┌───────────────┼───────────────┐
                                            │                              ▼               ▼               ▼
                                            │                     rename.py        dead_code.py    core/graph_layout.py
                                            │                     (safe rename)    (A6 report)      + render/svg.py
                                            │                                                        (CFG/call-graph SVG)
                                            └──────────────────────────────┬───────────────────────────────┘
                                                                            ▼
                                                       cli/main.py and web/server.py — thin adapters
```

See `docs/program-analysis.md` for the CFG construction algorithm, each
data-flow analysis's direction/lattice/transfer/join, and the call
graph's seven queries.

Everything produces diagnostics into one `DiagnosticCollector`, passed explicitly
through the pipeline (never a global — see `core/diagnostics.py`). Nothing raises to
the caller; `clens.cli.main.main()` is the only place a truly unexpected exception is
ever caught, and that path is meant to be unreachable (R7.1's exit code `2`). The web
server (`web/server.py`) has the same guarantee at its own boundary: a handler that
somehow raises becomes a `500` JSON response, never a crashed process.

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
| `cli/main.py` | All subcommands (`tokens`/`ast`/`highlight`/`check`/`symbols`/`complete`/`hover`/`serve`), `--json`, `-o`, exit codes |

`src/clens/core/**` never imports from `languages/` — enforced by
`tests/unit/test_layering.py` (D12). This is what makes the multi-language bonus
(Java, planned but not started — D13) a new `languages/java/` directory rather than
a rewrite.

### Phase 2 additions

| Module | Responsibility |
|---|---|
| `core/types.py` | The semantic `Type` hierarchy, the conversion rank table, `is_assignable` — see `docs/type-system.md` |
| `core/symbols.py` | `Symbol` (all nine S1.1 fields), `SymbolKind`, `Reference` |
| `core/scopes.py` | `Scope`, `ScopeKind`, `scope_at`/`symbols_visible_at` (D20's offset-based queries) |
| `languages/c/typecheck.py` | `resolve_type_spec` (`TypeSpec` → `Type`) and the whole expression-typing walk (`type_check`) |
| `languages/c/resolver.py` | Two-pass name resolution: `scan_declarations` (Pass 1), `resolve` (Pass 1 + Pass 2) — see `docs/semantic-analysis.md` |
| `languages/c/usage.py` | The crude use-before-init / unused-variable checks (S6.3) |
| `languages/c/semantic.py` | `SemanticModel`, `analyze()` — the Phase 2 entry point, mirroring `parse()` |
| `languages/c/queries.py` | The one query layer (D23): `completions_at`, `hover_at`, `symbols_of`, `diagnostics_of`, plus `scope_to_dict`/`symbol_to_dict` for the CLI and web JSON shapes |
| `web/renderer.py` | The interactive HTML renderer (`data-*` offsets, no document shell) — separate from `render/html.py`, which stays frozen and JS-free |
| `web/server.py` | stdlib `http.server` backend: `GET /`, `GET /static/*`, `POST /api/{analyze,complete,hover,cfg,callgraph,dead-code}` (the last three added in Phase 3) |
| `web/static/` | `index.html`, `app.js`, `style.css` — the vanilla-JS front end (no framework, no build step) |

`core/types.py`, `core/symbols.py`, and `core/scopes.py` are core (language-
agnostic). `SemanticModel`, `resolve_type_spec`, and everything in
`languages/c/queries.py` live in `languages/c/` instead, even though some of
the course document's own illustrative snippets show them as `core/*` —
each embeds or is parameterized over the C-specific AST (`ast.Program`,
`TypeSpec`), so putting them in `core/` would violate the same
core-never-imports-`languages/` rule Phase 1 established. `scope_at` and
`symbols_visible_at` are the one exception that *does* stay in `core/`:
they operate on a plain `Scope`, not a `SemanticModel`, so nothing about
them is C-specific.

### Phase 3 additions

| Module | Responsibility |
|---|---|
| `core/cfg.py` | `BasicBlock`, `ControlFlowGraph`, `EdgeLabel` — language-agnostic CFG structures (A1.2-A1.4) |
| `core/dataflow.py` | The generic worklist fixed-point solver (D26), parameterized by direction/join/transfer/boundary/initial |
| `core/graph.py` | `DirectedGraph`: adjacency both ways, BFS reachability, Tarjan SCC — language-agnostic, reused by the CFG renderer too |
| `core/graph_layout.py` | Pure layered-layout geometry (rank by BFS depth, center each rank, curve back-edges) — no I/O, feeds `render/svg.py` |
| `render/svg.py` | Emits SVG from a `Layout`, using `core/theme.py` colors; serves both the CFG and call-graph panes |
| `languages/c/cfg_builder.py` | Builds one CFG per function body (A1.1, A8.1), plus `render_cfg_text`/`cfg_layout`/`describe_node` |
| `languages/c/analyses.py` | The three required data-flow analyses (A2.1-A2.3) plus the reaching-definitions bonus, each ~15 lines of configuration over `core/dataflow.py` |
| `languages/c/call_graph.py` | `build_call_graph` (A3.1-A3.3) and the seven A3.5 queries, layered over `core/graph.py` |
| `languages/c/program_analysis.py` | `ProgramAnalysis`/`analyze_program()` (D25) — the Phase 3 sibling of `SemanticModel`, built only on demand |
| `languages/c/queries.py` (extended) | `goto_definition_at`, `find_references`, `find_references_by_name` (A4), following the §6.3 JSON shape exactly |
| `languages/c/rename.py` | Scope-aware safe rename (A5): conflict/shadow checks against the scope tree, unified diff, atomic apply |
| `languages/c/dead_code.py` | `find_dead_code` — all five A6 categories, combining CFG, call graph, and liveness results |

`core/cfg.py`, `core/dataflow.py`, `core/graph.py`, and
`core/graph_layout.py` stay language-agnostic for the same reason as
every other `core/` module: `switch`/`goto`/labels are out of this C
subset (`docs/known-limitations.md`), so every CFG built from this AST
happens to be reducible, but nothing in `core/cfg.py` or
`core/dataflow.py` assumes that — a second language plugs in the same
way Phase 1/2's core modules already do.

Go-to-definition and find-all-references (A4.1-A4.2) needed almost no
new machinery — `goto_definition_at` is nearly a direct read of
`Symbol.definition_loc`, and `find_references` is nearly a direct read of
`Symbol.references`, both already populated by Phase 2's resolver. This
is the payoff of building the symbol table with `references` as a first-
class field from the start, rather than deriving it later.

**A7.1/§6.6** (some interactive way to reach the Phase 3 navigation/CFG/
call-graph features) is satisfied by the web UI described in
`docs/bonus/web-ui.md` — stated explicitly here since there is no
separate interface built for it.

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

# Project Overview

## What this is

**c-lens** — a code-aware IDE feature set for a subset of C, built from scratch for
a university Compiler Design course. Three phases:

- **Phase 1 (current)** — Lexer, Parser, AST, syntax highlighter. Output: correctly
  colored source in ANSI and HTML.
- **Phase 2 (later)** — Symbol table, scope resolution, type checking, completion,
  hover, diagnostics.
- **Phase 3 (later)** — CFG, call graph, data-flow analysis, go-to-definition,
  find-references, safe rename, dead code detection.

Only Phase 1 is in scope. See `04-future-phases.md` for what must merely be *not
blocked*.

## Pipeline

```
source ──► Lexer ──► tokens ──► Parser ──► AST ──► Highlighter ──► ANSI / HTML
              │                    │                    │
              └────────────────────┴───► Diagnostics ◄───┘
```

Everything produces diagnostics into one collector. Nothing raises to the caller.

## Target repository layout

```
c-lens/
├── .agents/                     # this folder — agent environment
├── .github/workflows/ci.yml
├── src/clens/
│   ├── core/                    # language-agnostic. NEVER imports languages/
│   │   ├── token.py             # Token, TokenType, span helpers
│   │   ├── diagnostics.py       # Diagnostic, Severity, DiagnosticCollector
│   │   ├── source.py            # SourceFile: text, line index, offset<->line/col
│   │   ├── ast_nodes.py         # Node base, Span, expression/statement bases
│   │   ├── visitor.py           # NodeVisitor
│   │   ├── lexer_base.py        # generic master-regex scanner engine
│   │   ├── parser_base.py       # token cursor, expect/match/sync helpers
│   │   ├── highlight.py         # Category enum, HighlightMap
│   │   └── theme.py             # category -> (ansi, css)
│   ├── languages/c/
│   │   ├── keywords.py
│   │   ├── token_rules.py       # the ordered regex table
│   │   ├── lexer.py
│   │   ├── ast_nodes.py         # C-specific node types
│   │   ├── parser.py
│   │   ├── highlighter.py       # AST walk -> categories
│   │   └── grammar.ebnf         # copy of record; docs/ holds the annotated one
│   ├── render/
│   │   ├── ansi.py
│   │   └── html.py
│   └── cli/
│       └── main.py
├── tests/
│   ├── unit/
│   ├── golden/                  # snapshot tests
│   └── fixtures/                # .c inputs (seeded from .agents/fixtures)
├── docs/
├── tools/                       # first/follow generator, etc.
├── Dockerfile
├── .dockerignore
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

Deviate from this only with a reason recorded in `02-decisions.md`.

## Reference material available locally

`../pycparser/` — a clone sits beside this repo. **Read
`skills/pycparser-reference/SKILL.md` before opening it.** It is useful, and it is
also a trap in three specific ways.

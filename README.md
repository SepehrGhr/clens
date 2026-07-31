# clens

![CI](https://github.com/SepehrGhr/clens/actions/workflows/ci.yml/badge.svg)

**clens** is a code-aware IDE feature set for a subset of C, built from scratch:
a hand-written lexer, a recursive-descent parser, an AST, and a syntax
highlighter that consults the AST instead of just the token stream — so it can
tell a function call apart from a bare variable reference, which a regex-based
highlighter cannot do.

This is **Phase 1** of a three-phase university Compiler Design project. Phase 2
(symbol table, type checking) and Phase 3 (CFG, call graph, refactoring) are out
of scope for now; see `.agents/project/04-future-phases.md` for the hooks Phase 1
already leaves in place for them.

## Pipeline

```
SourceFile ──► Lexer ──► tokens ──► Parser ──► AST ──► Highlighter ──► HighlightMap
                                                                            │
                                                          render/ansi.py ◄──┼──► render/html.py
                                                                            │
                                                            ANSI text        HTML file
```

Every stage feeds one shared `DiagnosticCollector`. Nothing raises past its own
boundary — a file with lexical or syntax errors still gets highlighted for
everything that *did* parse. See `docs/architecture.md` for the full
module-by-module breakdown and the reasoning behind each design choice.

## Install

```bash
git clone https://github.com/SepehrGhr/clens.git
cd clens
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

Or with Docker (no local Python needed):

```bash
docker build -t clens .
docker run --rm clens --help
```

## Quickstart

```bash
clens tokens <file.c>                                   # dump the token stream
clens ast <file.c>                                      # pretty-print the AST
clens highlight <file.c>                                 # ANSI-colored, to your terminal
clens highlight <file.c> --format html -o out.html        # self-contained HTML file
clens check <file.c>                                      # diagnostics only
```

Every subcommand accepts `--json` for machine-readable output and `-o FILE` to
write to a file instead of stdout. Exit codes: `0` clean, `1` diagnostics with
an error present, `2` internal failure (meant to be unreachable — the tool
never crashes, see `docs/known-limitations.md` and rule 1 in
`.agents/AGENTS.md`).

## Usage, with real output

`clens ast tests/fixtures/valid/factorial.c`:

```
Program
  declarations[0]: FuncDecl(name='factorial')
    return_type: TypeSpec(base='int', struct_name=None, pointer_depth=0, is_const=False, storage=None)
    params[0]:   Param(name='n')
      type: TypeSpec(base='int', struct_name=None, pointer_depth=0, is_const=False, storage=None)
    body:        Block
      body[0]: IfStmt
        condition:   BinaryExpr(op='<=')
          left:  Identifier(name='n', loc=2:9)
          right: IntLiteral(value=1, loc=2:14)
        then_branch: ReturnStmt
          value: IntLiteral(value=1, loc=2:24)
      body[1]: ReturnStmt
        value: BinaryExpr(op='*')
          left:  Identifier(name='n', loc=3:12)
          right: CallExpr(callee='factorial', loc=3:16)
            args[0]: BinaryExpr(op='-')
              left:  Identifier(name='n', loc=3:26)
              right: IntLiteral(value=1, loc=3:30)
```

`clens check` on a file with a syntax error — position, message, and a caret
under the exact offending column, then recovery continues past it:

```
$ clens check tests/fixtures/syntax-errors/missing_expression.c
tests/fixtures/syntax-errors/missing_expression.c:1:9: error: expected expression, got ';'
  1 | int x = ;
    |         ^
$ echo $?
1
```

`clens highlight` renders `int factorial(int n) { ... }` with the function's
own name and its recursive call both colored as `function`, while the plain
variable `n` stays the default `variable` color — the same identifier used two
different ways gets two different colors, because the highlighter walks the
AST, not just the token stream. See the rendered
[`factorial.c` on GitHub Pages](https://sepehrghr.github.io/clens/) (published
by CI on every push to `main`) or `tests/golden/expected/factorial.html`
locally.

## Documentation

| Doc | Contents |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Pipeline, module map, parsing-strategy justification, data structures |
| [`docs/grammar.ebnf`](docs/grammar.ebnf) | The complete EBNF for the implemented C subset |
| [`docs/first-follow.md`](docs/first-follow.md) | FIRST/FOLLOW sets and the documented ambiguity resolutions |
| [`docs/lexical-specification.md`](docs/lexical-specification.md) | Formal regexes per token class, the NFA→DFA→minimization theory, a worked example |
| [`docs/known-limitations.md`](docs/known-limitations.md) | Every excluded C feature, with its reason |
| [`docs/testing.md`](docs/testing.md) | Copy-pasteable instructions to set up, run, and reproduce every test |
| [`docs/team.md`](docs/team.md) | Module ownership split |
| [`docs/third-party.md`](docs/third-party.md) | pycparser, credited as a design reference |
| [`.agents/`](.agents/) | The full agent working environment this project was built from: requirements, decisions, skills |

## Development

```bash
pip install -e . -r requirements-dev.txt
pytest --cov=src/clens --cov-report=term-missing   # tests + coverage
ruff check . && ruff format --check .                # lint
```

Full details in [`docs/testing.md`](docs/testing.md).

---
name: diagnostics
description: The unified LSP-shaped diagnostic system for c-lens — one Diagnostic type for lexer, parser, and later semantic errors, with severity, exact spans, and JSON export. Use whenever touching core/diagnostics.py, adding a new error message anywhere, or working on CLI error output.
---

# Diagnostics

Requirements: R1.5, R3.5, R7.1, decision D11.

## One type, from the start

Lexer errors, parser errors, and (in Phase 2) semantic errors all produce the same
`Diagnostic`. One collector, one sort order, one JSON shape, one renderer.

Shape it like an LSP `Diagnostic` now — Phase 2 requires severity, message, file,
line, column, **and a length to underline the exact offending span**, and Phase 3's
optional LSP-server bonus then becomes nearly free:

```python
@dataclass(slots=True)
class Diagnostic:
    severity: Severity          # ERROR | WARNING | INFO | HINT
    message: str
    file: str
    start: Position             # 1-based line, 1-based column
    end: Position
    code: str | None = None     # e.g. "E001-unterminated-string"
    source: str = "clens"
```

Expose `length` as a property derived from offsets. Keep raw offsets on the object
too — the renderer needs them.

## Collector

`DiagnosticCollector` with `.add()`, `.errors`, `.warnings`, `.has_errors`,
`.sorted()` (by file, then start offset), `.to_json()`, and `.format_pretty()`.

Passed explicitly into the lexer and parser. **Not a module-level global** — the
course document calls out avoidance of unnecessary global mutable state, and a
global makes tests order-dependent.

## Error codes

Assign a stable code to each error class (`E001` onward). Cheap now; makes tests
readable, makes the Phase 2 diagnostics table (thirteen defined rows) drop straight
in, and lets tests assert on a code rather than on message text that will be
reworded.

## Message quality

Graded. State what was expected and what was found:

- `unrecognized character '@'`
- `unterminated string literal`
- `expected expression, got ';'`
- `expected ')' to close parameter list, got '{'`

Not `syntax error`, not `invalid input`.

## Pretty output

For the CLI, render a caret span under the offending source line:

```
main.c:1:6: error: unrecognized character '@'
  1 | int x@ = 5;
    |      ^
```

Use `SourceFile.line_text()` and the diagnostic's offsets. Multi-character spans use
`^~~~`. This costs an hour and is the most visible quality signal in a demo.

## Definition of done

- [ ] One `Diagnostic` type used by lexer and parser alike
- [ ] Every error carries an exact start and end, verified by a test
- [ ] Collector is injected, never global
- [ ] `--json` output is stable and tested against a golden file
- [ ] Pretty format renders correctly for tabs, CRLF, and end-of-line positions

---
name: diagnostics
description: The unified LSP-shaped diagnostic system for c-lens across all phases — one Diagnostic type for lexer, parser, and semantic errors, the course document's thirteen required rows, error codes, and no-cascade discipline. Use whenever touching core/diagnostics.py or adding any error message anywhere.
---

# Diagnostics

Requirements: R1.5, R3.5, S6.1–S6.3, S9.2. Decision: D11.

## One type, all phases

Lexer, parser, and semantic errors all produce the same `Diagnostic`. One collector,
one sort order, one JSON shape, one renderer. The Phase 1 type already has every
field Phase 2 needs — see `project/07-phase1-interfaces.md`. **Do not create a
`SemanticError` class.**

Add one helper rather than inlining the conversion at forty call sites:

```python
def diagnostic_from_span(severity, message, file, span, source_file, code=None) -> Diagnostic
```

`Span` has offsets and a *start* line/column but no end line/column; derive the end
via `SourceFile`.

## The thirteen required rows (S6.1)

The course document's §5.5 table. Rows 1–4 exist from Phase 1 — unify, do not
duplicate.

| # | Code | Phase | Class | Severity |
|---|---|---|---|---|
| 1 | `E001` | Lexer | Unrecognized character | Error |
| 2 | `E002` | Lexer | Unterminated string literal | Error |
| 3 | `E010` | Parser | Unexpected token | Error |
| 4 | `E011` | Parser | Missing closing delimiter | Error |
| 5 | `S001` | Semantic | Undefined symbol | Error |
| 6 | `S002` | Semantic | Type mismatch in assignment | Error |
| 7 | `S003` | Semantic | Type mismatch in function call | Error |
| 8 | `S004` | Semantic | Duplicate declaration | Error |
| 9 | `S005` | Semantic | Wrong number of arguments | Error |
| 10 | `S006` | Semantic | Return type mismatch | Error |
| 11 | `S007` | Semantic | Variable shadows outer | **Warning** |
| 12 | `S008` | Semantic | Use before initialization | **Warning** |
| 13 | `S009` | Semantic | Unused variable | **Info** |

Severities are from the document; do not "improve" them. One test per row asserting
both the code and the severity, so the rubric is auditable by grep.

Codes beyond the table (narrowing conversion, bad member operator, calling a
non-function) continue the `S0xx` block. Keep a registry in one module so numbers
are not reused.

## No cascading (S9.2)

The single most visible quality signal. An undefined symbol used five times is
**one** diagnostic.

Mechanism: unresolved names and `ErrorExpr` nodes type as `UnknownType`, which is
compatible with everything and suppresses downstream reports (D17). Additionally:

- Report an undefined symbol once per unique name per scope, not per use.
- If a call's arity is wrong, report that and skip per-argument checks.
- Never report anything inside an `ErrorExpr` / `ErrorStmt` region — the parser
  already did.

Write the test: one undefined name used five times → exactly one diagnostic.

## Rows 12 and 13 are deliberately crude here (S6.3)

Proper use-before-initialization needs the Phase 3 CFG and definite-assignment
analysis; proper unused-variable needs liveness. Phase 2 does the cheap version off
`is_initialized` and `is_used`:

- **Row 12**: a read of a local with no prior write *in the same block*. This misses
  the branch case the document illustrates (`if (c) { x = 42; } printf(x);`) — that
  is exactly what Phase 3 upgrades. Say so in `docs/known-limitations.md`.
- **Row 13**: a symbol whose `references` list contains no reads. Skip parameters
  (unused parameters are normal in C) and globals.

## Message quality

Graded. Name the thing, give both locations where two are involved:

- `undefined symbol 'coutn'`
- `cannot assign 'char*' to 'int'`
- `conversion from 'double' to 'int' may lose precision`
- `expected 1 argument, got 2`
- `declaration of 'x' shadows an outer declaration at 3:9`
- `member access on pointer; did you mean '->'?`

Not `type error`, not `invalid`.

## Definition of done

- [ ] One `Diagnostic` type across all three phases
- [ ] All thirteen rows produced, one test each asserting code and severity
- [ ] No-cascade test passes
- [ ] Code registry in one module, no reuse
- [ ] `clens check` runs all three phases, sorted and deduplicated
- [ ] `--json` output stable, pinned by a golden file

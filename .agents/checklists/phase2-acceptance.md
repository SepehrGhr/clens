# Phase 2 Acceptance Checklist

Walk top to bottom before declaring Phase 2 done. Then re-walk
`checklists/phase1-acceptance.md` — it is a regression gate.

## Regression

- [x] Every item in `checklists/phase1-acceptance.md` still passes
- [x] `clens highlight --format html` output byte-identical to Phase 1; golden green
- [x] No JavaScript in `render/html.py` output
- [x] Coverage still ≥ 80%

## Robustness

- [x] No input crashes the semantic analyzer: empty file, comments only, a file that
      fails to parse entirely, unbalanced braces, `typedef`, random bytes
- [x] A file full of `ErrorExpr` / `ErrorStmt` regions analyzes without extra
      diagnostics and without a crash
- [x] One undefined symbol used five times → exactly one diagnostic
- [x] Wrong arity does not also emit per-argument type errors

## Symbol table

- [x] All nine S1.1 fields present and populated
- [x] `references` complete, with read/write distinction
- [x] Scope tree correct for global, function, block, for-init, struct
- [x] Struct scopes excluded from lexical lookup
- [x] `scope_at` correct at first char, last char, and one past the end of a scope
- [x] `SemanticModel` survives analysis and is queryable

## Resolution

- [x] Forward function call resolves; forward *local* reference errors
- [x] Mutual recursion resolves
- [x] Shadowing warning names both locations
- [x] Duplicate declaration fires in the same scope only
- [x] Prototype + matching definition merges; mismatched signature errors

## Types

- [x] Every `Expr` in every valid fixture has a non-`None` `type_annotation`
- [x] Conversion rank table fully tested
- [x] `UnknownType` absorbs in both directions
- [x] **The four golden examples from S4.7 pass with exact severities**
      (warning, error, error, error)
- [x] Swapped `.` / `->` produce their own distinct messages

## Completion and hover

- [x] All four contexts detected; comments and strings suppress completion
- [x] Member completion works on a complete parse **and** on `p.` mid-typing
- [x] S5.6 golden case returns exactly `x : int` and `y : int`
- [x] Argument-list completion re-ranks by expected parameter type
- [x] Ranking: exact prefix > case-insensitive > fuzzy; local beats global
- [x] Items carry `label`, `kind`, `detail`, `sortOrder`
- [x] Hover returns signature, enclosing scope, and doc comment

## Diagnostics

- [x] All thirteen S6.1 rows produced; one test each asserting code and severity
- [x] Severities match the document exactly (11 warning, 12 warning, 13 info)
- [x] `clens check` runs all three phases, sorted, deduplicated
- [x] `--json` stable and pinned by a golden file

## Interfaces

- [x] `clens symbols`, `complete`, `hover`, `serve` all work, all support `--json`
- [x] `core/queries.py` is pure and adapter-free; CLI and web are thin
      (lives at `languages/c/queries.py` — see `project/07-phase1-interfaces.md`'s
      note on why; the property itself — pure, no feature logic in either adapter —
      holds)
- [x] Web UI: live re-analysis, diagnostics panel with click-to-jump, symbol tree,
      hover card, completion popup
- [x] All three API endpoints tested via the handler, plus malformed input
- [x] Theme colors provably shared with `core/theme.py`
- [x] **Zero runtime dependencies added**

## Documentation

- [x] `docs/semantic-analysis.md` — scope model, two-pass algorithm, symbol table,
      attribute-grammar framing
- [x] `docs/type-system.md` — hierarchy, conversions, per-node rules, no-cascade
- [x] `docs/known-limitations.md` — all five Phase 2 entries appended
- [x] README — new commands, four screenshots, updated pipeline diagram
- [x] `docs/testing.md` — new commands, web UI instructions, all verified

## Defense readiness

- [ ] Both members can explain why two passes are needed, with the C example
- [ ] Both can explain why `Type` is separate from `TypeSpec`
- [ ] Both can explain `UnknownType` and the no-cascade design
- [ ] Both can explain which properties cannot be expressed in a CFG and why that
      forces semantic analysis to exist
- [ ] Both can trace `int y = factorial("hello");` end to end through every module
- [ ] Both can demo the web UI without notes

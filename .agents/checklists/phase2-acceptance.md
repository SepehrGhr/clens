# Phase 2 Acceptance Checklist

Walk top to bottom before declaring Phase 2 done. Then re-walk
`checklists/phase1-acceptance.md` — it is a regression gate.

## Regression

- [ ] Every item in `checklists/phase1-acceptance.md` still passes
- [ ] `clens highlight --format html` output byte-identical to Phase 1; golden green
- [ ] No JavaScript in `render/html.py` output
- [ ] Coverage still ≥ 80%

## Robustness

- [ ] No input crashes the semantic analyzer: empty file, comments only, a file that
      fails to parse entirely, unbalanced braces, `typedef`, random bytes
- [ ] A file full of `ErrorExpr` / `ErrorStmt` regions analyzes without extra
      diagnostics and without a crash
- [ ] One undefined symbol used five times → exactly one diagnostic
- [ ] Wrong arity does not also emit per-argument type errors

## Symbol table

- [ ] All nine S1.1 fields present and populated
- [ ] `references` complete, with read/write distinction
- [ ] Scope tree correct for global, function, block, for-init, struct
- [ ] Struct scopes excluded from lexical lookup
- [ ] `scope_at` correct at first char, last char, and one past the end of a scope
- [ ] `SemanticModel` survives analysis and is queryable

## Resolution

- [ ] Forward function call resolves; forward *local* reference errors
- [ ] Mutual recursion resolves
- [ ] Shadowing warning names both locations
- [ ] Duplicate declaration fires in the same scope only
- [ ] Prototype + matching definition merges; mismatched signature errors

## Types

- [ ] Every `Expr` in every valid fixture has a non-`None` `type_annotation`
- [ ] Conversion rank table fully tested
- [ ] `UnknownType` absorbs in both directions
- [ ] **The four golden examples from S4.7 pass with exact severities**
      (warning, error, error, error)
- [ ] Swapped `.` / `->` produce their own distinct messages

## Completion and hover

- [ ] All four contexts detected; comments and strings suppress completion
- [ ] Member completion works on a complete parse **and** on `p.` mid-typing
- [ ] S5.6 golden case returns exactly `x : int` and `y : int`
- [ ] Argument-list completion re-ranks by expected parameter type
- [ ] Ranking: exact prefix > case-insensitive > fuzzy; local beats global
- [ ] Items carry `label`, `kind`, `detail`, `sortOrder`
- [ ] Hover returns signature, enclosing scope, and doc comment

## Diagnostics

- [ ] All thirteen S6.1 rows produced; one test each asserting code and severity
- [ ] Severities match the document exactly (11 warning, 12 warning, 13 info)
- [ ] `clens check` runs all three phases, sorted, deduplicated
- [ ] `--json` stable and pinned by a golden file

## Interfaces

- [ ] `clens symbols`, `complete`, `hover`, `serve` all work, all support `--json`
- [ ] `core/queries.py` is pure and adapter-free; CLI and web are thin
- [ ] Web UI: live re-analysis, diagnostics panel with click-to-jump, symbol tree,
      hover card, completion popup
- [ ] All three API endpoints tested via the handler, plus malformed input
- [ ] Theme colors provably shared with `core/theme.py`
- [ ] **Zero runtime dependencies added**

## Documentation

- [ ] `docs/semantic-analysis.md` — scope model, two-pass algorithm, symbol table,
      attribute-grammar framing
- [ ] `docs/type-system.md` — hierarchy, conversions, per-node rules, no-cascade
- [ ] `docs/known-limitations.md` — all five Phase 2 entries appended
- [ ] README — new commands, four screenshots, updated pipeline diagram
- [ ] `docs/testing.md` — new commands, web UI instructions, all verified

## Defense readiness

- [ ] Both members can explain why two passes are needed, with the C example
- [ ] Both can explain why `Type` is separate from `TypeSpec`
- [ ] Both can explain `UnknownType` and the no-cascade design
- [ ] Both can explain which properties cannot be expressed in a CFG and why that
      forces semantic analysis to exist
- [ ] Both can trace `int y = factorial("hello");` end to end through every module
- [ ] Both can demo the web UI without notes

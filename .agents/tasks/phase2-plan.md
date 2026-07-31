# Phase 2 Task Plan

Same discipline as Phase 1: work top to bottom, one or two commits per task, tick
the box in the same commit. Target **40–50 commits**.

Legend: `→ skill` = read first. `→ S#` = requirement IDs.

Before Stage 0: read `project/07-phase1-interfaces.md` end to end. Phase 2 plugs
into every name in it.

---

## Stage 0 — Carry-over and gap repair (≈5 commits)

- [x] **P0.1** Drop in the Phase 2 agent environment; commit it.
- [x] **P0.2** Run `pytest` and walk `checklists/phase1-acceptance.md`. Everything
      must still be green **before** any Phase 2 code. Fix anything that is not.
- [x] **P0.3** Add `MemberExpr.member_span: Span` — parser, node, tests, and the
      golden AST snapshot. → `project/07-phase1-interfaces.md` gap 1
- [x] **P0.4** Add `CallExpr.callee_span: Span`. Same treatment. → gap 2
- [x] **P0.5** Add `diagnostic_from_span(...)` helper to `core/diagnostics.py`, and
      a `SEMANTIC` error-code block (`S001`…). Retrofit nothing in Phase 1 — just
      make the helper available. → `skills/diagnostics`

## Stage 1 — Semantic types (≈6 commits)

→ `skills/type-system`.

- [x] **P1.1** `core/types.py`: `Type` base, `PrimitiveType`, `PointerType`,
      `ArrayType`, `StructType`, `FunctionType`, `UnknownType`. Frozen, structurally
      compared, with a readable `__str__` (`"int"`, `"char*"`, `"(int) -> int"`) —
      that string is what hover and completion `detail` show. → S4.1, D16
- [x] **P1.2** Rank table and `usual_arithmetic_conversion(a, b) -> Type`. → D18
- [x] **P1.3** `is_assignable(target, source) -> AssignResult` returning
      ok / warn-narrowing / error, so callers do not re-derive severity. → S4.5
- [x] **P1.4** `resolve_type_spec(spec, scope) -> Type` — bridges syntactic to
      semantic, resolving `struct Point` against the scope. → D15
- [x] **P1.5** Wire `Expr.type_annotation`'s forward reference to the real `Type`
      under `TYPE_CHECKING`; remove the `# noqa: F821`.
- [x] **P1.6** Tests: every conversion pair in the rank table, pointer rules,
      `unknown` absorbing everything (D17), `__str__` for every variant.

## Stage 2 — Symbol table and scopes (≈6 commits)

→ `skills/symbol-table`.

- [x] **P2.1** `core/symbols.py`: `SymbolKind`, `Symbol` with **all nine** S1.1
      fields, `Reference`. → S1.1
- [x] **P2.2** `Scope`: kind, parent, children, ordered symbol map, covered span.
      `declare()`, `lookup_local()`, `lookup()`. → S1.2
- [x] **P2.3** `scope_at(offset)` and `symbols_visible_at(offset)`. → S1.4, D20
      Signature is `(root: Scope, offset)`, not `(model, offset)` as the skill's
      illustrative snippet shows: `SemanticModel` embeds the C-specific AST and
      cannot live in core, so these stay pure core functions over `Scope`
      directly. `analyze()`'s caller (or Stage 5's `core/queries.py`) passes
      `model.global_scope`.
- [x] **P2.4** `SemanticModel`: global scope, scope tree, flat symbol index,
      annotated AST. → D19
      Lives in `languages/c/semantic.py`, not `core/`: it embeds `ast.Program`
      (C-specific), same layering reason as `resolve_type_spec`.
- [x] **P2.5** Tests for nesting, shadowing lookups, offset queries at scope
      boundaries (first char, last char, one past the end).
- [x] **P2.6** `clens symbols <file>` CLI command + `--json`. → S8.1
      Landed here, after Stage 3's `analyze()`, per the deferral decided with
      the user back in Stage 2.

## Stage 3 — Name resolution (≈6 commits)

→ `skills/name-resolution`.

- [x] **P3.1** Pass 1 — declaration scan: functions, prototypes, structs, globals
      into the global scope. → S2.1
- [x] **P3.2** Pass 2 — scope construction while walking bodies: function scope
      holds params, `Block` opens a scope, `ForStmt` opens a scope for its init
      declarations (**remember `init` can be a list**). → S2.2
- [x] **P3.3** Reference resolution: `Identifier`, `CallExpr.callee`, and struct tag
      references. Populate `references`, set `is_used`. → S3.3
      P3.2 and P3.3 landed together: scope construction and reference
      resolution are the same tree walk, not separable steps.
- [x] **P3.4** Diagnostics: undefined symbol (S6.1 row 5), duplicate declaration
      (row 8), shadowing warning (row 11). → S3.1, S3.2
- [x] **P3.5** Prototype-then-definition must not fire duplicate-declaration;
      mismatched signatures between them must. Test both.
- [x] **P3.6** Tests: forward reference, mutual recursion, shadowing at three
      depths, redeclaration in the same scope vs an inner one, `ErrorStmt` regions
      skipped silently.

## Stage 4 — Type checking (≈7 commits)

→ `skills/type-system`.

- [x] **P4.1** Expression typing walk: literals, identifiers, unary, binary,
      ternary, assignment, index, sizeof. Every node annotated. → S4.1–S4.3
- [x] **P4.2** `MemberExpr`: resolve the field against the struct's scope; `.` on a
      pointer and `->` on a non-pointer are errors with distinct messages.
- [x] **P4.3** `CallExpr`: arity check (row 9), per-argument type check (row 7),
      calling a non-function, calling an undefined function. → S4.4
- [x] **P4.4** Assignment checking, including the narrowing warning. → S4.5
- [x] **P4.5** Return checking against the enclosing function, including `void`
      returning a value and a non-void with a bare `return`. → S4.6
      P4.1-P4.5 landed as one commit: `_TypeChecker` in `languages/c/typecheck.py`
      is a single cohesive walk over the already name-resolved `SemanticModel`,
      not five separable pieces. Ternary mismatch also got its own code
      (S013, TERNARY_TYPE_MISMATCH) since the skill explicitly calls it an
      error, alongside narrowing (S010), bad member access (S011, covering
      both swapped operators and unknown fields), and non-callable (S012).
      Binary/unary/index operand combinations the course document doesn't
      explicitly call out (e.g. `struct + int`, indexing a non-array) degrade
      to `unknown` silently rather than inventing new diagnostics.
- [x] **P4.6** **The four golden examples from S4.7**, as one test file, asserting
      exact severities: warning, error, error, error.
- [x] **P4.7** No-cascade test: a file with one undefined symbol used five times
      produces exactly one diagnostic. → S9.2

## Stage 5 — Completion and hover (≈6 commits)

→ `skills/completion-engine`.

- [x] **P5.1** `core/queries.py` with `completions_at`, `hover_at`, `symbols_of`,
      `diagnostics_of`. Pure functions over a `SemanticModel`. → D23
      Lives in `languages/c/queries.py`, not `core/`: every function takes a
      `SemanticModel`, which embeds the C AST — same layering reason as
      `SemanticModel` and `resolve_type_spec`. `SemanticModel` also gained
      `tokens` and `diagnostics` fields (07-phase1-interfaces.md updated in
      the same commit): completion/hover need the full trivia-inclusive
      token stream, and `diagnostics_of` needs somewhere to read from.
- [x] **P5.2** Context detection from the token preceding the cursor: member,
      general, argument-list. `::` documented N/A. → S5.2
      Token-based throughout (not AST-based): `p.` with nothing typed after
      is a syntax error, and that's the normal mid-typing state.
- [x] **P5.3** Member completion, including the S5.6 golden example (with
      `struct Point p;`, not the initializer-list form — see the note in S5.6).
- [x] **P5.4** General scope completion + parameter-type-guided completion inside an
      argument list. → S5.2
- [ ] **P5.5** Ranking: prefix, then fuzzy, with scope-distance tie-breaks; emit
      `label` / `kind` / `detail` / `sortOrder`. → S5.4, S5.5, D24
- [ ] **P5.6** Hover: signature, enclosing scope, and attached doc comment from the
      retained comment tokens. → S7

## Stage 6 — Diagnostics completion (≈4 commits)

→ `skills/diagnostics`.

- [ ] **P6.1** Crude use-before-initialization (row 12) and unused variable
      (row 13), from `is_initialized` / `is_used`. → S6.3
- [ ] **P6.2** Audit all thirteen rows against the table; one test per row asserting
      severity and code. → S6.1
- [ ] **P6.3** `clens check` now runs lexer + parser + semantic in one pass, sorted,
      deduplicated. → S8.1
- [ ] **P6.4** `clens complete` and `clens hover` CLI commands + `--json`. → S8.1

## Stage 7 — Web UI (≈7 commits)

→ `skills/web-ui`.

- [ ] **P7.1** `web/renderer.py` — an interactive HTML renderer emitting
      `data-*` attributes per token span. **Separate from `render/html.py`**, which
      stays frozen and JS-free. → S8.3
- [ ] **P7.2** `web/server.py` — stdlib `http.server`, JSON endpoints
      `/api/analyze`, `/api/complete`, `/api/hover`. Thin adapters over
      `core/queries.py`. → D22, D23
- [ ] **P7.3** `web/static/index.html` + `app.js` + `style.css` — side-by-side
      editor and rendered pane, debounced re-analysis.
- [ ] **P7.4** Panels: diagnostics list (click to jump), symbol tree, hover card.
- [ ] **P7.5** Completion popup at the caret, triggered by typing and by Ctrl+Space.
- [ ] **P7.6** `clens serve [--port]` command; tests for every endpoint via the
      handler directly, no live socket.
- [ ] **P7.7** Screenshots into `docs/images/`, embedded in the README.

## Stage 8 — Docs and gate (≈5 commits)

- [ ] **P8.1** `docs/semantic-analysis.md` — scope model, resolution algorithm,
      symbol table structure. → deliverable
- [ ] **P8.2** `docs/type-system.md` — the type lattice, conversion table, checking
      rules, and the attribute-grammar framing the course document asks for.
- [ ] **P8.3** `docs/known-limitations.md` — append Phase 2 entries (S4.8 N/A,
      S5.2 `::` N/A, S6.3 crude rows, the S5.6 fixture deviation).
- [ ] **P8.4** README: new commands, web UI screenshots, updated pipeline diagram.
      `docs/testing.md` updated with the new commands.
- [ ] **P8.5** Coverage back to ≥80%; walk `checklists/phase2-acceptance.md` **and**
      re-walk `checklists/phase1-acceptance.md`. Only then report Phase 2 complete.

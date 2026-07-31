# Phase 2 Written Deliverables

Appends to `05-deliverables.md`. Same principles: English, synced with the code in
the same commit, framed as decisions rather than omissions.

## D9 — `docs/semantic-analysis.md`
- The scope model: which constructs open scopes, and why struct scopes sit off the
  lexical chain.
- The two-pass algorithm and why C requires it (forward references, mutual
  recursion).
- Symbol table structure, with all nine fields and what each is for.
- The shadowing rule and the duplicate-declaration rule.
- Worked example: the scope chain for `factorial.c`, in the tree format the course
  document uses in §5.1.1.

The course document frames semantic analysis as attribute grammars and
context-sensitive properties — use that vocabulary. Say explicitly which properties
cannot be expressed in the CFG and therefore had to move here. That framing is what
the section is testing.

## D10 — `docs/type-system.md`
- The `Type` hierarchy and why it is separate from the syntactic `TypeSpec`.
- The conversion rank table and the usual-arithmetic-conversion rule.
- Assignability rules, including which mismatches are warnings and which are errors.
- Per-node typing rules, as a table.
- `UnknownType` and the no-cascade design — this is a genuinely good design decision
  and is worth a paragraph of its own.
- Explicit note that C is statically typed, so S4.8's flow-sensitive inference for
  dynamic languages is N/A.

## D11 — `docs/known-limitations.md` (append)
- S4.8 flow-sensitive inference: N/A, target language is statically typed.
- S5.2 `::` scope-resolution completion: N/A, C has no scope-resolution operator.
- S6.3 rows 12 and 13 are block-local approximations pending the Phase 3 CFG. State
  precisely what they miss — the `if`-branch case from the document's own example.
- The S5.6 fixture uses `struct Point p;` rather than the document's
  `struct Point p = {1, 2};`, because initializer lists are out of subset.
- `sizeof` yields `int` rather than `size_t`.

## D12 — README and `docs/testing.md` (update)
- New commands: `symbols`, `complete`, `hover`, `serve`.
- Web UI screenshots (four, per `skills/web-ui`).
- Updated pipeline diagram: source → lexer → parser → **semantic analyzer** →
  highlighter / intellisense.
- `docs/testing.md`: copy-pasteable commands for the new subcommands, and how to
  start and use the web UI.

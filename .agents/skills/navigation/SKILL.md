---
name: navigation
description: Go-to-definition, find-all-references, and the exact JSON response shape for c-lens Phase 3. Nearly free given Phase 2's Symbol.references — use whenever adding queries to languages/c/queries.py or the corresponding CLI/web endpoints.
---

# Navigation

Requirements: A4.1–A4.4.

## This is the cheapest stage in Phase 3

Phase 2 already populated `Symbol.definition_loc` and `Symbol.references` during
resolution, exactly so these features would be lookups rather than analyses. If you
find yourself walking the AST here, stop — the data is already indexed.

Hover (A4.3) was delivered in Phase 2 as S7. Verify it still works, claim it, move on.

## Go-to-definition (A4.1)

```python
def goto_definition_at(model: SemanticModel, offset: int) -> DefinitionInfo | None
```

1. `_identifier_token_at(model.tokens, offset)` — the helper already exists in
   `queries.py`.
2. Resolve it: `scope_at(model.global_scope, offset)` then `lookup(name)`.
3. For a member access (`p.x`), resolve through the struct's scope instead — reuse
   `_struct_scope(model, struct_type)`.
4. Return the symbol's `definition_loc`.

Cursor on the *definition itself* should return that same definition, not `None`.
Small detail; graders try it.

Overridden methods (base + override) — N/A for C.

## Find all references (A4.2)

```python
def find_references(model: SemanticModel, symbol: Symbol) -> list[Reference]
```

It is `symbol.references`. Two additions worth making:

- **Include the definition site**, flagged as such. IDEs do, and a references list
  that omits the declaration looks incomplete.
- **Sort by offset.** Insertion order is resolution order, which is close but not
  guaranteed identical.

Also provide a cursor-driven form (`references_at(model, offset)`) so the CLI and web
UI can go straight from a click.

## The JSON shape (A4.4)

Course document §6.3, exactly:

```json
{
  "symbol": "factorial",
  "kind": "function",
  "type": "(int) -> int",
  "defined_at": { "file": "main.c", "line": 1, "col": 5 },
  "references": [
    { "file": "main.c", "line": 15, "col": 12 },
    { "file": "main.c", "line": 16, "col": 24 }
  ]
}
```

⚠️ The key is **`col`**, not `column`. Phase 2's `Diagnostic.to_dict()` uses
`column`. Do not unify them — match each spec where it is specified. Golden test.

`type` is `str(symbol.type)`, which for a function is already `"(int) -> int"`.

`file` exists for forward compatibility; this project is single-file.

## CLI (A7.2)

```
clens goto-def <file> <line> <col>
clens find-refs <file> <symbol>
```

Note `find-refs` takes a **name**, per the document's example. If the name is
ambiguous (same name in several scopes), list all matches with their definition
sites rather than guessing.

## Definition of done

- [ ] Go-to-definition works for variables, parameters, functions, struct tags, and
      struct fields
- [ ] Cursor on a definition returns that definition
- [ ] References include the definition site, flagged, sorted by offset
- [ ] JSON matches §6.3 exactly, including `col`
- [ ] Ambiguous `find-refs` name lists all matches
- [ ] Both CLI commands work with `--json`

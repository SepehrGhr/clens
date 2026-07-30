---
name: ast-and-visitors
description: How to design c-lens AST nodes and the NodeVisitor base — dataclass nodes, spans on every node, the type_annotation hook for Phase 2, and dispatch that four later passes will reuse. Use whenever touching core/ast_nodes.py, core/visitor.py, or languages/*/ast_nodes.py.
---

# AST and visitors

Requirements: R4.1–R4.4.

## Node design

One `@dataclass(slots=True)` per grammatical construct. Not dicts, not a generic
`Node(kind=...)` bag — Phases 2 and 3 dispatch on type, and typo-safe field access
matters when four passes are reading these.

Base classes in `core/ast_nodes.py`:

```python
@dataclass(slots=True)
class Span:
    start_offset: int
    end_offset: int
    line: int        # 1-based, of the first token
    column: int      # 1-based

@dataclass(slots=True)
class Node:
    span: Span

@dataclass(slots=True)
class Expr(Node):
    type_annotation: "Type | None" = None   # Phase 2 fills this. Untouched in Phase 1.

@dataclass(slots=True)
class Stmt(Node): ...

@dataclass(slots=True)
class Decl(Node): ...
```

C-specific nodes live in `languages/c/ast_nodes.py`. The course document names
`BinaryExpr`, `IfStmt`, `FuncDecl`, `CallExpr`, `ReturnStmt`; the full inventory
follows from the grammar. Cross-check node names and child fields against
pycparser's `_c_ast.cfg` — read `skills/pycparser-reference/SKILL.md` first.

## Spans (R4.2)

Every node carries a span covering the **whole construct**: start = first token's
start, end = last token's end. Line and column are the first token's, 1-based.

Golden test, from the course document section 4.3.2 — the AST for
`return n * factorial(n - 1);` on line 3 must report `n` at `3:12`, `factorial` at
`3:16`, the inner `n` at `3:26`, and `1` at `3:30`.

Do **not** use the location numbers from section 5.1.1 of the course document as
test data. They are internally inconsistent. Section 4.3.2 is the reliable example.

Helper: `join(a: Span, b: Span) -> Span` for building parent spans from children.
Use it everywhere rather than hand-computing.

## Error nodes

`ErrorExpr` and `ErrorStmt` placeholders, each carrying a span. The parser emits
them when recovery kicks in. They let the highlighter color the broken region and
let the AST printer show *where* parsing gave up — much better output than a hole.

## Named fields, not flat lists

`IfStmt(condition, then_branch, else_branch)` — not `IfStmt(children=[...])`.
Phase 3 builds the CFG by walking these named fields; flattening now means
reconstructing structure later.

## NodeVisitor (R4.4)

```python
class NodeVisitor:
    def visit(self, node):
        method = getattr(self, f"visit_{type(node).__name__}", self.generic_visit)
        return method(node)

    def generic_visit(self, node):
        for child in iter_child_nodes(node):
            self.visit(child)
```

Write `iter_child_nodes()` generically off dataclass fields so new node types work
without registration. Test the visitor on its own with a counting subclass — it is
used five times across the project and a bug here is expensive.

Also provide `walk(node)` yielding all nodes, for the cases that want a flat scan.

## Stable identity

Do not rebuild nodes during traversal. Phase 3 rename operates on symbol identity
anchored to node identity; passes must annotate in place, not reconstruct.

## Definition of done

- [ ] One node type per grammar production; names match the grammar
- [ ] Every node has a span; `join()` used for parents
- [ ] `type_annotation` present on `Expr`, defaulting to `None`, unused in Phase 1
- [ ] `ErrorExpr` / `ErrorStmt` exist and carry spans
- [ ] `NodeVisitor` and `walk()` tested independently
- [ ] AST pretty-printer reproduces the section 4.3.2 shape for golden diffing

# Phase 2 Interfaces — the real API surface

Transcribed from the delivered Phase 2 code. **Use these names exactly.** If the
code and this file disagree, the code wins — fix this file in the same commit.

Read this and `07-phase1-interfaces.md` before writing any Phase 3 code.

---

## `clens.core.symbols`

```python
class SymbolKind(Enum):
    VARIABLE = "variable"; FUNCTION = "function"; PARAMETER = "parameter"
    TYPE = "type"; FIELD = "field"      # no CLASS/METHOD in this subset

@dataclass(slots=True, frozen=True)
class Reference:
    span: Span
    is_read: bool = False
    is_write: bool = False              # independent, not exclusive: `x += 1` is both

@dataclass(slots=True)
class Symbol:
    name: str
    kind: SymbolKind
    type: Type
    scope: Scope
    definition_loc: Span
    references: list[Reference] = []
    signature: FunctionType | None = None
    is_initialized: bool = False
    is_used: bool = False
```

`Reference.is_read` / `is_write` were recorded in Phase 2 **specifically** for
Phase 3 liveness and definite-assignment. They are the input to those analyses;
do not re-derive read/write from the AST.

## `clens.core.scopes`

```python
class ScopeKind(Enum): ...              # GLOBAL FUNCTION BLOCK STRUCT FOR_INIT
@dataclass(slots=True)
class Scope: ...                        # kind, parent, children, symbols, span, owner
def scope_at(root: Scope, offset: int) -> Scope
def symbols_visible_at(root: Scope, offset: int) -> list[Symbol]
```

⚠️ Both take a **root Scope**, not a `SemanticModel`. Call as
`scope_at(model.global_scope, offset)`.

## `clens.core.types`

```python
Type; PrimitiveType(name); PointerType(pointee); ArrayType(element, size)
StructType(name, decl); FunctionType(params: tuple, ret); UnknownType()
class AssignResult(Enum): OK NARROWING INCOMPATIBLE
def usual_arithmetic_conversion(a, b) -> Type
def is_assignable(target, source) -> AssignResult
```

All frozen, structurally compared, each with a user-facing `__str__`
(`"char*"`, `"(int) -> int"`).

## `clens.languages.c.semantic`

```python
@dataclass(slots=True)
class SemanticModel:
    program: Program                    # type-annotated AST
    global_scope: Scope
    source: SourceFile
    diagnostics: DiagnosticCollector
    all_scopes: list[Scope] = []
    symbols_by_name: dict[str, list[Symbol]] = {}
    tokens: list[Token] = []            # full stream incl. trivia

def analyze(program, source, diagnostics, tokens=None) -> SemanticModel
```

**`SemanticModel` is the input to every Phase 3 pass.** Phase 3 adds a
`ProgramAnalysis` alongside it (see D25) rather than growing this class.

## `clens.languages.c.queries` — the query layer (D23)

⚠️ **Lives in `languages/c/`, not `core/`.** It takes a `SemanticModel`, which
embeds the C-specific AST, so core layering forbids `core/queries.py`. Phase 3
queries go in this same module.

```python
@dataclass(slots=True, frozen=True)
class CompletionItem: label: str; kind: str; detail: str; sort_order: float
@dataclass(slots=True, frozen=True)
class HoverInfo: signature; scope_description; doc_comment

def symbols_of(model) -> list[Symbol]
def scope_to_dict(scope) -> dict
def symbol_to_dict(symbol) -> dict
def diagnostics_of(model) -> list[Diagnostic]
def completions_at(model, offset: int) -> list[CompletionItem]
def hover_at(model, offset: int) -> HoverInfo | None
```

**All positions are 0-based offsets.** Adapters convert via `SourceFile`. Phase 3
queries follow the same rule — no exceptions.

Useful private helpers already there, worth reusing rather than rewriting:
`_identifier_token_at(tokens, offset)`, `_last_significant_before(tokens, offset)`,
`_scope_distance(from_scope, to_scope)`, `_struct_scope(model, struct_type)`.

## `clens.web.server`

```python
def _build_model(text) -> (source, diagnostics, tokens, program, model)
def handle_analyze(body) -> dict            # {source} -> {html, diagnostics, symbols}
def handle_complete(body) -> dict
def handle_hover(body) -> dict
def _offset_and_model(body) -> (offset|None, model)
_POST_ROUTES = {"/api/analyze": ..., "/api/complete": ..., "/api/hover": ...}
def dispatch_post(path, raw_body) -> (payload, status)
class ClensRequestHandler(BaseHTTPRequestHandler)
def serve(host="127.0.0.1", port=8000)
```

**The pattern to follow for new endpoints:** write a `handle_*(body) -> dict`
plain function, register it in `_POST_ROUTES`, and test it by calling
`dispatch_post` directly — no socket. `dispatch_post` already catches every
exception into a 500, so rule 1 holds automatically.

`_build_model` re-runs the whole pipeline per request (D21). Phase 3's analyses
plug in there.

## Phase 2 facts that shape Phase 3

- **`resolve_type_spec` lives in `languages/c/typecheck.py`**, not core.
- **`usage.py` holds the crude row-12/13 checks.** Phase 3 replaces their logic
  with real definite-assignment and liveness. See D27.
- **Row 12 is currently scoped to scalar primitives only** and misses the
  `if (c) { x = 42; } printf(x);` case. That gap is precisely what Phase 3's
  definite-assignment analysis closes; it is already written up in
  `docs/known-limitations.md` and that entry must be **rewritten**, not appended
  to, when Phase 3 lands.
- **`SizeofExpr` types as `int`**, not `size_t`. Irrelevant to Phase 3.
- **`switch`, `goto`, and labels are out of subset.** The CFG therefore only ever
  handles `if`, `while`, `for`, `return`, `break`, `continue` — no arbitrary
  control transfer, no irreducible graphs. This is why the CFG is tractable, and
  it is worth saying out loud at the defense.
- **Single-file only.** Go-to-definition and find-references return `file` fields
  for forward compatibility, but there is one file. Do not build multi-file.

# Phase 1 Interfaces — the real API surface

Transcribed from the delivered Phase 1 code. **Use these names exactly.** If the
code and this file ever disagree, the code wins — fix this file in the same commit.

Read this before writing any Phase 2 code. Phase 2 plugs into every one of these.

---

## `clens.core.token`

```python
class TokenType(Enum): ...              # KEYWORD, IDENT, INT_LIT, ... INVALID, EOF

@dataclass(slots=True, frozen=True)
class Span:
    start_offset: int    # 0-based, inclusive
    end_offset: int      # 0-based, exclusive
    line: int            # 1-based, of the first character
    column: int          # 1-based

@dataclass(slots=True)
class Token: ...         # type, lexeme, span, is_trivia, ...

def iter_significant(tokens: Iterable[Token]) -> Iterator[Token]
```

`Span` is frozen — build new ones, never mutate.

## `clens.core.source`

```python
@dataclass(slots=True)
class SourceFile:
    # .text, .filename, .line_text(line), offset <-> line/column conversion
```

Phase 2 must not reimplement position math. Everything goes through `SourceFile`.

## `clens.core.diagnostics`

```python
class Severity(Enum):
    ERROR = "error"; WARNING = "warning"; INFO = "info"; HINT = "hint"

@dataclass(slots=True, frozen=True)
class Position:
    line: int; column: int; offset: int

@dataclass(slots=True)
class Diagnostic:
    severity: Severity
    message: str
    file: str
    start: Position
    end: Position
    code: str | None = None
    source: str = "clens"

    @property
    def length(self) -> int
    def to_dict(self) -> dict[str, Any]

@dataclass(slots=True)
class DiagnosticCollector:
    def add(self, diagnostic: Diagnostic) -> None
    @property diagnostics / errors / warnings -> list[Diagnostic]
    @property has_errors -> bool
    def sorted(self) -> list[Diagnostic]
    def to_json(self) -> str
    def format_pretty(self, source: SourceFile) -> str
```

**All Phase 2 semantic errors use this exact type.** Do not create a
`SemanticError` class. `Severity.INFO` already exists, which the "unused variable"
row needs.

Helper you will want, and should add once in `core/diagnostics.py` rather than
inlining everywhere:

```python
def diagnostic_from_span(severity, message, file, span, source_file, code=None) -> Diagnostic
```

`Span` carries offsets and a start line/column but not the *end* line/column, which
`Position` needs — derive it via `SourceFile`.

## `clens.core.ast_nodes`

```python
@dataclass(slots=True)
class Node:
    span: Span
    INLINE_FIELDS: ClassVar[tuple[str, ...]] = ()   # AST printer: render as name=value
    SHOW_LOC: ClassVar[bool] = False                # AST printer: render loc=line:col

@dataclass(slots=True)
class Expr(Node):
    type_annotation: Type | None = None   # <- Phase 2 fills this

class Stmt(Node); class Decl(Node)
class ErrorExpr(Expr): message: str = ""
class ErrorStmt(Stmt): message: str = ""

def join(start: Span, end: Span) -> Span
```

`type_annotation` is currently an unresolved forward reference with a `# noqa: F821`.
When Phase 2 defines `Type`, import it under `TYPE_CHECKING` and remove the noqa.

## `clens.core.visitor`

```python
def iter_child_nodes(node: Node) -> Iterator[Node]   # dataclass-field order; expands lists/tuples
class NodeVisitor:
    def visit(self, node) -> Any                     # dispatches to visit_<ClassName>
    def generic_visit(self, node) -> Any             # recurses into children
def walk(node: Node) -> Iterator[Node]               # depth-first pre-order
```

⚠️ `iter_child_nodes` walks **every** `Node`-typed field, and `TypeSpec` and `Field`
are `Node` subclasses. A naive `walk()` therefore visits `TypeSpec` nodes too. Phase 2
passes must handle or skip them deliberately — do not assume everything reached is an
expression or statement.

## `clens.core.highlight` / `clens.core.theme` / `clens.core.ast_printer`

```python
class Category(Enum): ...            # 12 categories; BOOLEAN currently unreachable
HighlightMap                          # dict[token_index, Category]
class Style: ...                      # frozen; ansi + css per category
def format_ast(root: Node) -> str
```

## `clens.core.lexer_base` / `clens.core.parser_base`

```python
class TokenRule; def compile_master_regex(rules); class LexerEngine
class ParseError(Exception); class ParserBase
```

## `clens.languages.c`

```python
# lexer.py
def tokenize(source: SourceFile, diagnostics: DiagnosticCollector) -> list[Token]
# parser.py
def parse(source: SourceFile, diagnostics: DiagnosticCollector) -> ast.Program
class Parser(ParserBase)
# highlighter.py
def highlight(tokens: list[Token], program: ast.Program) -> HighlightMap
```

Phase 2's entry point mirrors these:

```python
# languages/c/semantic.py
def analyze(program: ast.Program, source: SourceFile,
            diagnostics: DiagnosticCollector) -> SemanticModel
```

## `clens.render`

```python
def render_ansi(source: SourceFile, tokens: list[Token], highlight_map: HighlightMap) -> str
def render_html(...)   # self-contained, embedded CSS, NO JavaScript (R6.2, graded)
```

**Do not add JavaScript, data attributes, or interactivity to `render_html`.** R6.2 is
a graded Phase 1 requirement and a golden test pins its output. The web UI gets its
own renderer — see `skills/web-ui/SKILL.md`.

---

## The C AST node inventory

All in `clens.languages.c.ast_nodes`, all `@dataclass(slots=True, kw_only=True)`.
**Construct with keywords**: `BinaryExpr(span=s, op="+", left=a, right=b)`.

### Program structure
| Node | Base | Fields |
|---|---|---|
| `Program` | `Node` | `declarations: list[Decl]` |
| `TypeSpec` | `Node` | `base: str`, `struct_name: str\|None`, `struct_name_span: Span\|None`, `pointer_depth: int`, `is_const: bool`, `storage: str\|None` |
| `Field` | `Node` | `type: TypeSpec`, `name: str`, `name_span: Span` |

`TypeSpec.base` ∈ `{"void","char","int","float","double","struct"}`.

### Declarations
| Node | Base | Fields |
|---|---|---|
| `FuncDecl` | `Decl` | `return_type: TypeSpec`, `name: str`, `name_span: Span`, `params: list[Param]`, `body: Block\|None` |
| `Param` | `Decl` | `type: TypeSpec`, `name: str`, `name_span: Span`, `array: bool`, `array_size: Expr\|None` |
| `VarDecl` | `Decl` | `type: TypeSpec`, `name: str`, `name_span: Span`, `array: bool`, `array_size: Expr\|None`, `init: Expr\|None` |
| `StructDecl` | `Decl` | `name: str`, `name_span: Span`, `fields: list[Field]` |

`body is None` means prototype. `int a=1, b, c=3;` produces **three sibling
`VarDecl` nodes** with no wrapper — duplicate-declaration checking must cope.

### Statements
| Node | Fields |
|---|---|
| `Block` | `body: list[Stmt \| Decl]` |
| `IfStmt` | `condition`, `then_branch`, `else_branch: Stmt\|None` |
| `WhileStmt` | `condition`, `body` |
| `ForStmt` | `init: Stmt \| list[VarDecl] \| None`, `condition: Expr\|None`, `update: Expr\|None`, `body` |
| `ReturnStmt` | `value: Expr\|None` |
| `BreakStmt`, `ContinueStmt`, `EmptyStmt` | — |
| `ExprStmt` | `expr: Expr` |

⚠️ `ForStmt.init` can be a **list** of `VarDecl`. `for (int i = 0, j = 9; ...)`
declares two names in the for-scope. Handle the list case.

### Expressions
| Node | Fields |
|---|---|
| `Identifier` | `name: str` |
| `IntLiteral` / `FloatLiteral` / `StringLiteral` / `CharLiteral` | `value` |
| `BinaryExpr` | `op: str`, `left`, `right` |
| `UnaryExpr` | `op: str`, `operand`, `prefix: bool` |
| `AssignExpr` | `op: str`, `target`, `value` |
| `TernaryExpr` | `condition`, `then_expr`, `else_expr` |
| `CallExpr` | `callee: str`, `args: list[Expr]` |
| `IndexExpr` | `array`, `index` |
| `MemberExpr` | `obj: Expr`, `member: str`, `arrow: bool` |
| `SizeofExpr` | `target: TypeSpec \| Expr` |

---

## ⚠️ Two gaps found in review — fix in Stage 0

**1. `MemberExpr.member` has no span.** Renaming a struct field, find-all-references
on a field, and member completion all need the span of `x` in `p.x`. It is *not*
safely derivable: `MemberExpr.span` ends at the member, so
`end_offset - len(member)` works for `p.x` but breaks for `p . x` or
`p /*c*/ . x`, both of which this lexer accepts. **Add `member_span: Span`.**

**2. `CallExpr.callee` has no span.** Needed for go-to-definition and
find-all-references on call sites. This one *is* derivable — the callee is the first
token of the call expression, so
`Span(span.start_offset, span.start_offset + len(callee), span.line, span.column)`
is correct. Add `callee_span: Span` anyway for symmetry with `name_span` elsewhere
and so Phase 3 has one obvious way to do it.

Both are small parser edits plus the golden AST snapshot regenerating. Do them
first, in Stage 0, before anything depends on the workaround.

---

## Other Phase 1 facts worth knowing

- **PREPROC tokens are skipped by the parser** (commit `baeb852`). `#include` lines
  never reach the AST. Semantic analysis will never see them; that is fine and
  intended.
- **String and char literal values are stored raw**, escapes not decoded. Type
  checking does not care (`"..."` is `char*` either way), but do not assume
  `len(StringLiteral.value)` is the decoded length.
- **`typedef` is detected and reported as unsupported**, then recovered. The
  semantic analyzer will occasionally see a partial AST where a typedef was skipped.
- **`Category.BOOLEAN` is unreachable** — the subset has no `true`/`false`. Leave it.
- **Error recovery means the AST may contain `ErrorExpr` / `ErrorStmt` anywhere.**
  Every Phase 2 pass must handle them: skip silently, never re-report, never crash.
  This is the single most likely source of Phase 2 crashes.

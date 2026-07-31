# Phase 2 Requirements

Every Phase 2 requirement from the course document, with stable IDs. Phase 1 used
`R` prefixes; Phase 2 uses **`S`** (semantic) so test names stay unambiguous.

Source: course document §5 (Phase Two), plus the always-on requirements in §8–§9.

---

## S1 — Symbol table

### S1.1 Entry fields
The course document specifies exactly nine fields. Treat as a checklist:

| Field | Content |
|---|---|
| `name` | The identifier string |
| `kind` | `variable`, `function`, `type`, `parameter`, `class`, `field`, `method` — C uses variable / function / parameter / type / field |
| `type` | Declared or inferred type, as a type expression |
| `scope` | Reference to the enclosing scope node |
| `definition_loc` | File, line, column of the declaration site |
| `references` | List of all usage locations |
| `signature` | For functions: parameter types and return type |
| `is_initialized` | Whether assigned before use |
| `is_used` | Whether read anywhere in its scope |

`references` and `is_used` are the ones that get skipped. Three Phase 3 features are
built on `references`; populate it correctly now.

### S1.2 Scope hierarchy
Scopes form a tree mirroring block structure. Lookup walks inner → outer. Scope
kinds in C: global, function (holds parameters), block, struct (holds fields),
and the `for`-init scope.

### S1.3 The scope tree survives analysis
Do not discard it after checking. Completion, hover, and every Phase 3 navigation
feature query it by cursor position. It is a returned artifact, not a temporary.

### S1.4 Cursor queries
`scope_at(offset)` and `symbols_visible_at(offset)` must be answerable. This is why
Phase 1 put end offsets on every node.

---

## S2 — Two-pass resolution

### S2.1 Pass 1: declaration scan
Collect all top-level names — functions (including prototypes) and structs and
globals — into the global scope **before** entering any function body.

### S2.2 Pass 2: resolution
Walk bodies and expressions, resolving every name against the fully populated
scope chain.

### S2.3 Why it is required here
C allows calling a function declared later in the file, and mutual recursion. A
single pass would report false "undefined symbol" errors. The course document
names C function prototypes as the motivating case.

---

## S3 — Name resolution rules

### S3.1 Lexical scope resolution
1. Search the innermost scope first.
2. Walk outward through enclosing scopes to global.
3. (OOP languages also search the class scope and superclass chain — N/A for C;
   document as N/A, it costs one line.)
4. Not found anywhere → **"undefined symbol" error** with source location.
5. Found in an outer scope but shadowed by an inner declaration → **"variable
   shadows outer declaration" warning**.

### S3.2 Shadowing is a warning, not an error
Easy to miss; it is an explicit requirement and it appears in the §5.5 diagnostics
table.

### S3.3 Reference recording
Every resolved use appends to the symbol's `references` list, and sets `is_used`
when the use is a read.

---

## S4 — Type system (statically typed language)

### S4.1 Annotate every expression
Every expression AST node gets its computed type in `type_annotation`. Not just the
ones that produce errors — Phase 3 and completion both read these.

### S4.2 Literal typing
`42` ⇒ int; `3.14` ⇒ double; `"hello"` ⇒ char*; `'c'` ⇒ char.

### S4.3 Binary expressions
Apply typing rules per operator, including implicit widening: `int + double` ⇒
double.

### S4.4 Function calls
Verify argument **count** and argument **types** against the declared signature.

### S4.5 Assignments
Verify the right-hand side type is assignable to the left-hand side declared type.

### S4.6 Return statements
Verify the returned type matches the enclosing function's return type. A `void`
function returning a value is an error.

### S4.7 The four golden examples
From the course document §5.3.1. These are the first four type-checker tests:

```c
int x = 3.14;                  /* Warning: double -> int loses precision */
char *s = 42;                  /* Error: cannot assign int to char* */
int y = factorial("hello");    /* Error: argument type mismatch:
                                  expected int, got char* */
void foo() { return 5; }       /* Error: void function returning a value */
```

Note the first is a **warning**, the rest are **errors**. Match that.

### S4.8 Dynamically typed languages
The document requires flow-sensitive inference for Python/JavaScript. **N/A** — our
target is C (decision D1). Record as N/A in the docs; do not build it.

---

## S5 — Auto-completion engine

The course document calls this **"the central deliverable of Phase 2."**

### S5.1 Input
A source file and a cursor position (line + column).

### S5.2 Context detection
Determine the completion context from the token preceding the cursor:

| Preceding | Context |
|---|---|
| `.` or `->` | Member-access completion |
| `::` | Scope-resolution completion (C++/Java) — **N/A for C**, document it |
| Statement start, or after an operator | General scope completion: all visible symbols |
| Inside a function argument list | Parameter-type-guided completion |

### S5.3 Symbol query
Query the symbol table for everything visible at the cursor location.

### S5.4 Ranking
Filter and rank by **prefix match first, then fuzzy match**.

### S5.5 Structured result
Each item carries: `label`, `kind`, `detail` (type or signature), and a
`sortOrder` score.

### S5.6 Golden example — member access
From §5.4:

```c
struct Point { int x; int y; };
struct Point p = {1, 2};
p.|                       /* cursor here */
```

Offers exactly:

| Label | Kind | Detail |
|---|---|---|
| `x` | Field | `int` |
| `y` | Field | `int` |

⚠️ Note this fixture uses an **initializer list** `{1, 2}`, which is excluded from
our subset (`03-c-subset.md`: compound literals and designated initializers are
out). Use `struct Point p;` in the test fixture and record the deviation in
`docs/known-limitations.md`. Do not widen the subset for this.

---

## S6 — Diagnostic system

### S6.1 The thirteen rows
The document's §5.5 table. All must be produced with the stated severity. The first
four already exist from Phase 1 and must be unified, not duplicated.

| # | Phase | Error class | Severity |
|---|---|---|---|
| 1 | Lexer | Unrecognized character | Error |
| 2 | Lexer | Unterminated string literal | Error |
| 3 | Parser | Unexpected token | Error |
| 4 | Parser | Missing closing delimiter | Error |
| 5 | Semantic | Undefined symbol | Error |
| 6 | Semantic | Type mismatch in assignment | Error |
| 7 | Semantic | Type mismatch in function call | Error |
| 8 | Semantic | Duplicate declaration | Error |
| 9 | Semantic | Wrong number of arguments | Error |
| 10 | Semantic | Return type mismatch | Error |
| 11 | Semantic | Variable shadows outer | **Warning** |
| 12 | Semantic | Use before initialization | **Warning** |
| 13 | Semantic | Unused variable | **Info** |

### S6.2 Required fields
Every diagnostic carries severity, message, file, line, column, and **length** — to
underline the exact offending span. Phase 1's `Diagnostic` already has all of these.

### S6.3 Rows 12 and 13 get crude versions now
Proper use-before-initialization and dead-assignment detection needs the Phase 3
CFG and liveness analysis. Phase 2 does the cheap version from `is_initialized` and
`is_used` flags: flag a read of a variable with no prior assignment *in the same
block*, and flag a symbol whose `references` list contains no reads. Both get
upgraded in Phase 3. Document the limitation.

---

## S7 — Hover information

Listed in the course document under §6.3 (Phase 3), but it is the same symbol-table
query as completion `detail`. **Build it here, claim it in Phase 3.**

Given a cursor over a symbol, return: full type signature, enclosing scope, and any
attached documentation comment.

The doc-comment part is why Phase 1 retained comment tokens (R1.8). Attach a
comment to a declaration when it is the nearest preceding comment token with only
whitespace between.

---

## S8 — Interface

### S8.1 CLI additions
- `clens symbols <file>` — dump the symbol table and scope tree
- `clens complete <file> <line> <col>` — completion list
- `clens hover <file> <line> <col>` — hover info
- `clens check <file>` — now includes semantic diagnostics
- `--json` on all of them

### S8.2 Web UI
See decision D22 and `skills/web-ui/SKILL.md`. This is the interactive interface,
and it also satisfies the Phase 3 §6.6 interface requirement.

### S8.3 Phase 1 output is frozen
`clens highlight --format html` must keep producing the exact same no-JavaScript
output (R6.2). The web UI is a separate renderer. A golden test pins this.

---

## S9 — Always-on

### S9.1 Never crash
Unchanged from R9.5, and now harder: the AST may contain `ErrorExpr` / `ErrorStmt`
from Phase 1 recovery, and semantic analysis must handle unresolved types
throughout. Every pass must tolerate an `unknown` type without cascading.

### S9.2 No cascading errors
One undefined symbol must produce **one** diagnostic, not one per use and not a
downstream flood of type errors. Unresolved symbols get the `unknown` type, and
`unknown` is compatible with everything for the purpose of suppressing follow-on
errors.

### S9.3 Phase 1 stays green
`checklists/phase1-acceptance.md` is a regression gate. Every item still passes.

### S9.4 Coverage
≥80% maintained. Phase 1 delivered 99.84%; do not regress it meaningfully.

### S9.5 Commits
Same discipline as Phase 1. Target 40–50 commits for Phase 2.

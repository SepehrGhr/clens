# FIRST/FOLLOW Sets and Ambiguity Analysis

Companion to `docs/grammar.ebnf` (R2.3): FIRST and FOLLOW sets for every non-terminal,
and a written argument that there are no FIRST/FIRST or FIRST/FOLLOW conflicts at
`k=1` — except the ones documented explicitly in §4, which are all resolved by
left-factoring a shared prefix rather than left unresolved.

## 1. Terminal shorthand

To keep the tables readable, terminal groups are abbreviated:

| Shorthand | Terminals |
|---|---|
| `IDENT` | any identifier token |
| `INT` `FLOAT` `STRING` `CHAR` | `INT_LIT` `FLOAT_LIT` `STRING_LIT` `CHAR_LIT` |
| `TYPEKW` | `void char int float double` |
| `STORKW` | `static extern volatile register` |
| a literal like `"if"` or `"+"` | that exact keyword/operator/delimiter lexeme |

## 2. FIRST sets

Each expression precedence level's FIRST set is identical to the level below it,
since every level's production begins by parsing the next-higher-precedence
operand (`docs/grammar.ebnf`'s whole point in being left-recursion-free). That
FIRST set is derived once, at `primary_expr`, and named `FIRST(expr)` below to
avoid repeating a 15-terminal set eleven times.

**`FIRST(expr)`** = `IDENT, INT, FLOAT, STRING, CHAR, "(", "-", "!", "&", "*", "~", "++", "--", "sizeof"`

| Non-terminal | FIRST |
|---|---|
| `program` | `FIRST(external_decl) ∪ {ε}` (may be empty — an empty file) |
| `external_decl` | `TYPEKW, STORKW, "const", "struct"` |
| `param_list` / `param` | `TYPEKW, STORKW, "const", "struct"` |
| `struct_decl` | `"struct"` |
| `field_decl` | `TYPEKW, STORKW, "const", "struct"` |
| `var_decl_stmt` / `declarator` | `TYPEKW, STORKW, "const", "struct"` (declarator itself: `IDENT`) |
| `type_spec` | `TYPEKW, STORKW, "const", "struct"` |
| `storage_qualifier` | `STORKW` |
| `base_type` | `TYPEKW, "struct"` |
| `block` | `"{"` |
| `block_item` | `TYPEKW, STORKW, "const", "struct"` (var_decl_stmt) `∪` `FIRST(statement)` |
| `statement` | `"{", "if", "while", "for", "return", "break", "continue", ";"` `∪ FIRST(expr)` |
| `if_stmt` | `"if"` |
| `while_stmt` | `"while"` |
| `for_stmt` | `"for"` |
| `for_init` | `TYPEKW, STORKW, "const", "struct"` (decl) `∪ FIRST(expr) ∪ {ε}` (empty init) |
| `return_stmt` | `"return"` |
| `expr_stmt` | `FIRST(expr)` |
| `expression` … `unary_expr` | `FIRST(expr)` (all eleven cascade levels — see note above) |
| `postfix_expr` | `FIRST(expr)` |
| `postfix_op` | `"(", "[", ".", "->", "++", "--"` |
| `arg_list` | `FIRST(expr)` |
| `primary_expr` | `IDENT, INT, FLOAT, STRING, CHAR, "("` |

## 3. FOLLOW sets (only where a production has an empty/optional alternative)

FOLLOW only matters for an LL(1) decision when a non-terminal can derive the
empty string, or when an optional trailing clause needs one token of lookahead
to decide "is there more, or not." Every such spot in this grammar:

| Non-terminal / decision point | FOLLOW / lookahead token | Used to decide |
|---|---|---|
| `program` | `EOF` | loop termination |
| `[ assign_op , assignment_expr ]` (in `assignment_expr`) | `assign_op` tokens vs. `FOLLOW(assignment_expr)` = `; ) ] , :` | assignment vs. "just return the ternary" |
| `[ "?" , ... ]` (in `ternary_expr`) | `"?"` vs. `FOLLOW(ternary_expr)` = `; ) ] , : =` and compound-assign ops | ternary vs. "just return the logical-or" |
| binary cascade loops (`{ op , next }`) | that level's operator set vs. `FOLLOW` = whatever can follow the whole expression | continue the loop vs. stop |
| `postfix_expr`'s `{ postfix_op }` | `postfix_op`'s FIRST vs. `FOLLOW(postfix_expr)` | continue the postfix chain vs. stop |
| `[ else , statement ]` (in `if_stmt`) | `"else"` vs. `FOLLOW(if_stmt)` | dangling else — see §4 |
| `[ param_list ]`, `[ arg_list ]` | `")"` vs. `FIRST(param)`/`FIRST(arg)` | empty list vs. at least one |
| `[ for_init ]`, `[ expression ]` in `for_stmt` | `";"`/`")"` vs. `FIRST(...)` | clause present vs. omitted |
| `{ "," , declarator }` | `","` vs. `";"` | more declarators vs. end of statement |
| `{ "*" }` (pointer stars in `type_spec`) | `"*"` vs. `IDENT` (or `")"`, `","` in a param) | more pointer depth vs. done |

In every row, the two token sets are disjoint — no FIRST/FOLLOW conflict at
`k=1`.

## 4. Documented ambiguities and how they're resolved

None of these are left unresolved — each has one deterministic rule, applied
consistently by the recursive-descent structure itself (`languages/c/parser.py`).

### 4.1 Dangling else (the classic one)

`if_stmt = "if" "(" expression ")" statement [ "else" statement ]` — when `else`
could grammatically attach to any enclosing still-open `if`, this grammar (like
C itself) attaches it to the **nearest** one.

This falls out of the recursive-descent structure with no special-casing:
`parse_if_stmt`'s `then_branch = parse_statement()` call returns *before*
`parse_if_stmt` checks for a trailing `"else"`. If `then_branch` was itself an
`if` with no `else`, that inner call already consumed its own `"else"` (if
present) before returning — so by the time the outer `if` looks for `"else"`,
the inner one has already claimed it. Tested in
`tests/unit/test_parser_statements.py::test_dangling_else_binds_to_nearest_if`.

### 4.2 `func_decl` vs. `var_decl_stmt` (shared `type_spec IDENT` prefix)

Both start with `type_spec`, so `FIRST(func_decl)` and `FIRST(var_decl_stmt)`
are identical — a naive table-driven LL(1) parser would see a conflict here.
The resolution is left-factoring, standard practice for removing exactly this
class of conflict: parse the common prefix (`type_spec` then `IDENT`) once,
then make the decision on the **next** token — `"("` means `func_decl`,
anything else means `var_decl_stmt`. One token of lookahead *after* the shared
prefix, not a FIRST/FIRST conflict.

### 4.3 `struct_decl` vs. a `struct`-typed declaration

`struct_decl = "struct" identifier "{" ...` and a `struct Point p;` variable
declaration both start with `"struct" identifier`. Same resolution as §4.2:
parse `"struct" identifier` once, then look at the next token — `"{"` means
`struct_decl`, anything else means the type-spec continues normally (pointer
stars, then the declared name). Implemented as a two-token lookahead in
`Parser.parse_external_decl` (`self.peek(2).lexeme == "{"`) before committing to
either path.

### 4.4 `sizeof(type)` vs. `sizeof(expr)`

`sizeof` followed by `"("` is ambiguous until the token *after* `"("` is seen:
`sizeof(int)` is a type, `sizeof(x)` is a parenthesized expression. Resolved by
one token of lookahead: if the token after `"("` starts a `type_spec`
(`TYPEKW`, `STORKW`, `"const"`, or `"struct"`), parse a type; otherwise fall
through to ordinary unary-expression parsing, which already handles
`"(" expression ")"` in `primary_expr`.

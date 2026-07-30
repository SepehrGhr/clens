# Decisions (ADRs)

Settled. Do not revisit without asking the user. Each entry says what was chosen,
what was rejected, and why — so that a later "wouldn't it be simpler to…" can be
answered without redoing the analysis.

---

**D1 — Target language: a subset of C.**
The course document's own EBNF fragment, every worked example across all three
phases, and the type-checking examples are C. Static typing makes Phase 2 far
cheaper than the flow-sensitive inference the document demands for dynamic
languages. Rejected: Python (inference burden, INDENT/DEDENT lexing), Java (forces
class scopes and virtual-dispatch call graphs in Phase 3), a toy language
(evaluators supply their own real files).

**D2 — Implementation language: Python 3.11+.**
Fastest to write; `re`, `dataclasses`, `difflib`, `json` cover most needs; the
richest reference material for this specific project is Python. Core library keeps
**zero runtime dependencies**.

**D3 — Subset boundaries: see `03-c-subset.md`.**
`typedef` is excluded, and that is a load-bearing decision: with `typedef`, C's
grammar is context-sensitive (the "lexer hack" — the lexer must consult the symbol
table to know whether an identifier is a type name). Without it, `IDENT` is
unambiguous and the grammar stays cleanly LL(1). This is documented as a deliberate
design decision in `docs/known-limitations.md`, not hidden.

**D4 — pycparser is a reference, not a dependency.**
It is architecturally what we are building (v3.00 replaced PLY with a hand-written
lexer and recursive-descent parser, pure Python, BSD). It still cannot be used as
our engine: it discards comments, has no error recovery, and gives no end positions.
Full analysis and a list of what *is* safe to lift: `skills/pycparser-reference/SKILL.md`.

**D5 — Lexer: single master regex with named groups.**
Ordered alternation, longest-first, driven by `re.finditer`. Maximal munch falls
out of ordering. The document explicitly permits a regex library. Rejected:
char-by-char DFA (2× the code, more bugs, no marks unless the rubric demands a real
DFA — see the open question in `05-deliverables.md`), and PLY (dependency, weakens
the "we built it" story). The formal regex + NFA→DFA→minimization writeup is a
*separate written deliverable* and is produced regardless.

**D6 — Parser: hand-written recursive descent, LL(1).**
The document lists it first and names Clang/GCC/rustc as users. Table-driven LALR
gives no usable error recovery, cannot be explained at the defense, and does not
produce the custom AST shapes Phases 2–3 need.

**D7 — Direct AST, no CST.**
The document permits either. A CST doubles node count for zero downstream benefit.

**D8 — AST nodes are `@dataclass(slots=True)`, one class per construct.**
Not dicts. Dispatch is by type via a single `NodeVisitor`.

**D9 — Highlighting via an offset map.**
Flat token list with offsets → AST walk produces `token_index -> category` →
renderer iterates the *original source* by offset. Guarantees byte-faithful output
including trivia, and lets one map feed both renderers. Rejected: AST-walk emitting
spans directly, which loses whitespace and comments since they are not AST nodes.

**D10 — Theme: VS Code Dark+ hex values, in one `theme.py` table.**
Category → (ANSI code, CSS rule). Covers all twelve required categories.

**D11 — Diagnostics use the LSP shape from day one.**
`severity` / `message` / `range{start{line,character},end{...}}` / `source` / `code`.
Phase 2 needs exactly these fields including a span length; Phase 3's optional LSP
server bonus then becomes nearly free. Costs nothing now.

**D12 — `core/` never imports from `languages/`.**
Language-specific data (keywords, token rules, grammar, later type rules) lives in
`src/clens/languages/c/`. Enforced by a test that greps core for forbidden imports.
This is the multi-language bonus, pre-paid.

**D13 — Second language will be Java, added at the very end, not now.**
Same C-family lexer, no preprocessor, no pointers, clean grammar, and it exercises
the OOP scope chain and virtual dispatch the later phases keep referencing. C++
looks cheaper and is not. **Build nothing Java-specific in Phase 1** — only keep the
`core`/`languages` boundary honest.

**D14 — Docker, CI, and the test suite are built during Phase 1.**
They are listed bonuses that cost near-zero early and get skipped when rushed. The
CI badge is a stated requirement for that bonus.

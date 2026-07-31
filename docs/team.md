# Team

**TODO: fill in real names and confirm/adjust the split below before submitting.**
This file is currently a placeholder — see `.agents/skills/git-workflow/SKILL.md`
§"Authorship across two members": the grading requirement is commits
**genuinely distributed** across both members, under each person's own git
identity, not just a document describing an intended split.

## Members

| Name | Role |
|---|---|
| TODO | Member 1 |
| TODO | Member 2 |

## Ownership split

A split by pipeline stage, so each half is a coherent, explainable unit at the
defense:

| Area | Modules | Owner |
|---|---|---|
| Lexer | `core/lexer_base.py`, `languages/c/keywords.py`, `languages/c/token_rules.py`, `languages/c/lexer.py`, `docs/lexical-specification.md` | TODO |
| Parser | `core/parser_base.py`, `languages/c/parser.py`, `docs/grammar.ebnf`, `docs/first-follow.md` | TODO |
| AST & visitor | `core/ast_nodes.py`, `core/visitor.py`, `core/ast_printer.py`, `languages/c/ast_nodes.py` | TODO |
| Highlighter & rendering | `core/highlight.py`, `core/theme.py`, `languages/c/highlighter.py`, `render/ansi.py`, `render/html.py` | TODO |
| CLI, diagnostics, DevOps | `core/diagnostics.py`, `core/source.py`, `cli/main.py`, `Dockerfile`, `.github/workflows/ci.yml` | TODO |
| Documentation | `docs/architecture.md`, `docs/known-limitations.md`, `docs/testing.md`, `README.md` | TODO |

Whoever doesn't own a module must still be able to explain it at the defense —
that's the actual point of splitting ownership rather than co-writing
everything (course requirement, restated in
`.agents/skills/git-workflow/SKILL.md`).

## Branching / commit convention

Committing straight to `main` (see `.agents/skills/git-workflow/SKILL.md`
§"Branching" — a two-person project doesn't need long-lived feature branches).
Conventional commit format, scopes: `core`, `lexer`, `parser`, `ast`,
`highlight`, `render`, `cli`, `docs`, `ci`, `docker`, `tests`.

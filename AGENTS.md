# AGENTS.md

Agent instructions for this repository live in **`.agents/`**.

Read `.agents/AGENTS.md` first, then `.agents/tasks/phase1-plan.md`.

Quick facts:
- Project: **c-lens** — compiler front-end and IDE feature set for a subset of C.
- Current scope: **Phase 1 only** (lexer, parser, AST, syntax highlighter).
- Language: Python 3.11+, zero runtime dependencies in the core.
- Reference clone at `../pycparser` — read
  `.agents/skills/pycparser-reference/SKILL.md` before opening it.

Four rules that override anything else:
1. The tool must never crash on any input. Errors become diagnostics.
2. Highlighting must consult the AST, not just tokens.
3. Do not implement Phase 2 or Phase 3 features.
4. Never credit yourself in a commit message, comment, or document.

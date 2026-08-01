# Post-Project Future Work

Phases 1, 2, and 3 are the project. This file records what is deliberately deferred
**past** the project, and exists so nobody implements it mid-Phase-3 by accident.

The user-facing version of this list is `docs/future-work.md` (requirement A10,
decision D30) — write that with full detail per `skills/bonus-docs/SKILL.md`. This
file is the short internal version.

## Deferred, with the reason

| Item | Why deferred | Plugs into |
|---|---|---|
| **Dominator / post-dominator trees** | Bonus, not required. Naive iterative algorithm is ~20 lines and matches Lengauer-Tarjan on graphs this size | `core/cfg.py` |
| **Dominance frontier + SSA form** | Highest-value remaining bonus, and the one most likely to overrun. Frontier is cheap once dominators exist; φ-placement and renaming is the real work | after dominators |
| **Java as a second language** (D32) | Was the cheapest bonus in Phase 1, now the most expensive: needs lexer, grammar, parser, AST, type rules, scope rules, and a class-scope model with virtual dispatch | `src/clens/languages/java/` |
| **LSP server** (D31) | Web UI already satisfies the §6.6 interface requirement, and `pygls` would break the zero-runtime-dependency property | `src/clens/lsp/` |
| **Incremental re-parsing** (D21) | Full re-analysis per keystroke is fast enough at this file size; correctness beat latency | `web/server.py`'s `_build_model` |
| **C preprocessor pass** | Directives are tokenized, never expanded. A real pass needs location mapping back to pre-expansion positions | before the lexer |
| **Multi-file support** | Navigation already carries `file` fields; needs a translation-unit model and cross-file resolution | `languages/c/semantic.py` |

## Do not implement any of these during Phase 3

If a task appears to require one, you have misread it. Ask.

The one thing Phase 3 *does* take from this list is **reaching definitions** (task
Q2.7) — it is one more configuration of the generic solver, roughly fifteen lines,
and doing it while the machinery is fresh costs almost nothing.

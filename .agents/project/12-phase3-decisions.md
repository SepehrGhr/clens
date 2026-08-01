# Phase 3 Decisions (D25 – D32)

Continues `02-decisions.md` (D1–D14) and `08-phase2-decisions.md` (D15–D24).
Settled — do not revisit without asking the user.

---

**D25 — `ProgramAnalysis` is a new artifact alongside `SemanticModel`, not inside
it.** Phase 3 builds CFGs, a call graph, and data-flow results. Putting them on
`SemanticModel` would mean every Phase 2 consumer pays for analysis it does not use,
and `analyze()` would grow a second responsibility.

```python
@dataclass(slots=True)
class ProgramAnalysis:
    model: SemanticModel
    cfgs: dict[str, ControlFlowGraph]     # keyed by function name
    call_graph: CallGraph
    dataflow: dict[str, DataFlowResults]  # keyed by function name
```

Built by `analyze_program(model) -> ProgramAnalysis` in
`languages/c/program_analysis.py`, mirroring `analyze()`'s contract: takes the
collector, never raises, never returns `None`.

**D26 — One generic worklist solver, three analyses.**
`core/dataflow.py` holds a solver parameterized by direction (forward/backward),
join (intersection/union), transfer function, and initial value. Definite
assignment, liveness, and (bonus) reaching definitions are each ~15 lines of
configuration.

This is also the single best thing to show at the defense: the course document
describes data-flow as a fixed-point computation over a lattice, and a generic
solver *is* that abstraction, made concrete. Writing three bespoke loops would
score worse and cost more.

**D27 — Phase 2's crude row-12/13 checks are replaced, not supplemented.**
`languages/c/usage.py` currently approximates use-before-initialization and unused
variables from `Symbol` flags. Phase 3 replaces those implementations with real
definite-assignment and liveness results. Same diagnostic codes (`S008`, `S009`),
same severities — better analysis behind them.

The `docs/known-limitations.md` entry describing the approximation must be
**rewritten** to describe what is now actually done, not appended to. Leaving a
stale limitation claiming a weakness you have since fixed reads badly.

**D28 — Graph rendering is server-generated SVG, hand-emitted.**
No Graphviz binary (not installable in every grading environment), no `networkx`,
no JS graph library — all would break the zero-runtime-dependency claim.

CFGs from this subset are small and, because `goto` and `switch` are out of scope,
always **reducible and structured**. A simple layered layout (rank by BFS depth from
ENTRY, center each rank horizontally, orthogonal edges with a back-edge curve) is
~150 lines and produces a perfectly readable diagram. Call graphs use the same
layered engine.

Emit SVG text from Python. The web UI embeds it directly; the CLI can write it to a
file. Same layout code for both, matching the two-renderers-one-map pattern from
Phase 1.

**D29 — Every bonus gets its own document in `docs/bonus/`.**
One file per bonus, each with the same four sections: **Goal** (what it is and which
course-document bonus item it satisfies), **Motivation** (why it was worth doing
here), **Implementation** (how, with the key design decisions and file pointers),
**Seeing it work** (exact commands, expected output, screenshots where relevant).

`docs/bonus/README.md` indexes them with a status table. Retroactive write-ups
needed for Docker, CI/CD, the test suite/coverage, and the Web UI.

Rationale: bonus credit is only awarded for what a grader can find and verify. A
feature that exists but is undocumented is invisible. These files are also the
natural answer to "tell us what extra you did" at the defense.

**D30 — `docs/future-work.md` records deliberately deferred work.**
Contents: dominator/post-dominator trees, dominance frontier and SSA form, Java as a
second language, LSP server, incremental re-parsing, a C preprocessor pass, and
multi-file support. Each entry: what it is, why it was deferred, rough effort, and
where it would plug into the existing architecture.

This is framing, not an apology. A "deferred with a plan" list demonstrates
architectural command; an unexplained absence looks like an oversight.

**D31 — No LSP server.** The web UI already satisfies the §6.6 interface
requirement, so LSP is pure bonus, and `pygls` is a runtime dependency that would
break the zero-dependency claim in the README. Deferred to `future-work.md`.
`queries.py` stays adapter-free so it remains cheap if ever wanted.

**D32 — Java stays out of Phase 3.** Deferred to `future-work.md`. It was the
cheapest bonus in Phase 1 and is now the most expensive: a second language needs
lexer rules, grammar, parser, AST, type rules, scope rules, and a class-scope model
with virtual dispatch. Only worth it if everything else is finished and polished.

---
name: dataflow
description: The generic worklist data-flow solver and the three required analyses for c-lens Phase 3 — definite assignment, live variables, unreachable code, plus bonus reaching definitions. Use whenever touching core/dataflow.py or languages/c/analyses.py.
---

# Data-flow analysis

Requirements: A2.1–A2.4. Decisions: D26, D27.

## Write one solver, not three (D26)

The course document describes data-flow as a fixed-point computation over a lattice.
A generic solver **is** that abstraction made concrete — it is the single most
defensible artifact in Phase 3, and it makes each analysis ~15 lines. Three bespoke
loops would cost more and score worse.

```python
@dataclass(frozen=True, slots=True)
class Analysis:
    direction: Direction            # FORWARD | BACKWARD
    join: Callable[[list[set]], set]   # intersection (must) | union (may)
    transfer: Callable[[BasicBlock, set], set]
    boundary: set                   # value at ENTRY (forward) / EXIT (backward)
    initial: set                    # value at every other block before iteration

def solve(cfg: ControlFlowGraph, analysis: Analysis) -> dict[BasicBlock, tuple[set, set]]
```

Returns `(in_set, out_set)` per block. Standard worklist: seed all blocks, push all,
pop and recompute, push affected neighbours on change, terminate at fixed point.

Test the solver **standalone on a toy lattice** before wiring any real analysis to
it (Q2.1). A solver bug otherwise looks like three unrelated analysis bugs.

⚠️ **Must-analyses need the right initial value.** Definite assignment initialises
non-entry blocks to the *full* variable set, not the empty set — otherwise
intersection immediately collapses to empty and everything looks uninitialised. This
is the classic bug. Entry gets the boundary value (empty: nothing assigned yet).

## Gen/kill from Phase 2's references (Q2.2)

`Reference` already carries `is_read` and `is_write`, recorded during Phase 2
resolution precisely for this. **Do not re-derive them from the AST.**

Per block, walk its statements' spans and collect the references falling inside:
- `gen` (defs) = symbols with a write
- `use` = symbols with a read, *before* any write in the same block

Order within a block matters for `use`: in `x = x + 1`, `x` is used before it is
defined; in `x = 1; y = x;`, `x`'s def precedes its use.

## The three required analyses

| | Direction | Lattice | Transfer | Join |
|---|---|---|---|---|
| **Definite assignment** (A2.1) | Forward | ⟨2^Vars, ⊇⟩ must | `out = in ∪ defs(b)` | **Intersection** |
| **Live variables** (A2.2) | Backward | ⟨2^Vars, ⊆⟩ may | `in = use(b) ∪ (out − def(b))` | **Union** |
| **Reaching definitions** (bonus) | Forward | ⟨2^Defs, ⊆⟩ may | `out = gen(b) ∪ (in − kill(b))` | **Union** |

State all four columns for each analysis in `docs/program-analysis.md` — A2.4 asks
for exactly this and the document spells them out, so it is clearly assessed.

**Definite assignment** reports a warning at each read of a variable not in the
block's `in` set (accounting for writes earlier in the same block). Golden case:

```c
int x;
if (condition) { x = 42; }
printf("%d\n", x);   /* warning: x uninitialized on the false path */
```

**Live variables** yields dead assignments: a write whose variable is not live
immediately after it.

## Unreachable code (A2.3)

Not a data-flow problem — two structural checks:

1. A block with no predecessors and which is not ENTRY.
2. Statements following an unconditional `return`/`break`/`continue` within a block.
   The CFG builder already detects these — `build_stmt` returned `None` with
   statements remaining. Collect them there rather than re-deriving.

Severity: **warning**.

## Replacing Phase 2's crude checks (D27)

`languages/c/usage.py` currently approximates rows 12 and 13 from `Symbol` flags.
Replace the implementations; keep the codes (`S008`, `S009`) and severities
(warning, info).

Then **rewrite** — do not append to — the `docs/known-limitations.md` entry that
describes the approximation and its `if (c) { x = 42; } printf(x);` blind spot. That
blind spot is now closed; leaving the old text claiming a weakness you have fixed
reads badly and understates the work.

Expect the existing row-12/13 tests to change. That is correct: the crude version
deliberately did not warn on the branch case, and the real one does. Update them and
say so in the commit message.

## Definition of done

- [ ] Solver tested standalone on a toy lattice, both directions, both joins
- [ ] Must-analysis initial value correct (full set, not empty)
- [ ] All three analyses configured through the one solver
- [ ] Golden definite-assignment case warns
- [ ] Dead assignments detected via liveness
- [ ] Unreachable blocks and post-jump statements both reported as warnings
- [ ] `usage.py` rewired; codes and severities unchanged
- [ ] `known-limitations.md` entry rewritten, not appended
- [ ] Direction/lattice/transfer/join documented per analysis

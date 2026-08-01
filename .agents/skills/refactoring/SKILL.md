---
name: refactoring
description: Scope-aware safe rename and dead code detection for c-lens Phase 3. Rename is the one feature the course document threatens with zero credit if done by text substitution — read before touching languages/c/rename.py.
---

# Safe rename and dead code

Requirements: A5.1–A5.3, A6.

## The zero-credit warning

The course document: *"A simple text-substitution approach is not acceptable and
will receive zero credit for this feature."*

Rename operates on **symbol identity**. Never on strings. The correct algorithm is
short precisely because Phase 2's scope tree did the hard part:

1. Resolve the cursor offset to a `Symbol`.
2. Collect `symbol.definition_loc` + `symbol.references` — these spans, and no
   others, are what change.
3. Check conflicts and shadowing.
4. Emit a diff.
5. Apply atomically.

If your implementation contains `str.replace` or a regex over source text, it is
wrong.

## Conflict check (A5.1 step 2)

The new name must not already exist in the **same** scope as the symbol.
`scope.lookup_local(new_name)` — refuse with a message naming the conflicting
declaration's location.

## Shadow check (A5.1 step 3)

Two directions, both required:

- **Renaming would shadow something**: an enclosing scope declares `new_name`, and
  after the rename an inner reference to that outer name would resolve to ours
  instead. Walk outward with `lookup(new_name)`.
- **Renaming would be shadowed**: an inner scope nested inside ours declares
  `new_name`, so our references inside that region would now resolve to theirs.
  Walk the scope subtree downward.

Both are refusals with an explanatory message. Getting only the first is the common
half-implementation; the second is what distinguishes a real check.

## Unified diff (A5.1 step 4)

`difflib.unified_diff` over the original and rewritten source, split by lines. One
line of code, and it satisfies the requirement exactly.

## Atomic application (A5.1 step 5)

Apply edits **right to left by offset** so earlier spans stay valid as later ones
change length. Build the new text in memory; only write when every edit succeeded.
All or nothing.

## The golden test (A5.3)

Course document §6.4 — rename `n` to `number` inside `factorial`:

```c
int factorial(int n) {          int factorial(int number) {
    if (n <= 1)                     if (number <= 1)
        return 1;                       return 1;
    return n *                      return number *
        factorial(n-1);                 factorial(number-1);
}                               }
/* Other functions with a variable 'n' are NOT changed. */
```

The fixture must contain a *second* function using `n`, and the test must assert it
is byte-identical after the rename. That contrast is the whole point.

Also test: rename to an existing same-scope name → refused; rename that would shadow
→ refused; rename a parameter, a global, a function, and a struct field.

---

# Dead code (A6)

Five categories, combining everything built in Phase 3:

| Category | Source |
|---|---|
| Unreachable functions | Call graph reachability from `main` |
| Unreachable basic blocks | CFG, no predecessors |
| Post-jump statements | CFG builder's `None`-with-statements-remaining case |
| Unused variables | Liveness — never live after their definition |
| Dead assignments | A write whose variable is not live immediately after |

The course document's §6.5 example contains all five in one file. Make it a fixture
and assert each category fires exactly once.

Report each with an appropriate severity: unreachable code and dead assignments as
**warnings**, unused variables as **info** (matching Phase 2's row 13).

## Definition of done

- [ ] No string substitution anywhere in the rename path
- [ ] Both shadow directions checked
- [ ] Conflict check with the conflicting location named
- [ ] Unified diff produced
- [ ] Edits applied right-to-left, atomically
- [ ] §6.4 golden test passes, including the untouched second function
- [ ] Refusal cases tested
- [ ] All five dead-code categories fire on the §6.5 fixture

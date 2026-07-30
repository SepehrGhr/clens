# Written Deliverables

These are graded separately from the code. The course document names the grammar
specification as a required Phase 1 deliverable and requires complete technical
documentation with each phase. Written work is the cheapest mark-per-hour in the
project — do it properly and keep it in sync with the code.

All docs live in `docs/`. Write them in English. Update them in the same commit as
the code change that invalidates them.

---

## D1 — `docs/grammar.ebnf`
The complete EBNF for the implemented subset. Must match `project/03-c-subset.md`
and the parser exactly. Head comment: notation conventions used (`*`, `?`, `|`,
quoting), and a note that the grammar is left-recursion-free by construction.

## D2 — `docs/lexical-specification.md`
1. A table: every token class → its formal regular expression → an example.
2. How the individual regexes compose into a single recognizer: Thompson's
   construction (regex → NFA), subset construction (NFA → DFA), Hopcroft
   minimization (DFA → minimal DFA).
3. The priority rules that resolve ambiguity between rules: longest match
   (maximal munch), and keyword-before-identifier.
4. A short honest note on the implementation strategy actually used (ordered
   master regex) and why it is equivalent in observable behaviour.
5. Worked example: a small NFA→DFA conversion for a two- or three-token subset,
   drawn out. This is the part that demonstrates understanding; don't skip it.

~2 pages. Pure theory, no implementation risk, fully graded.

## D3 — `docs/first-follow.md`
FIRST and FOLLOW sets for every non-terminal in the grammar. A written argument
that there are no FIRST/FIRST or FIRST/FOLLOW conflicts at k=1. The dangling-else
ambiguity is stated explicitly along with the disambiguation rule used.

Consider generating these sets with a small script in `tools/` and committing both
the script and its output — it keeps them honest as the grammar changes, and the
script itself is a good thing to show at the defense.

## D4 — `docs/architecture.md`
Module-by-module description, the pipeline diagram, the parsing strategy choice
with justification, the rejected alternatives, and the data structures used.

## D5 — `docs/known-limitations.md`
Every exclusion from `03-c-subset.md`, each with its reason. Framing matters: these
are scoping decisions with rationale, not omissions.

## D6 — `docs/testing.md`
Step-by-step instructions to run the tool and reproduce every test, written for
someone who has never seen the repo. The document requires step-by-step test
instructions explicitly.

## D7 — `docs/team.md`
Division of responsibilities: who owns which module. Required by the course
document. Both members must be able to explain the other's components.

## D8 — `README.md`
Project summary, the pipeline diagram, install and quickstart, CLI usage examples
with real output, links to all the above, **and the CI status badge** (required for
the CI bonus).

---

## Open question for the user — do not guess

The course PDF's evaluation-criteria tables (§4.6, §5.6, §6.7) and most of the
bonus section §7 did not extract from the file; their contents are unknown.

The one that changes Phase 1 work: **if §4.6 weights a hand-implemented DFA
heavily, decision D5 flips** from the master-regex approach to a hand-written DFA
with an explicit transition table.

If you are an agent and the user has not resolved this, proceed with D5 as written
and flag it once. Do not switch approaches on your own initiative.

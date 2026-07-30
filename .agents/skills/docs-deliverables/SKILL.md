---
name: docs-deliverables
description: How to write the graded written deliverables for c-lens — grammar EBNF, lexical specification with the NFA/DFA theory writeup, FIRST/FOLLOW tables, architecture, known limitations, testing guide, team split, README. Use whenever writing or updating anything in docs/ or the README.
---

# Written deliverables

Full list and required contents: `project/05-deliverables.md`. This skill is about
how to write them well.

The written work is the cheapest marks in the project. It is also what the graders
read first and what the defense questions come from.

## Principles

- **English, matching the course document's terminology.** If the document says
  "maximal munch", say maximal munch.
- **Sync docs with code in the same commit.** A grammar file that disagrees with the
  parser is worse than no grammar file, and it will be noticed — they will run both.
- **Show worked examples.** A hand-drawn NFA-to-DFA conversion for a three-token
  subset demonstrates understanding in a way a paragraph of description does not.
- **State limitations as decisions.** "Excluded `typedef` because it makes C's
  grammar context-sensitive and would require the lexer to consult the symbol table
  mid-parse" reads as command of the material. "Not implemented" reads as an
  omission. Same fact.
- **Prefer generated over hand-maintained.** FIRST/FOLLOW sets computed by a small
  script in `tools/` stay correct as the grammar changes, and the script itself is
  worth showing.

## Traps

- The lexical specification must document formal regexes for **every** token class
  *and* explain how they compose into one DFA with priority rules. Both halves are
  asked for. Do not write only the table.
- The ambiguity argument must be explicit about the dangling-else case rather than
  claiming the grammar is unambiguous. Stating a known ambiguity and its
  disambiguation rule is the correct, defensible answer.
- `docs/testing.md` is written for someone who has never seen the repo. Commands
  must be copy-pasteable and must actually work — try them.
- The README badge is a stated requirement for the CI bonus, not decoration.

## Diagrams

ASCII or Mermaid in markdown; both render on GitHub and neither adds a build step.
The pipeline diagram belongs in the README and in `docs/architecture.md`.

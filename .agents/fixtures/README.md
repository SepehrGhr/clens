# Fixtures

Test inputs. Copy these into `tests/fixtures/` during task T0.4 and add more as the
subset grows.

- `valid/` — must parse with zero diagnostics
- `lexical-errors/` — must produce specific lexer diagnostics and keep scanning
- `syntax-errors/` — must produce specific parser diagnostics and keep parsing
- `golden/` — expected outputs taken from the course document; these are exact

Every file in `valid/` is automatically subject to:
- the round-trip fidelity test (R5.3)
- the truncation robustness test (R3.5)
- token span tiling (no gaps or overlaps)

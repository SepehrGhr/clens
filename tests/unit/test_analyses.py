"""A2.1-A2.3 real data-flow analyses (`.agents/skills/dataflow/SKILL.md`),
each configured through `core/dataflow.py`'s one solver.
"""

from __future__ import annotations

from clens.core.diagnostics import DiagnosticCollector
from clens.core.source import SourceFile
from clens.languages.c.analyses import (
    collect_local_symbols,
    find_dead_assignments,
    find_uninitialized_uses,
    reaching_definitions,
    unreachable_blocks,
)
from clens.languages.c.ast_nodes import FuncDecl
from clens.languages.c.cfg_builder import build_cfg
from clens.languages.c.parser import parse
from clens.languages.c.semantic import analyze


def _cfg_and_symbols(text: str, name: str):
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    program = parse(source, diagnostics)
    model = analyze(program, source, diagnostics)
    func = next(d for d in program.declarations if isinstance(d, FuncDecl) and d.name == name)
    cfg = build_cfg(func)
    symbols = collect_local_symbols(model, func)
    return cfg, symbols


# --- A2.1 Definite assignment -------------------------------------------------


def test_golden_definite_assignment_warns_on_the_false_path():
    """Course document 6.1.1: `int x; if (c) { x = 42; } printf(x);` warns
    -- exactly what Phase 2's crude row-12 check missed."""
    cfg, symbols = _cfg_and_symbols(
        "int report(int value);\n"
        "int f(int condition) {\n"
        "    int x;\n"
        "    if (condition) { x = 42; }\n"
        "    return report(x);\n"
        "}\n",
        "f",
    )
    violations = find_uninitialized_uses(cfg, symbols)
    names = {v.symbol.name for v in violations}
    assert names == {"x"}


def test_definite_assignment_clean_on_every_path_does_not_warn():
    cfg, symbols = _cfg_and_symbols(
        "int report(int value);\n"
        "int g(int condition) {\n"
        "    int y;\n"
        "    if (condition) { y = 1; } else { y = 2; }\n"
        "    return report(y);\n"
        "}\n",
        "g",
    )
    assert find_uninitialized_uses(cfg, symbols) == []


def test_parameters_are_always_definitely_assigned():
    cfg, symbols = _cfg_and_symbols("int f(int n) { return n; }\n", "f")
    assert find_uninitialized_uses(cfg, symbols) == []


def test_read_before_write_within_the_same_block_is_caught():
    cfg, symbols = _cfg_and_symbols(
        "int report(int value);\nint f(void) { int x; return report(x); }\n", "f"
    )
    violations = find_uninitialized_uses(cfg, symbols)
    assert {v.symbol.name for v in violations} == {"x"}


# --- A2.2 Live variables / dead assignments -----------------------------------


def test_dead_code_fixture_flags_only_the_overwritten_first_value():
    """`.agents/fixtures/analysis/dead_code.c`'s bar(): `y`'s first value
    (from `compute()`) is overwritten before any read; the second (`99`)
    IS read via `use(y)` and must not be flagged."""
    cfg, symbols = _cfg_and_symbols(
        "int compute(void);\n"
        "int use(int v);\n"
        "int bar(void) {\n"
        "    int y = compute();\n"
        "    y = 99;\n"
        "    int z = 1;\n"
        "    return use(y);\n"
        "}\n",
        "bar",
    )
    dead = find_dead_assignments(cfg, symbols)
    dead_names_and_order = [(d.symbol.name, d.reference.span.start_offset) for d in dead]
    names = {name for name, _ in dead_names_and_order}
    assert names == {"y", "z"}
    # Only y's *first* write (the declaration's initializer) is dead.
    y_dead_offsets = [off for name, off in dead_names_and_order if name == "y"]
    assert len(y_dead_offsets) == 1


def test_live_variable_read_later_is_not_a_dead_assignment():
    cfg, symbols = _cfg_and_symbols(
        "int use(int v);\nint f(void) { int x = 1; return use(x); }\n", "f"
    )
    assert find_dead_assignments(cfg, symbols) == []


# --- A2.3 Unreachable code -----------------------------------------------------


def test_unreachable_fixture_flags_both_patterns():
    """`.agents/fixtures/analysis/unreachable.c`: unconditional-return and
    return-inside-if-branch, both structurally unreachable afterward."""
    cfg, _ = _cfg_and_symbols("int foo(void) {\n    return 42;\n    return 0;\n}\n", "foo")
    unreachable = unreachable_blocks(cfg)
    assert len(unreachable) == 1
    assert [s for s in unreachable[0].statements] != []


def test_unreachable_after_return_inside_if_branch():
    cfg, _ = _cfg_and_symbols(
        "void bar(int x) {\n    if (x > 0) {\n        return;\n        x++;\n    }\n}\n",
        "bar",
    )
    assert len(unreachable_blocks(cfg)) == 1


def test_while_1_exit_reported_unreachable_not_hidden():
    cfg, _ = _cfg_and_symbols(
        "int spin(void) {\n    while (1) {\n        int x = 0;\n        x = x + 1;\n    }\n}\n",
        "spin",
    )
    unreachable = unreachable_blocks(cfg)
    assert any(block is cfg.exit for block in unreachable)


def test_reachable_function_has_no_unreachable_blocks():
    cfg, _ = _cfg_and_symbols("int factorial(int n) { return n; }\n", "factorial")
    assert unreachable_blocks(cfg) == []


# --- Bonus: reaching definitions ----------------------------------------------


def test_reaching_definitions_distinguishes_branches():
    cfg, symbols = _cfg_and_symbols(
        "int use(int v);\n"
        "int f(int c) {\n"
        "    int x;\n"
        "    if (c) { x = 1; } else { x = 2; }\n"
        "    return use(x);\n"
        "}\n",
        "f",
    )
    result = reaching_definitions(cfg, symbols)
    x = next(s for s in symbols if s.name == "x")
    # The join block (holding `return use(x)`) should have both branches'
    # definitions of x reaching it.
    join_block = next(b for b in cfg.blocks if any(id(x) == var for var, _ in result[id(b)][0]))
    reaching_defs = {def_block for var, def_block in result[id(join_block)][0] if var == id(x)}
    assert len(reaching_defs) == 2

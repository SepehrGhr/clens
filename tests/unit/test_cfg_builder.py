"""CFG construction (A1.1-A1.5, A8.1). `.agents/skills/cfg/SKILL.md`."""

from __future__ import annotations

from clens.core.cfg import BlockKind, ControlFlowGraph, EdgeLabel
from clens.core.diagnostics import DiagnosticCollector
from clens.core.source import SourceFile
from clens.languages.c.ast_nodes import FuncDecl
from clens.languages.c.cfg_builder import build_cfg, cfg_layout, describe_node
from clens.languages.c.parser import parse


def _cfg_for(text: str, name: str) -> ControlFlowGraph | None:
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    program = parse(source, diagnostics)
    func = next(d for d in program.declarations if isinstance(d, FuncDecl) and d.name == name)
    return build_cfg(func)


def _labels(cfg: ControlFlowGraph, block) -> list[str]:
    return [describe_node(s) for s in block.statements]


def test_factorial_golden_cfg():
    """Course document 6.1: `ENTRY -> B1 --true--> B2 -> EXIT`,
    `B1 --false--> B3 -> EXIT`."""
    cfg = _cfg_for(
        "int factorial(int n) {\n    if (n <= 1) return 1;\n    return n * factorial(n - 1);\n}\n",
        "factorial",
    )
    assert cfg is not None
    assert len(cfg.blocks) == 5

    assert cfg.entry.kind is BlockKind.ENTRY
    assert cfg.exit.kind is BlockKind.EXIT
    assert cfg.entry.statements == []
    assert cfg.exit.statements == []

    [(b1, label)] = cfg.entry.successors
    assert label is EdgeLabel.FALLTHROUGH
    assert _labels(cfg, b1) == ["n <= 1"]

    successors = {lbl: block for block, lbl in b1.successors}
    assert set(successors) == {EdgeLabel.TRUE, EdgeLabel.FALSE}

    b2 = successors[EdgeLabel.TRUE]
    assert _labels(cfg, b2) == ["return 1"]
    assert b2.successors == [(cfg.exit, EdgeLabel.FALLTHROUGH)]

    b3 = successors[EdgeLabel.FALSE]
    assert _labels(cfg, b3) == ["return n * factorial(n - 1)"]
    assert b3.successors == [(cfg.exit, EdgeLabel.FALLTHROUGH)]

    assert cfg.exit.predecessors == [b2, b3]


def test_prototype_has_no_cfg():
    cfg = _cfg_for("int declared_never_defined(int n);\n", "declared_never_defined")
    assert cfg is None


def test_empty_body_is_entry_straight_to_exit():
    cfg = _cfg_for("void f(void) {}\n", "f")
    assert cfg is not None
    assert cfg.blocks == [cfg.entry, cfg.exit]
    assert cfg.entry.successors == [(cfg.exit, EdgeLabel.FALLTHROUGH)]
    assert cfg.exit.predecessors == [cfg.entry]


def test_if_else_both_branches_join():
    cfg = _cfg_for(
        "int f(int c) {\n    int r;\n    if (c) { r = 1; } else { r = 2; }\n    return r;\n}\n",
        "f",
    )
    assert cfg is not None
    header = cfg.entry.successors[0][0]
    assert _labels(cfg, header) == ["int r", "c"]
    branches = {lbl: block for block, lbl in header.successors}
    assert set(branches) == {EdgeLabel.TRUE, EdgeLabel.FALSE}
    then_tail = branches[EdgeLabel.TRUE]
    else_tail = branches[EdgeLabel.FALSE]
    assert _labels(cfg, then_tail) == ["r = 1"]
    assert _labels(cfg, else_tail) == ["r = 2"]
    # Both branches fall through to the same join block, which holds the
    # trailing `return r;`.
    join = then_tail.successors[0][0]
    assert else_tail.successors[0][0] is join
    assert _labels(cfg, join) == ["return r"]


def test_while_loop_back_edge_and_break_continue():
    cfg = _cfg_for(
        "int f(int n) {\n"
        "    while (n > 0) {\n"
        "        if (n == 3) { n = n - 1; continue; }\n"
        "        if (n == 7) { break; }\n"
        "        n = n - 1;\n"
        "    }\n"
        "    return n;\n"
        "}\n",
        "f",
    )
    assert cfg is not None
    header = cfg.entry.successors[0][0]
    assert _labels(cfg, header) == ["n > 0"]
    labels = {lbl for _, lbl in header.successors}
    assert labels == {EdgeLabel.TRUE, EdgeLabel.FALSE}

    # There must be at least one BACK edge (the loop closing / `continue`).
    back_edges = [
        (block, lbl) for block in cfg.blocks for _, lbl in block.successors if lbl is EdgeLabel.BACK
    ]
    assert back_edges, "expected at least one BACK edge for the loop"


def test_for_loop_update_runs_before_back_edge():
    cfg = _cfg_for(
        "int f(int n) {\n"
        "    int total = 0;\n"
        "    for (int i = 0; i < n; i = i + 1) {\n"
        "        total = total + i;\n"
        "    }\n"
        "    return total;\n"
        "}\n",
        "f",
    )
    assert cfg is not None
    # The latch block (holding the update) must have a BACK edge to a block
    # whose only statement is the loop condition.
    latch_candidates = [
        block for block in cfg.blocks if any(lbl is EdgeLabel.BACK for _, lbl in block.successors)
    ]
    assert latch_candidates
    for latch in latch_candidates:
        assert any(describe_node(s) == "i = i + 1" for s in latch.statements)


def test_while_1_with_no_break_has_unreachable_exit():
    """A8.1: `while(1)` with no exit -- the EXIT node is genuinely
    unreachable, and that is correct, not a bug to "fix"."""
    cfg = _cfg_for(
        "int spin(void) {\n    while (1) {\n        int x = 0;\n        x = x + 1;\n    }\n}\n",
        "spin",
    )
    assert cfg is not None
    # `after` (what would follow the loop) has no predecessor: the only
    # edge into it would be the loop's false branch, which is correctly
    # omitted for a literal `while(1)`. EXIT is reachable only through
    # `after`'s own (structural) edge, so it too is unreachable in
    # practice -- Stage 2's reachability sweep is what actually reports
    # this; here we assert the graph shape that makes it true.
    (after,) = [b for b in cfg.blocks if b.successors == [(cfg.exit, EdgeLabel.FALLTHROUGH)]]
    assert after.predecessors == []


def test_break_with_no_enclosing_loop_does_not_crash():
    """A recovered AST could hand the builder a `break` outside any loop;
    it must not raise (A8.1)."""
    cfg = _cfg_for("void f(void) { break; }\n", "f")
    assert cfg is not None


def test_error_stmt_region_is_opaque_and_does_not_crash():
    # A genuinely malformed body triggers parser recovery, producing
    # ErrorStmt/ErrorExpr nodes the builder must treat as ordinary
    # straight-line statements.
    cfg = _cfg_for("int f(void) { return }\n", "f")
    assert cfg is not None


def test_cfg_layout_places_entry_first_and_exit_last():
    cfg = _cfg_for(
        "int factorial(int n) {\n    if (n <= 1) return 1;\n    return n * factorial(n - 1);\n}\n",
        "factorial",
    )
    layout = cfg_layout(cfg)
    assert set(layout.nodes) == {"ENTRY", "B1", "B2", "B3", "EXIT"}
    assert layout.nodes["ENTRY"].rank < layout.nodes["B1"].rank
    assert layout.nodes["EXIT"].rank > layout.nodes["B2"].rank
    assert layout.nodes["EXIT"].rank > layout.nodes["B3"].rank
    assert layout.nodes["B1"].label == "B1\nn <= 1"

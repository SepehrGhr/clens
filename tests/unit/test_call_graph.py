"""A3.1-A3.5: call graph construction and all seven required queries,
against `.agents/fixtures/analysis/call_graph.c`'s scenario (direct
recursion, mutual recursion, a 3-cycle, a dead function, a function only
reachable through another dead function, and a leaf).
"""

from __future__ import annotations

from pathlib import Path

from clens.core.diagnostics import DiagnosticCollector
from clens.core.source import SourceFile
from clens.languages.c.call_graph import (
    build_call_graph,
    call_graph_layout,
    dead_functions,
    recursive_functions,
)
from clens.languages.c.parser import parse
from clens.languages.c.semantic import analyze

FIXTURE = Path(__file__).parent.parent.parent / ".agents" / "fixtures" / "analysis" / "call_graph.c"


def _build(text: str):
    source = SourceFile(text, "a.c")
    diagnostics = DiagnosticCollector()
    program = parse(source, diagnostics)
    model = analyze(program, source, diagnostics)
    return build_call_graph(model)


def _fixture_call_graph():
    return _build(FIXTURE.read_text())


def test_nodes_are_every_function_with_a_body():
    cg = _fixture_call_graph()
    assert cg.graph.nodes == {
        "leaf",
        "self_recursive",
        "ping",
        "pong",
        "a_fn",
        "b_fn",
        "c_fn",
        "only_from_orphan",
        "orphan",
        "main",
    }


def test_prototype_only_function_is_not_a_node_but_call_is_recorded():
    cg = _build("int later(int n);\nint f(void) { return later(1); }\n")
    assert "later" not in cg.graph.nodes
    assert cg.unresolved and cg.unresolved[0].callee_name == "later"


# --- Queries 1-2: direct callees / callers ------------------------------------


def test_direct_callees_and_callers():
    cg = _fixture_call_graph()
    assert cg.graph.successors("main") == {"leaf", "self_recursive", "ping", "a_fn"}
    assert cg.graph.predecessors("leaf") == {"main"}


# --- Queries 3-4: transitive callees / callers --------------------------------


def test_transitive_callees_of_main_reach_the_whole_live_graph():
    cg = _fixture_call_graph()
    callees = cg.graph.reachable_from("main")
    assert callees == {"leaf", "self_recursive", "ping", "pong", "a_fn", "b_fn", "c_fn"}
    assert "orphan" not in callees
    assert "only_from_orphan" not in callees


def test_transitive_callers_of_c_fn_include_the_whole_cycle_and_main():
    cg = _fixture_call_graph()
    callers = cg.graph.reachable_to("c_fn")
    assert callers == {"a_fn", "b_fn", "c_fn", "main"}


# --- Query 5: recursion detection ----------------------------------------------


def test_recursive_functions_covers_direct_and_mutual_and_the_3_cycle():
    cg = _fixture_call_graph()
    assert recursive_functions(cg) == {"self_recursive", "ping", "pong", "a_fn", "b_fn", "c_fn"}


def test_leaf_and_orphan_are_not_recursive():
    cg = _fixture_call_graph()
    recursive = recursive_functions(cg)
    assert "leaf" not in recursive
    assert "orphan" not in recursive
    assert "only_from_orphan" not in recursive


# --- Query 6: dead functions ----------------------------------------------------


def test_dead_functions_are_unreachable_from_main():
    cg = _fixture_call_graph()
    assert dead_functions(cg) == {"orphan", "only_from_orphan"}


def test_no_main_declares_nothing_dead():
    """A library-style file has no principled entry point; rather than
    flagging every function as dead, nothing is (A8.1-style robustness,
    documented choice)."""
    cg = _build("int add(int a, int b) { return a + b; }\nint twice(int a) { return add(a, a); }\n")
    assert cg.has_main is False
    assert dead_functions(cg) == set()


# --- Query 7: strongly connected components ------------------------------------


def test_scc_distinguishes_self_loop_two_cycle_and_three_cycle():
    cg = _fixture_call_graph()
    components = {frozenset(c) for c in cg.graph.strongly_connected_components()}
    assert frozenset({"self_recursive"}) in components
    assert frozenset({"ping", "pong"}) in components
    assert frozenset({"a_fn", "b_fn", "c_fn"}) in components
    assert frozenset({"leaf"}) in components


def test_leaf_is_a_singleton_scc_without_a_self_edge():
    """A single-node SCC is only *recursive* if it also has a self-edge --
    `leaf` is the contrast case: alone in its SCC, but not recursive."""
    cg = _fixture_call_graph()
    components = cg.graph.strongly_connected_components()
    leaf_component = next(c for c in components if c == ["leaf"])
    assert leaf_component == ["leaf"]
    assert "leaf" not in recursive_functions(cg)


def test_call_graph_layout_ranks_from_main():
    cg = _fixture_call_graph()
    layout = call_graph_layout(cg)
    assert set(layout.nodes) == cg.graph.nodes
    assert layout.nodes["main"].rank == 0
    assert layout.nodes["leaf"].rank > 0

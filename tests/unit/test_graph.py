"""`core/graph.py`'s generic directed graph: adjacency, reverse adjacency,
BFS reachability, and Tarjan SCC -- tested standalone before
`languages/c/call_graph.py` configures it for function names.
"""

from __future__ import annotations

from clens.core.graph import DirectedGraph


def _chain() -> DirectedGraph[str]:
    """a -> b -> c -> d, a simple acyclic chain."""
    g: DirectedGraph[str] = DirectedGraph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", "d")
    return g


def test_successors_and_predecessors():
    g = _chain()
    assert g.successors("a") == {"b"}
    assert g.predecessors("b") == {"a"}
    assert g.successors("d") == set()
    assert g.predecessors("a") == set()


def test_reachable_from_excludes_self_on_an_acyclic_graph():
    g = _chain()
    assert g.reachable_from("a") == {"b", "c", "d"}
    assert g.reachable_from("d") == set()


def test_reachable_to_is_the_reverse_query():
    g = _chain()
    assert g.reachable_to("d") == {"a", "b", "c"}
    assert g.reachable_to("a") == set()


def test_reachable_from_includes_self_when_a_real_cycle_loops_back():
    g: DirectedGraph[str] = DirectedGraph()
    g.add_edge("a", "b")
    g.add_edge("b", "a")
    assert g.reachable_from("a") == {"a", "b"}


def test_isolated_node_has_no_neighbours():
    g: DirectedGraph[str] = DirectedGraph()
    g.add_node("solo")
    assert g.successors("solo") == set()
    assert g.reachable_from("solo") == set()


# --- Tarjan SCC ---------------------------------------------------------------


def _components_as_sets(components: list[list[str]]) -> set[frozenset[str]]:
    return {frozenset(c) for c in components}


def test_scc_acyclic_graph_is_all_singletons():
    g = _chain()
    components = _components_as_sets(g.strongly_connected_components())
    assert components == {frozenset({"a"}), frozenset({"b"}), frozenset({"c"}), frozenset({"d"})}


def test_scc_self_loop_is_a_singleton_component():
    g: DirectedGraph[str] = DirectedGraph()
    g.add_edge("f", "f")
    components = g.strongly_connected_components()
    assert len(components) == 1
    assert components[0] == ["f"]


def test_scc_two_cycle():
    g: DirectedGraph[str] = DirectedGraph()
    g.add_edge("ping", "pong")
    g.add_edge("pong", "ping")
    components = _components_as_sets(g.strongly_connected_components())
    assert frozenset({"ping", "pong"}) in components


def test_scc_three_cycle():
    g: DirectedGraph[str] = DirectedGraph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", "a")
    components = _components_as_sets(g.strongly_connected_components())
    assert frozenset({"a", "b", "c"}) in components


def test_scc_mixed_graph_separates_the_cycle_from_the_rest():
    g: DirectedGraph[str] = DirectedGraph()
    g.add_edge("leaf", "leaf")  # not added; leaf has no outgoing edge in this test
    g = DirectedGraph()
    g.add_node("leaf")
    g.add_edge("entry", "leaf")
    g.add_edge("entry", "a")
    g.add_edge("a", "b")
    g.add_edge("b", "a")
    components = _components_as_sets(g.strongly_connected_components())
    assert frozenset({"a", "b"}) in components
    assert frozenset({"leaf"}) in components
    assert frozenset({"entry"}) in components

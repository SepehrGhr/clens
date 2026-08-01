"""A small generic directed graph: adjacency, reverse adjacency, BFS
reachability, and Tarjan's strongly-connected-components algorithm.
Language-agnostic -- `languages/c/call_graph.py` is the sole current user,
keyed by function name.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Generic, TypeVar

__all__ = ["DirectedGraph"]

N = TypeVar("N")


@dataclass(slots=True)
class DirectedGraph(Generic[N]):
    nodes: set[N] = field(default_factory=set)
    _adjacency: dict[N, set[N]] = field(default_factory=dict)
    _reverse: dict[N, set[N]] = field(default_factory=dict)

    def add_node(self, node: N) -> None:
        self.nodes.add(node)
        self._adjacency.setdefault(node, set())
        self._reverse.setdefault(node, set())

    def add_edge(self, source: N, target: N) -> None:
        self.add_node(source)
        self.add_node(target)
        self._adjacency[source].add(target)
        self._reverse[target].add(source)

    def successors(self, node: N) -> set[N]:
        """Direct callees, for the call graph (A3.5 row 1)."""
        return set(self._adjacency.get(node, set()))

    def predecessors(self, node: N) -> set[N]:
        """Direct callers (A3.5 row 2), via the reverse adjacency kept
        alongside the forward one -- no re-scan needed."""
        return set(self._reverse.get(node, set()))

    def reachable_from(self, start: N) -> set[N]:
        """Every node reachable from `start` via one or more edges (A3.5
        row 3: transitively reachable callees). `start` itself is included
        only if a real path loops back to it -- this is not "insert start
        first", it is BFS seeded from `start`'s own successors.
        """
        return self._bfs(self._adjacency.get(start, set()), self._adjacency)

    def reachable_to(self, target: N) -> set[N]:
        """Every node that can reach `target` (A3.5 row 4), by BFS on the
        reverse adjacency -- the same algorithm as `reachable_from`, just
        walking edges backward.
        """
        return self._bfs(self._reverse.get(target, set()), self._reverse)

    @staticmethod
    def _bfs(start_frontier: set[N], adjacency: dict[N, set[N]]) -> set[N]:
        seen: set[N] = set(start_frontier)
        queue: deque[N] = deque(start_frontier)
        while queue:
            node = queue.popleft()
            for neighbor in adjacency.get(node, set()):
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        return seen

    def strongly_connected_components(self) -> list[list[N]]:
        """Tarjan's algorithm (A3.5 row 7). A single-node component with no
        self-edge is just an ordinary acyclic node, not a cycle -- callers
        that want "is this a real cycle" must additionally check for a
        self-edge on size-1 components (see `call_graph.is_recursive`).
        """
        index_counter = 0
        indices: dict[N, int] = {}
        lowlink: dict[N, int] = {}
        on_stack: set[N] = set()
        stack: list[N] = []
        components: list[list[N]] = []

        def strongconnect(node: N) -> None:
            nonlocal index_counter
            indices[node] = index_counter
            lowlink[node] = index_counter
            index_counter += 1
            stack.append(node)
            on_stack.add(node)

            for successor in self._adjacency.get(node, set()):
                if successor not in indices:
                    strongconnect(successor)
                    lowlink[node] = min(lowlink[node], lowlink[successor])
                elif successor in on_stack:
                    lowlink[node] = min(lowlink[node], indices[successor])

            if lowlink[node] == indices[node]:
                component: list[N] = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                components.append(component)

        for node in self.nodes:
            if node not in indices:
                strongconnect(node)
        return components

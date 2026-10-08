"""The prerequisite graph: gateway courses and long chains (F3.2).

An edge A -> B means A appears in B's prerequisite rule. A gateway course is one
that many later courses depend on, directly or through a chain; failing or
delaying it delays all of them. Offering-based bottlenecks (F3.1) need the
registrar's offering history and are not computed yet.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import networkx as nx

from app.domain.catalog import Catalog, Program
from app.domain.requisites import course_codes


def prerequisite_graph(catalog: Catalog, codes: Iterable[str] | None = None) -> nx.DiGraph:
    """Graph of PRE rules among ``codes`` (default: the whole catalog)."""
    nodes = set(codes) if codes is not None else set(catalog.courses)
    graph = nx.DiGraph()
    graph.add_nodes_from(nodes)
    for code in nodes:
        for prerequisite in course_codes(catalog.prerequisite(code)):
            if prerequisite in nodes and prerequisite != code:
                graph.add_edge(prerequisite, code)
    return graph


def program_courses(program: Program) -> set[str]:
    """Courses a program names outside its open free-elective pool."""
    return {code for group in program.leaf_groups() if not group.is_open_pool for code in group.courses}


@dataclass(frozen=True)
class Gateway:
    code: str
    dependents: tuple[str, ...]  # every program course that needs it, directly or through a chain
    direct_dependents: tuple[str, ...]


def gateways(program: Program, catalog: Catalog, minimum: int = 2) -> list[Gateway]:
    graph = prerequisite_graph(catalog, program_courses(program))
    result = []
    for code in graph.nodes:
        later = nx.descendants(graph, code)
        if len(later) >= minimum:
            result.append(Gateway(code, tuple(sorted(later)), tuple(sorted(graph.successors(code)))))
    result.sort(key=lambda g: (-len(g.dependents), g.code))
    return result


def longest_chain(graph: nx.DiGraph) -> list[str]:
    """Longest prerequisite chain."""
    if graph.number_of_nodes() == 0:
        return []
    return list(nx.dag_longest_path(_acyclic(graph)))


def chain_lengths(graph: nx.DiGraph) -> dict[str, int]:
    """For each course, how many terms it and its longest chain of dependents need (itself = 1)."""
    dag = _acyclic(graph)
    lengths: dict[str, int] = {}
    for code in reversed(list(nx.topological_sort(dag))):
        lengths[code] = 1 + max((lengths[child] for child in dag.successors(code)), default=0)
    return lengths


def _acyclic(graph: nx.DiGraph) -> nx.DiGraph:
    """Drop the edges of any cycle (a data error the import report flags) so chains stay finite."""
    if nx.is_directed_acyclic_graph(graph):
        return graph
    dag = graph.copy()
    dag.remove_edges_from(edge for cycle in nx.simple_cycles(graph) for edge in _cycle_edges(cycle))
    return dag


def find_cycles(catalog: Catalog) -> list[list[str]]:
    graph = prerequisite_graph(catalog)
    return [sorted(cycle) for cycle in nx.simple_cycles(graph)]


def _cycle_edges(cycle: list[str]) -> list[tuple[str, str]]:
    return [(cycle[i], cycle[(i + 1) % len(cycle)]) for i in range(len(cycle))]

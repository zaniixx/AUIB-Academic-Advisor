"""The degree map (F5.1, F5.2): every course on the student's path, by term, with prerequisite links.

Columns run from completed terms through the current term to the planned ones.
Each node carries a status (done, in progress, planned, an open choice, or blocked)
and each edge says "this course is needed before that one". The web app draws it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from app.domain.catalog import Catalog, Program, level_courses
from app.domain.planner import ItemKind, Plan
from app.domain.record import AttemptStatus, StudentRecord
from app.domain.requisites import AllOf, AnyOf, Expr, LevelReq, course_codes
from app.domain.terms import Term


class NodeStatus(StrEnum):
    DONE = "done"
    IN_PROGRESS = "in_progress"
    PLANNED = "planned"
    CHOICE = "choice"  # an open-choice slot the student fills
    BLOCKED = "blocked"  # could not be scheduled


class ColumnKind(StrEnum):
    COMPLETED = "completed"
    CURRENT = "current"
    PLANNED = "planned"
    UNSCHEDULED = "unscheduled"


@dataclass(frozen=True)
class MapColumn:
    label: str
    kind: ColumnKind


@dataclass(frozen=True)
class MapNode:
    key: str
    code: str | None
    title: str
    units: float
    status: NodeStatus
    column: int
    group_label: str | None


@dataclass(frozen=True)
class MapEdge:
    source: str
    target: str


@dataclass(frozen=True)
class DegreeMap:
    columns: list[MapColumn]
    nodes: list[MapNode]
    edges: list[MapEdge]


def degree_map(
    plan: Plan, record: StudentRecord, catalog: Catalog, program: Program, in_session: Term
) -> DegreeMap:
    groups = {
        counted.code: leaf.group.label for leaf in plan.progress.leaves.values() for counted in leaf.courses
    }
    columns: list[MapColumn] = []
    nodes: list[MapNode] = []

    def add_column(label: str, kind: ColumnKind) -> int:
        columns.append(MapColumn(label, kind))
        return len(columns) - 1

    def add_course(code: str, status: NodeStatus, column: int, units: float | None = None) -> None:
        nodes.append(
            MapNode(
                key=code,
                code=code,
                title=catalog.title(code),
                units=units if units is not None else record.units_of(code, catalog),
                status=status,
                column=column,
                group_label=groups.get(code),
            )
        )

    # Completed courses, in the term of their latest completed attempt.
    completed_terms: dict[str, Term | None] = {}
    for attempt in record.attempts:
        if attempt.status is AttemptStatus.COMPLETED:
            previous = completed_terms.get(attempt.code)
            if attempt.code not in completed_terms or (
                attempt.term and (previous is None or attempt.term > previous)
            ):
                completed_terms[attempt.code] = attempt.term
    undated = sorted(code for code, term in completed_terms.items() if term is None)
    if undated:
        column = add_column("Earlier", ColumnKind.COMPLETED)
        for code in undated:
            add_course(code, NodeStatus.DONE, column)
    for term in sorted({term for term in completed_terms.values() if term is not None}):
        column = add_column(term.label, ColumnKind.COMPLETED)
        for code in sorted(code for code, t in completed_terms.items() if t == term):
            add_course(code, NodeStatus.DONE, column)

    # Courses in progress now.
    if record.in_progress:
        column = add_column(f"{in_session.label} (now)", ColumnKind.CURRENT)
        for code in sorted(record.in_progress):
            add_course(code, NodeStatus.IN_PROGRESS, column)

    # The plan, term by term.
    for planned in plan.terms:
        column = add_column(planned.term.label, ColumnKind.PLANNED)
        for item in planned.items:
            if item.kind is ItemKind.SLOT:
                nodes.append(
                    MapNode(
                        item.key, None, item.title, item.units, NodeStatus.CHOICE, column, item.group_label
                    )
                )
            elif item.code:
                add_course(item.code, NodeStatus.PLANNED, column, item.units)

    if plan.unscheduled:
        column = add_column("Not scheduled", ColumnKind.UNSCHEDULED)
        for item in plan.unscheduled:
            if item.code:
                add_course(item.code, NodeStatus.BLOCKED, column, item.units)

    on_map = {node.code for node in nodes if node.code}
    level_map = level_courses(program, catalog)
    edges = [
        MapEdge(source, node.key)
        for node in nodes
        if node.code
        for source in sorted(_needs(catalog.prerequisite(node.code), level_map) & on_map)
        if source != node.code
    ]
    return DegreeMap(columns, nodes, edges)


def _needs(rule: Expr | None, level_map: Mapping[int, frozenset[str]]) -> set[str]:
    """Courses a rule refers to, including "all 300-level major courses"."""
    if isinstance(rule, LevelReq):
        return set(level_map.get(rule.level, frozenset()))
    if isinstance(rule, AllOf | AnyOf):
        return set().union(*(_needs(item, level_map) for item in rule.items))
    return course_codes(rule)

from datetime import date

from app.domain.catalog import Catalog, Program
from app.domain.journey import ColumnKind, NodeStatus, degree_map
from app.domain.planner import PlanOptions, build_plan
from app.domain.terms import Season, Term

from .students import new_student, second_year


def test_map_runs_from_completed_terms_to_the_plan(
    cs_program: Program, cs_catalog: Catalog, today: date
) -> None:
    record = second_year()
    plan = build_plan(cs_program, cs_catalog, record, PlanOptions(), today)
    journey = degree_map(plan, record, cs_catalog, cs_program, Term(2026, Season.FALL))
    labels = [column.label for column in journey.columns]
    assert labels[:3] == ["Fall 2025", "Spring 2026", "Fall 2026 (now)"]
    assert [c.kind for c in journey.columns[:3]] == [
        ColumnKind.COMPLETED,
        ColumnKind.COMPLETED,
        ColumnKind.CURRENT,
    ]
    assert labels[3] == plan.terms[0].term.label
    nodes = {node.key: node for node in journey.nodes}
    assert nodes["CSC 101"].status is NodeStatus.DONE
    assert nodes["CSC 230"].status is NodeStatus.IN_PROGRESS
    assert nodes["CSC 231"].status is NodeStatus.PLANNED
    assert any(node.status is NodeStatus.CHOICE for node in journey.nodes)
    assert len({node.key for node in journey.nodes}) == len(journey.nodes)


def test_map_links_prerequisites(cs_program: Program, cs_catalog: Catalog, today: date) -> None:
    record = new_student()
    plan = build_plan(cs_program, cs_catalog, record, PlanOptions(), today)
    journey = degree_map(plan, record, cs_catalog, cs_program, Term(2026, Season.FALL))
    edges = {(edge.source, edge.target) for edge in journey.edges}
    assert ("CSC 230", "CSC 231") in edges
    assert ("MAT 111", "CSC 231") in edges
    assert ("CSC 390", "CSC 499") in edges  # "all 300-level major courses" includes the internships
    column = {node.key: node.column for node in journey.nodes}
    assert all(column[source] < column[target] for source, target in edges)

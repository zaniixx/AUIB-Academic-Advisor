"""Read-only catalog: programs, requirement trees, courses and their rules."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app import __version__
from app.api import convert
from app.api import schemas as s
from app.api.deps import CatalogDep, SessionDep, TodayDep, published_program
from app.domain.codes import normalize_code
from app.domain.graph import gateways, longest_chain, prerequisite_graph, program_courses
from app.domain.planner import PlanOptions
from app.domain.recommend import GOALS, INTERESTS, Workload
from app.domain.requisites import describe, format_rule
from app.domain.terms import current_term
from app.services.catalog_edit import course_offerings

router = APIRouter(prefix="/api/v1", tags=["catalog"])


@router.get("/meta", summary="Choices and assumptions the web app shows")
def meta(catalog: CatalogDep) -> s.MetaOut:
    defaults = PlanOptions()
    return s.MetaOut(
        version=__version__,
        catalog_revision=catalog.revision,
        interests=[s.OptionOut(id=i.id, label=i.label) for i in INTERESTS],
        goals=[s.OptionOut(id=g.id, label=g.label) for g in GOALS],
        workloads=[w.value for w in Workload],
        paces=["on_time", "fastest"],
        standing_credits=convert.standing_credits(),
        defaults={
            "preferred_units": defaults.preferred_units,
            "max_units": defaults.max_units,
            "summer_max_units": defaults.summer_max_units,
            "regular_terms_to_graduate": defaults.regular_terms_to_graduate,
        },
        assumptions=convert.ASSUMPTIONS,
        disclaimer=convert.DISCLAIMER,
    )


@router.get("/programs", summary="Published programs, one entry per program with its versions (F11.2, F0.4)")
def programs(
    catalog: CatalogDep, kind: Annotated[str | None, Query(pattern="^(major|minor)$")] = None
) -> list[s.ProgramSummaryOut]:
    return [convert.family_summary(versions) for versions in catalog.families(kind)]


@router.get("/programs/{program_id}", summary="A program's requirement tree")
def program_detail(program_id: str, catalog: CatalogDep) -> s.ProgramDetailOut:
    program = published_program(catalog, program_id)
    summary = convert.program_summary(program)
    return s.ProgramDetailOut(**summary.model_dump(), root=convert.group_out(program.root, catalog))


@router.get(
    "/programs/{program_id}/insights", summary="Gateway courses and the longest prerequisite chain (F3.2)"
)
def insights(
    program_id: str, catalog: CatalogDep, limit: Annotated[int, Query(ge=1, le=50)] = 10
) -> s.InsightsOut:
    program = published_program(catalog, program_id)
    found = gateways(program, catalog)[:limit]
    chain = longest_chain(prerequisite_graph(catalog, program_courses(program)))
    return s.InsightsOut(
        gateways=[
            s.GatewayOut(
                course=convert.course_ref(g.code, catalog),
                dependents=len(g.dependents),
                direct_dependents=list(g.direct_dependents),
            )
            for g in found
        ],
        longest_chain=[convert.course_ref(code, catalog) for code in chain],
    )


@router.get("/courses", summary="Search the catalog")
def courses(
    catalog: CatalogDep,
    q: Annotated[str | None, Query(max_length=60)] = None,
    subject: Annotated[str | None, Query(pattern="^[A-Za-z]{2,4}$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=5000)] = 0,
) -> s.CourseListOut:
    needle = (q or "").strip().lower()
    code_query = normalize_code(needle) if needle else None
    matches = []
    for course in sorted(catalog.courses.values(), key=lambda c: c.code):
        if course.hidden or (subject and course.subject != subject.upper()):
            continue
        if (
            needle
            and needle not in course.code.lower()
            and needle not in course.title.lower()
            and course.code != code_query
        ):
            continue
        matches.append(course)
    return s.CourseListOut(
        total=len(matches),
        courses=[convert.course_ref(c.code, catalog) for c in matches[offset : offset + limit]],
    )


@router.get("/courses/{code}", summary="A course with its rules shown beside their source text (F0.2)")
def course_detail(code: str, catalog: CatalogDep, session: SessionDep, today: TodayDep) -> s.CourseOut:
    normal = normalize_code(code)
    course = catalog.course(normal) if normal else None
    if course is None or course.hidden:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No course {code!r} in the catalog")
    graph = prerequisite_graph(catalog)
    rules = [
        s.RuleOut(
            kind=rule.kind.value,
            english=describe(rule.expr),
            rule=format_rule(rule.expr),
            source_text=rule.source_text,
            status=rule.status.value,
            reviewed=rule.reviewed,
            overridden=rule.overridden,
        )
        for rule in catalog.rules.get(course.code, {}).values()
    ]
    groups = [
        {
            "program_id": program.id,
            "program_name": program.name,
            "group_key": group.key,
            "group_label": group.label,
        }
        for program in catalog.published_programs()
        for group in program.leaf_groups()
        if course.code in group.courses and not group.is_open_pool
    ]
    return s.CourseOut(
        code=course.code,
        title=course.title,
        units=course.credit_units,
        description=course.description,
        component=course.component,
        notices=list(course.notices),
        offered_terms=sorted(season.name.lower() for season in course.offered_terms)
        if course.offered_terms
        else None,
        rules=rules,
        unlocks=[
            convert.course_ref(c, catalog)
            for c in sorted(graph.successors(course.code))
            if catalog.visible(c)
        ],
        groups=groups,
        offerings=convert.term_offerings_out(
            course_offerings(session, course.code, since=current_term(today)), catalog
        ),
    )

"""The quick questions a student answers when setting up a plan (F2.1).

The questions depend on the major: its areas come from the electives it lets students choose, and the
directions after graduation from the topics its courses cover, so a new program gets fitting questions
with no code changes. The answers fill ``interests``, ``avoid``, ``plans`` and ``goal`` in the student's
preferences, which rank electives (see recommend.py).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from app.domain.catalog import Catalog, GroupRole, Program, group_requires_all
from app.domain.interests import GOALS, INTERESTS, PLANS, TRAITS, Goal, Interest, interest_matches

MAX_AREAS = 6
MAX_DIRECTIONS = 5
# Kept for profiles saved before these questions; the plans question asks about them now.
_NOT_A_DIRECTION = {"researcher", "entrepreneur", "undecided"}

Field = Literal["interests", "avoid", "plans", "goal"]


@dataclass(frozen=True)
class Option:
    id: str
    label: str


@dataclass(frozen=True)
class Question:
    id: str
    field: Field
    kind: Literal["single", "multi"]
    title: str
    hint: str
    options: tuple[Option, ...]
    # Asked only when the answer to question ``show_if[0]`` is one of ``show_if[1]``.
    show_if: tuple[str, tuple[str, ...]] | None = None


def questions_for(program: Program, catalog: Catalog) -> list[Question]:
    questions: list[Question] = []
    areas = major_areas(program, catalog)
    if len(areas) >= 2:
        questions.append(
            Question(
                "major_areas",
                "interests",
                "multi",
                f"Which parts of {program.name} do you enjoy most?",
                "Pick any. Matching major electives are suggested first.",
                tuple(Option(area.id, area.label) for area in areas),
            )
        )
    questions.append(
        Question(
            "topics",
            "interests",
            "multi",
            "Outside your major, what sounds interesting?",
            "Pick any. This shapes your core liberal arts and free electives.",
            tuple(Option(i.id, i.label) for i in INTERESTS if i.general),
        )
    )
    questions.append(
        Question(
            "avoid",
            "avoid",
            "multi",
            "Anything you would rather avoid in a course?",
            "Pick any. Electives whose descriptions mention these come later. Required courses stay.",
            tuple(Option(trait.id, trait.label) for trait in TRAITS),
        )
    )
    questions.append(
        Question(
            "plans",
            "plans",
            "single",
            "After you graduate, what is the plan?",
            "Pick the closest. You can change it later.",
            tuple(Option(plan.id, plan.label) for plan in PLANS),
        )
    )
    # Only a major with electives beyond the core liberal arts has courses a direction could choose.
    directions = career_directions(program, catalog) if _has_choices(program, catalog) else []
    if directions:
        questions.append(
            Question(
                "goal",
                "goal",
                "single",
                "Which direction appeals most?",
                "Courses that help with it are suggested first.",
                (*(Option(goal.id, goal.label) for goal in directions), Option("undecided", "Not sure yet")),
                show_if=("plans", ("work", "grad_school")),
            )
        )
    return questions


def major_areas(program: Program, catalog: Catalog) -> list[Interest]:
    """The topics of the major's electives, most covered first; its other courses when it has no electives
    but free electives. Empty when the student has no choice outside the core liberal arts."""
    electives: list[str] = []
    core: list[str] = []
    free = False
    for group in program.leaf_groups():
        if group.role is GroupRole.FREE_ELECTIVE:
            free = True
        elif group.role is GroupRole.MAJOR_ELECTIVE and not group_requires_all(group, catalog):
            electives.extend(group.courses)
        elif group.role is not GroupRole.GENERAL_EDUCATION:
            core.extend(group.courses)
    found = _ranked(electives, catalog)
    if len(found) < 2 and free:
        found = _ranked(electives + core, catalog)
    return found[:MAX_AREAS]


def career_directions(program: Program, catalog: Catalog) -> list[Goal]:
    """Careers the major's own courses prepare for (its main topic is taught), best covered first."""
    courses = [
        code
        for group in program.leaf_groups()
        if group.role not in (GroupRole.GENERAL_EDUCATION, GroupRole.FREE_ELECTIVE)
        for code in group.courses
    ]
    coverage = {area.id: score for area, score in _coverage(courses, catalog).items()}
    scored = []
    for goal in GOALS:
        if goal.id in _NOT_A_DIRECTION or coverage.get(goal.main_topic or "", 0.0) < 1.0:
            continue
        score = sum(weight * coverage.get(area, 0.0) for area, weight in goal.weights.items())
        scored.append((score, goal))
    scored.sort(key=lambda pair: -pair[0])
    return [goal for _score, goal in scored[:MAX_DIRECTIONS]]


def _has_choices(program: Program, catalog: Catalog) -> bool:
    return any(
        group.role is GroupRole.FREE_ELECTIVE
        or (group.role is GroupRole.MAJOR_ELECTIVE and not group_requires_all(group, catalog))
        for group in program.leaf_groups()
    )


def _coverage(courses: Iterable[str], catalog: Catalog) -> dict[Interest, float]:
    """How much of ``courses`` each major topic covers: 1 per course naming it in its title, 0.25 per
    course mentioning it only in its description."""
    found: dict[Interest, float] = {}
    titled: dict[Interest, int] = {}
    for code in dict.fromkeys(courses):
        course = catalog.courses.get(code)
        if course is None or course.hidden:
            continue
        for interest in INTERESTS:
            if interest.general or (interest.subjects and course.subject not in interest.subjects):
                continue
            match = interest_matches(course.title, course.description, interest)
            if match >= 1.0:
                titled[interest] = titled.get(interest, 0) + 1
            if match:
                found[interest] = found.get(interest, 0.0) + (1.0 if match >= 1.0 else 0.25)
    # A topic counts only when at least one course is about it, not merely mentions it.
    return {interest: score for interest, score in found.items() if titled.get(interest)}


def _ranked(courses: list[str], catalog: Catalog) -> list[Interest]:
    coverage = _coverage(courses, catalog)
    order = {interest.id: index for index, interest in enumerate(INTERESTS)}
    return sorted(coverage, key=lambda interest: (-coverage[interest], order[interest.id]))

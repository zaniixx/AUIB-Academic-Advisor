"""In-memory catalog: courses, their requisite rules and program requirement trees.

The planning code reads only these objects. They are built from the database
(``app.services.catalog_cache``) or straight from a program package in tests.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from app.domain import codes
from app.domain.requisites import Expr, ParseStatus, RuleKind
from app.domain.terms import Season

DEFAULT_COURSE_UNITS = 3.0


class GroupRole(StrEnum):
    CORE = "core"
    GENERAL_EDUCATION = "general_education"
    MAJOR_ELECTIVE = "major_elective"
    FREE_ELECTIVE = "free_elective"
    OTHER = "other"


@dataclass(frozen=True)
class Course:
    code: str
    title: str
    units: float | None
    description: str = ""
    component: str | None = None
    notices: tuple[str, ...] = ()
    # Seasons the course runs in; None means every Fall and Spring (and summer when the
    # student plans summers). Internships, for example, run in summer only.
    offered_terms: frozenset[Season] | None = None

    def offered_in(self, season: Season) -> bool:
        return self.offered_terms is None or season in self.offered_terms

    @property
    def summer_only(self) -> bool:
        return self.offered_terms == frozenset({Season.SUMMER})

    @property
    def subject(self) -> str:
        return codes.subject_of(self.code)

    @property
    def level(self) -> int | None:
        return codes.level_of(self.code)

    @property
    def is_placeholder(self) -> bool:
        return codes.is_placeholder(self.code)

    @property
    def credit_units(self) -> float:
        return self.units if self.units is not None else DEFAULT_COURSE_UNITS


@dataclass(frozen=True)
class Rule:
    course: str
    kind: RuleKind
    source_text: str
    expr: Expr | None  # the rule in force: the admin's correction if there is one
    status: ParseStatus
    reviewed: bool = False
    overridden: bool = False
    id: int | None = None


@dataclass(frozen=True)
class Group:
    key: str
    title: str  # as SIS shows it
    label: str  # readable name
    units_required: float
    role: GroupRole = GroupRole.OTHER
    courses: tuple[str, ...] = ()
    children: tuple[Group, ...] = ()

    @property
    def is_leaf(self) -> bool:
        return not self.children

    @property
    def is_open_pool(self) -> bool:
        return self.role is GroupRole.FREE_ELECTIVE

    def walk(self) -> Iterator[Group]:
        yield self
        for child in self.children:
            yield from child.walk()


@dataclass(frozen=True)
class Program:
    id: str
    name: str
    kind: str  # "major" or "minor"
    total_units: float
    root: Group
    catalog_year: str | None = None
    source: str | None = None
    source_date: str | None = None
    published: bool = True

    def groups(self) -> list[Group]:
        return list(self.root.walk())

    def leaf_groups(self) -> list[Group]:
        return [group for group in self.root.walk() if group.is_leaf]

    def group(self, key: str) -> Group | None:
        return next((g for g in self.root.walk() if g.key == key), None)


@dataclass
class Catalog:
    courses: dict[str, Course]
    rules: dict[str, dict[RuleKind, Rule]] = field(default_factory=dict)
    programs: dict[str, Program] = field(default_factory=dict)
    revision: int = 0

    def course(self, code: str) -> Course | None:
        return self.courses.get(code)

    def units(self, code: str) -> float:
        course = self.courses.get(code)
        return course.credit_units if course else DEFAULT_COURSE_UNITS

    def title(self, code: str) -> str:
        course = self.courses.get(code)
        return course.title if course else code

    def prerequisite(self, code: str) -> Expr | None:
        rule = self.rules.get(code, {}).get(RuleKind.PRE)
        return rule.expr if rule else None

    def corequisites(self, code: str) -> list[Expr]:
        """Rules satisfied by a course taken in the same term or earlier."""
        rules = self.rules.get(code, {})
        return [
            rule.expr
            for kind in (RuleKind.CO, RuleKind.PRE_OR_CO)
            if (rule := rules.get(kind)) is not None and rule.expr is not None
        ]

    def subjects(self) -> frozenset[str]:
        return frozenset(course.subject for course in self.courses.values())

    def published_programs(self, kind: str | None = None) -> list[Program]:
        return sorted(
            (p for p in self.programs.values() if p.published and (kind is None or p.kind == kind)),
            key=lambda p: p.name,
        )


def level_courses(program: Program, catalog: Catalog) -> Mapping[int, frozenset[str]]:
    """Core courses of a program by level, for rules like "All major program 300-level classes"."""
    by_level: dict[int, set[str]] = {}
    for group in program.leaf_groups():
        if group.role is not GroupRole.CORE:
            continue
        for code in group.courses:
            level = codes.level_of(code)
            if level is not None:
                by_level.setdefault(level, set()).add(code)
    return {level: frozenset(found) for level, found in by_level.items()}


def group_requires_all(group: Group, catalog: Catalog) -> bool:
    """True when every listed course is needed: the list adds up to exactly the units required."""
    if group.is_open_pool or not group.courses:
        return False
    pool = sum(catalog.units(code) for code in group.courses)
    return abs(pool - group.units_required) < 1e-6


def readable_group_label(title: str) -> str:
    """Fallback label for SIS group titles such as "CLA-Humanities Electives - Courses"."""
    label = re.sub(r"\s*-\s*(courses|requirements)\s*$", "", title, flags=re.I)
    label = re.sub(r"^CLA\s*-\s*", "", label)
    label = re.sub(r"\s*-\s*", " - ", label).strip(" -")
    return label[:1].upper() + label[1:]


OFFERED_TERM_NAMES = {season.name.lower(): season for season in Season}


def parse_offered_terms(value: object) -> frozenset[Season] | None:
    """``["summer"]`` -> {Season.SUMMER}; missing or empty means "every regular term"."""
    if not isinstance(value, list) or not value:
        return None
    seasons = {
        OFFERED_TERM_NAMES[name] for name in (str(v).lower() for v in value) if name in OFFERED_TERM_NAMES
    }
    return frozenset(seasons) or None

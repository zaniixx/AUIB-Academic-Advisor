"""In-memory catalog: courses, their requisite rules and program requirement trees.

The planning code reads only these objects. They are built from the database
(``app.services.catalog_cache``) or straight from a program package in tests.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from app.domain import codes
from app.domain.requisites import Advisory, AdvisoryReq, AllOf, AnyOf, CourseReq, Expr, ParseStatus, RuleKind
from app.domain.terms import Season, Term

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
    # Hidden by an admin: not shown to students or planned, but completed attempts still count.
    hidden: bool = False

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
    hidden: bool = False
    # Versions of one program share a family (F0.4). Each applies to students who joined from
    # ``valid_from`` until the next version's ``valid_from``; None means "from the start".
    family: str = ""
    valid_from: Term | None = None
    # Regular semesters (Fall and Spring) of the standard degree: 8 for most majors, 10 for the
    # five-year Dentistry and Pharmacy degrees. A plan that runs longer says so.
    standard_terms: int = 8

    @property
    def family_id(self) -> str:
        return self.family or self.id

    @property
    def available(self) -> bool:
        """Offered to students: published and not hidden by an admin."""
        return self.published and not self.hidden

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
    # Published term schedules (F0.5): the courses offered in each term that has one.
    schedules: dict[Term, frozenset[str]] = field(default_factory=dict)

    def course(self, code: str) -> Course | None:
        return self.courses.get(code)

    def offered(self, code: str, term: Term) -> bool:
        """Can ``code`` be planned in ``term``? It must exist, not be hidden, run in that
        season, and, when the term's schedule is published, be on it."""
        course = self.courses.get(code)
        if course is None or course.hidden or not course.offered_in(term.season):
            return False
        schedule = self.schedules.get(term)
        return schedule is None or code in schedule

    def visible(self, code: str) -> bool:
        """A course students can see and choose (not hidden by an admin)."""
        course = self.courses.get(code)
        return course is not None and not course.hidden

    def units(self, code: str) -> float:
        course = self.courses.get(code)
        return course.credit_units if course else DEFAULT_COURSE_UNITS

    def title(self, code: str) -> str:
        course = self.courses.get(code)
        return course.title if course else code

    def prerequisite(self, code: str) -> Expr | None:
        rule = self.rules.get(code, {}).get(RuleKind.PRE)
        return self._plannable(rule.expr) if rule and rule.expr is not None else None

    def corequisites(self, code: str) -> list[Expr]:
        """Rules satisfied by a course taken in the same term or earlier."""
        rules = self.rules.get(code, {})
        return [
            self._plannable(rule.expr)
            for kind in (RuleKind.CO, RuleKind.PRE_OR_CO)
            if (rule := rules.get(kind)) is not None and rule.expr is not None
        ]

    def _plannable(self, expr: Expr) -> Expr:
        """``expr`` with every course missing from the catalog turned into a note for the advisor.

        A rule can name a course that does not exist (a misprint in a description, or a course
        AUIB no longer lists). Planning it would add a course nobody can take, and requiring it
        would hold up the course for good, so the student is told to check it instead.
        """
        match expr:
            case CourseReq(code) if code not in self.courses:
                return AdvisoryReq(Advisory.NOTE, f"{code}, which is not in the course catalog")
            case AllOf(items):
                return AllOf(tuple(self._plannable(item) for item in items))
            case AnyOf(items):
                return AnyOf(tuple(self._plannable(item) for item in items))
        return expr

    def subjects(self) -> frozenset[str]:
        return frozenset(course.subject for course in self.courses.values())

    def published_programs(self, kind: str | None = None) -> list[Program]:
        return sorted(
            (p for p in self.programs.values() if p.available and (kind is None or p.kind == kind)),
            key=lambda p: p.name,
        )

    def versions(self, family: str) -> list[Program]:
        """The available versions of a program, oldest first (a version with no start date first)."""
        found = [p for p in self.programs.values() if p.available and p.family_id == family]
        return sorted(found, key=lambda p: (p.valid_from is not None, p.valid_from or EARLIEST_TERM, p.id))

    def families(self, kind: str | None = None) -> list[list[Program]]:
        """Each offered program as its list of versions, ordered by the newest version's name."""
        names = {p.family_id for p in self.published_programs(kind)}
        groups = [self.versions(family) for family in names]
        return sorted((g for g in groups if g), key=lambda g: g[-1].name)


EARLIEST_TERM = Term(1, Season.SPRING)


@dataclass(frozen=True)
class VersionChoice:
    """Which version of a program a student follows, and why (F0.4)."""

    program: Program
    versions: tuple[Program, ...]  # every available version of the program, oldest first
    entry: Term | None  # the term the student joined AUIB
    how: Literal["only", "joined", "chosen", "earliest"]


class VersionError(LookupError):
    """The program, or the version asked for, is not available."""


def choose_version(
    catalog: Catalog, program_id: str, entry: Term | None, chosen: str | None = None
) -> VersionChoice:
    """The version of ``program_id``'s program that applies to a student who joined in ``entry``.

    ``program_id`` may name the program (its family) or any of its versions. A student follows
    the newest version that applied when they joined; one who joined before every version on
    file follows the oldest. ``chosen`` (a version id) overrides this when the registrar has
    approved a move to another version.
    """
    named = catalog.programs.get(program_id)
    family = named.family_id if named is not None else program_id
    versions = tuple(catalog.versions(family))
    if not versions:
        raise VersionError(f"Program {program_id!r} is not available")
    if chosen:
        match = next((v for v in versions if v.id == chosen), None)
        if match is None:
            raise VersionError(f"{chosen!r} is not a version of this program")
        return VersionChoice(match, versions, entry, "chosen")
    if len(versions) == 1:
        return VersionChoice(versions[0], versions, entry, "only")
    if entry is None:
        return VersionChoice(versions[-1], versions, entry, "joined")
    applied = [v for v in versions if v.valid_from is None or v.valid_from <= entry]
    if applied:
        return VersionChoice(applied[-1], versions, entry, "joined")
    return VersionChoice(versions[0], versions, entry, "earliest")


def version_range(version: Program, versions: Sequence[Program]) -> str:
    """Whom a version applies to, such as "students who joined from Fall 2025 until Summer 2027"."""
    later = [
        v.valid_from
        for v in versions
        if v.valid_from is not None and (version.valid_from is None or v.valid_from > version.valid_from)
    ]
    until = min(later) if later else None
    if version.valid_from is None and until is None:
        return "every student"
    if version.valid_from is None:
        return f"students who joined before {until}"
    if until is None:
        return f"students who joined from {version.valid_from} on"
    return f"students who joined from {version.valid_from} and before {until}"


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

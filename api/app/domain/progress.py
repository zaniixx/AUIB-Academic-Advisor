"""Which courses count toward which requirement, and what is left (F1.2, F4.1, F4.2).

Each course counts toward one requirement group at most. Groups are filled in
the order SIS lists them, and a course that a full group cannot use moves on to
the next group that lists it (usually free electives). Courses that fit nowhere
are reported as not counting toward the degree. How SIS itself allocates a
course that fits several groups is still an open question for the registrar,
so the app says plainly that the registrar's audit is authoritative.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.catalog import Catalog, Group, Program, group_requires_all

EPSILON = 1e-6


class CourseState(StrEnum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    PLANNED = "planned"


_STATE_ORDER = {CourseState.COMPLETED: 0, CourseState.IN_PROGRESS: 1, CourseState.PLANNED: 2}


@dataclass(frozen=True)
class CountedCourse:
    code: str
    units: float
    state: CourseState


@dataclass
class GroupProgress:
    group: Group
    courses: list[CountedCourse] = field(default_factory=list)
    children: list[GroupProgress] = field(default_factory=list)

    @property
    def required(self) -> float:
        return self.group.units_required

    def _units(self, state: CourseState) -> float:
        if self.children:
            return sum(child._units(state) for child in self.children)
        return sum(course.units for course in self.courses if course.state is state)

    def counted(self, state: CourseState) -> float:
        """Units in ``state`` that count, capped so a group never exceeds what it requires."""
        earlier = sum(self._capped(s) for s in CourseState if _STATE_ORDER[s] < _STATE_ORDER[state])
        return min(self._capped(state), max(0.0, self.required - earlier))

    def _capped(self, state: CourseState) -> float:
        total = sum(child.counted(state) for child in self.children) if self.children else self._units(state)
        return min(total, self.required)

    @property
    def completed(self) -> float:
        return self.counted(CourseState.COMPLETED)

    @property
    def in_progress(self) -> float:
        return self.counted(CourseState.IN_PROGRESS)

    @property
    def planned(self) -> float:
        return self.counted(CourseState.PLANNED)

    @property
    def remaining(self) -> float:
        """Units still needed after completed, in-progress and planned courses."""
        return max(0.0, self.required - self.completed - self.in_progress - self.planned)

    @property
    def remaining_after_current(self) -> float:
        """Units still needed after completed and in-progress courses (ignoring the plan)."""
        return max(0.0, self.required - self.completed - self.in_progress)

    @property
    def is_satisfied(self) -> bool:
        return self.remaining_after_current <= EPSILON

    def codes(self) -> set[str]:
        if self.children:
            return set().union(*(child.codes() for child in self.children))
        return {course.code for course in self.courses}


@dataclass
class ProgramProgress:
    program: Program
    root: GroupProgress
    leaves: dict[str, GroupProgress]
    not_counted: list[CountedCourse]

    @property
    def percent_complete(self) -> float:
        if self.root.required <= 0:
            return 100.0
        return round(100.0 * self.root.completed / self.root.required, 1)

    def leaf_for(self, code: str) -> GroupProgress | None:
        return next((leaf for leaf in self.leaves.values() if code in leaf.codes()), None)


def allocate(
    program: Program, catalog: Catalog, courses: Iterable[tuple[str, float, CourseState]]
) -> ProgramProgress:
    leaves = program.leaf_groups()
    order = {group.key: index for index, group in enumerate(leaves)}
    memberships = {group.key: frozenset(group.courses) for group in leaves}
    progress = {group.key: GroupProgress(group) for group in leaves}
    assigned: dict[str, float] = dict.fromkeys(order, 0.0)
    not_counted: list[CountedCourse] = []

    def eligible(code: str) -> list[Group]:
        return [group for group in leaves if code in memberships[group.key]]

    items = [CountedCourse(code, units, state) for code, units, state in courses]
    # Completed work claims places first; within that, courses with the fewest
    # possible groups go first so flexible courses do not crowd them out.
    items.sort(
        key=lambda c: (
            _STATE_ORDER[c.state],
            len(eligible(c.code)) or 99,
            min((order[g.key] for g in eligible(c.code)), default=99),
            c.code,
        )
    )
    for item in items:
        target = next(
            (g for g in eligible(item.code) if assigned[g.key] < g.units_required - EPSILON),
            None,
        )
        if target is None:
            not_counted.append(item)
            continue
        assigned[target.key] += item.units
        progress[target.key].courses.append(item)

    root = _assemble(program.root, progress)
    return ProgramProgress(program, root, progress, not_counted)


def _assemble(group: Group, leaves: dict[str, GroupProgress]) -> GroupProgress:
    if group.is_leaf:
        return leaves[group.key]
    return GroupProgress(group, children=[_assemble(child, leaves) for child in group.children])


@dataclass(frozen=True)
class LeftItem:
    """One line of the "what's left" checklist."""

    group_key: str
    group_label: str
    units_needed: float
    required_courses: tuple[str, ...]  # every one of these is still needed
    options: tuple[str, ...]  # pick enough of these to cover units_needed
    open_pool: bool


def whats_left(progress: ProgramProgress, catalog: Catalog) -> list[LeftItem]:
    items = []
    for leaf in progress.leaves.values():
        needed = leaf.remaining_after_current
        if needed <= EPSILON:
            continue
        taken = leaf.codes()
        counted_elsewhere = {c.code for other in progress.leaves.values() for c in other.courses}
        open_codes = tuple(
            code
            for code in leaf.group.courses
            if code not in taken and code not in counted_elsewhere and not _placeholder(code)
        )
        if group_requires_all(leaf.group, catalog):
            items.append(LeftItem(leaf.group.key, leaf.group.label, needed, open_codes, (), False))
        else:
            items.append(
                LeftItem(
                    leaf.group.key,
                    leaf.group.label,
                    needed,
                    (),
                    () if leaf.group.is_open_pool else open_codes,
                    leaf.group.is_open_pool,
                )
            )
    return items


def _placeholder(code: str) -> bool:
    return "X" in code.split(" ", 1)[-1]

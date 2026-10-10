"""Term-by-term plans to graduation (F1.3, F1.4, F1.6, F1.9).

Planning happens in two steps.

1. Selection: every course still required (complete course lists, locked
   choices and the prerequisites they need), major electives that fit the
   student's interests without lengthening their longest prerequisite chain,
   and "slots" for open choices such as humanities or free electives, which the
   student fills from the recommendations.
2. Scheduling: term by term, place every course whose prerequisites are done,
   longest remaining prerequisite chain first, then fill the rest with slots.
   "On time" pace keeps terms at the student's preferred load and goes above it
   (never above the maximum) only when needed to graduate within the standard
   number of regular terms; "fastest" fills every term to the maximum.
   A term the student has built themselves (F1.9) holds only the courses they
   put there; the planner fills the terms after it.

The heuristic is deterministic, explains itself and plans a full degree in
milliseconds; see docs/decisions/0003-heuristic-planner.md.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Collection, Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import date
from enum import StrEnum

import networkx as nx

from app.domain.catalog import Catalog, Group, GroupRole, Program, group_requires_all, level_courses
from app.domain.graph import chain_lengths, gateways
from app.domain.progress import EPSILON, CourseState, ProgramProgress, allocate
from app.domain.recommend import Preferences, rank_courses, suggest_for_group, suggestible
from app.domain.record import StudentRecord
from app.domain.requisites import (
    DEFAULT_STANDING_CREDITS,
    EvalContext,
    Expr,
    LevelReq,
    Standing,
    course_codes,
    courses_to_add,
    evaluate,
)
from app.domain.terms import Season, Term, current_term, first_planning_term

MAX_PLAN_TERMS = 36  # including summers
TYPICAL_COURSE_UNITS = 3.0
SUGGESTIONS_PER_SLOT = 3
MAX_ALTERNATIVES = 12


class Pace(StrEnum):
    ON_TIME = "on_time"
    FASTEST = "fastest"


@dataclass(frozen=True)
class Lock:
    code: str
    term: Term


@dataclass(frozen=True)
class PlanOptions:
    preferred_units: float = 15.0
    max_units: float = 18.0
    pace: Pace = Pace.ON_TIME
    include_summer: bool = False
    summer_max_units: float = 6.0
    start_term: Term | None = None
    locks: tuple[Lock, ...] = ()
    not_before: tuple[tuple[str, Term], ...] = ()  # used by what-if to push a course later
    exclude: frozenset[str] = frozenset()
    include: frozenset[str] = frozenset()  # courses the student wants; the planner picks the term
    # Terms the student built (F1.9): they hold the student's locked courses and nothing else.
    built_terms: frozenset[Term] = frozenset()
    preferences: Preferences = field(default_factory=Preferences)
    standing_credits: Mapping[Standing, int] = field(default_factory=lambda: dict(DEFAULT_STANDING_CREDITS))
    regular_terms_to_graduate: int = 8


class ItemKind(StrEnum):
    COURSE = "course"
    SLOT = "slot"


@dataclass(frozen=True)
class PlanItem:
    kind: ItemKind
    key: str  # course code, or "slot:<group>:<n>"
    title: str
    units: float
    reason: str
    code: str | None = None
    group_key: str | None = None
    group_label: str | None = None
    locked: bool = False
    unlocks: int = 0  # program courses that depend on this one
    advisories: tuple[str, ...] = ()
    suggestions: tuple[str, ...] = ()
    # Courses that could take this item's place in the same term ("replace with").
    alternatives: tuple[str, ...] = ()


@dataclass
class PlannedTerm:
    term: Term
    items: list[PlanItem]
    built: bool = False  # the student chose this term's courses (F1.9)

    @property
    def units(self) -> float:
        return sum(item.units for item in self.items)


@dataclass(frozen=True)
class PlanIssue:
    severity: str  # "warning" or "info"
    message: str
    code: str | None = None


@dataclass
class Plan:
    start_term: Term
    terms: list[PlannedTerm]
    graduation_term: Term | None
    on_time_term: Term | None
    issues: list[PlanIssue]
    unscheduled: list[PlanItem]
    progress: ProgramProgress  # courses only; open-choice slots are in slot_units
    critical_chain: list[str]
    slot_units: dict[str, float] = field(default_factory=dict)  # group key -> units planned as slots
    # The minor's progress once the planned courses are done; None without a minor. A course
    # may count toward the major and the minor at the same time.
    minor_progress: ProgramProgress | None = None

    def term_of(self, key: str) -> Term | None:
        for planned in self.terms:
            if any(item.key == key for item in planned.items):
                return planned.term
        return None

    def course_terms(self) -> dict[str, Term]:
        return {item.code: t.term for t in self.terms for item in t.items if item.code}


@dataclass(frozen=True)
class EligibleCourse:
    code: str
    title: str
    units: float
    group_key: str
    group_label: str
    unlocks: int
    advisories: tuple[str, ...] = ()
    take_with: tuple[str, ...] = ()  # corequisites to take in the same term


@dataclass(frozen=True)
class _Slot:
    key: str
    group_key: str
    group_label: str
    units: float
    suggestions: tuple[str, ...]


@dataclass
class _Selection:
    courses: dict[str, str]  # code -> why it is in the plan
    slots: list[_Slot]
    issues: list[PlanIssue]
    elective_picks: set[str] = field(default_factory=set)  # electives the planner chose for the student
    minor_picks: set[str] = field(default_factory=set)  # courses chosen for the minor's choose-from lists


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def build_plan(
    program: Program,
    catalog: Catalog,
    record: StudentRecord,
    options: PlanOptions,
    today: date,
    minor: Program | None = None,
    alternatives: bool = True,
) -> Plan:
    """The plan to graduation. Without ``alternatives`` the "replace with" lists are left empty,
    which saves time when only the terms and the graduation term are needed."""
    start = options.start_term or first_planning_term(today, options.include_summer)
    in_session = current_term(today)
    selection = _select(program, catalog, record, options, minor)
    deadline = _on_time_term(record, start, options)

    def schedule(target_deadline: Term | None) -> Plan:
        return _schedule(program, catalog, record, options, start, in_session, selection, target_deadline)

    if options.pace is Pace.FASTEST or deadline is None or deadline < start:
        plan = schedule(None)
    else:
        plan = schedule(deadline)
        if plan.unscheduled or (plan.graduation_term is not None and plan.graduation_term > deadline):
            fastest = schedule(None)
            if _sooner(fastest, plan):
                plan = fastest
    if deadline is not None and plan.graduation_term is not None and plan.graduation_term > deadline:
        plan.issues.insert(
            0,
            PlanIssue(
                "warning",
                f"The standard {options.regular_terms_to_graduate}-semester finish would be "
                f"{deadline.label}. At up to {options.max_units:g} credits a term the earliest finish is "
                f"{plan.graduation_term.label}.",
            ),
        )
    plan.on_time_term = deadline
    plan.issues[0:0] = selection.issues
    if alternatives:
        plan.terms = _attach_alternatives(plan, program, catalog, record, options, selection, minor)
    if minor is not None:
        plan.minor_progress = _with_planned(minor, catalog, record, plan.course_terms())
    return plan


def current_progress(program: Program, catalog: Catalog, record: StudentRecord) -> ProgramProgress:
    """``program``'s progress from the student's completed and in-progress courses alone."""
    return allocate(program, catalog, _counted(record, catalog))


def _with_planned(
    program: Program, catalog: Catalog, record: StudentRecord, planned: Iterable[str]
) -> ProgramProgress:
    """``program``'s progress once ``planned`` courses are done, on top of the student's record."""
    courses = [(code, catalog.units(code), CourseState.PLANNED) for code in sorted(planned)]
    return allocate(program, catalog, [*_counted(record, catalog), *courses])


def eligible_next_term(
    program: Program,
    catalog: Catalog,
    record: StudentRecord,
    options: PlanOptions,
    term: Term | None = None,
    minor: Program | None = None,
    before: Collection[str] = (),
    alongside: Collection[str] = (),
) -> list[EligibleCourse]:
    """Courses that count toward an unmet requirement and can be taken next term (F1.3).

    With ``term``, courses that cannot run in that term (internships outside summer,
    courses missing from the term's published schedule, hidden courses) are left out.
    With ``minor``, its unmet requirements count too. ``before`` are courses planned for
    earlier terms, counted as done; ``alongside`` are courses already chosen for this
    term: they count toward requirements, satisfy corequisites and are not listed again.
    """
    have = record.have | frozenset(before)
    chosen = frozenset(alongside) - have
    planned_codes = sorted((have - record.have) | chosen)
    planned = [(code, catalog.units(code), CourseState.PLANNED) for code in planned_codes]
    programs = [program] if minor is None else [program, minor]
    progress = {
        leaf_key: leaf
        for each in programs
        for leaf_key, leaf in allocate(each, catalog, [*_counted(record, catalog), *planned]).leaves.items()
    }
    leaves = [leaf for each in programs for leaf in each.leaf_groups()]
    level_map = level_courses(program, catalog)
    unlocks = {g.code: len(g.dependents) for g in gateways(program, catalog, minimum=1)}
    context = EvalContext(
        completed=have,
        credits=record.completed_units(catalog)
        + record.in_progress_units(catalog)
        + sum(catalog.units(code) for code in have - record.have),
        concurrent=chosen,
        level_courses=level_map,
        standing_credits=options.standing_credits,
    )
    eligible_codes = {
        code
        for leaf in leaves
        if not leaf.is_open_pool
        for code in leaf.courses
        if code in catalog.courses
        and code not in have
        and code not in chosen
        and (catalog.visible(code) if term is None else catalog.offered(code, term))
        and evaluate(catalog.prerequisite(code), context).satisfied
    }

    result: list[EligibleCourse] = []
    seen: set[str] = set()
    for leaf in leaves:
        if leaf.is_open_pool or progress[leaf.key].remaining <= EPSILON:
            continue
        for code in leaf.courses:
            if code in seen or code not in eligible_codes or catalog.courses[code].is_placeholder:
                continue
            take_with: set[str] = set()
            corequisites_ok = True
            for rule in catalog.corequisites(code):
                if evaluate(rule, context).satisfied:
                    continue
                needed = courses_to_add(rule, have | chosen, level_map, lambda _c: 1.0)
                if needed <= eligible_codes:
                    take_with |= needed
                else:
                    corequisites_ok = False
            if not corequisites_ok:
                continue
            seen.add(code)
            result.append(
                EligibleCourse(
                    code=code,
                    title=catalog.title(code),
                    units=catalog.units(code),
                    group_key=leaf.key,
                    group_label=leaf.label,
                    unlocks=unlocks.get(code, 0),
                    advisories=evaluate(catalog.prerequisite(code), context).advisories,
                    take_with=tuple(sorted(take_with)),
                )
            )
    return result


def building_term(plan: Plan) -> PlannedTerm | None:
    """The term the student is building now (F1.9): the first planned term they have not built."""
    return next((planned for planned in plan.terms if not planned.built), None)


def term_choices(
    program: Program,
    catalog: Catalog,
    record: StudentRecord,
    options: PlanOptions,
    plan: Plan,
    planned: PlannedTerm,
    minor: Program | None = None,
) -> list[EligibleCourse]:
    """Courses the student could add to ``planned`` besides the ones the plan already has there (F1.9).

    Courses in earlier terms count as done and the student's own courses in this term count as
    taken with it, so a course is listed when it still counts toward a requirement, runs that
    term and has its prerequisites done by the end of the term before.
    """
    index = plan.terms.index(planned)
    before = {item.code for earlier in plan.terms[:index] for item in earlier.items if item.code}
    chosen = {item.code for item in planned.items if item.code and item.locked}
    in_term = {item.code for item in planned.items if item.code}
    found = eligible_next_term(program, catalog, record, options, planned.term, minor, before, chosen)
    # A student who does not plan summers only sees a summer for the courses that run then alone.
    summer_only = planned.term.season is Season.SUMMER and not options.include_summer
    return [
        course
        for course in found
        if course.code not in in_term and (not summer_only or catalog.courses[course.code].summer_only)
    ]


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def _counted(record: StudentRecord, catalog: Catalog) -> list[tuple[str, float, CourseState]]:
    return [(c, record.units_of(c, catalog), CourseState.COMPLETED) for c in sorted(record.completed)] + [
        (c, record.units_of(c, catalog), CourseState.IN_PROGRESS) for c in sorted(record.in_progress)
    ]


def _select(
    program: Program,
    catalog: Catalog,
    record: StudentRecord,
    options: PlanOptions,
    minor: Program | None = None,
) -> _Selection:
    have = record.have
    level_map = level_courses(program, catalog)
    named = [program] if minor is None else [program, minor]
    useful = {
        code
        for each in named
        for leaf in each.leaf_groups()
        if not leaf.is_open_pool
        for code in leaf.courses
    }
    issues: list[PlanIssue] = []

    def cost(code: str) -> float:
        return (0.5 if code in useful else 1.0) + (0.0 if code in catalog.courses else 1.0)

    chosen: dict[str, str] = {}
    for lock in options.locks:
        if lock.code not in have:
            chosen[lock.code] = "You placed this course"
    for code in sorted(options.include):
        if code not in have and code in catalog.courses:
            chosen.setdefault(code, "You chose this course")
    for leaf in program.leaf_groups():
        if group_requires_all(leaf, catalog):
            for code in leaf.courses:
                if code not in have:
                    chosen.setdefault(code, f"Required: {leaf.label}")
    _add_prerequisites(chosen, have, catalog, level_map, cost)

    def progress_with(selected: Mapping[str, str]) -> ProgramProgress:
        planned = [(code, catalog.units(code), CourseState.PLANNED) for code in sorted(selected)]
        return allocate(program, catalog, _counted(record, catalog) + planned)

    def longest(selected: Mapping[str, str]) -> int:
        return max(chain_lengths(_planning_graph(selected, catalog, level_map)).values(), default=0)

    picks: set[str] = set()
    minor_picks: set[str] = set()
    context = EvalContext(
        completed=have,
        credits=record.completed_units(catalog) + record.in_progress_units(catalog),
        level_courses=level_map,
        standing_credits=options.standing_credits,
    )

    def choose(
        group: Group,
        why: Callable[[str], str],
        still_needed: Callable[[Mapping[str, str]], float],
        chosen_for: set[str],
    ) -> None:
        """Add the group's best-ranked courses until it is covered, keeping the longest chain if possible."""
        nonlocal chosen
        candidates = [
            code
            for code in group.courses
            if code in catalog.courses
            and code not in have
            and code not in chosen
            and code not in options.exclude
            and not catalog.courses[code].is_placeholder
            and not catalog.courses[code].hidden
        ]
        ranked = rank_courses(candidates, catalog, options.preferences, context, group.courses)
        baseline = longest(chosen)
        needed = still_needed(chosen)
        # First pass: courses that do not lengthen the longest prerequisite chain
        # (and so cannot delay graduation); second pass: anything still needed.
        for allow_longer in (False, True):
            for suggestion in ranked:
                if needed <= EPSILON:
                    return
                if suggestion.code in chosen:
                    continue
                trial = dict(chosen)
                trial[suggestion.code] = why(suggestion.reasons[0])
                _add_prerequisites(trial, have, catalog, level_map, cost)
                if any(code not in catalog.courses for code in trial.keys() - chosen.keys()):
                    continue
                if not allow_longer and longest(trial) > baseline:
                    continue
                chosen = trial
                chosen_for.add(suggestion.code)
                needed = still_needed(chosen)

    if minor is not None:
        # The minor comes before the major's open choices, so its courses fill the major's free
        # electives and CLA slots wherever they count there instead of adding units.
        the_minor = minor
        for leaf in the_minor.leaf_groups():

            def minor_needs(selected: Mapping[str, str], key: str = leaf.key) -> float:
                return _with_planned(the_minor, catalog, record, selected).leaves[key].remaining

            def minor_reason(reason: str, label: str = leaf.label) -> str:
                return f"{label} ({_lower_first(reason)})"

            if minor_needs(chosen) <= EPSILON:
                continue
            if group_requires_all(leaf, catalog):
                for code in leaf.courses:
                    if code not in have:
                        chosen.setdefault(code, f"Required for the {the_minor.name} minor")
                _add_prerequisites(chosen, have, catalog, level_map, cost)
                continue
            choose(leaf, minor_reason, minor_needs, minor_picks)
            remaining = minor_needs(chosen)
            if remaining > EPSILON:
                issues.append(
                    PlanIssue(
                        "warning",
                        f"{leaf.label} still needs {remaining:g} credits that no listed course can cover.",
                    )
                )

    progress = progress_with(chosen)
    for leaf in program.leaf_groups():
        if leaf.role is not GroupRole.MAJOR_ELECTIVE or progress.leaves[leaf.key].remaining <= EPSILON:
            continue

        def major_needs(selected: Mapping[str, str], key: str = leaf.key) -> float:
            return progress_with(selected).leaves[key].remaining

        def major_reason(reason: str, label: str = leaf.label) -> str:
            return f"{label}: {reason}"

        choose(leaf, major_reason, major_needs, picks)
        progress = progress_with(chosen)

    slots: list[_Slot] = []
    exclude = set(have) | set(chosen) | set(options.exclude)
    for leaf in program.leaf_groups():
        remaining = progress.leaves[leaf.key].remaining
        if remaining <= EPSILON:
            continue
        if group_requires_all(leaf, catalog):
            issues.append(
                PlanIssue(
                    "warning", f"{leaf.label} still needs {remaining:g} credits that no listed course covers."
                )
            )
            continue
        count = math.ceil(remaining / TYPICAL_COURSE_UNITS - EPSILON)
        found = suggest_for_group(
            leaf,
            remaining,
            catalog,
            options.preferences,
            context,
            exclude,
            limit=SUGGESTIONS_PER_SLOT * count,
        )
        codes = [suggestion.code for suggestion in found.suggestions]
        for index in range(count):
            # Each slot gets its own suggestions, so the plan does not repeat the same courses.
            own = codes[index * SUGGESTIONS_PER_SLOT : (index + 1) * SUGGESTIONS_PER_SLOT]
            slots.append(
                _Slot(
                    key=f"slot:{leaf.key}:{index + 1}",
                    group_key=leaf.key,
                    group_label=leaf.label,
                    units=min(TYPICAL_COURSE_UNITS, remaining - TYPICAL_COURSE_UNITS * index),
                    suggestions=tuple(own or codes[:SUGGESTIONS_PER_SLOT]),
                )
            )
    return _Selection(chosen, slots, issues, picks, minor_picks)


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:]


def _add_prerequisites(
    chosen: dict[str, str],
    have: frozenset[str],
    catalog: Catalog,
    level_map: Mapping[int, frozenset[str]],
    cost: Callable[[str], float],
) -> None:
    """Add every course the chosen courses need first, until nothing new is needed."""
    pending = list(chosen)
    while pending:
        code = pending.pop()
        for rule in (catalog.prerequisite(code), *catalog.corequisites(code)):
            for needed in sorted(courses_to_add(rule, have | frozenset(chosen), level_map, cost)):
                if needed not in chosen:
                    chosen[needed] = f"Needed before {code}"
                    pending.append(needed)


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------


def _schedule(
    program: Program,
    catalog: Catalog,
    record: StudentRecord,
    options: PlanOptions,
    start: Term,
    in_session: Term,
    selection: _Selection,
    deadline: Term | None,
) -> Plan:
    return _Scheduler(program, catalog, record, options, start, in_session, selection, deadline).run()


@dataclass
class _TermDraft:
    """What has been put into the term being filled so far."""

    term: Term
    capacity: float
    courses: list[str] = field(default_factory=list)
    slots: list[_Slot] = field(default_factory=list)
    units: float = 0.0

    def fits(self, units: float) -> bool:
        return self.units + units <= self.capacity + EPSILON


class _Scheduler:
    def __init__(
        self,
        program: Program,
        catalog: Catalog,
        record: StudentRecord,
        options: PlanOptions,
        start: Term,
        in_session: Term,
        selection: _Selection,
        deadline: Term | None,
    ) -> None:
        self.program, self.catalog, self.record, self.options = program, catalog, record, options
        self.start, self.in_session, self.selection, self.deadline = start, in_session, selection, deadline
        self.level_map = level_courses(program, catalog)
        self.graph = _planning_graph(selection.courses, catalog, self.level_map)
        self.chains = chain_lengths(self.graph)
        self.dependents = {code: len(nx.descendants(self.graph, code)) for code in self.graph.nodes}
        self.unlocks = {g.code: len(g.dependents) for g in gateways(program, catalog, minimum=1)}
        self.not_before = dict(options.not_before)
        self.issues: list[PlanIssue] = []
        self.locks: dict[str, Term] = {}
        for lock in options.locks:
            if lock.code not in selection.courses:
                continue
            if lock.term < start:
                message = f"{lock.code} is locked to {lock.term.label}, which has passed."
                self.issues.append(PlanIssue("warning", message, lock.code))
            else:
                self.locks[lock.code] = lock.term
        self.pending = sorted(selection.courses, key=self._priority)
        self.pending_slots = list(selection.slots)
        self.completed = set(record.have)
        self.credits = record.completed_units(catalog) + record.in_progress_units(catalog)
        self.advisories: dict[str, tuple[str, ...]] = {}
        self.entry = record.first_term() or start

    # Ordering ------------------------------------------------------------

    def _priority(self, code: str) -> tuple[int, int, int, str]:
        """Longest chain of dependents first: delaying those delays graduation."""
        return (-self.chains.get(code, 1), -self.dependents.get(code, 0), _level(code, self.catalog), code)

    def _by_level(self, code: str) -> tuple[int, int, int, str]:
        """Flexible courses follow the usual degree-map order: 100-level first."""
        return (_level(code, self.catalog), -self.chains.get(code, 1), -self.dependents.get(code, 0), code)

    # Checks --------------------------------------------------------------

    def _context(self, concurrent: list[str] | None = None) -> EvalContext:
        return EvalContext(
            completed=frozenset(self.completed),
            credits=self.credits,
            concurrent=frozenset(concurrent or ()),
            level_courses=self.level_map,
            standing_credits=self.options.standing_credits,
        )

    def _ready(self, code: str, term: Term) -> bool:
        if code in self.locks or term < self.not_before.get(code, term):
            return False
        # Hidden courses, the wrong season, or missing from the term's published schedule.
        if code in self.catalog.courses and not self.catalog.offered(code, term):
            return False
        result = evaluate(self.catalog.prerequisite(code), self._context())
        if result.satisfied:
            self.advisories[code] = result.advisories
        return result.satisfied

    def _remaining_units(self) -> float:
        return sum(self.catalog.units(c) for c in self.pending) + sum(s.units for s in self.pending_slots)

    def _capacity(self, term: Term) -> float:
        options = self.options
        if term.season is Season.SUMMER:
            return options.summer_max_units
        if self.deadline is None:
            return options.max_units
        terms_left = term.regular_terms_until(self.deadline)
        if terms_left <= 0:
            return options.max_units
        return min(options.max_units, max(options.preferred_units, self._remaining_units() / terms_left))

    def _horizon(self, term: Term) -> int:
        """Terms left to finish in; tells urgent chain courses from flexible ones."""
        if self.deadline is not None:
            return max(1, term.regular_terms_until(self.deadline))
        longest = max((self.chains.get(c, 1) for c in self.pending), default=1)
        return max(longest, math.ceil(self._remaining_units() / self.options.max_units))

    # Filling a term ------------------------------------------------------

    def _place_locked(self, draft: _TermDraft) -> None:
        for code in [c for c in self.pending if self.locks.get(c) == draft.term]:
            check = evaluate(self.catalog.prerequisite(code), self._context())
            self.advisories[code] = check.advisories
            if not check.satisfied:
                missing = ", ".join(check.missing)
                message = f"{code} is locked to {draft.term.label} but still needs {missing}."
                self.issues.append(PlanIssue("warning", message, code))
            draft.courses.append(code)
            draft.units += self.catalog.units(code)
        if draft.units > self.options.max_units + EPSILON:
            limit = f"{self.options.max_units:g}"
            message = f"{draft.term.label} is over {limit} credits because of locked courses."
            self.issues.append(PlanIssue("warning", message))

    def _fill_courses(self, draft: _TermDraft, order: list[str], wanted: Callable[[str], bool]) -> None:
        changed = True
        while changed:  # repeat so a course whose corequisite was just placed can join
            changed = False
            for code in order:
                if code in draft.courses or not wanted(code) or not self._ready(code, draft.term):
                    continue
                size = self.catalog.units(code)
                if not draft.fits(size):
                    continue
                rules = self.catalog.corequisites(code)
                if all(evaluate(rule, self._context(draft.courses)).satisfied for rule in rules):
                    draft.courses.append(code)
                    draft.units += size
                    changed = True
                    continue
                known = frozenset(self.completed | set(draft.courses))
                partners = set().union(*(courses_to_add(r, known, self.level_map, _flat_cost) for r in rules))
                extra = sum(self.catalog.units(p) for p in partners)
                if (
                    partners
                    and partners <= set(self.pending) - set(draft.courses)
                    and all(self._ready(p, draft.term) for p in partners)
                    and draft.fits(size + extra)
                ):
                    draft.courses.extend([code, *sorted(partners)])
                    draft.units += size + extra
                    changed = True

    def _fill_slots(self, draft: _TermDraft, limit: float) -> None:
        added = 0.0
        for slot in list(self.pending_slots):
            if added >= limit - EPSILON:
                break
            if draft.fits(slot.units):
                draft.slots.append(slot)
                self.pending_slots.remove(slot)
                draft.units += slot.units
                added += slot.units

    def _fill(self, term: Term) -> _TermDraft:
        draft = _TermDraft(term, self._capacity(term))
        if term in self.options.built_terms:
            # The student chose this term's courses (F1.9): nothing else goes in.
            self._place_locked(draft)
            return draft
        if term.season is Season.SUMMER and not self.options.include_summer:
            # The student did not plan summers, but some courses (internships) run only then.
            self._place_locked(draft)
            self._fill_courses(draft, self.pending, self._summer_only)
            return draft
        horizon = self._horizon(term)
        year_level = 100 * min(4, 1 + max(0, self.entry.regular_terms_until(term) - 1) // 2)
        flexible = sorted(self.pending, key=self._by_level)
        picks = self.selection.elective_picks

        # Order of filling: courses whose chain of dependents needs (nearly) every
        # remaining term; required courses at the student's year level (100-level
        # in year one, and so on); this term's share of open-choice slots, so
        # electives spread across the degree; then anything else that fits.
        self._place_locked(draft)
        self._fill_courses(draft, self.pending, lambda c: self.chains.get(c, 1) >= horizon - 1)
        self._fill_courses(
            draft, flexible, lambda c: c not in picks and _level(c, self.catalog) <= year_level
        )
        slot_units = sum(s.units for s in self.pending_slots)
        share = math.ceil(slot_units / horizon / TYPICAL_COURSE_UNITS) * TYPICAL_COURSE_UNITS
        self._fill_slots(draft, share)
        self._fill_courses(draft, flexible, lambda _c: True)
        self._fill_slots(draft, math.inf)
        return draft

    def _summer_only(self, code: str) -> bool:
        course = self.catalog.courses.get(code)
        return course is not None and course.summer_only

    # The whole plan ------------------------------------------------------

    def run(self) -> Plan:
        terms: list[PlannedTerm] = []
        term, stalled = self.start, 0
        for _ in range(MAX_PLAN_TERMS):
            if not self.pending and not self.pending_slots:
                break
            draft = self._fill(term)
            if draft.courses or draft.slots:
                items = [self._course_item(code) for code in draft.courses]
                items += [_slot_item(slot) for slot in draft.slots]
                terms.append(PlannedTerm(term, items, built=term in self.options.built_terms))
                stalled = 0
            elif term.season is not Season.SUMMER:
                waiting = self._waiting(term) or term in self.options.built_terms
                stalled = 0 if waiting else stalled + 1
                if stalled >= 2:
                    break
            self.pending = [c for c in self.pending if c not in draft.courses]
            self.completed.update(draft.courses)
            self.credits += draft.units
            term = term.next(include_summer=True)  # summers are skipped in _fill unless needed
        return self._result(terms)

    def _waiting(self, term: Term) -> bool:
        """True when an empty term is deliberate: a course is held for a later term."""
        return any(
            self.not_before.get(code, term) > term or self.locks.get(code, term) > term
            for code in self.pending
        )

    def _result(self, terms: list[PlannedTerm]) -> Plan:
        catalog = self.catalog
        unscheduled = [self._course_item(code) for code in self.pending]
        unscheduled += [_slot_item(slot) for slot in self.pending_slots]
        for code in self.pending:
            missing = evaluate(catalog.prerequisite(code), self._context()).missing
            course = catalog.courses.get(code)
            if missing:
                reason = f"it needs {', '.join(missing)}"
            elif course is not None and course.hidden:
                reason = "it is not offered at the moment"
            else:
                reason = "it does not fit the credit limits or the terms it runs in"
            self.issues.append(PlanIssue("warning", f"{code} could not be scheduled because {reason}.", code))
        for code, notes in sorted(self.advisories.items()):
            if code not in self.pending:
                self.issues.extend(PlanIssue("info", f"{code}: {note}", code) for note in notes)

        planned = [
            (code, catalog.units(code), CourseState.PLANNED)
            for code in self.selection.courses
            if code not in self.pending
        ]
        progress = allocate(self.program, catalog, [*_counted(self.record, catalog), *planned])
        graduation = terms[-1].term if terms else _last_in_progress_term(self.record, self.in_session)
        slot_totals: dict[str, float] = {}
        for planned_term in terms:
            for item in planned_term.items:
                if item.kind is ItemKind.SLOT and item.group_key:
                    slot_totals[item.group_key] = slot_totals.get(item.group_key, 0.0) + item.units
        return Plan(
            start_term=self.start,
            terms=terms,
            graduation_term=graduation,
            on_time_term=self.deadline,
            issues=self.issues,
            unscheduled=unscheduled,
            progress=progress,
            critical_chain=_critical_chain(self.graph, self.chains),
            slot_units=slot_totals,
        )

    def _course_item(self, code: str) -> PlanItem:
        return PlanItem(
            kind=ItemKind.COURSE,
            key=code,
            code=code,
            title=self.catalog.title(code),
            units=self.catalog.units(code),
            reason=self.selection.courses.get(code, ""),
            locked=code in self.locks,
            unlocks=self.unlocks.get(code, 0),
            advisories=self.advisories.get(code, ()),
        )


def _attach_alternatives(
    plan: Plan,
    program: Program,
    catalog: Catalog,
    record: StudentRecord,
    options: PlanOptions,
    selection: _Selection,
    minor: Program | None = None,
) -> list[PlannedTerm]:
    """List, for each open-choice item, the courses that could take its place in the same term.

    An item has alternatives when it counts toward a group where the student chooses
    (electives, open slots) and no other planned course depends on it. A course qualifies
    when it counts toward the same group, runs in that season, fits the unit limit, has
    its prerequisites done by the end of the previous term and has its corequisites in
    the same term (requirement 3 of the 2026-10-08 clarifications). A course chosen for
    the minor is replaced only by another course of the same minor requirement.
    """
    level_map = level_courses(program, catalog)
    graph = _planning_graph(selection.courses, catalog, level_map)
    groups = {group.key: group for group in program.leaf_groups()}
    group_of = {
        counted.code: leaf.group
        for leaf in plan.progress.leaves.values()
        for counted in leaf.courses
        if counted.state is CourseState.PLANNED
    }
    planned_codes = {item.code for t in plan.terms for item in t.items if item.code}
    # Courses the minor needs that were not picked from one of its lists (such as a course
    # every student of the minor takes) have nothing that could replace them.
    keep: set[str] = set()
    if minor is not None:
        for leaf in _with_planned(minor, catalog, record, planned_codes).leaves.values():
            for counted in leaf.courses:
                if counted.state is not CourseState.PLANNED:
                    continue
                if counted.code in selection.minor_picks:
                    group_of[counted.code] = leaf.group
                else:
                    keep.add(counted.code)
    taken = planned_codes | set(record.have) | set(options.exclude)
    credits = record.completed_units(catalog) + record.in_progress_units(catalog)
    base = EvalContext(
        record.have, credits, level_courses=level_map, standing_credits=options.standing_credits
    )
    ranked: dict[str, list[str]] = {}

    def candidates(group: Group) -> list[str]:
        if group.key not in ranked:
            pool = catalog.courses if group.is_open_pool else group.courses
            choosable = [code for code in pool if suggestible(code, catalog, set())]
            order = rank_courses(choosable, catalog, options.preferences, base, group.courses)
            ranked[group.key] = [suggestion.code for suggestion in order]
        return ranked[group.key]

    completed = set(record.have)
    result = []
    for planned in plan.terms:
        before = EvalContext(
            frozenset(completed), credits, level_courses=level_map, standing_credits=options.standing_credits
        )
        same_term = [item.code for item in planned.items if item.code]
        limit = options.summer_max_units if planned.term.season is Season.SUMMER else options.max_units
        items = []
        for item in planned.items:
            group = (
                groups.get(item.group_key or "")
                if item.kind is ItemKind.SLOT
                else group_of.get(item.code or "")
            )
            # A course another planned course depends on cannot be swapped out.
            needed_later = item.code in graph and any(
                successor in planned_codes for successor in graph.successors(item.code)
            )
            if group is None or group_requires_all(group, catalog) or needed_later or item.code in keep:
                items.append(item)
                continue
            others = frozenset(code for code in same_term if code != item.code)
            room = limit - (planned.units - item.units)
            with_others = EvalContext(
                frozenset(completed),
                credits,
                concurrent=others,
                level_courses=level_map,
                standing_credits=options.standing_credits,
            )
            options_found: list[str] = []
            for code in candidates(group):
                course = catalog.courses[code]
                if (
                    code in taken
                    or not catalog.offered(code, planned.term)
                    or course.credit_units > room + EPSILON
                    or not evaluate(catalog.prerequisite(code), before).satisfied
                    or not all(evaluate(rule, with_others).satisfied for rule in catalog.corequisites(code))
                ):
                    continue
                options_found.append(code)
                if len(options_found) >= MAX_ALTERNATIVES:
                    break
            items.append(
                replace(item, alternatives=tuple(options_found), group_key=group.key, group_label=group.label)
            )
        result.append(PlannedTerm(planned.term, items, planned.built))
        completed.update(same_term)
        credits += planned.units
    return result


def _flat_cost(_code: str) -> float:
    return 1.0


def _level(code: str, catalog: Catalog) -> int:
    course = catalog.courses.get(code)
    return (course.level or 0) if course else 0


def _sooner(candidate: Plan, current: Plan) -> bool:
    if len(candidate.unscheduled) != len(current.unscheduled):
        return len(candidate.unscheduled) < len(current.unscheduled)
    if candidate.graduation_term is None or current.graduation_term is None:
        return candidate.graduation_term is None
    return candidate.graduation_term < current.graduation_term


def _planning_graph(
    chosen: Mapping[str, str], catalog: Catalog, level_map: Mapping[int, frozenset[str]]
) -> nx.DiGraph:
    graph = nx.DiGraph()
    graph.add_nodes_from(chosen)
    for code in chosen:
        rule = catalog.prerequisite(code)
        needed = course_codes(rule) | _level_dependencies(rule, level_map)
        graph.add_edges_from((before, code) for before in needed if before in chosen and before != code)
    return graph


def _level_dependencies(rule: Expr | None, level_map: Mapping[int, frozenset[str]]) -> set[str]:
    if isinstance(rule, LevelReq):
        return set(level_map.get(rule.level, frozenset()))
    items: tuple[Expr, ...] = getattr(rule, "items", ())
    return set().union(*(_level_dependencies(item, level_map) for item in items))


def _critical_chain(graph: nx.DiGraph, chains: Mapping[str, int]) -> list[str]:
    if not chains:
        return []
    code = min(chains, key=lambda c: (-chains[c], c))
    chain = [code]
    while successors := [s for s in graph.successors(code) if chains.get(s, 0) == chains[code] - 1]:
        code = sorted(successors)[0]
        chain.append(code)
    return chain


def _slot_item(slot: _Slot) -> PlanItem:
    return PlanItem(
        kind=ItemKind.SLOT,
        key=slot.key,
        title=f"{slot.group_label} (your choice)",
        units=slot.units,
        reason=f"Choose any course that counts toward {slot.group_label}",
        group_key=slot.group_key,
        group_label=slot.group_label,
        suggestions=slot.suggestions,
    )


def _on_time_term(record: StudentRecord, start: Term, options: PlanOptions) -> Term | None:
    """The last regular term of a standard-length degree, counted from the student's first term."""
    term = record.first_term() or start
    count = 0
    for _ in range(4 * options.regular_terms_to_graduate):
        if term.is_regular:
            count += 1
            if count == options.regular_terms_to_graduate:
                return term
        term = term.next(include_summer=True)
    return None


def _last_in_progress_term(record: StudentRecord, in_session: Term) -> Term | None:
    """Graduation term when nothing is left to plan: the term of the last in-progress course."""
    terms = [a.term for a in record.attempts if a.code in record.in_progress and a.term is not None]
    if terms:
        return max(terms)
    return in_session if record.in_progress else None

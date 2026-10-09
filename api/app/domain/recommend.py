"""Elective recommendations (F2.1, F2.2).

Ranking is deliberately simple and explainable: a course scores points for
matching the student's interests, plans after graduation and career direction (by
keywords in its title and description), for being takeable next term and for
opening other courses the student would like, and loses points for what the student
would rather avoid when its description mentions it. Every suggestion lists the
reasons behind its score. Review-based workload and difficulty (F2.3) will join the
score once reviews exist.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.catalog import Catalog, Group, Program, group_requires_all
from app.domain.graph import prerequisite_graph
from app.domain.interests import (
    GOALS,
    GOALS_BY_ID,
    INTERESTS,
    INTERESTS_BY_ID,
    PLANS_BY_ID,
    TRAITS_BY_ID,
    Goal,
    Interest,
    has_trait,
    interest_matches,
)
from app.domain.requisites import EvalContext, evaluate

__all__ = ["GOALS", "INTERESTS", "Goal", "Interest", "interest_matches"]

MAX_UNDERGRADUATE_LEVEL = 400


class Workload(StrEnum):
    LIGHT = "light"
    BALANCED = "balanced"
    CHALLENGING = "challenging"


# What a course loses when its description mentions something the student would rather avoid.
AVOID_PENALTY = 0.6
# A direction or a plan counts for a course only when its title names a topic that helps, or its
# description mentions several; one passing mention (0.4) is not enough.
DIRECTION_THRESHOLD = 0.5


@dataclass(frozen=True)
class Preferences:
    interests: tuple[str, ...] = ()
    goal: str | None = None
    workload: Workload = Workload.BALANCED
    plans: str | None = None  # after graduation: see interests.PLANS
    avoid: tuple[str, ...] = ()  # see interests.TRAITS


@dataclass(frozen=True)
class Suggestion:
    code: str
    title: str
    units: float
    score: float
    reasons: tuple[str, ...]
    eligible_now: bool
    missing: tuple[str, ...] = ()


@dataclass(frozen=True)
class GroupSuggestions:
    group: Group
    units_needed: float
    suggestions: tuple[Suggestion, ...] = field(default_factory=tuple)


def rank_courses(
    candidates: Iterable[str],
    catalog: Catalog,
    preferences: Preferences,
    context: EvalContext,
    pool_for_unlocks: Iterable[str] = (),
) -> list[Suggestion]:
    """Score ``candidates`` for this student, best first."""
    candidate_list = [c for c in dict.fromkeys(candidates) if c in catalog.courses]
    pool = set(pool_for_unlocks) | set(candidate_list)
    graph = prerequisite_graph(catalog, pool)
    goal = GOALS_BY_ID.get(preferences.goal or "")
    affinity = {code: _affinity(code, catalog, preferences, goal)[0] for code in pool}

    suggestions = []
    for code in candidate_list:
        course = catalog.courses[code]
        score, reasons = _affinity(code, catalog, preferences, goal)
        check = evaluate(catalog.prerequisite(code), context)
        if check.satisfied:
            score += 0.5
            reasons.append("You can take it next term")
        else:
            score -= 0.3 * len(check.missing)
            reasons.append("Needs " + ", ".join(check.missing) + " first")
        liked_later = sorted(c for c in graph.successors(code) if affinity.get(c, 0) > 0)
        if liked_later:
            score += 0.3 * len(liked_later)
            reasons.append(
                "Opens " + ", ".join(liked_later[:3]) + (" and more" if len(liked_later) > 3 else "")
            )
        level = course.level or 100
        if preferences.workload is Workload.LIGHT and level <= 200:
            score += 0.3
            reasons.append("Introductory level, which suits a lighter workload")
        elif preferences.workload is Workload.CHALLENGING and level >= 300:
            score += 0.3
            reasons.append("Advanced level, which suits a challenging workload")
        for trait_id in preferences.avoid:
            trait = TRAITS_BY_ID.get(trait_id)
            if trait and has_trait(course.title, course.description, course.component, trait):
                score -= AVOID_PENALTY
                reasons.append(f"Its description mentions {trait.noun}, which you would rather avoid")
        suggestions.append(
            Suggestion(code, course.title, course.credit_units, round(score, 2), tuple(reasons),
                       check.satisfied, check.missing)
        )  # fmt: skip
    suggestions.sort(key=lambda s: (-s.score, not s.eligible_now, s.code))
    return suggestions


def _affinity(
    code: str, catalog: Catalog, preferences: Preferences, goal: Goal | None
) -> tuple[float, list[str]]:
    course = catalog.courses[code]
    score, reasons = 0.0, []
    for interest_id in preferences.interests:
        interest = INTERESTS_BY_ID.get(interest_id)
        if interest and (match := interest_matches(course.title, course.description, interest)):
            score += match
            reasons.append(f"Matches your interest: {interest.label}")
    if goal:
        goal_score = _weighted(course.title, course.description, goal.weights)
        if goal_score >= DIRECTION_THRESHOLD:
            score += 0.6 * goal_score
            reasons.append(f"Useful for your direction: {goal.label}")
    plan = PLANS_BY_ID.get(preferences.plans or "")
    if plan and plan.weights:
        plan_score = _weighted(course.title, course.description, plan.weights)
        if plan_score >= DIRECTION_THRESHOLD:
            score += 0.5 * plan_score
            reasons.append(plan.reason)
    return score, reasons


def _weighted(title: str, description: str, weights: dict[str, float]) -> float:
    return sum(
        weight * interest_matches(title, description, INTERESTS_BY_ID[topic])
        for topic, weight in weights.items()
    )


def suggest_for_group(
    group: Group,
    units_needed: float,
    catalog: Catalog,
    preferences: Preferences,
    context: EvalContext,
    exclude: set[str],
    limit: int = 5,
) -> GroupSuggestions:
    if group.is_open_pool:
        candidates = [code for code in catalog.courses if suggestible(code, catalog, exclude)]
    else:
        candidates = [code for code in group.courses if suggestible(code, catalog, exclude)]
    ranked = rank_courses(candidates, catalog, preferences, context, pool_for_unlocks=group.courses)
    if group.is_open_pool:
        ranked = [s for s in ranked if s.score > 0.5 or s.eligible_now][: limit * 4]
    return GroupSuggestions(group, units_needed, tuple(ranked[:limit]))


def suggestible(code: str, catalog: Catalog, exclude: set[str]) -> bool:
    """A real undergraduate course with units that the student has not ruled out or an admin hidden."""
    course = catalog.courses.get(code)
    if course is None or code in exclude or course.is_placeholder or course.hidden:
        return False
    return (course.level or 0) <= MAX_UNDERGRADUATE_LEVEL and (course.units or 0) > 0


def open_groups(program: Program, catalog: Catalog) -> list[Group]:
    """Groups where the student chooses courses (not "take every course on the list")."""
    return [group for group in program.leaf_groups() if not group_requires_all(group, catalog)]

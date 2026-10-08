"""Elective recommendations (F2.1, F2.2).

Ranking is deliberately simple and explainable: a course scores points for
matching the student's interests and career goal (by keywords in its title and
description), for being takeable next term and for opening other courses the
student would like. Every suggestion lists the reasons behind its score.
Review-based workload and difficulty (F2.3) will join the score once reviews exist.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.catalog import Catalog, Group, Program, group_requires_all
from app.domain.graph import prerequisite_graph
from app.domain.requisites import EvalContext, evaluate

MAX_UNDERGRADUATE_LEVEL = 400


@dataclass(frozen=True)
class Interest:
    id: str
    label: str
    keywords: tuple[str, ...]


INTERESTS: tuple[Interest, ...] = (
    Interest("ai", "AI and machine learning", ("artificial intelligence", "machine learning", "deep learning",
             "neural", "pattern recognition", "computational intelligence", "intelligent")),
    Interest("data", "Data science and databases", ("data", "database", "statistic", "probability",
             "mining", "analytics")),
    Interest("software", "Software development", ("software", "programming", "object-oriented", "c++",
             "python", "c#", ".net", "algorithm")),
    Interest("web_mobile", "Web and mobile apps", ("web", "mobile", "internet", "user interface")),
    Interest("security", "Security and networks", ("security", "cyber", "network", "cloud", "cryptograph")),
    Interest("systems", "Computer systems and hardware", ("operating system", "architecture", "parallel",
             "distributed", "digital logic", "hardware", "compiler", "embedded")),
    Interest("vision", "Images and computer vision", ("image", "vision", "graphics", "visual")),
    Interest("bio", "Bioinformatics and health", ("bioinformatics", "biolog", "health", "genom", "medic")),
    Interest("business", "Business and entrepreneurship", ("business", "management", "marketing", "finance",
             "accounting", "entrepreneur", "econom")),
    Interest("society", "Society, ethics and politics", ("ethic", "politic", "society", "sociolog", "global",
             "law", "public")),
    Interest("mind", "Psychology and education", ("psycholog", "learning", "education", "human development",
             "behavior")),
    Interest("culture", "History, culture and the arts", ("history", "civilization", "literature", "cinema",
             "theatre", "heritage", "archaeolog", "anthropolog", "philosoph", "humanities", "linguistic")),
    Interest("science", "Natural sciences", ("physics", "chemistry", "biology", "environment", "astronomy",
             "geograph", "climate")),
    Interest("communication", "Writing and communication", ("writing", "communication", "speaking", "media")),
)  # fmt: skip


@dataclass(frozen=True)
class Goal:
    id: str
    label: str
    weights: dict[str, float]


GOALS: tuple[Goal, ...] = (
    Goal("software_engineer", "Software engineer", {"software": 1.0, "web_mobile": 0.6, "systems": 0.4}),
    Goal("data_scientist", "Data scientist", {"data": 1.0, "ai": 0.8}),
    Goal("ai_engineer", "AI / machine learning engineer", {"ai": 1.0, "data": 0.6, "vision": 0.5}),
    Goal("security_engineer", "Cybersecurity or network engineer", {"security": 1.0, "systems": 0.6}),
    Goal("researcher", "Graduate school or research", {"ai": 0.5, "data": 0.5, "systems": 0.5}),
    Goal("entrepreneur", "Start a company", {"business": 1.0, "web_mobile": 0.6, "software": 0.4}),
    Goal("undecided", "Not sure yet", {}),
)


class Workload(StrEnum):
    LIGHT = "light"
    BALANCED = "balanced"
    CHALLENGING = "challenging"


@dataclass(frozen=True)
class Preferences:
    interests: tuple[str, ...] = ()
    goal: str | None = None
    workload: Workload = Workload.BALANCED


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


_INTERESTS_BY_ID = {interest.id: interest for interest in INTERESTS}
_GOALS_BY_ID = {goal.id: goal for goal in GOALS}


def interest_matches(text_title: str, text_description: str, interest: Interest) -> float:
    title, description = text_title.lower(), text_description.lower()
    if any(keyword in title for keyword in interest.keywords):
        return 1.0
    if any(keyword in description for keyword in interest.keywords):
        return 0.4
    return 0.0


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
    goal = _GOALS_BY_ID.get(preferences.goal or "")
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
        interest = _INTERESTS_BY_ID.get(interest_id)
        if interest and (match := interest_matches(course.title, course.description, interest)):
            score += match
            reasons.append(f"Matches your interest in {interest.label.lower()}")
    if goal:
        goal_score = sum(
            weight * interest_matches(course.title, course.description, _INTERESTS_BY_ID[interest_id])
            for interest_id, weight in goal.weights.items()
        )
        if goal_score > 0:
            score += 0.6 * goal_score
            reasons.append(f"Useful for your goal: {goal.label.lower()}")
    return score, reasons


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
    """A real undergraduate course with units that the student has not ruled out."""
    course = catalog.courses.get(code)
    if course is None or code in exclude or course.is_placeholder:
        return False
    return (course.level or 0) <= MAX_UNDERGRADUATE_LEVEL and (course.units or 0) > 0


def open_groups(program: Program, catalog: Catalog) -> list[Group]:
    """Groups where the student chooses courses (not "take every course on the list")."""
    return [group for group in program.leaf_groups() if not group_requires_all(group, catalog)]

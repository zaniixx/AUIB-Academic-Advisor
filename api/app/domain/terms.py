"""Academic terms.

SIS labels terms by academic year, e.g. ``2024/2025 Fall`` (Fall 2024) and
``2024/2025 Spring`` (Spring 2025). Internally a term is a calendar year plus a
season, ordered Spring < Summer < Fall within a year.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import IntEnum


class Season(IntEnum):
    SPRING = 1
    SUMMER = 2
    FALL = 3

    @property
    def label(self) -> str:
        return self.name.capitalize()


_ACADEMIC_YEAR_RE = re.compile(r"(\d{4})\s*[/-]\s*(\d{4})\s+(fall|spring|summer)\b", re.I)
_SEASON_YEAR_RE = re.compile(r"\b(fall|spring|summer)(?:\s+semester)?[\s,-]+(\d{4})\b", re.I)
_YEAR_SEASON_RE = re.compile(r"\b(\d{4})\s+(fall|spring|summer)\b", re.I)


@dataclass(frozen=True, order=True)
class Term:
    year: int
    season: Season

    @property
    def label(self) -> str:
        return f"{self.season.label} {self.year}"

    @property
    def academic_year(self) -> str:
        start = self.year if self.season is Season.FALL else self.year - 1
        return f"{start}/{start + 1}"

    @property
    def is_regular(self) -> bool:
        return self.season is not Season.SUMMER

    def __str__(self) -> str:
        return self.label

    def next(self, include_summer: bool = False) -> Term:
        if self.season is Season.FALL:
            return Term(self.year + 1, Season.SPRING)
        if self.season is Season.SPRING:
            return Term(self.year, Season.SUMMER) if include_summer else Term(self.year, Season.FALL)
        return Term(self.year, Season.FALL)

    def regular_terms_until(self, other: Term) -> int:
        """Number of Fall/Spring terms from this term up to and including ``other``."""
        count, term = 0, self
        while term <= other:
            if term.is_regular:
                count += 1
            term = term.next(include_summer=True)
        return count

    @classmethod
    def parse(cls, text: str) -> Term | None:
        """Parse ``2024/2025 Fall``, ``Fall 2024`` or ``2024 Fall``; None if unrecognised."""
        if match := _ACADEMIC_YEAR_RE.search(text):
            start, _end, season_name = match.groups()
            season = Season[season_name.upper()]
            year = int(start) if season is Season.FALL else int(start) + 1
            return cls(year, season)
        if match := _SEASON_YEAR_RE.search(text):
            season_name, year_text = match.groups()
            return cls(int(year_text), Season[season_name.upper()])
        if match := _YEAR_SEASON_RE.search(text):
            year_text, season_name = match.groups()
            return cls(int(year_text), Season[season_name.upper()])
        return None


def current_term(today: date) -> Term:
    """The term in session (or about to start) on ``today``."""
    if today.month <= 5:
        return Term(today.year, Season.SPRING)
    if today.month <= 7:
        return Term(today.year, Season.SUMMER)
    return Term(today.year, Season.FALL)


def first_planning_term(today: date, include_summer: bool) -> Term:
    """The first term a new plan schedules: the one after the term in session."""
    return current_term(today).next(include_summer)

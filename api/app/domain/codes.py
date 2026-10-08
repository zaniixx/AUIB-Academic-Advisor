"""Course codes as SIS writes them: subject, space, number (``CSC 231``, ``BIO 101L``).

Placeholder codes such as ``ATH 3XX`` or ``HUM XXX`` stand for transfer credit
at a level rather than a real course; they can appear in a student's history
but are never recommended or scheduled.
"""

from __future__ import annotations

import re

_CODE_RE = re.compile(r"^\s*([A-Za-z]{2,4})\s*-?\s*(\d{3}[A-Za-z]?|\d[Xx]{2}|[Xx]{3})\s*$")


def normalize_code(raw: str) -> str | None:
    """Return the canonical ``SUBJ 123`` form, or None if ``raw`` is not a course code."""
    match = _CODE_RE.match(raw)
    if not match:
        return None
    subject, number = match.groups()
    return f"{subject.upper()} {number.upper()}"


def subject_of(code: str) -> str:
    return code.split(" ", 1)[0]


def number_of(code: str) -> str:
    return code.split(" ", 1)[1] if " " in code else ""


def is_placeholder(code: str) -> bool:
    return "X" in number_of(code)


def level_of(code: str) -> int | None:
    """Course level in hundreds (``CSC 343`` -> 300); None for ``XXX`` placeholders."""
    number = number_of(code)
    if not number or not number[0].isdigit():
        return None
    return int(number[0]) * 100

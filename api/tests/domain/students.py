"""Fictional student records used across the planner tests."""

from app.domain.record import Attempt, AttemptStatus, StudentRecord, build_record
from app.domain.terms import Season, Term

FALL_2025 = Term(2025, Season.FALL)
SPRING_2026 = Term(2026, Season.SPRING)
FALL_2026 = Term(2026, Season.FALL)
FALL_2023 = Term(2023, Season.FALL)


def _done(term: Term, *codes: str, grade: str = "B") -> list[Attempt]:
    return [Attempt(code, AttemptStatus.COMPLETED, term, grade) for code in codes]


def _current(*codes: str) -> list[Attempt]:
    return [Attempt(code, AttemptStatus.IN_PROGRESS, FALL_2026) for code in codes]


def new_student() -> StudentRecord:
    return build_record([])


def second_year() -> StudentRecord:
    """Entered Fall 2025; three CS courses and a lab science in progress."""
    return build_record(
        _done(FALL_2025, "CSC 101", "MAT 111", "ENL 101", "UNI 101", "HIS 101")
        + _done(SPRING_2026, "CSC 140", "MAT 112", "ENL 201", "PSY 101", "BIO 101")
        + _current("CSC 230", "CSC 132", "MAT 202", "ENL 210", "CHE 100")
    )


def with_a_failure() -> StudentRecord:
    """Failed MAT 112 once and passed it on the retake; withdrew from a humanities course."""
    attempts = (
        *second_year().attempts,
        Attempt("MAT 112", AttemptStatus.FAILED, FALL_2025, "F"),
        Attempt("LIT 101", AttemptStatus.WITHDRAWN, SPRING_2026, "W"),
    )
    return build_record(attempts)


def nearly_done() -> StudentRecord:
    """Entered Fall 2023 with almost everything finished."""
    core = [
        "CSC 132", "CSC 140", "CSC 230", "CSC 231", "CSC 313", "CSC 337", "CSC 343", "CSC 345",
        "CSC 364", "CSC 390", "CSC 391", "CSC 422", "CSC 445", "MAT 112", "MAT 130", "MAT 202", "STA 210",
    ]  # fmt: skip
    cla = ["UNI 101", "ENL 101", "ENL 201", "ENL 210", "CSC 101", "MAT 111", "HIS 101", "PHI 101", "LIT 101",
           "HUM 101", "PSY 101", "SOC 101", "BIO 101", "ENV 201"]  # fmt: skip
    electives = ["CSC 233", "CSC 311", "CSC 421", "MGT 201", "MKT 201"]
    return build_record(_done(FALL_2023, *core, *cla, *electives) + _current("CSC 448", "CSC 450", "CSC 232"))

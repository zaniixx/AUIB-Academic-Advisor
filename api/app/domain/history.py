"""Read a pasted SIS Course History page (requirement F11.3).

Students open SIS -> Academic Record -> Course History, press Ctrl+A, Ctrl+C and
paste. The paste holds the whole page: menus, headers, then one row per attempt
with the columns Course, Description, Term, Grade, Units and Status. Browsers
copy table cells either tab-separated on one line or one per line, and SIS
renders some status text twice, so this parser works on a flat stream of cells
and recognises each column by its shape rather than its position.

Nothing is dropped silently (F11.4): rows that need a decision carry an issue,
and lines that mention a course code but could not be read are reported.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from app.domain.codes import normalize_code
from app.domain.record import ALL_GRADES, AttemptStatus, status_from_grade
from app.domain.terms import Term

MAX_PASTE_CHARACTERS = 300_000

_CODE_ONLY_RE = re.compile(r"^[A-Za-z]{2,4}\s?-?(?:\d{3}[A-Za-z]?|\d[Xx]{2}|[Xx]{3})$")
_CODE_AND_TITLE_RE = re.compile(r"^([A-Za-z]{2,4}\s?-?(?:\d{3}[A-Za-z]?|\d[Xx]{2}|[Xx]{3}))\s*[-:]\s+(.+)$")
_CODE_ANYWHERE_RE = re.compile(r"\b[A-Z]{2,4}\s?\d{3}[A-Z]?\b")
_UNITS_RE = re.compile(r"^\d{1,2}(?:\.\d{1,2})?$")
_SINGLE_LINE_ROW_RE = re.compile(
    r"^(?P<code>[A-Za-z]{2,4}\s?-?(?:\d{3}[A-Za-z]?|\d[Xx]{2}|[Xx]{3}))\s+(?P<title>.+?)\s+"
    r"(?P<term>(?:\d{4}\s*/\s*\d{4}\s+)?(?:Fall|Spring|Summer)(?:\s+\d{4})?)"
    r"(?:\s+(?P<grade>[A-Z][+-]?|IP|NP|CR|WF|WP|AU|TR))?"
    r"(?:\s+(?P<units>\d{1,2}(?:\.\d{1,2})?))?"
    r"(?:\s+(?P<status>Taken|In Progress|Enrolled|Registered|Transferred|Transfer|Withdrawn|Dropped"
    r"|Repeated|Completed))?"
    r"\s*$",
    re.I,
)
_TERM_CELL_RE = re.compile(
    r"^(?:\d{4}\s*[/-]\s*\d{4}\s+)?(?:fall|spring|summer)(?:\s+semester)?(?:\s+\d{4})?$", re.I
)
_HEADER_CELLS = {"course", "description", "term", "grade", "units", "status", "repeat"}

_STATUS_WORDS: dict[str, str] = {
    "taken": "taken",
    "completed": "taken",
    "in progress": "in_progress",
    "enrolled": "in_progress",
    "registered": "in_progress",
    "transferred": "transfer",
    "transfer": "transfer",
    "transfer credit": "transfer",
    "withdrawn": "withdrawn",
    "dropped": "withdrawn",
    "repeated": "repeated",
    "not taken": "not_taken",
}


@dataclass
class HistoryRow:
    code: str
    line: int
    title: str | None = None
    term: Term | None = None
    term_text: str | None = None
    grade: str | None = None
    units: float | None = None
    sis_status: str | None = None
    status: AttemptStatus | None = None
    issues: list[str] = field(default_factory=list)


@dataclass
class UnreadLine:
    line: int
    text: str
    reason: str


@dataclass
class HistoryParseResult:
    rows: list[HistoryRow]
    unread: list[UnreadLine]  # lines mentioning a course code that could not be read
    ignored_line_count: int  # menu and header lines with no course code
    duplicates_removed: int


@dataclass
class _Cell:
    text: str
    line: int


def parse_course_history(text: str, catalog_titles: Mapping[str, str] | None = None) -> HistoryParseResult:
    """Parse a Course History paste into one row per attempt."""
    catalog_titles = catalog_titles or {}
    cells = _cells(text[:MAX_PASTE_CHARACTERS])
    rows: list[HistoryRow] = []
    consumed_lines: set[int] = set()
    current: HistoryRow | None = None

    for cell in cells:
        start = _row_start(cell.text)
        if start is not None:
            code, title = start
            current = HistoryRow(code=code, line=cell.line, title=title)
            rows.append(current)
            consumed_lines.add(cell.line)
            continue
        if (whole_row := _single_line_row(cell)) is not None:
            rows.append(whole_row)
            consumed_lines.add(cell.line)
            current = whole_row  # a duplicated status cell may follow
            continue
        if current is None:
            continue
        if _absorb(current, cell.text):
            consumed_lines.add(cell.line)
            continue
        current = None  # anything else ends the row (page footer, next section)

    rows = [row for row in rows if row.sis_status != "not_taken"]
    for row in rows:
        _finish(row, catalog_titles)
    unique, duplicates = _deduplicate(rows)

    lines = text[:MAX_PASTE_CHARACTERS].splitlines()
    unread: list[UnreadLine] = []
    ignored = 0
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or number in consumed_lines:
            continue
        if _CODE_ANYWHERE_RE.search(stripped):
            unread.append(
                UnreadLine(number, stripped[:200], "Mentions a course code but is not a Course History row")
            )
        else:
            ignored += 1
    return HistoryParseResult(unique, unread, ignored, duplicates)


def _cells(text: str) -> list[_Cell]:
    cells = []
    for number, line in enumerate(text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), start=1):
        for part in line.replace(" ", " ").split("\t"):
            part = re.sub(r"\s+", " ", part).strip()
            if part:
                cells.append(_Cell(part, number))
    return cells


def _row_start(cell: str) -> tuple[str, str | None] | None:
    if _CODE_ONLY_RE.match(cell):
        code = normalize_code(cell)
        return (code, None) if code else None
    if match := _CODE_AND_TITLE_RE.match(cell):
        code = normalize_code(match.group(1))
        return (code, match.group(2).strip()) if code else None
    return None


def _single_line_row(cell: _Cell) -> HistoryRow | None:
    """A whole row copied as one line separated by spaces."""
    match = _SINGLE_LINE_ROW_RE.match(cell.text)
    if not match or (code := normalize_code(match.group("code"))) is None:
        return None
    term = Term.parse(match.group("term"))
    status = match.group("status")
    return HistoryRow(
        code=code,
        line=cell.line,
        title=match.group("title").strip(),
        term=term,
        term_text=match.group("term") if term else None,
        grade=match.group("grade").upper() if match.group("grade") else None,
        units=float(match.group("units")) if match.group("units") else None,
        sis_status=_STATUS_WORDS.get(status.lower()) if status else None,
    )


def _absorb(row: HistoryRow, cell: str) -> bool:
    """Put ``cell`` into the right column of ``row``; False if it belongs to no column."""
    lower = cell.lower()
    if lower in _HEADER_CELLS:
        return True
    if lower in _STATUS_WORDS:
        status = _STATUS_WORDS[lower]
        if row.sis_status is None:
            row.sis_status = status
        return True  # a second copy of the status is SIS rendering it twice
    if row.term is None and _TERM_CELL_RE.match(cell) and (term := Term.parse(cell)):
        row.term, row.term_text = term, cell
        return True
    if row.grade is None and cell.upper() in ALL_GRADES and (row.term is not None or row.title is not None):
        row.grade = cell.upper()
        return True
    if row.units is None and _UNITS_RE.match(cell) and (row.term is not None or row.title is not None):
        row.units = float(cell)
        return True
    if row.title is None and row.term is None and not _row_start(cell):
        row.title = cell
        return True
    return False


def _finish(row: HistoryRow, catalog_titles: Mapping[str, str]) -> None:
    from_grade = status_from_grade(row.grade)
    match row.sis_status:
        case "in_progress":
            row.status = AttemptStatus.IN_PROGRESS
        case "transfer":
            row.status = AttemptStatus.COMPLETED
        case "withdrawn":
            row.status = AttemptStatus.WITHDRAWN
        case "repeated":
            row.status = AttemptStatus.NOT_COUNTED
            row.issues.append("SIS marks this attempt as repeated, so a later attempt counts instead")
        case "taken":
            row.status = from_grade or AttemptStatus.COMPLETED
            if from_grade is None:
                row.issues.append("No grade shown; counted as completed")
        case _:
            row.status = from_grade
            if row.status is None:
                row.issues.append("Status not shown; choose completed or in progress")
    if row.code not in catalog_titles:
        row.issues.append("Not in the catalog loaded for this app (transfer credit or another program?)")
    elif not row.title:
        row.title = catalog_titles[row.code]
    if row.term is None:
        row.issues.append("Term not recognised")


def _deduplicate(rows: list[HistoryRow]) -> tuple[list[HistoryRow], int]:
    seen: set[tuple[object, ...]] = set()
    unique = []
    for row in rows:
        key = (row.code, row.term, row.grade, row.status)
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique, len(rows) - len(unique)

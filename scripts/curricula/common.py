"""Shared pieces for writing program packages from AUIB's released curriculum documents."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from extract import REPO, WORK

CATALOG_FILE = REPO / "data" / "catalog" / "courses.json"
PROGRAMS_DIR = REPO / "data" / "programs"

ADDED_NOTICE = "This course is not in the SIS course catalog yet"
# The SIS courses only: courses an earlier run added carry ADDED_NOTICE and are added again.
CATALOG: dict[str, dict] = {
    code: course
    for code, course in json.loads(CATALOG_FILE.read_text(encoding="utf-8")).items()
    if not any(ADDED_NOTICE in notice for notice in course.get("notices") or ())
}
SIS_CODES = frozenset(CATALOG)
DESCRIPTIONS: dict[str, dict[str, dict]] = {}  # filled by load_descriptions()
ADDED: dict[str, dict] = {}  # courses this run adds to the catalog
SUMMER_ONLY: set[str] = set()

# The core liberal arts lists in SIS (the Computer Science program's CLA, scraped 2026-10-08), widened
# with the courses the CIS and College of Healthcare Technology documents list for every program.
CLA_HUMANITIES = [
    "ARC 101", "CIN 101", "ENL 212", "HIS 101", "HIS 102", "HIS 105", "HUM 101", "LIT 101", "PHA 210",
    "PHI 101", "POL 125", "THE 101", "TLD 100", "TLD 101", "TLD 102", "TLD 103",
    "HIS 201", "HIS 341", "HIS 350",
]
CLA_SOCIAL = [
    "ARC 100", "ARC 102", "COM 101", "ECO 101", "FIN 101", "HCT 108", "MIS 101", "POL 101", "POL 112",
    "POL 191", "PSY 101", "PSY 334", "SOC 101", "TLD 203", "TLD 208",
    "HUM 210",
]
CLA_NATURAL = ["BIO 101", "CHE 100", "CHE 105", "CSC 100", "ENV 201", "GEO 101", "PHY 100", "PHY 105"]
CLA_MATH = ["MAT 101", "MAT 101A", "MAT 102", "MAT 111"]
CLA_HISTORY = ["HIS 101", "HIS 102", "HIS 105", "HIS 201", "HIS 341", "HIS 350"]


def load_descriptions() -> None:
    DESCRIPTIONS.update(json.loads((WORK / "descriptions.json").read_text(encoding="utf-8")))


def units_of(code: str) -> float:
    raw = ADDED.get(code) or CATALOG.get(code)
    if raw is None:
        raise KeyError(f"{code} is in neither the catalog nor this run's additions")
    return float(raw["units"] or 0)


def known(code: str) -> bool:
    return code in CATALOG or code in ADDED


def clean(text: str) -> str:
    text = text.replace("\ufffd", "'").replace("\u2019", "'").replace("\u2013", "-")
    return re.sub(r"\s+", " ", text).strip()


# A course heading inside a description means the next course's text ran on (its heading had no credits).
_HEADING = re.compile(r"\s(?P<code>[A-Z]{3} \d{3}L?) ?[-'] ?[A-Z][a-z]")
_TRAILER = re.compile(r"\s(?:(?:Spring|Fall|Summer) Semester\b|Technical Electives\b|HCT 4[8X][Xx0-9]? ).*$")


def trim_description(code: str, text: str) -> str:
    """Drop what follows the course's own description: a semester heading, or another course's text."""
    text = _TRAILER.sub("", clean(text))
    for match in _HEADING.finditer(text):
        before = text[max(0, match.start() - 14) : match.start()].lower()
        if match.group("code") != code and "requisite" not in before:
            return text[: match.start()].strip()
    return text


def add_course(
    code: str,
    title: str,
    units: float,
    description: str,
    source: str,
    component: str | None = None,
) -> None:
    """Add a course the documents require that the SIS catalog does not have."""
    if code in CATALOG:
        raise ValueError(f"{code} is already in the SIS catalog")
    if component is None:
        component = "Laboratory" if code.endswith("L") else "Clinical" if code.endswith("C") else "Lecture"
    ADDED[code] = {
        "code": code,
        "title": clean(title),
        "units": f"{units:.2f}",
        "career": None,
        "grading": None,
        "component": component,
        "campus": None,
        "academic_group": None,
        "academic_org": None,
        "course_attribute": None,
        "enrollment_requirement": None,
        "other_fields": {},
        "notices": [
            f"Taken from {source}. This course is not in the SIS course catalog yet, so confirm it with the college."
        ],
        "description": trim_description(code, description),
        "prerequisites": [],
        "corequisites": [],
    }


def from_document(
    source_key: str,
    code: str,
    source: str,
    title: str | None = None,
    units: float | None = None,
    description: str | None = None,
    found_as: str | None = None,
) -> None:
    """Add ``code`` from a parsed course description (``found_as`` when the document misprints its code)."""
    entry = DESCRIPTIONS[source_key].get(found_as or code)
    if entry is None and description is None:
        raise KeyError(f"No description of {found_as or code} in {source_key}")
    add_course(
        code,
        title or entry["title"],
        units if units is not None else entry["credits"],
        description if description is not None else entry["text"],
        source,
    )


# --- requirement trees ----------------------------------------------------------------------


@dataclass
class G:
    """A requirement group: a leaf lists courses, a branch holds sub-groups."""

    title: str
    label: str
    units: float
    courses: list[str] = field(default_factory=list)
    children: list[G] = field(default_factory=list)
    role: str | None = None


def leaf(title: str, label: str, courses: list[str], units: float | None = None, role: str | None = None) -> G:
    """A group; without ``units`` every listed course is required."""
    total = sum(units_of(code) for code in courses) if units is None else units
    if role is None and units is None:
        role = "core"
    return G(title, label, total, courses=list(dict.fromkeys(courses)), role=role)


def branch(title: str, label: str, children: list[G]) -> G:
    return G(title, label, sum(child.units for child in children), children=children)


def pick(pool: list[str], count: int, title: str, label: str, exclude: set[str] = frozenset(), role="general_education") -> G:
    courses = [code for code in dict.fromkeys(pool) if code not in exclude and known(code)]
    return G(title, label, 3.0 * count, courses=courses, role=role)


def cla(
    prefix: str,
    *,
    math: list[str] | None = None,
    humanities_required: list[str] = (),
    humanities_history: int = 0,
    social_required: list[str] = (),
    social_choice: list[str] | None = None,
    natural_required: list[str] = (),
    exclude: set[str] = frozenset(),
) -> G:
    """The university's core liberal arts (42 credits): first-year experience, communication skills
    (ENL 101, 201, 210), quantitative reasoning (CSC 101 and one mathematics course), four humanities,
    two social sciences and two natural sciences, with the courses a program fixes in each category."""
    taken = set(exclude) | set(humanities_required) | set(social_required) | set(natural_required)
    children = [
        leaf(f"{prefix} CLA - First-year experience", "First-year experience", ["UNI 101"]),
        leaf(f"{prefix} CLA - Communication skills", "Communication skills", ["ENL 101", "ENL 201", "ENL 210"]),
        leaf(f"{prefix} CLA - Computer science", "Quantitative reasoning: computing", ["CSC 101"]),
    ]
    maths = math or CLA_MATH
    if len(maths) == 1:
        children.append(leaf(f"{prefix} CLA - Mathematics", "Quantitative reasoning: mathematics", maths))
    else:
        children.append(
            pick(maths, 1, f"{prefix} CLA - Mathematics", "Quantitative reasoning: mathematics", exclude, "general_education")
        )
    # Humanities: four courses.
    left = 4 - len(humanities_required) - humanities_history
    if humanities_required:
        children.append(leaf(f"{prefix} CLA - Humanities (required)", "Humanities: required", list(humanities_required)))
    if humanities_history:
        children.append(
            pick(CLA_HISTORY, humanities_history, f"{prefix} CLA - History", f"Humanities: {humanities_history} history courses", taken)
        )
    if left:
        children.append(pick(CLA_HUMANITIES, left, f"{prefix} CLA - Humanities electives", "Humanities electives", taken))
    # Social sciences: two courses.
    left = 2 - len(social_required) - (1 if social_choice else 0)
    if social_required:
        children.append(leaf(f"{prefix} CLA - Social sciences (required)", "Social sciences: required", list(social_required)))
    if social_choice:
        children.append(
            pick(social_choice, 1, f"{prefix} CLA - Social sciences (choice)", "Social sciences: " + " or ".join(social_choice), taken)
        )
    if left:
        children.append(pick(CLA_SOCIAL, left, f"{prefix} CLA - Social science electives", "Social science electives", taken))
    # Natural sciences: two courses.
    left = 2 - len(natural_required)
    if natural_required:
        children.append(leaf(f"{prefix} CLA - Natural sciences (required)", "Natural sciences: required", list(natural_required)))
    if left:
        children.append(pick(CLA_NATURAL, left, f"{prefix} CLA - Natural sciences", "Natural sciences", taken))
    group = branch(f"{prefix} CLA - Core Liberal Arts", "Core liberal arts (CLA)", children)
    assert group.units == 42, (prefix, group.units)
    return group


def cla_pool(exclude: set[str]) -> list[str]:
    """Any course of the core liberal arts lists, for documents that leave "CLA" slots open."""
    return [code for code in dict.fromkeys(CLA_HUMANITIES + CLA_SOCIAL + CLA_NATURAL) if code not in exclude]


def free_pool(min_level: int = 100) -> list[str]:
    """Free electives: any undergraduate course in the SIS catalog (no placeholders such as "HIS 3XX")."""
    codes = []
    for code in CATALOG:
        subject, number = code.split(" ", 1)
        digits = re.match(r"\d{3}", number)
        if not digits or "X" in number or subject == "YYY":
            continue
        if min_level <= int(digits.group()) < 500:
            codes.append(code)
    return codes


# --- writing packages -----------------------------------------------------------------------


@dataclass
class Program:
    id: str
    name: str
    total: float
    source: str
    source_date: str | None
    published: bool
    root: G
    standard_terms: int = 8
    notes: list[str] = field(default_factory=list)


def flatten(root: G) -> list[dict]:
    entries: list[dict] = []

    def walk(group: G, level: int, parent: str | None) -> None:
        entries.append(
            {
                "index": len(entries),
                "title": group.title,
                "level": level,
                "parent": parent,
                "units_required": float(group.units),
                "courses": [] if group.children else group.courses,
            }
        )
        for child in group.children:
            walk(child, level + 1, group.title)

    walk(root, 0, None)
    return entries


def group_settings(root: G) -> dict[str, dict]:
    settings: dict[str, dict] = {}

    def walk(group: G) -> None:
        entry = {"label": group.label}
        if group.role and not group.children:
            entry["role"] = group.role
        settings[group.title] = entry
        for child in group.children:
            walk(child)

    walk(root)
    return settings


def dump(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def write_program(program: Program) -> None:
    assert abs(program.root.units - program.total) < 1e-6, (program.id, program.root.units, program.total)
    folder = PROGRAMS_DIR / program.id
    folder.mkdir(parents=True, exist_ok=True)
    meta = {
        "id": program.id,
        "name": program.name,
        "kind": "major",
        "sis_title": None,
        "catalog_year": None,
        "total_units": float(program.total),
        "standard_terms": program.standard_terms,
        "source": program.source,
        "source_date": program.source_date,
        "published": program.published,
        "groups": group_settings(program.root),
    }
    (folder / "program.json").write_bytes(dump(meta).encode("utf-8"))
    (folder / "requirements.json").write_bytes(dump(flatten(program.root)).encode("utf-8"))


def write_catalog() -> None:
    merged = dict(CATALOG)
    merged.update(ADDED)
    for code in SUMMER_ONLY:
        merged[code] = {**merged[code], "offered_terms": ["summer"]}
    ordered = {code: merged[code] for code in sorted(merged)}
    CATALOG_FILE.write_bytes(dump(ordered).encode("utf-8"))


def check(program: Program) -> list[str]:
    """Problems that would stop validation, found before writing."""
    problems = []

    def walk(group: G) -> None:
        if group.children:
            total = sum(child.units for child in group.children)
            if abs(total - group.units) > 1e-6:
                problems.append(f"{group.title}: children add up to {total:g}, not {group.units:g}")
            for child in group.children:
                walk(child)
            return
        missing = [code for code in group.courses if not known(code)]
        if missing:
            problems.append(f"{group.title}: missing {missing}")
        if group.role != "free_elective":
            pool = sum(units_of(code) for code in group.courses if known(code))
            if pool + 1e-6 < group.units:
                problems.append(f"{group.title}: courses add up to {pool:g} < {group.units:g}")

    walk(program.root)
    return problems

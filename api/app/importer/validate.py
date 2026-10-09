"""Checks the course catalog and each program package must pass before import (F0.7).

Errors block the import. Warnings are listed in the import report and, for a program,
block publishing unless the admin running the import accepts them. Every finding
names the file and entry it is about, so a data maintainer can fix the source and
re-import.

The course catalog is checked on its own (codes, offering seasons, requisite rules);
a program is checked against the catalog it will be planned with: every course its
requirements list must be in the catalog, and problems with those courses' rules are
raised as warnings for that program.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.catalog import OFFERED_TERM_NAMES, Catalog, Course, Group, Program
from app.domain.codes import normalize_code
from app.domain.graph import find_cycles
from app.domain.requisites import ParseStatus, course_codes
from app.importer.package import (
    CourseList,
    PackageError,
    ProgramPackage,
    build_courses,
    build_program,
    link_tree,
    parse_rules,
)

CATALOG_ID = "course-catalog"
CATALOG_FILE = "courses.json"


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class Finding:
    severity: Severity
    where: str
    message: str


@dataclass
class ValidationReport:
    program_id: str
    findings: list[Finding] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.WARNING]

    @property
    def ok(self) -> bool:
        return not self.errors

    def add(self, severity: Severity, where: str, message: str) -> None:
        self.findings.append(Finding(severity, where, message))


def validate_courses(course_list: CourseList) -> ValidationReport:
    """Check the shared course catalog: codes, offering seasons and requisite rules."""
    report = ValidationReport(CATALOG_ID)
    for raw_code, raw in course_list.raw_courses.items():
        if normalize_code(raw_code) is None:
            report.add(Severity.ERROR, f"{CATALOG_FILE}: {raw_code!r}", "Not a valid course code")
        offered = raw.get("offered_terms")
        if offered is not None and (
            not isinstance(offered, list) or any(str(v).lower() not in OFFERED_TERM_NAMES for v in offered)
        ):
            report.add(
                Severity.ERROR,
                f"{CATALOG_FILE}: {raw_code}",
                "offered_terms must be a list of fall, spring and summer",
            )

    courses = build_courses(course_list)
    available = frozenset(courses)
    for code, course in courses.items():
        if course.units is None:
            report.add(Severity.INFO, f"{CATALOG_FILE}: {code}", "No credits given; planning assumes 3")

    rules = parse_rules(courses)
    statuses = Counter(rule.status for found in rules.values() for rule in found)
    for code, found in sorted(rules.items()):
        for rule in found:
            if rule.status in (ParseStatus.PARTIAL, ParseStatus.UNPARSED):
                report.add(
                    Severity.INFO,
                    f"{CATALOG_FILE}: {code}",
                    f"{rule.kind.value} rule only partly understood: {rule.source_text!r}",
                )
            for needed in sorted(course_codes(rule.expr) - available):
                report.add(
                    Severity.INFO,
                    f"{CATALOG_FILE}: {code}",
                    f"Requisite {needed} is not in the catalog, so it cannot be planned",
                )
        scraped = {
            normalize_code(c) or c
            for part in ("prerequisites", "corequisites")
            for item in course_list.raw_courses.get(code, {}).get(part) or []
            for c in item.get("codes") or []
        }
        parsed = set().union(*(course_codes(rule.expr) for rule in found)) if found else set()
        if scraped and scraped != parsed:
            report.add(
                Severity.INFO,
                f"{CATALOG_FILE}: {code}",
                f"Parser found {sorted(parsed) or 'no codes'}; scraper found {sorted(scraped)}. "
                "Check on review.",
            )
    for cycle in find_cycles(Catalog(courses, {c: {r.kind: r for r in f} for c, f in rules.items()})):
        report.add(Severity.WARNING, CATALOG_FILE, f"Prerequisites form a loop: {' -> '.join(cycle)}")

    report.stats = {
        "courses": len(courses),
        "rules": sum(statuses.values()),
        **{f"rules_{status.value}": count for status, count in statuses.items()},
    }
    return report


def validate_package(package: ProgramPackage, catalog: Catalog) -> ValidationReport:
    """Validate ``package`` against ``catalog``, the courses and rules it will be planned with."""
    report = ValidationReport(package.meta.id)
    meta = package.meta

    roots = link_tree(package.entries)
    if len(roots) != 1:
        titles = ", ".join(root.title for root in roots) or "none"
        report.add(Severity.ERROR, "requirements.json", f"Needs exactly one top-level group; found: {titles}")
        return report
    try:
        program = build_program(package)
    except PackageError as error:
        report.add(Severity.ERROR, "requirements.json", str(error))
        return report

    for title in meta.groups:
        if not any(entry.title == title for entry in package.entries):
            report.add(Severity.WARNING, "program.json: groups", f"No requirement group is titled {title!r}")
    validate_program(program, catalog, report)
    return report


@dataclass(frozen=True)
class Places:
    """Where findings point: the package files, or the admin page's form."""

    meta: str = "program.json"
    groups: str = "requirements.json"


PACKAGE_FILES = Places()
ADMIN_FORM = Places(meta="Program", groups="Requirement")


def validate_program(
    program: Program, catalog: Catalog, report: ValidationReport, places: Places = PACKAGE_FILES
) -> None:
    """Check a program's requirement tree against ``catalog`` (shared by imports and the admin page)."""
    if program.catalog_year is None:
        report.add(
            Severity.WARNING,
            f"{places.meta}: catalog_year",
            "Catalog year not set; confirm with the registrar",
        )
    if abs(program.root.units_required - program.total_units) > 1e-6:
        report.add(
            Severity.WARNING,
            f"{places.meta}: total_units",
            f"total_units is {program.total_units:g} but the top requirement group needs "
            f"{program.root.units_required:g}",
        )
    _check_version(program, catalog, report, places)
    available = frozenset(catalog.courses)
    for group in program.groups():
        _check_group(group, available, catalog.courses, report, places)

    # Courses this program names directly (not only through the open free-elective pool)
    # are the ones whose problems can affect its plans, so those are warnings here.
    named = sorted(
        {code for group in program.leaf_groups() if not group.is_open_pool for code in group.courses}
        & available
    )
    for code in named:
        if catalog.courses[code].hidden:
            report.add(
                Severity.WARNING,
                f"{CATALOG_FILE}: {code}",
                "Hidden in the admin page, so it is never planned",
            )
        if catalog.courses[code].units is None:
            report.add(Severity.WARNING, f"{CATALOG_FILE}: {code}", "No credits given; planning assumes 3")
        for rule in catalog.rules.get(code, {}).values():
            if rule.overridden or rule.reviewed:
                continue  # an admin has checked or corrected it
            if rule.status in (ParseStatus.PARTIAL, ParseStatus.UNPARSED):
                report.add(
                    Severity.WARNING,
                    f"{CATALOG_FILE}: {code}",
                    f"{rule.kind.value} rule only partly understood: {rule.source_text!r}",
                )
            for needed in sorted(course_codes(rule.expr) - available):
                report.add(
                    Severity.WARNING,
                    f"{CATALOG_FILE}: {code}",
                    f"Requisite {needed} is not in the catalog, so it cannot be planned",
                )

    report.stats = {"groups": len(program.groups()), "courses_named": len(named)}


def _check_version(program: Program, catalog: Catalog, report: ValidationReport, places: Places) -> None:
    """A version must join an existing program of the same kind, and start in a term of its own (F0.4)."""
    others = [p for p in catalog.programs.values() if p.family_id == program.family_id and p.id != program.id]
    if program.family and program.family != program.id and not others:
        report.add(
            Severity.ERROR,
            f"{places.meta}: family",
            f"There is no program {program.family!r} for this to be a version of",
        )
    for other in others:
        if other.kind != program.kind:
            report.add(
                Severity.ERROR,
                f"{places.meta}: family",
                f"{other.name} is a {other.kind}, so a {program.kind} cannot be a version of it",
            )
        if other.valid_from == program.valid_from:
            start = f"from {program.valid_from}" if program.valid_from else "from the start"
            report.add(
                Severity.ERROR,
                f"{places.meta}: valid_from",
                f"Another version ({other.id}) already applies {start}; give this version its own first term",
            )


def _check_group(
    group: Group,
    available: frozenset[str],
    courses: Mapping[str, Course],
    report: ValidationReport,
    places: Places,
) -> None:
    where = f"{places.groups}: {group.title}"
    if group.units_required <= 0:
        report.add(Severity.ERROR, where, "units_required is missing or zero")
    if group.children:
        total = sum(child.units_required for child in group.children)
        if abs(total - group.units_required) > 1e-6:
            report.add(
                Severity.WARNING,
                where,
                f"Sub-groups add up to {total:g} credits but the group requires {group.units_required:g}",
            )
        return
    if not group.courses:
        report.add(Severity.ERROR, where, "Group has no courses and no sub-groups")
        return
    missing = sorted(code for code in group.courses if code not in available)
    if missing:
        listed = ", ".join(missing[:10]) + (" and more" if len(missing) > 10 else "")
        report.add(Severity.ERROR, where, f"Lists courses missing from the course catalog: {listed}")
    if not group.is_open_pool:
        pool = sum(courses[code].credit_units if code in courses else 3.0 for code in group.courses)
        if pool + 1e-6 < group.units_required:
            report.add(
                Severity.ERROR,
                where,
                f"Listed courses add up to {pool:g} credits, less than the {group.units_required:g} required",
            )

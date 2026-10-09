"""Read the course catalog and program packages from disk into catalog objects."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.domain.catalog import (
    Catalog,
    Course,
    Group,
    GroupRole,
    Program,
    Rule,
    parse_offered_terms,
    readable_group_label,
)
from app.domain.codes import normalize_code
from app.domain.requisites import parse_description
from app.domain.terms import Term

MAX_PACKAGE_FILE_BYTES = 20 * 1024 * 1024


class PackageError(ValueError):
    """A package or the course list cannot be read at all (missing file, invalid JSON, broken metadata)."""


class GroupSetting(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str | None = None
    role: GroupRole | None = None


class ProgramMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["major", "minor"]
    sis_title: str | None = None
    catalog_year: str | None = None
    total_units: float = Field(gt=0, le=400)
    # Regular semesters of the standard degree (eight for a four-year major).
    standard_terms: int = Field(default=8, ge=2, le=14)
    source: str | None = None
    source_date: date | None = None
    published: bool = False
    # F0.4: another version of the program ``family`` (a program id), applying to students who
    # joined from ``valid_from`` (a term such as "Fall 2027"); leave both out for a first version.
    family: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    valid_from: str | None = None
    groups: dict[str, GroupSetting] = Field(default_factory=dict)

    @field_validator("valid_from")
    @classmethod
    def _term(cls, value: str | None) -> str | None:
        if value is None:
            return None
        term = Term.parse(value)
        if term is None:
            raise ValueError("valid_from must be a term like 'Fall 2027'")
        return term.label


@dataclass
class GroupEntry:
    """One requirement group as the scraper lists it, after merging duplicates."""

    title: str
    level: int
    parent: str | None
    units_required: float | None
    courses: list[str]
    position: int
    children: list[GroupEntry] = field(default_factory=list)


@dataclass
class ProgramPackage:
    path: Path
    meta: ProgramMeta
    entries: list[GroupEntry]


@dataclass
class CourseList:
    """Every AUIB course, shared by all programs: ``data/catalog/courses.json`` in the scraper's format."""

    path: Path
    raw_courses: dict[str, dict[str, Any]]


def load_package(path: Path) -> ProgramPackage:
    meta_raw = _read_json(path / "program.json")
    try:
        meta = ProgramMeta.model_validate(meta_raw)
    except ValidationError as error:
        raise PackageError(f"program.json is invalid: {error}") from error
    requirements = _read_json(path / "requirements.json")
    if not isinstance(requirements, list):
        raise PackageError("requirements.json must be a list of requirement groups")
    return ProgramPackage(path, meta, _merge_entries(requirements))


def load_courses(path: Path) -> CourseList:
    courses = _read_json(path)
    if not isinstance(courses, dict):
        raise PackageError(f"{path.name} must map course codes to course details")
    return CourseList(path, courses)


def _read_json(file: Path) -> Any:
    if not file.is_file():
        raise PackageError(f"Missing file: {file.name}")
    if file.stat().st_size > MAX_PACKAGE_FILE_BYTES:
        raise PackageError(f"{file.name} is larger than {MAX_PACKAGE_FILE_BYTES // (1024 * 1024)} MB")
    try:
        return json.loads(file.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise PackageError(f"{file.name} is not valid JSON: {error}") from error


def _merge_entries(raw: list[dict[str, Any]]) -> list[GroupEntry]:
    """PeopleSoft renders every group twice; keep one entry per group and merge course lists."""
    merged: dict[tuple[str, int, str | None], GroupEntry] = {}
    for item in raw:
        try:
            key = (str(item["title"]).strip(), int(item["level"]), item.get("parent"))
        except (KeyError, TypeError, ValueError) as error:
            raise PackageError(f"Requirement entry is missing title or level: {item!r:.200}") from error
        courses = [str(code) for code in item.get("courses") or []]
        if key in merged:
            existing = merged[key].courses
            existing.extend(code for code in courses if code not in existing)
            continue
        units = item.get("units_required")
        merged[key] = GroupEntry(
            title=key[0],
            level=key[1],
            parent=key[2],
            units_required=float(units) if units is not None else None,
            courses=list(dict.fromkeys(courses)),
            position=len(merged),
        )
    return list(merged.values())


def link_tree(entries: list[GroupEntry]) -> list[GroupEntry]:
    """Attach children to parents (by the most recent group one level up); returns the roots."""
    for entry in entries:
        entry.children = []
    roots: list[GroupEntry] = []
    latest_at_level: dict[int, GroupEntry] = {}
    for entry in entries:
        if entry.level == 0:
            roots.append(entry)
        else:
            parent = latest_at_level.get(entry.level - 1)
            if parent is None or (entry.parent and parent.title != entry.parent):
                parent = next(
                    (
                        e
                        for e in reversed(entries[: entry.position])
                        if e.level == entry.level - 1 and e.title == entry.parent
                    ),
                    parent,
                )
            if parent is None:
                roots.append(entry)
            else:
                parent.children.append(entry)
        latest_at_level[entry.level] = entry
        for deeper in [level for level in latest_at_level if level > entry.level]:
            del latest_at_level[deeper]
    return roots


def course_from_raw(code: str, raw: dict[str, Any]) -> Course:
    units_text = str(raw.get("units") or "").strip()
    try:
        units: float | None = float(units_text) if units_text else None
    except ValueError:
        units = None
    return Course(
        code=code,
        title=_clean(raw.get("title")) or code,
        units=units,
        description=_clean(raw.get("description")) or "",
        component=raw.get("component") or None,
        notices=tuple(str(n) for n in raw.get("notices") or ()),
        offered_terms=parse_offered_terms(raw.get("offered_terms")),
    )


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).replace("�", " ").replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", text).strip()


def build_program(package: ProgramPackage) -> Program:
    roots = link_tree(package.entries)
    if len(roots) != 1:
        raise PackageError(f"requirements.json must have exactly one top-level group, found {len(roots)}")
    used_keys: set[str] = set()

    def convert(entry: GroupEntry) -> Group:
        setting = package.meta.groups.get(entry.title, GroupSetting())
        key = unique_key(entry.title, used_keys)
        children = tuple(convert(child) for child in entry.children)
        courses = tuple(code for raw in entry.courses if (code := normalize_code(raw)))
        return Group(
            key=key,
            title=entry.title,
            label=setting.label or readable_group_label(entry.title),
            units_required=entry.units_required or 0.0,
            role=setting.role or (_guess_role(entry.title) if not children else GroupRole.OTHER),
            courses=() if children else courses,
            children=children,
        )

    meta = package.meta
    return Program(
        id=meta.id,
        name=meta.name,
        kind=meta.kind,
        total_units=meta.total_units,
        root=convert(roots[0]),
        catalog_year=meta.catalog_year,
        source=meta.source,
        source_date=meta.source_date.isoformat() if meta.source_date else None,
        published=meta.published,
        family=meta.family or "",
        valid_from=Term.parse(meta.valid_from) if meta.valid_from else None,
        standard_terms=meta.standard_terms,
    )


def unique_key(title: str, used: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80] or "group"
    key, counter = base, 2
    while key in used:
        key, counter = f"{base}-{counter}", counter + 1
    used.add(key)
    return key


def _guess_role(title: str) -> GroupRole:
    lower = title.lower()
    if "free elective" in lower:
        return GroupRole.FREE_ELECTIVE
    if "major elective" in lower:
        return GroupRole.MAJOR_ELECTIVE
    return GroupRole.OTHER


def build_courses(course_list: CourseList) -> dict[str, Course]:
    courses = {}
    for raw_code, raw in course_list.raw_courses.items():
        code = normalize_code(raw_code)
        if code:
            courses[code] = course_from_raw(code, raw)
    return courses


def parse_rules(courses: dict[str, Course]) -> dict[str, list[Rule]]:
    subjects = frozenset(course.subject for course in courses.values())
    return {
        code: [
            Rule(code, parsed.kind, parsed.source_text, parsed.expr, parsed.status)
            for parsed in parse_description(course.description, subjects)
        ]
        for code, course in courses.items()
    }


def catalog_from_packages(course_list: CourseList, packages: Sequence[ProgramPackage] = ()) -> Catalog:
    """Build a catalog straight from the files (tests and offline validation; the app reads the database)."""
    courses = build_courses(course_list)
    rules = {
        code: {rule.kind: rule for rule in found} for code, found in parse_rules(courses).items() if found
    }
    programs = {package.meta.id: build_program(package) for package in packages}
    return Catalog(courses=courses, rules=rules, programs=programs)

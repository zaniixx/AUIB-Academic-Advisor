"""Request and response shapes for editing the catalog in the admin page.

Courses, bulk course uploads, programs, term schedules and backups. Like every input
in this API, each list and string has a limit.
"""

from __future__ import annotations

import base64
import binascii
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.api.schemas import (
    AdminRuleOut,
    CourseCode,
    OfferingOut,
    StrictModel,
    TermOfferingsOut,
    TermOut,
    TermText,
    _code,
)
from app.domain.catalog import GroupRole
from app.domain.codes import normalize_code
from app.domain.terms import Term
from app.importer.tables import MAX_XLSX_BYTES

Season = Literal["fall", "spring", "summer"]
RuleKindName = Literal["pre", "co", "pre_or_co"]
ProgramId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$", examples=["casc-computer-science"])]
MAX_GROUP_DEPTH = 6
MAX_GROUPS = 300


# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------


class CourseFieldsIn(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    units: float | None = Field(default=None, ge=0, le=30, description="None: planning assumes 3")
    description: str = Field(default="", max_length=20_000)
    component: str | None = Field(default=None, max_length=60)
    offered_terms: list[Season] | None = Field(
        default=None,
        max_length=3,
        description="Seasons it runs in; null or empty means every Fall and Spring",
    )
    notices: list[Annotated[str, Field(max_length=300)]] = Field(default_factory=list, max_length=20)

    @field_validator("offered_terms")
    @classmethod
    def _seasons(cls, value: list[str] | None) -> list[str] | None:
        return sorted(set(value)) if value else None


class CourseCreateIn(CourseFieldsIn):
    code: CourseCode
    hidden: bool = False

    _check_code = field_validator("code")(_code)


class HiddenIn(StrictModel):
    hidden: bool


class RuleCreateIn(StrictModel):
    kind: RuleKindName
    rule: str = Field(max_length=2000, description="Rule in the admin rule language")
    note: str | None = Field(default=None, max_length=1000)


class AdminCourseSummaryOut(BaseModel):
    code: str
    title: str
    units: float | None
    hidden: bool
    admin_edited: bool
    source_changed: bool
    origin: Literal["import", "admin"]


class AdminCourseListOut(BaseModel):
    total: int
    counts: dict[str, int]
    courses: list[AdminCourseSummaryOut]


class AdminCourseOut(AdminCourseSummaryOut):
    description: str
    component: str | None
    notices: list[str]
    offered_terms: list[str] | None
    imported_values: dict[str, object] | None = Field(
        description="The values from the course files, kept while an admin edit is in force"
    )
    rules: list[AdminRuleOut]
    counts_toward: list[str]
    offerings: list[TermOfferingsOut]


# ---------------------------------------------------------------------------
# Tables (bulk courses, term schedules)
# ---------------------------------------------------------------------------


class TableIn(StrictModel):
    """Either text (CSV, or cells pasted from a spreadsheet) or an .xlsx file in base64."""

    text: str | None = Field(default=None, max_length=3_000_000)
    xlsx_base64: str | None = Field(default=None, max_length=(MAX_XLSX_BYTES * 4) // 3 + 8)
    dry_run: bool = Field(default=True, description="Only check and preview; nothing is saved")

    @model_validator(mode="after")
    def _one_source(self) -> TableIn:
        if (self.text is None) == (self.xlsx_base64 is None):
            raise ValueError("Send either text or xlsx_base64")
        return self

    def xlsx_bytes(self) -> bytes | None:
        if self.xlsx_base64 is None:
            return None
        try:
            return base64.b64decode(self.xlsx_base64, validate=True)
        except binascii.Error as error:
            raise ValueError("xlsx_base64 is not valid base64") from error


class RowOut(BaseModel):
    line: int = Field(description="Row number as the spreadsheet shows it (the header is row 1)")
    code: str | None
    action: Literal["create", "update", "unchanged", "error", "skip"]
    messages: list[str]


class CourseBulkOut(BaseModel):
    applied: bool
    counts: dict[str, int]
    columns: list[str] = Field(description="Columns that were recognised")
    ignored_columns: list[str]
    rows: list[RowOut] = Field(description="Every row that creates, changes or has a problem")


class ScheduleUploadIn(TableIn):
    term: TermText

    @field_validator("term")
    @classmethod
    def _term(cls, value: str) -> str:
        if Term.parse(value) is None:
            raise ValueError("Not a term like 'Spring 2027'")
        return value


class ScheduleSummaryOut(BaseModel):
    term: TermOut
    courses: int
    sections: int
    updated_at: datetime
    updated_by: str


class ScheduleOut(ScheduleSummaryOut):
    offerings: list[OfferingOut]


class ScheduleUploadOut(BaseModel):
    applied: bool
    term: TermOut
    counts: dict[str, int]
    columns: list[str]
    ignored_columns: list[str]
    rows: list[RowOut] = Field(description="Rows that were skipped, with the reason")


# ---------------------------------------------------------------------------
# Programs
# ---------------------------------------------------------------------------


class GroupDraftIn(StrictModel):
    label: str = Field(min_length=1, max_length=200, description="The name students see")
    title: str | None = Field(default=None, max_length=300, description="The SIS title, if different")
    role: GroupRole = GroupRole.OTHER
    units_required: float = Field(gt=0, le=400)
    courses: list[Annotated[str, Field(max_length=16)]] = Field(
        default_factory=list, max_length=2000, description="Course codes; leave empty when it has sub-groups"
    )
    children: list[GroupDraftIn] = Field(default_factory=list, max_length=60)

    @field_validator("courses")
    @classmethod
    def _codes(cls, value: list[str]) -> list[str]:
        codes = []
        for raw in value:
            code = normalize_code(raw)
            if code is None:
                raise ValueError(f"{raw!r} is not a course code like 'CSC 231'")
            codes.append(code)
        return list(dict.fromkeys(codes))

    @model_validator(mode="after")
    def _courses_or_children(self) -> GroupDraftIn:
        if self.children and self.courses:
            raise ValueError(f"{self.label!r} has sub-groups, so its courses belong in those sub-groups")
        return self


class ProgramDraftIn(StrictModel):
    id: ProgramId
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["major", "minor"]
    catalog_year: str | None = Field(default=None, max_length=20)
    total_units: float = Field(gt=0, le=400)
    standard_terms: int = Field(
        default=8,
        ge=2,
        le=14,
        description="Regular semesters of the standard degree (8 for a four-year major)",
    )
    source: str | None = Field(default=None, max_length=300)
    source_date: date | None = None
    published: bool = False
    accept_warnings: bool = Field(default=False, description="Publish even though the check found warnings")
    family: ProgramId | None = Field(
        default=None, description="Make this a version of an existing program: that program's id (F0.4)"
    )
    valid_from: TermText | None = Field(
        default=None, description="Applies to students who joined from this term; empty means from the start"
    )
    root: GroupDraftIn

    @field_validator("valid_from")
    @classmethod
    def _first_term(cls, value: str | None) -> str | None:
        if value is None:
            return None
        term = Term.parse(value)
        if term is None:
            raise ValueError("Not a term like 'Fall 2027'")
        return term.label

    @model_validator(mode="after")
    def _tree_size(self) -> ProgramDraftIn:
        count = 0

        def walk(group: GroupDraftIn, depth: int) -> None:
            nonlocal count
            count += 1
            if depth > MAX_GROUP_DEPTH:
                raise ValueError(f"Requirement groups can be nested at most {MAX_GROUP_DEPTH} levels deep")
            if count > MAX_GROUPS:
                raise ValueError(f"A program can have at most {MAX_GROUPS} requirement groups")
            for child in group.children:
                walk(child, depth + 1)

        walk(self.root, 1)
        return self


class GroupDraftOut(BaseModel):
    key: str
    label: str
    title: str
    role: GroupRole
    units_required: float
    courses: list[str]
    children: list[GroupDraftOut]


class FindingOut(BaseModel):
    severity: Literal["error", "warning", "info"]
    where: str
    message: str


class ProgramCheckOut(BaseModel):
    ok: bool
    findings: list[FindingOut]
    stats: dict[str, int]


class AdminProgramSummaryOut(BaseModel):
    id: str
    name: str
    kind: str
    catalog_year: str | None
    total_units: float
    published: bool
    hidden: bool
    origin: Literal["import", "admin"]
    admin_edited: bool
    groups: int
    family: str = Field(description="The program this is a version of (its own id for a first version)")
    valid_from: str | None = Field(description="Applies to students who joined from this term")
    standard_terms: int = Field(description="Regular semesters of the standard degree")


class AdminProgramOut(AdminProgramSummaryOut):
    source: str | None
    source_date: date | None
    root: GroupDraftOut


class ProgramSaveOut(BaseModel):
    saved: bool = Field(description="False when the check found errors; the findings say what to fix")
    program: AdminProgramOut | None
    findings: list[FindingOut]


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------


class BackupIn(StrictModel):
    passphrase: str = Field(
        min_length=12, max_length=500, description="Needed to read the backup; not stored"
    )

    # Spaces at either end are part of a passphrase.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


MAX_BACKUP_BYTES = 5 * 1024 * 1024


class RestoreFileIn(StrictModel):
    """An uploaded backup file (base64) and the passphrase or key it was made with."""

    backup_base64: str = Field(max_length=(MAX_BACKUP_BYTES * 4) // 3 + 8)
    passphrase: str = Field(min_length=1, max_length=500)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    def backup_bytes(self) -> bytes:
        try:
            return base64.b64decode(self.backup_base64, validate=True)
        except binascii.Error as error:
            raise ValueError("The backup file could not be read") from error


class RestoreIn(RestoreFileIn):
    confirm: Literal["RESTORE"] = Field(description="Type RESTORE to confirm replacing the data")


class BackupTableOut(BaseModel):
    name: str
    in_backup: int
    now: int


class BackupCheckOut(BaseModel):
    created_at: str
    app_version: str
    schema_revision: str | None
    restorable: bool
    problem: str | None = Field(description="Why it cannot be restored here, if it cannot")
    tables: list[BackupTableOut]


class BackupFileOut(BaseModel):
    filename: str
    data_base64: str


class RestoreOut(BaseModel):
    restored: dict[str, int] = Field(description="Rows restored per table")
    audit_log_kept: bool
    previous: BackupFileOut = Field(
        description="The data from just before the restore, encrypted with the same passphrase"
    )

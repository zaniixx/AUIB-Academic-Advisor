"""Read a table an admin uploads: CSV, cells pasted from a spreadsheet, or an .xlsx file.

Cells copied from Excel or Google Sheets paste as tab-separated text, so pasting and
CSV files share one reader. An .xlsx file is read with the standard library only
(it is a zip of XML parts); only its first sheet is used. Everything is bounded:
file size, unpacked size, rows, columns and cell length, and an .xlsx part that
declares a DTD is refused (no spreadsheet needs one).

Column names are matched loosely ("Course Code", "course_code" and "CODE" are the
same column), so a registrar's export usually works without renaming its headers.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from xml.etree import ElementTree

MAX_ROWS = 5000
MAX_COLUMNS = 60
MAX_CELL_CHARS = 20_000
MAX_XLSX_BYTES = 5 * 1024 * 1024
MAX_XLSX_UNPACKED_BYTES = 60 * 1024 * 1024


class TableError(ValueError):
    """The upload cannot be read as a table at all."""


@dataclass(frozen=True)
class TableRow:
    line: int  # row number as the spreadsheet shows it (the header is row 1)
    cells: Mapping[str, str]  # normalised column name -> cell text

    def pick(self, *names: str) -> str:
        """The first non-empty cell among ``names`` (column aliases), or ""."""
        for name in names:
            value = self.cells.get(name, "").strip()
            if value:
                return value
        return ""


@dataclass(frozen=True)
class Table:
    columns: list[str]  # normalised column names, in sheet order
    rows: list[TableRow]


def column_key(name: str) -> str:
    """'Course Code ' -> 'course_code'."""
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def read_text(text: str) -> Table:
    """CSV, semicolon-separated or tab-separated text (a paste from a spreadsheet)."""
    text = text.lstrip("﻿")
    first = next((line for line in text.splitlines() if line.strip()), "")
    if not first:
        raise TableError("The table is empty")
    if "\t" in first:
        delimiter = "\t"
    elif first.count(";") > first.count(","):
        delimiter = ";"
    else:
        delimiter = ","
    csv.field_size_limit(MAX_CELL_CHARS)
    try:
        return _table(csv.reader(io.StringIO(text), delimiter=delimiter))
    except csv.Error as error:
        raise TableError(f"The table cannot be read: {error}") from error


def read_xlsx(data: bytes) -> Table:
    """The first sheet of an .xlsx workbook."""
    if len(data) > MAX_XLSX_BYTES:
        raise TableError(f"The file is larger than {MAX_XLSX_BYTES // (1024 * 1024)} MB")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as error:
        raise TableError("This is not an .xlsx file") from error
    with archive:
        if sum(info.file_size for info in archive.infolist()) > MAX_XLSX_UNPACKED_BYTES:
            raise TableError("The workbook is too large once unpacked")
        names = set(archive.namelist())

        def part(name: str) -> ElementTree.Element | None:
            if name not in names:
                return None
            raw = archive.read(name)
            # Entity tricks (billion laughs, external entities) need a DTD; spreadsheets never
            # have one, so any part declaring one is refused before it is parsed.
            if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
                raise TableError("The workbook contains a document type declaration, which is not allowed")
            try:
                return ElementTree.fromstring(raw)  # noqa: S314 - DTDs are refused above
            except ElementTree.ParseError as error:
                raise TableError(f"The workbook is damaged ({name})") from error

        shared = [
            "".join(text.text or "" for text in item.iter() if _local(text.tag) == "t")
            for item in _children(part("xl/sharedStrings.xml"), "si")
        ]
        sheet = part(_first_sheet(part("xl/workbook.xml"), part("xl/_rels/workbook.xml.rels")))
        if sheet is None:
            raise TableError("The workbook has no sheets")
        return _table(_sheet_rows(sheet, shared))


def _table(rows: Iterable[list[str]]) -> Table:
    header: list[str] | None = None
    found: list[TableRow] = []
    for line, row in enumerate(rows, start=1):
        if len(row) > MAX_COLUMNS:
            raise TableError(f"Row {line} has more than {MAX_COLUMNS} columns")
        if any(len(cell) > MAX_CELL_CHARS for cell in row):
            raise TableError(f"Row {line} has a cell longer than {MAX_CELL_CHARS} characters")
        if header is None:
            if not any(cell.strip() for cell in row):
                continue
            header = [column_key(cell) for cell in row]
            continue
        if not any(cell.strip() for cell in row):
            continue
        if len(found) >= MAX_ROWS:
            raise TableError(f"The table has more than {MAX_ROWS} rows; split it into smaller files")
        cells = {name: row[index].strip() for index, name in enumerate(header) if name and index < len(row)}
        found.append(TableRow(line, cells))
    if header is None:
        raise TableError("The table is empty")
    return Table([name for name in header if name], found)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ElementTree.Element | None, name: str) -> list[ElementTree.Element]:
    return [] if element is None else [child for child in element if _local(child.tag) == name]


def _first_sheet(workbook: ElementTree.Element | None, rels: ElementTree.Element | None) -> str:
    """The path of the workbook's first sheet (not always sheet1.xml)."""
    fallback = "xl/worksheets/sheet1.xml"
    found = workbook.iter() if workbook is not None else iter(())
    sheets = [element for element in found if _local(element.tag) == "sheet"]
    if not sheets or rels is None:
        return fallback
    rel_id = next((value for key, value in sheets[0].attrib.items() if _local(key) == "id"), None)
    for rel in rels:
        if rel.attrib.get("Id") == rel_id:
            target = rel.attrib.get("Target", "")
            return target.lstrip("/") if target.startswith("/") else f"xl/{target}"
    return fallback


def _column_index(reference: str) -> int:
    """'C7' -> 2."""
    index = 0
    for letter in re.sub(r"[^A-Z]", "", reference.upper()):
        index = index * 26 + (ord(letter) - 64)
    return max(index - 1, 0)


def _sheet_rows(sheet: ElementTree.Element, shared: list[str]) -> Iterable[list[str]]:
    for row in sheet.iter():
        if _local(row.tag) != "row":
            continue
        values: dict[int, str] = {}
        for position, cell in enumerate(child for child in row if _local(child.tag) == "c"):
            column = _column_index(cell.attrib["r"]) if "r" in cell.attrib else position
            if column >= MAX_COLUMNS:
                raise TableError(f"The sheet has more than {MAX_COLUMNS} columns")
            values[column] = _cell_text(cell, shared)
        yield [values.get(index, "") for index in range(max(values, default=-1) + 1)]


def _cell_text(cell: ElementTree.Element, shared: list[str]) -> str:
    kind = cell.attrib.get("t", "n")
    if kind == "inlineStr":
        return "".join(text.text or "" for text in cell.iter() if _local(text.tag) == "t")
    value = next((child.text or "" for child in cell if _local(child.tag) == "v"), "")
    if kind == "s":
        try:
            return shared[int(value)]
        except (ValueError, IndexError):
            return ""
    if kind == "b":
        return "TRUE" if value == "1" else "FALSE"
    if kind == "n" and value:
        try:
            number = float(value)
        except ValueError:
            return value
        return str(int(number)) if number.is_integer() else f"{number:g}"
    return value

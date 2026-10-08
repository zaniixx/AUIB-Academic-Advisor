"""Turn raw SIS scraper output into a program package and course data that are safe to commit.

The scraper saves what the logged-in student sees, including their own progress
("96.00 taken, 30.00 needed"). This script keeps only catalog facts:

* requirements.json (in the program package): drops ``page_text`` and ``element_id``
  (personal progress and page noise), removes the duplicate entries PeopleSoft renders
  for each group and merges their course lists.
* data/catalog/courses.json (shared by every program): the scraped courses are merged
  in. Titles and descriptions are cleaned, and the per-program ``requirements`` list is
  dropped, because which requirements list a course belongs in that program's
  requirements.json. Courses from other scrapes are kept, and so are fields maintainers
  add by hand. Course data is public catalog information.
* program.json: written from the command-line options when it does not exist yet.

Usage (from the repository root):

    python scripts/prepare_program_package.py --source sis_data \\
        --out data/programs/casc-computer-science \\
        --id casc-computer-science --name "Computer Science" --kind major \\
        --source-date 2026-10-08

Only the Python standard library is used so it runs anywhere the scraper runs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PERSONAL_REQUIREMENT_FIELDS = ("page_text", "element_id")
# Which of this program's requirement groups list the course: that belongs to the
# program's requirements.json, not to the shared catalog.
PROGRAM_COURSE_FIELDS = ("requirements",)
TEXT_FIELDS = ("title", "description")
# Fields the scraper cannot see and maintainers add by hand (e.g. "offered_terms":
# ["summer"] for internships). They are carried over when courses are scraped again.
MANUAL_COURSE_FIELDS = ("offered_terms",)
DEFAULT_CATALOG = Path(__file__).resolve().parents[1] / "data" / "catalog" / "courses.json"


def clean_text(value: str | None) -> str | None:
    """Replace characters that broke during scraping and collapse whitespace."""
    if value is None:
        return None
    value = value.replace("�", " ").replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", value).strip()


def prepare_requirements(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, int, str | None], dict[str, Any]] = {}
    for entry in raw:
        key = (entry["title"], int(entry["level"]), entry.get("parent"))
        courses = list(dict.fromkeys(entry.get("courses") or []))
        if key in merged:
            existing = merged[key]["courses"]
            existing.extend(code for code in courses if code not in existing)
            continue
        clean = {k: v for k, v in entry.items() if k not in PERSONAL_REQUIREMENT_FIELDS}
        clean["courses"] = courses
        merged[key] = clean
    result = list(merged.values())
    for position, entry in enumerate(result):
        entry["index"] = position
    return result


def prepare_courses(
    raw: dict[str, dict[str, Any]], previous: dict[str, dict[str, Any]] | None = None
) -> dict[str, dict[str, Any]]:
    """The catalog with the scraped courses merged in; courses only in ``previous`` are kept."""
    result: dict[str, dict[str, Any]] = dict(previous or {})
    for code in raw:
        course = {k: v for k, v in raw[code].items() if k not in PROGRAM_COURSE_FIELDS}
        for field in TEXT_FIELDS:
            course[field] = clean_text(course.get(field))
        for field in MANUAL_COURSE_FIELDS:
            if previous and field in previous.get(code, {}) and field not in course:
                course[field] = previous[code][field]
        result[code] = course
    return {code: result[code] for code in sorted(result)}


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Folder with the scraper's courses.json and requirements.json",
    )
    parser.add_argument("--out", type=Path, required=True, help="Program package folder to write")
    parser.add_argument("--id", required=True, help="Stable program id, e.g. casc-computer-science")
    parser.add_argument("--name", required=True, help="Display name, e.g. Computer Science")
    parser.add_argument("--kind", choices=("major", "minor"), default="major")
    parser.add_argument("--source-date", required=True, help="Date the data was scraped (YYYY-MM-DD)")
    parser.add_argument(
        "--catalog-year", default=None, help="Catalog year these requirements belong to, if known"
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG,
        help="Shared course catalog to merge the courses into",
    )
    args = parser.parse_args(argv)

    raw_requirements = json.loads((args.source / "requirements.json").read_text(encoding="utf-8"))
    raw_courses = json.loads((args.source / "courses.json").read_text(encoding="utf-8"))

    requirements = prepare_requirements(raw_requirements)
    previous = json.loads(args.catalog.read_text(encoding="utf-8")) if args.catalog.exists() else None
    courses = prepare_courses(raw_courses, previous)

    args.out.mkdir(parents=True, exist_ok=True)
    args.catalog.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.out / "requirements.json", requirements)
    write_json(args.catalog, courses)

    program_file = args.out / "program.json"
    if program_file.exists():
        print(f"Kept existing {program_file}")
    else:
        root = next(entry for entry in requirements if entry["level"] == 0)
        write_json(
            program_file,
            {
                "id": args.id,
                "name": args.name,
                "kind": args.kind,
                "sis_title": root["title"],
                "catalog_year": args.catalog_year,
                "total_units": root.get("units_required"),
                "source": "SIS Enroll by My Requirements, scraped under a student login",
                "source_date": args.source_date,
                "published": False,
                "groups": {},
            },
        )
        print(f"Wrote {program_file} (unpublished; review it, then set published to true)")

    print(f"Requirement groups: {len(raw_requirements)} raw entries -> {len(requirements)} unique")
    print(f"Course catalog {args.catalog}: {len(courses)} courses ({len(courses) - len(previous or {})} new)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# 0005. Programs are data packages

Date: 2026-10-08. Status: accepted.

## Context

The prototype is CS only, but adding other programs must be a simple import (F0.6). Program data comes
from the SIS scraper today and may come from registrar sheets later.

## Decision

- A program is a folder in `data/programs/` with `program.json` (metadata, readable group labels and
  roles, published flag) and `requirements.json` in the scraper's own format.
- Courses are one catalog for all of AUIB, `data/catalog/courses.json`, also in the scraper's format
  (changed on 2026-10-08; before that each package had its own `courses.json`). It is imported before
  any program, and a program may only list courses in it.
- Nothing in the code is specific to CS. Group roles (`core`, `major_elective`, `general_education`,
  `free_elective`) tell the planner how to treat each group; "take every course" groups are detected
  from their units.
- Imports are validated first (F0.7). Errors block the import; warnings block publishing unless
  accepted. Every import is recorded with its full report.

## Consequences

- A new program needs a scrape (or a converted registrar sheet), a reviewed `program.json` and one
  command. The CS package shows the format.
- Minor programs use the same format (`kind: "minor"`). A student plans a major with an optional
  minor; a course can count toward both, as AUIB allows. The first minors were written by hand from
  official announcements, because SIS shows a student only their own program.

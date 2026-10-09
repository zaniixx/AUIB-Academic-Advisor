# Adding a program

Adding a program, major or minor, is a data task with no code changes (F0.6). The data has two parts:

| Part | Where | Holds |
| --- | --- | --- |
| Course catalog | `data/catalog/courses.json` | Every AUIB course, shared by all programs: title, credits, description with its prerequisite sentence, offering seasons |
| Program package | `data/programs/<program-id>/` | `program.json` (name, kind, source, readable labels and roles) and `requirements.json` (the requirement tree and the courses each group lists) |

AUIB counts course load in credits. The data files and the code call that field `units`, as the SIS export does (`units`, `units_required`, `total_units`); everything people read says credits.

The catalog holds the 626 courses from the SIS scrape of 8 October 2026; the CS free-elective requirement
lists every undergraduate course, so that scrape covers the whole catalog. A program can only list courses
that are in the catalog, and validation stops a program that lists one that is not.

Computer Science came from SIS; the Psychology and Teaching and Learning Design minors came from official
documents (see [Minors](#minors)).

## 1. Get the data

Run the SIS scraper under a student login of the program, or ask the registrar for the program sheet
and convert it to the same JSON format. The scraper writes `courses.json`, `requirements.json` and
saved HTML pages to a folder such as `sis_data/`. That folder holds the student's browser session and
progress, so it must stay out of git (it is in `.gitignore`).

## 2. Make a package

```sh
python scripts/prepare_program_package.py --source sis_data \
  --out data/programs/<program-id> --id <program-id> --name "<Program name>" \
  --kind major --source-date <YYYY-MM-DD>
```

The script:

- writes the program's `requirements.json`, without the per-student fields and with the duplicate entries
  PeopleSoft shows for each requirement group merged;
- merges the scraped courses into `data/catalog/courses.json`: text is cleaned, the scraper's
  per-program `requirements` list is dropped (requirements belong in the package), and courses from other
  programs and hand-kept fields such as `offered_terms` are kept;
- writes an unpublished `program.json` if there is none.

Running it again on the same scrape changes nothing. Then edit `program.json`:

| Field | Meaning |
| --- | --- |
| `id` | Stable identifier, lowercase with hyphens |
| `name`, `kind` | Display name; `major` or `minor` |
| `catalog_year` | The catalog year these requirements belong to (confirm with the registrar) |
| `total_units` | Credits the program needs |
| `source`, `source_date` | Where and when the data came from; shown on every plan |
| `published` | Whether students can choose the program after import |
| `groups` | For each requirement group, keyed by its title: a readable `label` and a `role` |

Roles tell the planner how to treat a major's group:

| Role | Planner behaviour |
| --- | --- |
| `core` | Courses of a "take every course" list; used for rules such as "all 300-level major courses" |
| `major_elective` | The planner picks specific courses that fit the student's interests |
| `general_education` | Shown as open-choice slots with suggestions |
| `free_elective` | The open pool: any course counts |

Groups whose listed courses add up to exactly the credits required are treated as "take every course"
automatically.

### Offering seasons

The scraper cannot see when a course runs. Courses that run only in some seasons get an
`offered_terms` list in `data/catalog/courses.json`, for example the CS internships:

```json
"CSC 390": { "code": "CSC 390", "title": "Internship I in Computer Science", "offered_terms": ["summer"], ... }
```

Allowed values are `fall`, `spring` and `summer`; a course without the field runs every Fall and Spring.
The planner only places a course in a season it runs in, and uses a summer term for summer-only
courses even when the student does not plan other summer courses. `prepare_program_package.py` keeps
this field when courses are scraped again.

## Versions of a program

When a program's requirements change for a new intake, add a new version instead of changing the old
one: students who joined earlier keep the requirements they joined under (F0.4). In `program.json`:

```json
{ "id": "casc-computer-science-2027", "family": "casc-computer-science", "valid_from": "Fall 2027", ... }
```

`family` is the id of the program's first version and `valid_from` is the first term the new version
applies to. Each student follows the newest version that applied when they joined. In the admin page,
"New version" on a program does the same: it copies the requirements so only the changes need editing.
Two versions of one program cannot start in the same term.

## Minors

A minor is a package with `"kind": "minor"`. Students choose it next to their major, and the planner
plans both together:

- A course can count toward the major and the minor at the same time; the CEHD flier says minor courses
  "may meet the requirements of program requirements". The planner chooses the minor's courses first, so
  they fill the major's free electives and core liberal arts choices before any credits are added.
- In a minor, a group whose courses add up to its credits ("take every course") is required. In every other
  group the planner picks specific courses that fit the student's interests and keeps the longest
  prerequisite chain where it can. A minor's roles are therefore only labels.
- "Replace with" swaps a minor course only for another course of the same minor group. Courses every
  student of the minor takes have no replacement.

The two minors were written by hand from official documents, because they are not in the SIS scrape:

| Minor | Source | Requirements as modelled |
| --- | --- | --- |
| Psychology (`minor-psychology`) | Registrar's announcement "Minor in Psychology", 14 January 2024 | PSY 101 first; then any 5 of PSY 210, 226, 230, 240, 330, 332, 340, 350 (15 credit hours); 18 credits in all |
| Teaching and Learning Design (`minor-teaching-and-learning-design`) | CEHD flier "Minor in Teaching and Learning Design", Fall 2025 | One of TLD 100, 101, 102, 103; then TLD 202, two more 200-level TLD courses, one 300- or 400-level TLD course and one 400-level TLD course (15 credit hours); 18 credits in all |

To confirm with CEHD: the TLD lists leave out TLD 206 (marked "Learning Design pathway only"), the
internships TLD 302 and TLD 305, the TLD 401 capstone and the TLD 403 practicum, which belong to the TLD
major. Both minors need their catalog year confirmed by the registrar, like Computer Science.

## 3. Validate

```sh
cd api
python -m app.cli validate --verbose                              # the catalog and every package
python -m app.cli validate ../data/programs/<program-id> --verbose  # the catalog and one package
```

The course catalog is checked first: an invalid course code or offering season is an error; a prerequisite
loop is a warning. Each package is then checked against the catalog. Errors block the import: a group
listing a course that is missing from the catalog, a group with no courses, an impossible "take every
course" group, or more than one top-level group. Warnings (for example an unconfirmed catalog year,
prerequisites of the program's courses that are not in the catalog, rules the parser only partly
understood) should be checked and either fixed at the source or accepted; a rule an admin has approved or
corrected no longer warns.

## 4. Import

```sh
python -m app.cli import ../data/programs/<program-id>                  # publishes only if no warnings
python -m app.cli import ../data/programs/<program-id> --accept-warnings
python -m app.cli import-courses                                         # the course catalog only
python -m app.cli import-all --accept-warnings                           # the catalog and every package
```

`import` and `import-all` import the course catalog first, so a program is always checked against the
latest courses. Importing the same files again changes nothing. Changes made in the admin page are kept
(see [6. Changes in the admin page](#6-changes-in-the-admin-page)).

In Docker, rebuild the API image (it copies `data/catalog/` and `data/programs/` in). On start, the API
imports every program that is not in the database yet (`import-all --only-new`), so a new package such
as a minor arrives with the next deploy. Changed data for programs already imported is imported by hand:
`docker compose exec api python -m app.cli import-all`.

## 5. Review the prerequisite rules

Sign in at `/admin` with the admin token. The "Needs review" queue shows each rule beside the SIS
sentence it came from. For each rule, either approve it as shown or write a correction in the rule
language:

```text
CSC 230 AND MAT 111
CSC 345 OR MIS 201
STANDING(junior) AND (MAT 101 OR MAT 102)
CREDITS(90)
LEVEL(300)                      every 300-level course in the major core
CONSENT("Instructor approval")  shown to students, never blocks a plan
PLACEMENT("Math placement test")
NONE                            no requirement
```

Corrections survive re-imports. If the SIS description behind a corrected rule changes, the rule is
flagged "SIS text changed" for another look.

A rule the description does not state can be added from the course's page in the Courses tab; it has no
SIS sentence, so it is the only kind of rule that can be deleted.

## 6. Changes in the admin page

Small changes do not need a new package. In the admin page:

| Tab | What it does |
| --- | --- |
| Courses | Edit a course (title, credits, description, seasons, notices) and its rules; add a course by hand; upload many courses from a CSV, cells pasted from Excel or Google Sheets, or an .xlsx file (previewed first, saved all or nothing; blank cells keep the current value); hide a course |
| Majors and minors | Build a major or minor by hand as a tree of requirement groups and sub-categories, check it, publish it; edit an imported one; hide one from students |
| Term schedules | Publish the registrar's schedule for a term (F0.5) from the same kinds of tables; that term then plans only courses on it |
| Backup and restore | Download an encrypted backup, or restore the system from one ([operations.md](operations.md#encrypted-backups)) |

How imports treat these changes:

- **Edited courses keep the edit.** The values from the course files are stored beside the edit. If a
  later import brings different values, the course is flagged "Course files changed" (filter "Files
  changed"); "Go back to the course files" drops the edit and takes the files' values.
- **Courses added by hand** stay as they are. If the course files later include the same code, the
  course is flagged when the files' values differ.
- **Hidden courses and programs stay hidden.** A hidden course is not shown or planned; students who
  passed it keep the credit. A program that still requires it shows the course as "could not be
  scheduled", which is the cue to update the program.
- **Programs edited or added in the admin page are not replaced by an import.** The import stops with
  an error for that program; run it with `--replace-admin-edits` to replace the admin page's version
  with the package.

Every change is checked like an import (errors block saving; publishing with warnings needs a tick),
recorded in the audit log, and used by plans at once.

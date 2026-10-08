# Adding a program

Adding a program, major or minor, is a data task with no code changes (F0.6). The data has two parts:

| Part | Where | Holds |
| --- | --- | --- |
| Course catalog | `data/catalog/courses.json` | Every AUIB course, shared by all programs: title, units, description with its prerequisite sentence, offering seasons |
| Program package | `data/programs/<program-id>/` | `program.json` (name, kind, source, readable labels and roles) and `requirements.json` (the requirement tree and the courses each group lists) |

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
| `total_units` | Units the program needs |
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

Groups whose listed courses add up to exactly the units required are treated as "take every course"
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

## Minors

A minor is a package with `"kind": "minor"`. Students choose it next to their major, and the planner
plans both together:

- A course can count toward the major and the minor at the same time; the CEHD flier says minor courses
  "may meet the requirements of program requirements". The planner chooses the minor's courses first, so
  they fill the major's free electives and core liberal arts choices before any units are added.
- In a minor, a group whose courses add up to its units ("take every course") is required. In every other
  group the planner picks specific courses that fit the student's interests and keeps the longest
  prerequisite chain where it can. A minor's roles are therefore only labels.
- "Replace with" swaps a minor course only for another course of the same minor group. Courses every
  student of the minor takes have no replacement.

The two minors were written by hand from official documents, because they are not in the SIS scrape:

| Minor | Source | Requirements as modelled |
| --- | --- | --- |
| Psychology (`minor-psychology`) | Registrar's announcement "Minor in Psychology", 14 January 2024 | PSY 101 first; then any 5 of PSY 210, 226, 230, 240, 330, 332, 340, 350 (15 credit hours); 18 units in all |
| Teaching and Learning Design (`minor-teaching-and-learning-design`) | CEHD flier "Minor in Teaching and Learning Design", Fall 2025 | One of TLD 100, 101, 102, 103; then TLD 202, two more 200-level TLD courses, one 300- or 400-level TLD course and one 400-level TLD course (15 credit hours); 18 units in all |

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
latest courses. Importing the same files again changes nothing.

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

# Adding a program

Adding a program, major or minor, is a data task with no code changes (F0.6). The data has two parts:

| Part | Where | Holds |
| --- | --- | --- |
| Course catalog | `data/catalog/courses.json` | Every AUIB course, shared by all programs: title, credits, description with its prerequisite sentence, offering seasons |
| Program package | `data/programs/<program-id>/` | `program.json` (name, kind, source, readable labels and roles) and `requirements.json` (the requirement tree and the courses each group lists) |

AUIB counts course load in credits. The data files and the code call that field `units`, as the SIS export does (`units`, `units_required`, `total_units`); everything people read says credits.

The catalog holds 821 courses: the 626 from the SIS scrape of 8 October 2026 (the CS free-elective
requirement lists the undergraduate courses SIS offers), and 195 more that AUIB's released curricula
require but SIS does not list (see [Programs from the released curricula](#programs-from-the-released-curricula)). A program can only list courses
that are in the catalog, and validation stops a program that lists one that is not.

Computer Science came from SIS; the Psychology and Teaching and Learning Design minors and 18 more majors
came from official documents (see [Minors](#minors) and
[Programs from the released curricula](#programs-from-the-released-curricula)).

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
| `standard_terms` | Fall and Spring semesters of the standard degree: 8 (the default), 10 for a five-year degree |
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

## Programs from the released curricula

AUIB's colleges publish their curricula: Arts and Sciences as a spreadsheet of study plans, International
Studies and Business as Word degree plans, Healthcare Technology, Dentistry and Pharmacy as PDF curricula
with course descriptions. `scripts/curricula/build.py` turns them into packages. The documents go in
`sis_data/released doc` (outside git, like the rest of `sis_data`); the script needs `pdftotext` from
Poppler:

```sh
python scripts/curricula/build.py            # extract the text, then check every program
python scripts/curricula/build.py --write    # also write the packages and the added courses
```

Running it again on the same documents writes the same files. Every choice made where a document is
unclear or disagrees with SIS is commented in the script where it is made.

| Program (`id`) | Source | Credits | Status |
| --- | --- | --- | --- |
| Biology, Chemistry, Physics, English Literature, Psychology (`casc-…`) | CAS degree plans 2023 (suggested study plans) | 120 each | Published |
| International Relations and Security Studies (`cis-international-relations`) | CIS curriculum, Fall 2023 | 120 | Published |
| Business Administration: Accounting, Entrepreneurship, Finance and Banking, Management, Management Information Systems, Marketing (`cob-…`) | College of Business degree plans, November 2024 | 120 each | Published |
| Optometry and Vision Sciences, Anesthesia Technology (`coht-…`) | College of Healthcare Technology curricula, appendices I–II and VII–VIII | 121, 123 | Published |
| Dental Surgery (BDS) (`cod-dental-surgery`) | College of Dentistry curriculum | 189, ten semesters | Published |
| Radiologic Sciences (`coht-radiologic-sciences`) | Healthcare Technology appendices III–IV | 117 of 120 | Draft: the document gives Radiographic Anatomy and Pathology II the code RAD 450, which Practicum II also uses |
| Dental Technology (`coht-dental-technology`) | Healthcare Technology appendices V–VI | 119 of 120 | Draft: the document gives the CAD-CAM lab the code BDT 461L, which Digital Dentistry Lab II also uses |
| Pharmacy (BPharm) (`cop-pharmacy`) | College of Pharmacy curriculum | 174 of 180 | Draft: PHA 410 Physical Assessment is not in SIS, and the year-5 courses have other titles and credits in SIS |

A draft is imported unpublished, so students do not see it. Once the college confirms the missing
course, fix the program in the admin page (Majors and minors) and publish it there.

How the documents are modelled:

- **Core liberal arts (42 credits).** UNI 101, ENL 101, 201 and 210, CSC 101 and one mathematics course,
  four humanities, two social sciences and two natural sciences. The lists are SIS's (from the CS
  program) plus HIS 201, 341 and 350 and HUM 210, which the CIS and Healthcare Technology documents list
  for every program. A course a program names (BIO 101 for Biology, PSY 101 for Psychology, "2 HIS and
  1 GEO" for International Relations) is required in its category. Optometry and Dental Technology set
  most CLA courses and leave a few open; Anesthesia Technology and Radiologic Sciences set all fourteen.
- **Courses missing from SIS.** 195 courses the documents require are added to the catalog from their
  descriptions (credits and prerequisite sentences as printed), each with a notice that it is not in
  SIS yet. Courses with no description (for example ACC 201, BIO 420, POL 404 and 405) are added with
  their title and credits only.
- **Electives.** "Biology elective" and the like become the department's catalog courses at the
  program's level that are not already required; free electives are any undergraduate SIS course (300-
  or 400-level where the Business plans say so).
- **Summer.** Internships and practicums a study plan places in summer (BIO 485, CHE 352, PHY 389,
  LIT 390, PSY 480, OVS 390, ANT 295, ANT 399) are marked summer-only.
- **Length.** `standard_terms` in `program.json` is 10 for the five-year degrees, so their plans are
  measured against ten Fall and Spring semesters. The Dentistry curriculum takes 19 to 20 credits a
  term, so at the usual 18-credit maximum the plan finishes a term late and says so; students can raise
  their maximum in Adjust plan.

To confirm with the colleges:

| Program | Question |
| --- | --- |
| Biology | BIO 420 Microbiology (4 credits) is not in SIS, which has BIO 219 Medical Microbiology and its lab |
| International Relations | POL 404 and POL 405 are not in SIS; SIS has POL 295 Professional Development and Leadership Seminar. The electives include the POL courses SIS adds (POL 113, 200, 253, 342, 360, 390, 391) |
| Business (all tracks) | ACC 201 is not in SIS (nor ACC 202 and 301 for Accounting); "SOC 101 or HUM 210", and HUM 210 is not in SIS |
| Optometry | The descriptions number OVS 277 as OVS 227; the planning guide and the prerequisites use OVS 277. Some prerequisites name OVS 225, 320, 330 and 370, which the curriculum does not have |
| Anesthesia Technology | The required list includes ANT 450, which no year of the plan has; the year plan (123 credits) is followed |
| Radiologic Sciences | "PHY 241 Medical Physics and Dosimetry" is PHY 107 in SIS (PHY 241 is Mathematical Methods for Physics); RAD 390 has 2 credits in the planning guide and 3 in its description |
| Dentistry | "BIO 220 General Histology (3 credits)" is BIO 220 with its lab BIO 220L in SIS |
| Every program | The catalog year |

A prerequisite that names a course missing from the catalog, as some of these do, is shown to the student
as "check with your advisor" and never holds a course back or adds a course nobody can take. Correct it
in the admin page's review queue.

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

# Requirements traceability

Status of every requirement in the [project requirements document](../AUIB%20Academic%20Advisor%20—%20Project%20Requirements%20Document.md)
as of 2026-10-08. "Verify" means the feature is built and tested with synthetic data, but its acceptance
criterion needs real students, advisors or registrar data.

| Status | Meaning |
| --- | --- |
| Done | Built and covered by automated tests |
| Verify | Built; the acceptance check needs real people or data |
| Partial | Some of the requirement is built; the rest is noted |
| Not started | Planned for a later milestone or waiting on data |

## Prototype scope (F0, F1, basic F2, F11)

| ID | Requirement | Status | Where | Evidence |
| --- | --- | --- | --- | --- |
| F0.1 | Import courses, groups and descriptions from the scraper's JSON | Done | `api/app/importer/load.py` | `test_reimport_creates_no_duplicates`, `test_import_publishes_only_when_warnings_are_accepted` |
| F0.2 | Parse requisites into AND/OR rules; show each beside its source | Done | `api/app/domain/requisites.py`, course and admin pages | 51 tests in `test_requisites.py`; 343 of 351 CS-catalog rules fully parsed |
| F0.3 | Admin screen to correct rules; corrections survive re-import | Done | `api/app/api/routes/admin.py`, `web/src/components/admin/` | `test_correction_changes_plans_is_audited_and_survives_reimport`; rules the description does not state can be added (`test_rules_added_by_an_admin`) |
| F0.4 | Version requirements by catalog year, each version valid from a term; students follow the version in force when they joined | Done, one part waits for accounts | `programs.family` and `programs.valid_from`; `choose_version` in `api/app/domain/catalog.py`; admin "New version"; `family`/`valid_from` in `program.json`; the plan, the setup wizard and the printed document say which version applies and why | `test_versions.py` (9), `test_versions_api.py`, `test_a_package_can_be_a_new_version_of_a_program`. The entry term comes from the student's answer, else the first term in the Course History, else next term. Moving one student to a newer version is the student's choice, marked "registrar approval needed"; an admin-side move needs accounts (F9.4). The CS catalog year is unconfirmed |
| F0.5 | Import per-semester offerings | Done | Admin page, Term schedules; `api/app/services/catalog_edit.py`; `Catalog.offered` | CSV, spreadsheet paste or .xlsx; SIS class-search columns (subject, catalog number, section, days, start, end) are recognised. `test_a_term_schedule_decides_what_is_planned_that_term`, admin end-to-end test. Offering seasons in `courses.json` still cover terms without a schedule |
| F0.6 | Add a program by importing files; no code changes | Done | `api/app/importer/`, `docs/data-pipeline.md` | Planner and importer contain nothing specific to CS; two minors were added as data only |
| F0.7 | Check a package before publishing | Done | `api/app/importer/validate.py` | `test_broken_package_is_rejected_and_changes_nothing`, `test_validate_fails_for_a_broken_package` |
| F1.1 | Student enters completed and in-progress courses | Verify | Course History paste, manual add and edit in `/start` | Credits per group must be compared with SIS for 5 test students |
| F1.2 | Remaining requirements per group | Verify | `api/app/domain/progress.py` | `test_progress.py`; compare with SIS for test students |
| F1.3 | Courses eligible next term | Done | `eligible_next_term` | `test_eligible_courses_have_no_unmet_prerequisites` |
| F1.4 | Term-by-term plan within a credit limit | Done | `api/app/domain/planner.py` | `test_plans_respect_prerequisites_loads_and_requirements` (4 students × 4 settings) |
| F1.5 | Drop/delay impact under 2 seconds | Done | `api/app/domain/whatif.py` | `test_delaying_a_chain_course_delays_graduation`; a plan takes about 30 ms |
| F1.6 | Lock decided courses or terms | Done | Locks per course and term | `test_locked_courses_stay_put` |
| F1.7 | Flag courses that satisfy more than one requirement | Partial | Allocation shows where each course counts | No explicit "also counts toward" flag yet |
| F1.8 | Mark planned terms not checked against a published schedule | Done | `schedule_published` on each planned term; a quiet amber mark on the term card whose explanation shows on hover, keyboard focus or a tap; a note in the printed document and a mark per term in its overview | `test_a_term_schedule_decides_what_is_planned_that_term`, `advisor.test.ts`, end-to-end test |
| F2.1 | Onboarding questionnaire | Done | `/start`, step 4 | End-to-end test |
| F2.2 | Rank electives with reasons | Done | `api/app/domain/recommend.py` | `test_every_suggestion_explains_itself` |
| F2.3 | Use review-based workload and difficulty | Not started | | Needs course reviews (F8) |
| F2.4 | Balanced terms | Partial | Preferred load and spreading of electives | No difficulty data yet |
| F11.1 | Use without signing in | Done | Whole app | End-to-end test |
| F11.2 | Choose a major and, where modelled, a minor | Done | `/start`, step 1; `api/app/domain/planner.py` | Minors in Psychology and Teaching and Learning Design; `test_minor.py`, `test_plan_with_a_minor`, end-to-end test |
| F11.3 | Paste the SIS Course History | Verify | `api/app/domain/history.py` | Synthetic pastes pass; acceptance needs 10 students' anonymised pastes in `api/tests/fixtures/history/` |
| F11.4 | Confirm or fix parsed courses; unread lines listed | Done | `/start`, step 3 | `test_rows_that_need_a_decision_carry_issues`, end-to-end test |
| F11.5 | Guest data in the browser only; "Clear my data" | Done | `web/src/lib/profile.ts`, stateless API | ADR 0002; end-to-end test clears data |
| F11.6 | Turn a guest session into an account | Not started | | Needs AUIB sign-in (F9.1) |
| F11.7 | Reviews and share links need sign-in | Not applicable yet | | Neither feature exists yet |

## Later milestones

| ID | Requirement | Status | Notes |
| --- | --- | --- | --- |
| F3.1 | Flag courses offered once a year or less | Partial | Courses marked with offering seasons (internships: summer only) are planned only then and labelled on course pages; offering history is still needed |
| F3.2 | Flag gateway courses | Verify | Built (`/api/v1/programs/{id}/insights`, plan badges); an advisor should review the top 10 |
| F3.3 | Warn when a plan misses a bottleneck's only offering | Partial | The longest chain is shown and what-if reports delays; offering-based warnings need F0.5 |
| F4.1 | Percent complete and per-group progress | Done | Summary cards and requirement bars |
| F4.2 | "What's left" checklist | Done | Requirements section |
| F5.1 | Visual degree map with prerequisite arrows | Done | `api/app/domain/journey.py`, `web/src/components/plan/DegreeMap.tsx`; `test_journey.py`, end-to-end test (also at 380px) |
| F5.2 | Colour by status | Done | Map nodes and plan items show status by colour, icon and word |
| F5.3 | Read-only view for an advisor | Partial | The printable document (F5.4) can be saved as a PDF; shareable links need accounts |
| F5.4 | Printable document for the advisor | Done | `/plan/print`: `web/src/components/plan/AdvisorDocument.tsx`, `web/src/lib/advisor.ts`; Paper size (A4, the default), optional overview of every term (off by default), write-in lines for open choices; `advisor.test.ts`, end-to-end test (also checks print mode at 380px and on desktop) |
| F6.1 | Drag courses between terms | Partial | "Keep in term" locks, what-if delays and "Replace with" (below); no drag and drop |
| F6.2 | Compare up to 3 scenarios | Not started | |
| F6.3 | Simulate a change of major or minor | Not started | Needs more programs |
| F7.1 | Term and cumulative GPA | Verify | GPA card (`api/app/domain/gpa.py`, `test_gpa.py`); uses a standard 4.0 scale and grade replacement until AUIB confirms its rules; compare with SIS |
| F7.2 | Project GPA from expected grades | Done | GPA card, "Plan my grades": an expected grade per in-progress (and, optionally, next-term) course gives the projected CGPA; `project_gpa` in `api/app/domain/gpa.py`, `POST /api/v1/planner/gpa` | `test_expected_grades_project_the_cgpa`, `test_a_projected_retake_replaces_the_old_grade`, `test_gpa_projection_and_target`, end-to-end test |
| F7.3 | Grades needed for a target GPA | Done | "Plan my grades": a target CGPA gives the average grade the courses marked "Not sure" need, or says it is already met or out of reach (with the best possible CGPA); retake suggestions stay on the card | `test_grades_needed_for_a_target`, `test_a_target_can_be_out_of_reach_or_already_met`, `test_gpa_projection_and_target`, end-to-end test |
| F8.1–F8.5 | Course reviews | Not started | Needs accounts and moderation |
| F9.1 | Sign-in limited to AUIB email | Not started | Guest mode first; admin uses a token for now |
| F9.2 | Delete account and data | Partial | Guests clear their own data; accounts do not exist yet |
| F9.3 | Admin role; actions logged | Done | `test_correction_changes_plans_is_audited_and_survives_reimport` |
| F10 | AI chat assistant | Not started (post-release) | The planner's API endpoints are ready to be used as the assistant's tools |
| F9.4 | Login page; plans saved to the account; admins sign in | Not started | Needs AUIB single sign-on (F9.1) |
| F12 | Course requests for next semester | Not started | Builds on sign-in (F9.4) and term schedules (F0.5) |
| F13 | Automatic sync with SIS (post-launch) | Not started (post-launch) | Needs an official SIS API from AUIB IT |

## Clarifications of 2026-10-08

| Request | Status | Where | Evidence |
| --- | --- | --- | --- |
| Internships must be taken in summer | Done | `offered_terms` in `data/programs/casc-computer-science/courses.json`; migration `0002` fixes existing databases | `test_internships_are_planned_in_summer`, `test_internships_are_eligible_only_for_a_summer_term`, end-to-end test |
| Progress map as a visual aid | Done | Degree map section of the plan (F5.1) | `test_journey.py`, end-to-end test |
| "Replace with" for courses where the student chooses | Done | Plan items list courses of the same requirement that run that term, with prerequisites done earlier and corequisites in the same term | `test_replacement_options_follow_the_rules`, `test_replacing_an_elective_keeps_the_plan_valid`, end-to-end test |
| AUIB colours and style | Done | `web/src/app/globals.css` (values captured from auib.edu.iq), Ubuntu font, pill buttons | Visual review; automated contrast checks pass |
| CGPA card with last term GPA and a retake suggestion | Done | `GpaCard.tsx`, `api/app/domain/gpa.py` | `test_gpa.py`, `test_plan_includes_gpa_and_retake_suggestions`, end-to-end test |
| "Print for my advisor" as a structured document: the chosen semester and related information in one section, every term at a glance, and a notice that approval is not a promise of courses (F5.4) | Done | `/plan/print`, `web/src/lib/advisor.ts` | `advisor.test.ts`, end-to-end test |
| Advisor document: paper size choice (A4, the default), open choices as blank lines to write on, "Every term at a glance" added only on request | Done | `/plan/print` | `advisor.test.ts`, end-to-end test |
| Courses as one AUIB-wide catalog shared by every program, not a CS list | Done | `data/catalog/courses.json`, `api/app/importer/` | `test_catalog_is_shared_and_names_no_program`, `test_validate_checks_the_catalog_and_every_package` |
| Minors from the two PDFs in `sis_data/` (Psychology announcement, CEHD flier) | Done; TLD lists to confirm with CEHD | `data/programs/minor-psychology/`, `data/programs/minor-teaching-and-learning-design/` | `test_minor.py`, API and end-to-end tests |
| GPA card recommends one retake; the others open from "Other retake options" | Done | `web/src/components/plan/GpaCard.tsx` | End-to-end test |
| Degree progress shown as the completed percent with "+N% in progress" beside it | Done | `web/src/components/plan/SummaryCards.tsx` | Visual check |

## Clarifications of 2026-10-09

| Request | Status | Where | Evidence |
| --- | --- | --- | --- |
| Rework the UI so it is polished, modern and simple for students who are not technical, with animation and a clearer journey | Done | [design-system/auib-academic-advisor/MASTER.md](../design-system/auib-academic-advisor/MASTER.md); `web/src/components/ui.tsx`, `ui-client.tsx`, `icons.tsx`. Every page reworked. The plan page has a summary, then tabs (Plan, Requirements, Degree map, Explore courses, Notes) kept in the address; course rows open for actions; settings sit behind "Adjust plan". The wizard has a numbered stepper. | End-to-end tests (desktop and 380px phone, axe on each step); axe in light and dark mode on every page and plan tab; the plan page went from 9,291px to about 3,100px tall on desktop |
| Admin: edit imported courses and their rules | Done | Admin page, Courses; `PUT /api/v1/admin/courses/{code}`, `POST .../rules` | `test_an_edit_survives_reimport_and_can_be_undone`, `test_rules_added_by_an_admin` |
| Admin: add courses by hand | Done | Admin page, Courses, "Add a course" | `test_add_a_course_by_hand` |
| Admin: add many courses from a CSV or a spreadsheet | Done | Admin page, Courses, "Upload many courses" (CSV, paste from Excel or Google Sheets, .xlsx); previewed, saved all or nothing | `test_bulk_courses_preview_then_save`, `test_bulk_courses_from_a_spreadsheet_paste`, `test_bulk_courses_from_an_xlsx_file`, `test_a_workbook_with_a_dtd_is_refused` |
| Admin: hide a course, major or minor | Done | Courses and Majors and minors tabs | `test_hidden_courses_are_not_shown_or_planned`, `test_hidden_programs_are_not_offered` |
| Admin: add a major (with sub-categories) or a minor by hand | Done | Admin page, Majors and minors; the same checks as an import (`validate_program`) | `test_build_a_minor_by_hand_and_plan_with_it`, `test_a_program_edited_here_is_kept_by_imports` |
| Admin: export an encrypted backup with a passphrase or token | Done | Admin page, Backup and restore (passphrase or generated key); `backup-export`, `backup-inspect`, `backup-restore` commands; AES-256-GCM with scrypt | `test_encrypted_backup_round_trip`, `test_backups_from_the_command_line` |
| Admin: restore the system from an uploaded backup with its passphrase or key | Done | Admin page, Backup and restore: check the file (rows now and in the backup), type RESTORE, restore; the previous data downloads first as an undo file; the audit log is kept | `test_restore_from_the_admin_page`, `test_restore_refuses_a_backup_from_another_schema`, `test_an_upload_that_is_not_a_backup_is_refused`, admin end-to-end test (backs up, then restores the same file) |
| Admin: upload a term's course schedule from a sheet or CSV | Done | Admin page, Term schedules (F0.5); students see sections on course pages | `test_a_term_schedule_decides_what_is_planned_that_term`, admin end-to-end test |

## Non-functional requirements

| Area | Status | Evidence |
| --- | --- | --- |
| Privacy | Done | No student data stored; `no-store` responses; [security-and-privacy.md](security-and-privacy.md) |
| Data minimisation | Done | No SIS passwords or sessions; the app never logs into SIS |
| Security | Partial | HTTPS, headers, rate limits, audit log and encrypted backups (admin page and CLI) are built; AUIB sign-in and encrypting the nightly `pg_dump` files are open items |
| Performance | Done | About 20 ms per full-degree plan, including replacement options; `test_plan_is_fast_enough` |
| Scale (500 concurrent users) | Verify | Not load-tested yet |
| Availability | Verify | Health checks and automatic restarts; depends on hosting |
| Mobile (380px) | Done | Playwright "phone" project at 380px checks every step for sideways scrolling |
| Language (Arabic-ready) | Partial | Logical (start/end) CSS throughout; strings are not yet extracted for translation |
| Accessibility (WCAG 2.1 AA) | Partial | Automated axe checks pass on every page and plan tab, in light and dark mode; animations respect reduced motion; a manual audit is still needed |
| Transparency | Done | Disclaimer, assumptions and catalog source date on every plan |
| Maintainability | Done | Re-import is one command and idempotent |
| Portability | Done | Docker Compose; backup and restore tested; [operations.md](operations.md) |

## Prototype success metrics

| Metric | Target | Status |
| --- | --- | --- |
| Programs modelled | Computer Science | Done |
| Requirement accuracy vs SIS | 100% of CS groups match | Verify: groups and credits match the scrape; check against test students' SIS audits |
| Prerequisite accuracy | 95% after manual review | Verify: 98% parse fully; review queue ready |
| Plans checked by an advisor | 5 sample plans, no blocking errors | Not yet |
| Active student users | 20 testers | Not yet |

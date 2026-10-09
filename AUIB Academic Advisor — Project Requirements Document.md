# AUIB Academic Advisor — Project Requirements Document

Oct 8, 2026 · @zaniixx

## Overview

The AUIB Academic Advisor is a web app that tells each student what to take next, what is left to graduate, and what a change (dropping, delaying, switching) does to their graduation date. A working prototype is due within 2 months, before the next intake of new students; the full release follows within 3–4 months.

**Problem.** AUIB students plan their degrees inside SIS (PeopleSoft), which shows requirement groups and course lists but not prerequisite chains, offering patterns or the timeline impact of a decision. Prerequisites are buried in each course's description, so a student often learns a course was a bottleneck only after it has delayed them.

**Vision.** One place where a student sees their whole degree as a path, gets recommendations that fit their interests and goals, and learns from other students' experience of each course.

**Built by.** A single developer (the author), with possible university support after the prototype proves useful.

## Goals, non-goals and success metrics

The prototype succeeds if a Computer Science student can load their record, see exactly what is left, and get a correct term-by-term plan to graduation.

**Goals**

- Model AUIB's curriculum (courses, prerequisites, requirement groups) accurately enough to plan against.
- Answer the three questions students ask advisors most: what do I take next, what is left, and what happens if I drop this.
- Warn students about bottleneck courses before they cause a delay.
- Recommend electives that fit a student's interests and post-graduation goals.
- Earn university support by proving value with incoming students.

**Non-goals (for now)**

- Registering students for classes. Enrolment stays in SIS.
- Replacing human advisors. The app supports advising decisions; official degree audits stay with the registrar.
- A live integration with SIS. Data arrives by scrape or file import until the university offers more.
- Programs other than Computer Science in the prototype. CS is the only program with scraped data; others plug in through the same import (F0.6).
- An AI chat assistant in the prototype or full release. It is a possible addition after release (F10).

**Success metrics**

| Metric | Prototype target (month 2) | Full release target (month 4) |
| --- | --- | --- |
| Programs modelled | Computer Science | CS + at least 2 more programs |
| Requirement accuracy vs. SIS | 100% of CS requirement groups match | 100% for every modelled program |
| Prerequisite accuracy | 95% of CS prerequisites correct after manual review | 98% across programs |
| Plans checked by an advisor | 5 sample plans reviewed, no blocking errors | 20 plans reviewed |
| Active student users | 20 testers | 150 students in the first intake |
| Course reviews submitted | Not measured | 200 reviews |

## Users

Incoming students are the launch audience; continuing students are the long-term core; advisors and the registrar are the gatekeepers for adoption.

| User | What they need | Key features |
| --- | --- | --- |
| Incoming student (first term) | Understand how the degree is structured and what to take first | Journey visualization, default 4-year plan, progress tracking |
| Continuing student | Plan remaining terms, react to a failed or dropped course | Planning engine, what-if simulator, bottleneck warnings, GPA projector |
| Student choosing electives | Pick liberal-arts and major electives that fit their goals | Recommendations, course reviews |
| Academic advisor | Check a student's plan quickly in an advising session | Printed plan document, shareable read-only plan view |
| Registrar / IT | Confidence that data is accurate and student data is safe | Data source transparency, privacy controls |

## Scope and priorities

The curriculum data model comes first because every feature reads from it; after that, features ship in the order below.

| Priority | Feature | Release |
| --- | --- | --- |
| 0 | Curriculum data model and import pipeline | Prototype |
| 1 | Degree-planning engine (incl. drop/delay impact) | Prototype |
| 1 | Guest mode and Course History paste (feeds the planning engine) | Prototype |
| 2 | Course and elective recommendations | Prototype (basic), full release (refined) |
| 3 | Bottleneck course detection | Prototype if offering data arrives, else full release |
| 4 | Degree-progress tracking | Full release |
| 5 | Academic journey visualization | Full release |
| 6 | What-if schedule simulator | Full release |
| 7 | GPA tracker and projector | Full release |
| 8 | Course review system | Full release |
| 9 | AI chat assistant (potential) | After full release |

Progress tracking and a simple journey view fall out of the planning engine cheaply; pull them into the prototype if time allows. Reviews come last because they need a user base before they are useful. An AI chat assistant may follow the full release, once plans and data are proven accurate.

## Functional requirements

Each requirement has an ID for tracking; "Must" items are needed for the release named in Scope.

### F0 — Curriculum data and import

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| F0.1 | Import courses, requirement groups and descriptions from the SIS scraper's JSON output | Must | Re-importing the same file creates no duplicates |
| F0.2 | Parse prerequisites and corequisites from description text into structured rules (AND / OR / "or consent") | Must | Every parsed rule is shown beside its source sentence for review |
| F0.3 | Admin screen to correct parsed rules by hand | Must | A corrected rule survives the next import |
| F0.4 | Version requirements by catalog year: each version of a program records the term it applies from (for example Computer Science 2025 applies from Fall 2025). Publishing a new version (Computer Science 2027, from Fall 2027) closes the old one for new students, and every student follows the version in force when they joined AUIB | Must | A student who joined in 2025 is planned against the 2025 version even after the 2027 version is published; one who joins in 2027 gets the 2027 version; the student and their advisor can see which version applies, and an admin can move a student to a newer version when the registrar approves |
| F0.5 | Import per-semester offerings from a spreadsheet (CSV/XLSX) | Should | One file per term loads in under a minute |
| F0.6 | Add a program by importing its files in the scraper's JSON format (registrar sheets converted to it); nothing in the code is specific to CS | Must | A second program's files load and appear in the major list (F11.2) with no code change or redeploy |
| F0.7 | Check a new program's files before publishing: unknown course codes, missing courses, requirement totals that don't add up | Should | Problems are listed by file and entry; nothing is published until they are fixed or accepted |
| F0.8 | Admin screen to edit a course and its rules, add courses by hand, and add many from a CSV or spreadsheet | Should | An upload is previewed row by row and saved all or nothing; an admin's edit is kept when the course files are imported again |
| F0.9 | Hide a course, major or minor from students without deleting it | Should | A hidden course is not shown or planned, and students who passed it keep the credit |
| F0.10 | Build a major (with sub-categories) or a minor in the admin screen | Should | It passes the same checks as an imported program before it is published |
| F0.11 | Back up the database from the admin screen as an encrypted file (passphrase or generated key), and restore the system from such a file | Should | The file cannot be read without the passphrase; a restore is checked and confirmed first, keeps the audit log, and hands back the previous data so it can be undone |

### F1 — Degree-planning engine

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| F1.1 | Student enters completed and in-progress courses (manual entry, import, or Course History paste per F11.3) | Must | Credits per requirement group match SIS for 5 test students |
| F1.2 | Show remaining requirements per group: major core, major electives, CLA sub-groups, English, free electives | Must | Credits required / taken / needed match SIS exactly |
| F1.3 | List courses the student is eligible for next term | Must | No listed course has an unmet prerequisite |
| F1.4 | Generate a term-by-term plan to graduation under a credit-load limit | Must | Plan respects prerequisites, corequisites and load limits |
| F1.5 | Drop/delay impact: removing a course shows the new graduation term and every course that shifts | Must | Result shown in under 2 seconds |
| F1.6 | Lock courses or terms the student has already decided | Should | Regenerated plans keep locked items |
| F1.7 | Flag courses that satisfy more than one requirement and how SIS counts them | Could | Matches SIS's allocation for test students |
| F1.8 | Mark each planned term whose courses are not checked against a published schedule for that term: a quiet colour or a small warning icon, with a short note that the app does not know yet whether those courses will be offered | Must | Terms with a published schedule (F0.5) show no mark; every other planned term does, on screen and in the printed document; the mark never hides or blocks a course |

### F2 — Course and elective recommendations

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| F2.1 | Onboarding questionnaire: interests, career goals, preferred workload | Must | Takes under 3 minutes |
| F2.2 | Rank eligible electives per open requirement group by fit | Must | Each suggestion states why it was suggested |
| F2.3 | Factor in workload and difficulty from reviews once available | Should | Ranking changes when review data exists |
| F2.4 | Suggest a balanced term (mix of heavy and light courses) | Could | Planned term's combined workload stays under the student's stated limit |

### F3 — Bottleneck detection

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| F3.1 | Flag courses offered once a year or less, from offering history | Must | Flags match the registrar's offering data |
| F3.2 | Flag gateway courses that many later courses depend on (prerequisite graph fan-out) | Must | Top 10 gateways reviewed by an advisor as sensible |
| F3.3 | Warn when a plan misses a bottleneck's only offering and show the delay it causes | Must | Warning appears on the affected plan term |

### F4 — Degree-progress tracking

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| F4.1 | Overall percent complete and per-group progress | Must | Percentages match SIS |
| F4.2 | "What's left" checklist | Must | Lists every unmet requirement |

### F5 — Academic journey visualization

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| F5.1 | Visual map of the degree: courses as nodes, prerequisites as arrows, laid out by term | Must | Readable on a phone screen |
| F5.2 | Colour by status: done, in progress, planned, blocked | Must | Status matches the planning engine |
| F5.3 | Export or share a read-only view for an advisor | Should | Shared link needs no login to view |
| F5.4 | A printable document for the advisor: the semester being planned in detail (courses, credits, the requirement each counts toward, conditions to confirm, alternatives, the in-progress courses assumed passed; an open choice prints as a blank line to write the chosen course on), an optional overview of every term (off by default), and a sign-off area | Must | The student picks the paper size (A4 for now, the default); prints without the site's menus, with the semester on the first page; a notice at the top and beside the sign-off says the document schedules nothing and that an advisor's approval is not a promise that courses will be offered in upcoming terms |

### F6 — What-if schedule simulator

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| F6.1 | Drag courses between terms and see validity and graduation date update live | Must | Invalid moves are explained, not just blocked |
| F6.2 | Save and compare up to 3 scenarios side by side | Should | Comparison shows graduation term and credits per term |
| F6.3 | Simulate a change of major or minor | Could | Shows which completed credits transfer |
| F6.4 | Replace a course the student may choose (an elective or open choice) in a suggested plan with another from the same requirement that fits that term | Must | Only courses whose prerequisites are done in earlier terms and whose corequisites are in the same term are offered; the plan stays valid after the swap |

### F7 — GPA tracker and projector

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| F7.1 | Compute term and cumulative GPA using AUIB's grading scale and repeat rules | Must | Matches SIS GPA for test students |
| F7.2 | Project GPA from expected grades in planned courses | Must | Updates instantly as grades are changed |
| F7.3 | Show the grades needed to reach a target GPA or honours threshold | Should | Says plainly when a target is unreachable |
| F7.4 | A GPA card: CGPA, the last term's GPA under it, and under that the courses whose retake would raise the CGPA most | Should | Each suggestion shows the CGPA it would give with an A and with a B |

### F8 — Course review system

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| F8.1 | Students who took a course rate difficulty, workload (hours/week) and usefulness | Must | One review per student per course offering |
| F8.2 | Reviews record the term and instructor | Must | Aggregates can be filtered by instructor |
| F8.3 | Optional written comments, moderated before publishing | Must | Reported comments are hidden until reviewed |
| F8.4 | Reviews shown anonymously | Must | No reviewer identity visible to other students |
| F8.5 | Show aggregates only after a minimum number of reviews | Should | Fewer than 3 reviews shows "not enough reviews yet" |

### F9 — Accounts and access

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| F9.1 | Sign-in restricted to AUIB email addresses | Must | Non-AUIB emails are rejected |
| F9.2 | Student can delete their account and all their data | Must | Deletion completes within 30 days, reviews anonymised |
| F9.3 | Admin role for curriculum corrections and review moderation | Must | Admin actions are logged |
| F9.4 | Login page for students and admins with AUIB single sign-on; a signed-in student's plan is saved to their account and follows them across devices; admins sign in instead of using the shared token | Must | Login works with an AUIB account only; signing out leaves no data in the browser |

### F10 — AI chat assistant (post-release, potential)

A possible addition after the full release: students ask questions in plain language and get answers drawn from their own plan and the catalog. These requirements are provisional and get confirmed before work starts.

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| F10.1 | Answer plain-language questions about the student's degree ("Can I graduate a term early?", "What happens if I drop this course?") | Later | Answers match the planning engine's result for the same question |
| F10.2 | Ground every answer in app data and show the courses, requirements or plan terms it used | Later | Each answer links to its sources in the app |
| F10.3 | Refer the student to an advisor or the registrar for questions outside the data or about official decisions | Later | Never confirms registrations, exceptions or graduation eligibility |
| F10.4 | Send no student data to an AI provider without the student's consent, and only to providers that do not train on it | Later | Consent asked before first use; provider terms reviewed |

### F11 — Guest mode and Course History paste

Anyone can use the planner without an account: pick a major, an optional minor, and paste their SIS Course History. Guests get plans, progress and recommendations; anything tied to an identity needs AUIB sign-in.

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| F11.1 | Use the app without signing in | Must | A guest reaches a full plan without entering an email |
| F11.2 | Select a major and, where one is modelled, a minor | Must | Only programs with loaded requirements are listed; the minor is optional |
| F11.3 | Import course history by pasting the SIS page: Academic Record → Course History, Ctrl+A, Ctrl+C, then paste into the app | Must | Courses, terms, grades and status parse correctly for 10 test students' pastes |
| F11.4 | Show the parsed courses for the student to confirm or fix before planning | Must | Unrecognised lines are listed, never silently dropped |
| F11.5 | Keep guest data in the browser only; the server uses it to compute a plan and stores none of it | Must | No guest course history in the database or logs; a "Clear my data" button empties the browser |
| F11.6 | Turn a guest session into an account, keeping the entered data | Should | After AUIB sign-in, the course history and plan carry over |
| F11.7 | Writing reviews and creating advisor share links require sign-in | Must | Guests see a sign-in prompt for both |

### F12 — Course requests for next semester (planned, not built)

Signed-in students can ask for a course to be offered next semester, so departments see demand before the schedule is set.

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| F12.1 | A signed-in student requests a course for next semester, with an optional reason (for example "needed to graduate on time") | Should | One request per student per course per term; requires sign-in (F9.4) |
| F12.2 | The app suggests requests from the plan: courses the student needs next term that are not on the published schedule | Should | Suggestions come from the planning engine and the term schedule (F0.5) |
| F12.3 | Admins and departments see requests per course and term, with counts and how many students need the course to graduate on time | Should | Export to CSV; no grades or course histories are shown |
| F12.4 | Students see the status of their requests (received, under review, scheduled, not offered) | Could | A request is never a promise that the course will run |

### F13 — Automatic sync with SIS (post-launch, potential)

After launch, if AUIB IT provides an official SIS API, a signed-in student's course history could update automatically instead of being pasted.

| ID | Requirement | Priority | Acceptance criteria |
| --- | --- | --- | --- |
| F13.1 | With the student's consent, read their course history and grades from SIS through an official API provided by AUIB IT | Later | Only an API approved by AUIB IT; never scraping or the student's password |
| F13.2 | Keep the plan up to date when SIS changes (new grades, registrations), and show when it was last synced | Later | The student can see and undo what changed |
| F13.3 | The student can turn sync off and delete the synced data at any time | Later | Turning it off removes stored SIS data within 30 days |

## Data requirements

The app needs two kinds of data: a catalog that changes yearly and an offering schedule that changes every term. Prerequisites and offering history are the two hardest and most valuable items. CS catalog data is already scraped from SIS, and the prototype runs on it alone.

**Catalog data (once per catalog year)**

| Data | Source | Needed for | Status |
| --- | --- | --- | --- |
| Course list: code, title, credits, description, component, grading | SIS scraper (Course Detail page) | Everything | Done: 626 courses in one AUIB-wide catalog shared by every program |
| Prerequisites and corequisites | Parsed from SIS descriptions; registrar to confirm | Planning, bottlenecks, visualization | CS descriptions scraped; parsing built, review needed |
| Requirement groups per program, credits required, eligible courses | SIS scraper (Requirement Details page) | Planning, progress | Scraped for CS (scraper sees own program only) |
| Catalog year rules: which requirements apply to which entry year | Registrar | Planning | To request |
| Grading scale, GPA rules, repeat and withdrawal policy | Registrar / student handbook | GPA projector, drop impact | To request |
| Credit-load limits per term (normal, maximum, probation) | Registrar / handbook | Plan generation | To request |
| Requirement groups for other programs | Registrar, or a student in each program running the scraper | Multi-program support | To request |
| Requirement groups for minors | Registrar; published minor announcements | Minor selection (F11.2), planning | Done for Psychology and Teaching and Learning Design (from their announcements); others to request |
| Offering seasons for courses that do not run every term (internships run in summer only) | Data maintainers in the shared course catalog; registrar to confirm | Plan generation, bottlenecks | Done for CS internships |

**Term data (once per semester)**

| Data | Source | Needed for | Status |
| --- | --- | --- | --- |
| Courses offered this term | Registrar schedule export (spreadsheet) | Bottlenecks, plan generation | To request; the admin page loads it as CSV or .xlsx (F0.5) |
| Offering history for the last 3–4 years | Registrar | Bottleneck detection | To request |
| Sections: times, instructor, capacity | Registrar schedule export | What-if simulator, reviews | Nice to have |

**Student data (per student, entered by the student)**

Completed and in-progress courses, grades, entry year and program. In the prototype the student enters these by hand, imports them, or pastes their SIS Course History page (F11.3); guests' data stays in their browser; the "When/Typically Offered" column in SIS is the term the student took a course, not a catalog offering pattern, so it cannot replace registrar offering data.

**Core data model**

| Entity | Key fields |
| --- | --- |
| Course | code, title, credits, description, component, academic group |
| RequisiteRule | course, type (pre/co), expression tree (AND/OR of course codes), source text, reviewed flag |
| Program | name, type (major or minor), catalog year, total credits |
| RequirementGroup | program, parent group, title, credits required, selection rule |
| GroupCourse | requirement group, course |
| Offering | course, term, sections |
| Student | major, minor (optional), entry year, interests, goals |
| StudentCourse | student, course, term, grade, status |
| Plan | student, name, list of (term, course) |
| Review | course, term, instructor, difficulty, workload, usefulness, comment, moderation status |

## Data acquisition plan

SIS has no export or public API, so catalog data comes from the author's own logged-in SIS session, and term data comes from the registrar as a file. Get IT's approval before scaling either.

1. **Clear it with IT and the registrar.** Explain the project, ask whether automated reading of one's own SIS view is acceptable, and ask whether they would export the catalog directly instead.
2. **Primary route: SIS scraper.** A Playwright script (built) walks Enroll by My Requirements → Requirement Details → Course Detail under the student's own login and saves courses.json, requirements.json and courses.csv. Personal grades are kept in a separate optional file. Done for CS: everything SIS shows for the CS program is scraped.
3. **Fallback: capture helper.** If SIS blocks automated browsers, the student clicks through pages normally while a small in-browser script records each page. No bot-detection workarounds will be attempted.
4. **Other programs.** One volunteer student per program runs the scraper or capture helper, or the registrar supplies program sheets. Each program then loads through the same import as CS (F0.6).
5. **Term offerings.** Ask the registrar for one spreadsheet per semester (course code, term, sections) plus 3–4 years of history.
6. **Review and correct.** Every parsed prerequisite rule is checked on the admin screen (F0.3) before it is used for planning.

## System architecture and tech stack

One API server holds every feature's logic and reads from one database, so the curriculum model is built once and shared. Every part runs in its own Docker container, so moving to a new server means redeploying the same containers, not rebuilding the setup.

&#91;embedded content: system architecture · sources, API modules, database\]

Catalog data enters only through the import pipeline; students reach the API only through the web app.

| Layer | Suggested choice | Why |
| --- | --- | --- |
| Web app | Next.js (React) as an installable web app | One codebase for phones and laptops; no app-store approval |
| Journey map | React Flow or D3 | Draws prerequisite graphs with zoom and pan |
| API | Python with FastAPI | Same language as the scraper; good libraries for graph and scheduling logic |
| Planning logic | NetworkX for the prerequisite graph; a constraint solver (OR-Tools) for term plans | Topological ordering and load limits are solved problems in both |
| Database | PostgreSQL | Relational data with clear foreign keys; JSON columns for parsed rules |
| Sign-in | Email magic link or Google sign-in limited to AUIB domain | No passwords to store |
| Hosting | Any server or platform that runs Docker containers: a small cloud VM, Render, Railway, Fly.io, or AUIB IT's servers | Cheap for a prototype; changing host means redeploying the same containers |
| Containers | Docker for every service (web app, API, PostgreSQL, import pipeline, scraper), run together with Docker Compose | One command starts the whole app on any server; development matches production |
| AI assistant (post-release) | A hosted large-language-model API called by the API server, with the planning engine exposed as tools | Answers come from the same data and logic as every other feature; no model hosting to run |

## Non-functional requirements

Student grades are the most sensitive data the app holds, so privacy shapes the design more than performance does.

| Area | Requirement |
| --- | --- |
| Privacy | Grades and plans are visible only to the student (and an advisor they share a link with). Course reviews are anonymous. Guest data stays in the guest's browser and is never stored on the server. Catalog data is stored separately from personal data. |
| Data minimisation | Never store SIS passwords. The app never logs into SIS on a student's behalf. |
| Security | HTTPS everywhere, AUIB-email sign-in, role-based admin access, encrypted database backups, rate limits on guest requests. |
| Performance | Plan generation and drop impact under 2 seconds for a full degree (about 40 courses). Pages load under 3 seconds on a mobile connection. |
| Scale | 500 concurrent users during registration week. |
| Availability | 99% uptime during registration periods; planned maintenance outside them. |
| Mobile | Every screen usable on a 380px-wide phone; most students will use phones. |
| Language | English first; interface built so Arabic (right-to-left) can be added. |
| Accessibility | WCAG 2.1 AA for colour contrast and keyboard use; status never shown by colour alone. |
| Transparency | Every plan shows a disclaimer that the registrar's audit is authoritative, plus the catalog date the data comes from. |
| Maintainability | Re-importing a new catalog, or adding a program from its data files, takes under an hour of admin work. |
| Portability | Every service runs from a Docker image built from the repo, with settings in environment variables. Database data lives in a Docker volume backed up off the server. Moving to a new server needs only Docker, the Compose file, the settings and the latest backup, and takes under 2 hours. |

## Visual design

The app follows AUIB's public brand on [auib.edu.iq](https://auib.edu.iq/) so students recognise it as part of the university. Colour and font values were captured from the site on 2026-10-08 and are recorded in the token table below.

**Design principles**

- AUIB's brand colours fill the primary and accent roles. The app adds only neutral greys and the status colours it needs.
- English text uses the same fonts as auib.edu.iq. Arabic text uses a matching Arabic font with right-to-left layout, since the site runs English and Arabic side by side.
- Status colours (done, in progress, planned, blocked) must stay distinct from the brand accent and always pair with an icon or label.
- The official AUIB logo is used only with written approval from AUIB's communications office. Until then, the app shows its own name in the brand font beside a simple graduation-cap mark, with no university crest.
- Screens are built for students who are not technical: each screen answers its main question first and opens details on request. Motion is brief, explains a change, and switches off when the device asks for reduced motion. The full rules are in design-system/auib-academic-advisor/MASTER.md in the repository.

**Design tokens**

| Token | Used for | AUIB value (captured 2026-10-08) |
| --- | --- | --- |
| color.primary | Primary buttons, links, highlights, focus outline | #9C213F (maroon) |
| color.ink | Header bar and body text | #273237 (dark slate) |
| color.accent | Link hover, footer bar | #79726E (warm grey) |
| color.surface / color.background | Cards and page background | #FFFFFF / #F7F6F4 (a warmer tint of the site's #F4F4F4) |
| color.text / color.text-muted | Body text and secondary labels | #273237 / #5B6468 |
| color.status.done / in-progress / planned / blocked | Course status in plans and the journey map | #1D7044 / #1D5FC7 / #5B4BB7 / #C2410C (blocked kept apart from the maroon) |
| font.heading / font.body | English headings and body text | Ubuntu, weights 400, 500 and 700 |
| font.arabic | All Arabic text | Ubuntu Arabic (as on auib.edu.iq), Noto Sans Arabic as fallback |
| radius.card / radius.button | Corner rounding, matched to the site's cards and buttons | 16 px cards (the site uses 12 px); fully rounded (pill) buttons |
| logo.primary / logo.mono | App header and footer, once approved | Not used until AUIB communications approves |

- [x] Run the style-capture script on auib.edu.iq and record exact colours, fonts and logo files in this section
- [ ] Ask AUIB communications for brand guidelines and approval to use the logo

## Timeline and milestones

The prototype ships about 2 months from now, before the new-student intake; the full release follows about 2 months after that. Dates are a proposal and should be adjusted to AUIB's academic calendar.

&#91;embedded content: proposed timeline · prototype Dec 8, release Feb 8\]

The prototype demo is the gate for asking the university for support: it passes when the prototype targets in Goals are met for Computer Science students.

## Risks and mitigations

The biggest risk is data, not code: wrong prerequisites or missing offering history make every plan wrong.

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| SIS blocks the scraper or IT objects to it | Medium | High | Ask IT first; capture-helper fallback; request a registrar export |
| Prerequisite text is ambiguous ("or consent of instructor", "junior standing") | High | High | Keep source text beside every rule; manual review screen; registrar spot-check |
| No offering history from the registrar | Medium | Medium | Ship bottleneck detection on graph fan-out only (F3.2); add offering flags later |
| Students trust a wrong plan | Medium | High | Disclaimer on every plan; advisor review of sample plans before launch |
| Scope too large for one developer in 2 months | High | High | Prototype = F0, F1, basic F2 and F11 for CS only; everything else waits |
| Too few reviews to be useful | High | Low | Launch reviews after the user base exists; show nothing below 3 reviews |
| Review comments become personal attacks on instructors | Medium | High | Moderation before publishing; rate courses, not people; reporting button |
| Requirements change between catalog years | Medium | Medium | Version requirements by catalog year (F0.4) |
| AI assistant gives a confident but wrong answer | Medium | High | Build it only after the planning engine is proven; answer from engine results with sources shown (F10.2); disclaimer on every answer |
| SIS Course History layout changes, or pastes differ between browsers | Medium | Medium | Student confirms parsed courses before use (F11.4); sample pastes kept as parser tests; manual entry as fallback |

## Open questions

- [ ] Does AUIB IT allow automated reading of a student's own SIS view?
- [ ] Will the registrar provide a per-semester offering spreadsheet and 3–4 years of history?
- [ ] Which catalog year rules apply to current students, and where are they published?
- [ ] What are the credit-load limits (normal, maximum, probation, summer)?
- [ ] How does SIS allocate a course that satisfies more than one requirement group?
- [ ] Which programs follow Computer Science in the rollout?
- [ ] Should reviews name instructors, or only show instructor as a filter?
- [ ] Who hosts the app if the university adopts it: the author or AUIB IT?
- [ ] If the AI chat assistant goes ahead, which AI provider fits the budget and AUIB's privacy rules?
- [ ] How does the SIS Course History page show transfer credits, repeated courses and in-progress courses?

* [ ] Does AUIB have published brand guidelines, and may the app use the official logo?

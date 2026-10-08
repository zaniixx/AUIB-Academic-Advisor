# 0004. Requisite rules: parsed, shown with their source, corrected by admins

Date: 2026-10-08. Status: accepted.

## Context

SIS stores prerequisites only as free text in course descriptions ("Prerequisite: CSC 230 and MAT 111",
"Sophomore standing, and MAT 101 or MAT 102", "Introduction to Reading, (TLD204)"). The scraper's own
extraction misses or mangles some of these. Wrong prerequisites make every plan wrong, so accuracy
matters more than anything else (requirements document, risks).

## Decision

- Parse the description text into a rule tree: course codes, AND/OR, class standing, credit
  thresholds, "all 300-level major courses", and advisory conditions (consent, placement,
  recommended, unclear text).
- Advisory conditions never block a plan but are always shown to the student, so the app never guesses
  silently. Unclear text is kept verbatim as a note and the rule is marked "partial" or "unparsed".
- Store the parsed rule, its source sentence and its parse status. Admins review rules beside their
  source and can approve them or write a correction in a small rule language
  (`CSC 230 AND (MAT 111 OR MAT 102)`). Corrections survive re-imports; if the source sentence
  changes, the rule is flagged for another look.

## Consequences

- On the CS catalog, 343 of 351 rules parse completely, 7 correctly read "None" and 1 (an MBA
  admission condition) is kept as a note. Where the parser and the scraper disagree, the parser was
  right in every case checked (cross-listings, equivalences, lowercase codes, shorthand such as
  "TLD 302, 305"); the import report lists those cases.
- The 95% prerequisite-accuracy target still needs a human review, which the admin queue supports.
- Class standing thresholds (30/60/90 credits) are assumptions until AUIB confirms them; they live in
  one constant and are shown to students.

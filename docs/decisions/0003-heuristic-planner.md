# 0003. A heuristic planner instead of a constraint solver

Date: 2026-10-08. Status: accepted.

## Context

The requirements document suggests a constraint solver (OR-Tools) for term plans. Plans must respect
prerequisites, corequisites, class standing and unit limits, finish in under two seconds (F1.5), and be
explainable to students and advisors.

## Decision

A deterministic two-step heuristic in `api/app/domain/planner.py`:

1. **Selection.** Required courses, the prerequisites they need (choosing the cheapest alternative of an
   OR rule, preferring courses that also count toward a requirement), major electives ranked by the
   student's interests that do not lengthen the longest prerequisite chain, and open-choice slots for
   the rest.
2. **Scheduling.** Term by term: courses on the longest remaining chain first; then required courses at
   the student's year level; then the term's share of open-choice slots; then anything else that fits.
   "On time" pace keeps terms at the preferred load (15 units by default) and only goes higher, up to
   the maximum, when needed to finish within eight regular terms; "fastest" fills every term.

## Why not a solver now

- With prerequisite chains and unit caps as the only hard constraints, scheduling by longest remaining
  chain is a well-known, near-optimal rule. For a new CS student the fastest plan takes seven terms,
  exactly the length of the longest prerequisite chain (CSC 101 to CSC 450), so no schedule can be
  shorter.
- The heuristic explains itself: every course carries the reason it is in the plan, and the same input
  always gives the same plan, which matters when a student compares what-if scenarios.
- It plans a full degree in about 30 ms with no native dependency.

## Consequences

- If offering patterns (F3.1), time-slot clashes or many soft preferences are added, a constraint
  solver may give better plans. The planner sits behind one function, `build_plan`, so CP-SAT can be
  swapped in without changing the API. The test suite's plan-validity checks would apply unchanged.

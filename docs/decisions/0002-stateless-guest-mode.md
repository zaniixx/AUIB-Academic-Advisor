# 0002. Stateless guest mode

Date: 2026-10-08. Status: accepted.

## Context

Students should be able to use the planner without an account (F11). Course histories include grades,
the most sensitive data the app could hold, and the privacy requirement says guest data must never be
stored on the server (F11.5).

## Decision

- The browser keeps the guest's profile (program, course attempts, preferences) in local storage.
- Every planning request carries the whole profile; the API computes the answer in memory and keeps
  nothing. Planning responses are marked `Cache-Control: no-store`, and the API never logs request
  bodies or echoes submitted values in error messages.
- Pasted Course History text is parsed on the server, because the parser shares code with the catalog,
  and is discarded with the response.
- A "Clear my data" button removes the profile from the browser.

## Consequences

- A database breach cannot expose students' grades, and there is no personal data to delete on request.
- Plans are not available across devices until AUIB sign-in arrives (F9, F11.6); the account design
  will store a profile only with the student's consent.
- Each request is slightly larger (up to 300 course attempts are accepted) but planning stays fast
  (about 30 ms for a full degree).

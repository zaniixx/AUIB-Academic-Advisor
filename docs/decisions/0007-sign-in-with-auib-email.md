# 0007. Sign-in with an AUIB email address

Date: 2026-10-17. Status: accepted. Amends [ADR 0002](0002-stateless-guest-mode.md): students now sign
in, but their courses, grades and plans still stay in the browser.

## Context

The faculty advisor of the project asked that course and program data be available only to people with
a university email address (`name@auib.edu.iq`), verified by a code sent to that address (F9.1). Until
now the app had no sign-in and anyone could use it (F11.1). AUIB single sign-on (Google or Microsoft)
would also verify the address, but it needs AUIB IT to register the app and is not available yet.

## Decision

- **Who may sign in.** Only addresses whose domain is exactly one of `ADVISOR_ALLOWED_EMAIL_DOMAINS`
  (by default `auib.edu.iq`; subdomains and look-alikes are refused). Addresses are trimmed and
  lower-cased.
- **Codes.** A 6-digit code is emailed through SMTP. It expires after 10 minutes, works once and stops
  working after 5 wrong tries. A student can ask for one code a minute and 5 an hour, and one visitor
  for 10 an hour across all addresses. The database keeps only a keyed hash of each code (HMAC-SHA256
  with `ADVISOR_SECRET_KEY`), and deletes codes after a day.
- **Sessions.** A correct code starts a session: a 256-bit random token in an `HttpOnly`, `Secure`,
  `SameSite=Lax` cookie limited to `/api`, valid for 30 days (`ADVISOR_SESSION_DAYS`). The database
  keeps a SHA-256 hash of the token, the address and the dates; expired sessions are deleted.
- **What is protected.** Every catalog and planner endpoint (programs, courses, meta, plans, Course
  History parsing) answers 401 without a session. The health checks, sign-in itself and the admin API
  (which keeps its own token) do not need one. In the web app, the start, plan, courses and admin pages
  show the sign-in form until the student signs in; the home and privacy pages stay open.
- **Student data stays in the browser.** The session says who may use the app; it is not an account.
  Courses, grades, answers and plans are still kept only in the browser and sent with each planning
  request, as in ADR 0002. Nothing about a student is stored on the server except their address while
  they are signed in.
- **Shared computers.** The browser remembers which address its saved plan belongs to. When a different
  student signs in, the saved plan of the previous one is deleted from that browser first. Signing out
  offers to delete the plan from the browser (ticked by default), and to sign out on every device,
  which deletes all of the student's sessions and codes from the server (F9.2).
- **Production safeguards.** The API refuses to start in production without a secret key of at least
  32 characters and a working SMTP configuration. A development mode that writes codes to the log
  instead of emailing them is refused in production.

## Alternatives considered

- **AUIB single sign-on (Google or Microsoft).** Better for students (no code to type) and lets IT
  revoke access centrally; it remains the plan for accounts and for admins (F9.4). It needs IT to
  register the app and grant consent, so it would have delayed the advisor's requirement. Sign-in sits
  behind a small service (`app/services/auth.py`), so single sign-on can replace the email code later
  without touching the protected endpoints.
- **Magic links instead of codes.** A link opens in whatever browser the mail app chooses, often not the
  one the student was using, especially on phones; a code typed into the same page avoids that.
- **Signed (stateless) session cookies.** They cannot be revoked one by one; a session table lets a
  student sign out everywhere and lets an operator sign everyone out with one SQL statement.
- **Storing plans with the account.** Not requested, and it would put grades on the server. It stays a
  separate, opt-in step (F11.6).

## Consequences

- The server now holds AUIB email addresses of signed-in students and hashed codes; the inventory in
  `docs/security-and-privacy.md` lists them. They are excluded from encrypted backups.
- The app depends on a mail provider: AUIB's own SMTP relay, or a service such as Mailgun, Postmark,
  SendGrid or Brevo. If mail cannot be sent, the student is told to try again later (503) and nobody
  new can sign in; students already signed in are not affected.
- The deployment needs two new secrets (`ADVISOR_SECRET_KEY` and the SMTP password) and the SMTP
  settings, under Compose and on Heroku. Changing `ADVISOR_SECRET_KEY` only makes codes already sent
  stop working; sessions are not affected.
- Browser tests sign in with sessions issued by `python -m app.cli issue-session`, which needs access
  to the database and so cannot be used from outside the server.

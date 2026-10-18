# 0009. Admins and advisors by AUIB email, and one master token

Date: 2026-10-17. Status: accepted. Changes the admin access of [ADR 0001](0001-stack-and-deployment.md)
(a shared admin token) and builds on sign-in ([ADR 0007](0007-sign-in-with-auib-email.md)).

## Context

Every admin shared one token (`ADVISOR_ADMIN_TOKEN`), so the audit log could only say "admin", a person
who left kept access until the token changed, and changing it locked everyone out at once. A server
also had several secrets to set. Students now sign in with an emailed code (ADR 0007), which proves an
AUIB address belongs to the person signing in. Advisors will need their own access later (F5.3).

## Decision

- **Roles by address.** A `staff` table gives an AUIB address the role `admin` or `advisor`. Staff sign
  in exactly like students; the emailed code is the proof that the address is theirs, so nobody is
  vouched for by the person who adds them. The role is read on every request, so removing someone
  takes effect at once, without signing them out.
- **The master token.** `ADVISOR_ADMIN_TOKEN` becomes the master token. Only it adds or removes admins
  (in the admin page's People tab). It still opens the whole admin page, for emergencies such as the
  mail service being down. Every use is recorded in the audit log as "master token". The server's
  command line (`python -m app.cli staff`) may also add admins: anyone who can run it has the database.
- **Admins** sign in by email, use the admin page, and add or remove advisors. Every change they make is
  recorded under their address.
- **Advisors** have the role only, for now: they use the app like students until the advisor view
  exists (F5.3).
- **One secret fewer.** The key that hashes sign-in codes is derived from the master token
  (HMAC-SHA256 with a fixed label), unless `ADVISOR_SECRET_KEY` is set. A server needs the master token,
  and no longer a separate secret key.
- **What stays separate.** The data key (ADR 0008) is shared with CI and data maintainers, who must not
  hold the master token, and changing the master token would mean re-sealing the data. The database
  password is kept by PostgreSQL and set by Heroku, and the SMTP password is issued by the mail service.

## Alternatives considered

- **Admins can add other admins.** Simpler, but a stolen admin account could then create more admins.
- **Admin addresses in a setting** (for example `ADVISOR_ADMIN_EMAILS`). Changes would need a redeploy
  and would not be recorded in the audit log.
- **AUIB single sign-on with IT-managed groups** (F9.4). The better long-term answer; it needs AUIB IT,
  and the role table can then be filled from the groups.
- **Derive every secret from the master token.** See "What stays separate".

## Consequences

- The audit log names the admin who made each change; changes made with the master token say so.
- Admin access depends on mail delivery, as students' does; the master token is the way in when it fails.
- The `staff` table holds the addresses of admins and advisors. Like sign-in data, it is left out of
  encrypted backups; after moving to a new server, add the admins again with the master token or the
  command line.
- Changing the master token does not sign admins out; it only stops sign-in codes sent in the last ten
  minutes, unless `ADVISOR_SECRET_KEY` is set.

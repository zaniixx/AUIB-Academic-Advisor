# 0008. Course data sealed in the public repository

Date: 2026-10-17. Status: accepted.

## Context

Course and program data are only for students signed in with an AUIB email address (F9.1,
[ADR 0007](0007-sign-in-with-auib-email.md)). The repository on GitHub is public, and it held the same
data as plain files: the course catalog (`data/catalog/`), the program packages (`data/programs/`) and
the curriculum scripts that spell out each program (`scripts/curricula/`). Anyone could read them on
GitHub without signing in. The project wants the code to stay public.

The data is needed in four places: on a maintainer's computer (to edit it and run the tests), in CI
(tests and the import), in the Docker images (the import at start-up) and on Heroku (the release phase).

## Decision

- **One sealed file in git.** `data/sealed/curriculum.sealed` holds those three folders as JSON,
  compressed and encrypted with AES-256-GCM (`app/services/sealed_data.py`). The 20-byte header is
  authenticated, so a changed file is refused, and the file names inside are checked so a sealed file
  cannot write outside those folders. The plain folders are git-ignored.
- **One key, `ADVISOR_DATA_KEY`.** 32 random bytes in base64 (`python -m app.cli data-key`). It is kept
  by the maintainers (in a password manager, and in the git-ignored `.env` on their computers, the same
  file Docker Compose reads), in Heroku's config vars, in the `.env` of a Compose server, and as a GitHub Actions secret (and a
  Dependabot secret, because Dependabot's runs cannot read Actions secrets).
- **Opened only where needed, and only for as long as needed.** `data-unseal` writes the plain files on
  a maintainer's computer and `data-seal` seals them again; unsealing never overwrites unsealed edits.
  The images carry only the sealed file. The import commands open it into a temporary folder that is
  deleted when they finish, so the plain data never sits in an image or on a dyno's disk.
- **Guards.** CI fails if a plain data file is committed. A test fails while the plain files differ from
  the sealed copy, so changes are not left unsealed. CI no longer uploads the Playwright report, because
  artifacts of a public repository can be downloaded by anyone and its screenshots show course data.
- **Course details out of the public docs.** The course-by-course notes on how programs were modelled
  moved from `docs/data-pipeline.md` into `scripts/curricula/NOTES.md`, which is sealed.

## Alternatives considered

- **Make the repository private.** Simplest, but the project wants public code.
- **A private git submodule for the data.** Heroku's GitHub integration and the Heroku button do not
  fetch private submodules, and every contributor would need access to a second repository.
- **GitHub secrets for the data.** Secrets are for short values (48 KB each) and only CI can read them;
  Heroku builds from the repository.
- **git-crypt or SOPS.** Comparable protection, but they add a tool every maintainer, CI and the images
  must install; the API already ships AES-GCM for its backups (`cryptography`).
- **Keep the data only in the database.** Imports, validation and the tests all work from the files.

## Consequences

- **The old commits still hold the plain data.** Sealing protects new commits only. The plain files have
  to be removed from the history (with `git filter-repo`) and the branches force-pushed; GitHub also
  keeps the old commits reachable through pull requests and caches until they are purged (GitHub
  Support), or until the repository is recreated. Anyone who cloned the repository before keeps a copy.
- **A leaked key opens every sealed version.** A new key (`data-key`, then `data-unseal` with the old key
  and `data-seal` with the new one) protects later commits only, so the key is shared with as few
  people as possible.
- **The data is optional.** Without the key or the sealed file, the app starts with an empty catalog,
  and admins add courses and programs in the admin page (operations.md, Starting without course data).
- **Without the key** the plain data cannot be read: fork pull requests cannot run the API tests, and a
  server without the key skips the import and keeps the data its database already has.
- **Some course codes stay public.** Tests, examples and the home page name individual courses (for
  example as fixtures for prerequisite rules). They are fragments, not the catalog or a program's
  requirements; moving the test fixtures into the sealed file is possible if that is not acceptable.
- Diffs of the data are no longer visible in pull requests on GitHub; reviewers compare the plain files
  locally after `data-unseal`.

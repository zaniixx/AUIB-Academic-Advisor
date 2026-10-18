"""Command line for data maintainers.

python -m app.cli validate [../data/programs/casc-computer-science ...] [--courses FILE]
python -m app.cli import-courses [--courses FILE]
python -m app.cli import ../data/programs/minor-psychology [--accept-warnings]
python -m app.cli import-all [--only-if-empty | --only-new] [--accept-warnings]
python -m app.cli export-openapi ../web/openapi.json
python -m app.cli backup-export backup.aab | backup-inspect backup.aab | backup-restore backup.aab --yes
python -m app.cli data-unseal [--force] | data-seal | data-key
python -m app.cli staff list | staff add name@auib.edu.iq admin|advisor | staff remove name@auib.edu.iq

The course catalog (data/catalog/courses.json by default) is shared by every program.
"validate" checks it and then each program against it; "import" and "import-all"
import it first, so a program is always checked against the latest courses.

The repository holds the catalog and programs sealed (app/services/sealed_data.py, ADR 0008).
When the plain files are not on disk, the data commands open the sealed copy with
ADVISOR_DATA_KEY into a temporary folder that is deleted afterwards.

Backups are encrypted (see app/services/backup.py). The passphrase is read from
ADVISOR_BACKUP_PASSPHRASE, or asked for when that is not set.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from app.importer.load import ImportResult, import_courses, import_package
from app.importer.package import (
    CourseList,
    PackageError,
    ProgramPackage,
    catalog_from_packages,
    load_courses,
    load_package,
)
from app.importer.validate import Severity, ValidationReport, validate_courses, validate_package

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session, sessionmaker


def _engine() -> Engine:
    """The database the settings name, with their connection pool size."""
    from app.db import make_engine
    from app.settings import get_settings

    settings = get_settings()
    return make_engine(settings.database_url, settings.db_pool_size, settings.db_max_overflow)


def _print_report(report: ValidationReport, verbose: bool) -> None:
    print(f"\n{report.program_id}: {len(report.errors)} errors, {len(report.warnings)} warnings")
    print("  " + ", ".join(f"{k}={v}" for k, v in report.stats.items()))
    for finding in report.findings:
        if finding.severity is Severity.INFO and not verbose:
            continue
        print(f"  [{finding.severity.value}] {finding.where}: {finding.message}")


DATA_COMMANDS = {"validate", "import", "import-courses", "import-all"}


@contextmanager
def _course_data(args: argparse.Namespace) -> Iterator[None]:
    """Point the data commands at the plain course data: the files on disk when they are there (a
    maintainer's computer), else the sealed copy opened into a temporary folder (images, Heroku)."""
    from app.services import sealed_data
    from app.settings import REPO_ROOT, get_settings

    settings = get_settings()
    args.default_courses, args.default_data_dir = settings.courses_file, settings.data_dir
    if settings.courses_file.exists() or not settings.sealed_data.is_file():
        yield
        return
    configured = settings.data_key.get_secret_value() if settings.data_key else None
    key = sealed_data.find_key(configured, REPO_ROOT)
    with tempfile.TemporaryDirectory(prefix="advisor-data-") as folder:
        root = Path(folder)
        sealed_data.unseal_folder(settings.sealed_data, key, root, only=sealed_data.DATA_PATHS)
        args.default_courses = root / "data" / "catalog" / "courses.json"
        args.default_data_dir = root / "data" / "programs"
        yield


def _courses_path(args: argparse.Namespace) -> Path:
    return Path(args.courses) if args.courses else Path(args.default_courses)


def _package_paths(args: argparse.Namespace) -> list[Path]:
    if getattr(args, "paths", None):
        return [Path(p) for p in args.paths]
    root = Path(args.directory) if getattr(args, "directory", None) else Path(args.default_data_dir)
    return sorted(p for p in root.iterdir() if (p / "program.json").exists())


def _load(paths: list[Path]) -> tuple[list[ProgramPackage], bool]:
    packages, failed = [], False
    for path in paths:
        try:
            packages.append(load_package(path))
        except PackageError as error:
            print(f"\n{path}: cannot be read: {error}")
            failed = True
    return packages, failed


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        course_list = load_courses(_courses_path(args))
    except PackageError as error:
        print(f"\nCourse catalog cannot be read: {error}")
        return 1
    report = validate_courses(course_list)
    _print_report(report, args.verbose)
    failed = not report.ok
    packages, unreadable = _load(_package_paths(args))
    catalog = catalog_from_packages(course_list)
    for package in packages:
        program_report = validate_package(package, catalog)
        _print_report(program_report, args.verbose)
        failed = failed or not program_report.ok
    return 1 if failed or unreadable else 0


def _print_result(result: ImportResult, verbose: bool) -> None:
    _print_report(result.validation, verbose)
    published = "" if result.program_id == "course-catalog" else f", published={result.published}"
    print(f"  -> {result.status}{published}, {result.counts}")
    for note in result.notes:
        print(f"  note: {note}")


def _import(paths: list[Path], args: argparse.Namespace, *, only_new: bool = False) -> int:
    from sqlalchemy import select

    from app.db import make_session_factory
    from app.models import ProgramRow

    try:
        course_list: CourseList = load_courses(_courses_path(args))
    except PackageError as error:
        print(f"\nCourse catalog cannot be read: {error}")
        return 1
    packages, failed = _load(paths)
    factory = make_session_factory(_engine())
    with factory() as session:
        if only_new:
            existing = set(session.scalars(select(ProgramRow.id)))
            packages = [package for package in packages if package.meta.id not in existing]
            if not packages:
                print("No new programs; nothing to do.")
                return 1 if failed else 0
        catalog_result = import_courses(session, course_list, actor=args.actor)
        _print_result(catalog_result, args.verbose)
        if catalog_result.status != "imported":
            session.commit()  # keep the record of the rejected import
            return 1
        publish = None if args.publish is None else args.publish == "yes"
        for package in packages:
            result = import_package(
                session,
                package,
                actor=args.actor,
                publish=publish,
                accept_warnings=args.accept_warnings,
                replace_admin_edits=args.replace_admin_edits,
            )
            _print_result(result, args.verbose)
            failed = failed or result.status != "imported"
        session.commit()
    return 1 if failed else 0


def cmd_import(args: argparse.Namespace) -> int:
    return _import([Path(p) for p in args.paths], args)


def cmd_import_courses(args: argparse.Namespace) -> int:
    return _import([], args)


def cmd_import_all(args: argparse.Namespace) -> int:
    from sqlalchemy import select

    from app.db import make_session_factory
    from app.models import ProgramRow

    if args.only_if_empty:
        with make_session_factory(_engine())() as session:
            if session.scalar(select(ProgramRow.id).limit(1)) is not None:
                print("Programs already imported; nothing to do.")
                return 0
    return _import(_package_paths(args), args, only_new=args.only_new)


def cmd_export_openapi(args: argparse.Namespace) -> int:
    from app.main import create_app
    from app.settings import Settings

    app = create_app(Settings(database_url="sqlite+pysqlite:///:memory:"))
    Path(args.output).write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


def _passphrase(confirm: bool) -> str:
    from_env = os.environ.get("ADVISOR_BACKUP_PASSPHRASE")
    if from_env:
        return from_env
    first = getpass.getpass("Backup passphrase: ")
    if confirm and getpass.getpass("Same passphrase again: ") != first:
        raise SystemExit("The passphrases do not match.")
    return first


def _session_factory() -> sessionmaker[Session]:
    from app.db import make_session_factory

    return make_session_factory(_engine())


def cmd_backup_export(args: argparse.Namespace) -> int:
    from app.models import AuditLogRow
    from app.services.backup import BackupError, make_backup

    with _session_factory()() as session:
        try:
            blob, counts = make_backup(session, _passphrase(confirm=True))
        except BackupError as error:
            print(error)
            return 1
        session.add(
            AuditLogRow(actor=args.actor, action="backup.export", target="database", detail={"rows": counts})
        )
        session.commit()
    Path(args.output).write_bytes(blob)
    print(f"Wrote {args.output} ({len(blob):,} bytes): " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


def _read_backup(path: str) -> dict[str, object] | None:
    from app.services.backup import BackupError, read_backup

    try:
        return read_backup(Path(path).read_bytes(), _passphrase(confirm=False))
    except (BackupError, OSError) as error:
        print(error)
        return None


def cmd_backup_inspect(args: argparse.Namespace) -> int:
    data = _read_backup(args.file)
    if data is None:
        return 1
    tables = data["tables"]
    assert isinstance(tables, dict)
    print(f"Made {data['created_at']} by version {data['app_version']} (schema {data['schema_revision']})")
    print("  " + ", ".join(f"{name}={len(rows)}" for name, rows in tables.items()))
    return 0


def cmd_backup_restore(args: argparse.Namespace) -> int:
    from app.models import AuditLogRow
    from app.services.backup import BackupError, restore_data

    if not args.yes:
        print("Restoring replaces every table in the database. Run again with --yes to go ahead.")
        return 1
    data = _read_backup(args.file)
    if data is None:
        return 1
    with _session_factory()() as session:
        try:
            counts = restore_data(session, data)
        except BackupError as error:
            print(error)
            return 1
        session.add(
            AuditLogRow(
                actor=args.actor,
                action="backup.restore",
                target="database",
                detail={"rows": counts, "made": data["created_at"]},
            )
        )
        session.commit()
    print("Restored: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


def cmd_issue_session(args: argparse.Namespace) -> int:
    """Start a session without an emailed code, for automated tests and support. Anyone who can run
    this already has the server's database, so it opens nothing new; it still accepts only addresses
    at the allowed domains."""
    from app.services import auth
    from app.settings import get_settings

    settings = get_settings()
    try:
        email = auth.check_email(args.email, settings.allowed_email_domains)
    except auth.SignInError as error:
        print(error.message, file=sys.stderr)
        return 1
    with _session_factory()() as session:
        signed_in = auth.start_session(session, settings, email, auth.utcnow())
        session.commit()
    print(signed_in.token)
    return 0


def cmd_staff(args: argparse.Namespace) -> int:
    """List, add or remove admins and advisors from the server (ADR 0009). Anyone who can run this has
    the server's database, so it may add admins, like the master token; changes are audited as "cli"."""
    from app.services import auth, staff
    from app.settings import get_settings

    with _session_factory()() as session:
        if args.staff_command == "list":
            for row in staff.list_staff(session):
                print(f"{row.role:8} {row.email}  (added by {row.added_by}, {row.added_at:%Y-%m-%d})")
            return 0
        try:
            email = auth.check_email(args.email, get_settings().allowed_email_domains)
            if args.staff_command == "add":
                staff.grant(session, "cli", email, args.role, manage_admins=True)
            else:
                staff.revoke(session, "cli", email, manage_admins=True)
        except (auth.SignInError, staff.StaffError) as error:
            print(error.message, file=sys.stderr)
            return 1
        session.commit()
    print(f"{email}: {'now ' + args.role if args.staff_command == 'add' else 'removed'}.")
    return 0


def _data_key() -> bytes:
    from app.services import sealed_data
    from app.settings import REPO_ROOT, get_settings

    settings = get_settings()
    return sealed_data.find_key(
        settings.data_key.get_secret_value() if settings.data_key else None, REPO_ROOT
    )


def cmd_data_key(args: argparse.Namespace) -> int:
    from app.services import sealed_data

    print(sealed_data.new_key())
    return 0


def cmd_data_seal(args: argparse.Namespace) -> int:
    """Seal the plain course data on this computer into data/sealed/curriculum.sealed."""
    from app.services import sealed_data
    from app.settings import REPO_ROOT, get_settings

    sealed = get_settings().sealed_data
    count = sealed_data.seal_folder(REPO_ROOT, sealed, _data_key())
    if count is None:
        print(f"{sealed.relative_to(REPO_ROOT).as_posix()} already holds these files; nothing changed.")
    else:
        print(f"Sealed {count} files into {sealed.relative_to(REPO_ROOT).as_posix()}. Commit that file.")
    return 0


def cmd_data_unseal(args: argparse.Namespace) -> int:
    """Write the plain course data from the sealed copy (after cloning or pulling)."""
    from app.services import sealed_data
    from app.settings import REPO_ROOT, get_settings

    root = Path(args.to) if args.to else REPO_ROOT
    count = sealed_data.unseal_folder(get_settings().sealed_data, _data_key(), root, force=args.force)
    print(f"Wrote {count} files under {root}.")
    return 0


def cmd_check_settings(args: argparse.Namespace) -> int:
    """Run at start-up: say plainly which settings are missing, without echoing any value (a
    validation error's own message would show part of the raw settings, secrets included)."""
    from pydantic import ValidationError

    from app.settings import Settings

    try:
        settings = Settings()
    except ValidationError as error:
        print("The API cannot start until these settings are fixed:", file=sys.stderr)
        for problem in error.errors(include_url=False, include_input=False):
            field = f"ADVISOR_{str(problem['loc'][0]).upper()}: " if problem["loc"] else ""
            message = str(problem["msg"]).removeprefix("Value error, ")
            for line in message.splitlines():
                print(f"  - {field}{line}", file=sys.stderr)
        print("See .env.example and docs/operations.md (Configuration).", file=sys.stderr)
        return 1
    print(f"Settings are complete ({settings.environment}).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)

    def courses_option(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--courses", help="Course catalog file (default: data/catalog/courses.json)")

    validate = commands.add_parser(
        "validate", help="Check the course catalog and program packages without importing (F0.7)"
    )
    validate.add_argument("paths", nargs="*", help="Program packages (default: every package)")
    courses_option(validate)
    validate.add_argument("--verbose", action="store_true", help="Also show informational findings")
    validate.set_defaults(func=cmd_validate)

    def import_options(sub: argparse.ArgumentParser) -> None:
        courses_option(sub)
        sub.add_argument("--publish", choices=("yes", "no"), help="Override the package's published flag")
        sub.add_argument(
            "--accept-warnings", action="store_true", help="Publish even if validation has warnings"
        )
        sub.add_argument(
            "--replace-admin-edits",
            action="store_true",
            help="Replace programs that were edited in the admin page with the package",
        )
        sub.add_argument("--actor", default="cli", help="Name recorded in the audit log")
        sub.add_argument("--verbose", action="store_true")

    imp = commands.add_parser(
        "import", help="Import the course catalog, then validate and import program packages (F0.1, F0.6)"
    )
    imp.add_argument("paths", nargs="+")
    import_options(imp)
    imp.set_defaults(func=cmd_import)

    imp_courses = commands.add_parser("import-courses", help="Validate and import the course catalog only")
    import_options(imp_courses)
    imp_courses.set_defaults(func=cmd_import_courses)

    imp_all = commands.add_parser(
        "import-all", help="Import the course catalog and every package in the data folder"
    )
    imp_all.add_argument("directory", nargs="?")
    when = imp_all.add_mutually_exclusive_group()
    when.add_argument("--only-if-empty", action="store_true", help="Skip if any program is already imported")
    when.add_argument(
        "--only-new", action="store_true", help="Import only programs that are not in the database yet"
    )
    import_options(imp_all)
    imp_all.set_defaults(func=cmd_import_all)

    openapi = commands.add_parser("export-openapi", help="Write the OpenAPI schema for the web client")
    openapi.add_argument("output")
    openapi.set_defaults(func=cmd_export_openapi)

    backup_export = commands.add_parser("backup-export", help="Write an encrypted backup of the database")
    backup_export.add_argument("output")
    backup_export.add_argument("--actor", default="cli", help="Name recorded in the audit log")
    backup_export.set_defaults(func=cmd_backup_export)

    backup_inspect = commands.add_parser("backup-inspect", help="Decrypt a backup and show what it holds")
    backup_inspect.add_argument("file")
    backup_inspect.set_defaults(func=cmd_backup_inspect)

    backup_restore = commands.add_parser(
        "backup-restore", help="Replace the database's contents with an encrypted backup"
    )
    backup_restore.add_argument("file")
    backup_restore.add_argument("--yes", action="store_true", help="Confirm replacing every table")
    backup_restore.add_argument("--actor", default="cli", help="Name recorded in the audit log")
    backup_restore.set_defaults(func=cmd_backup_restore)

    issue = commands.add_parser(
        "issue-session",
        help="Print a session token (cookie advisor_session) for an AUIB address, for tests and support",
    )
    issue.add_argument("email")
    issue.set_defaults(func=cmd_issue_session)

    check = commands.add_parser("check-settings", help="Check the settings and list any that are missing")
    check.set_defaults(func=cmd_check_settings)

    people = commands.add_parser("staff", help="List, add or remove admins and advisors (ADR 0009)")
    people_commands = people.add_subparsers(dest="staff_command", required=True)
    people_commands.add_parser("list", help="List admins and advisors")
    add = people_commands.add_parser("add", help="Give an AUIB address a role")
    add.add_argument("email")
    add.add_argument("role", choices=("admin", "advisor"))
    remove = people_commands.add_parser("remove", help="Remove an admin or advisor")
    remove.add_argument("email")
    people.set_defaults(func=cmd_staff)

    data_key = commands.add_parser("data-key", help="Print a new random key for sealing the course data")
    data_key.set_defaults(func=cmd_data_key)

    data_seal = commands.add_parser(
        "data-seal", help="Seal the plain course data into data/sealed/curriculum.sealed (ADR 0008)"
    )
    data_seal.set_defaults(func=cmd_data_seal)

    data_unseal = commands.add_parser("data-unseal", help="Write the plain course data from the sealed copy")
    data_unseal.add_argument("--to", help="Folder to write into (default: the repository)")
    data_unseal.add_argument(
        "--force", action="store_true", help="Replace plain files that differ from the sealed copy"
    )
    data_unseal.set_defaults(func=cmd_data_unseal)

    args = parser.parse_args(argv)
    from app.services.sealed_data import SealError

    try:
        if args.command in DATA_COMMANDS:
            with _course_data(args):
                result: int = args.func(args)
        else:
            result = args.func(args)
    except SealError as error:
        print(error, file=sys.stderr)
        return 1
    return result


if __name__ == "__main__":
    sys.exit(main())

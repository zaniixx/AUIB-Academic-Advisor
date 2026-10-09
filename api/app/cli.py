"""Command line for data maintainers.

python -m app.cli validate [../data/programs/casc-computer-science ...] [--courses FILE]
python -m app.cli import-courses [--courses FILE]
python -m app.cli import ../data/programs/minor-psychology [--accept-warnings]
python -m app.cli import-all [--only-if-empty | --only-new] [--accept-warnings]
python -m app.cli export-openapi ../web/openapi.json
python -m app.cli backup-export backup.aab | backup-inspect backup.aab | backup-restore backup.aab --yes

The course catalog (data/catalog/courses.json by default) is shared by every program.
"validate" checks it and then each program against it; "import" and "import-all"
import it first, so a program is always checked against the latest courses.

Backups are encrypted (see app/services/backup.py). The passphrase is read from
ADVISOR_BACKUP_PASSPHRASE, or asked for when that is not set.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
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
    from sqlalchemy.orm import Session, sessionmaker


def _print_report(report: ValidationReport, verbose: bool) -> None:
    print(f"\n{report.program_id}: {len(report.errors)} errors, {len(report.warnings)} warnings")
    print("  " + ", ".join(f"{k}={v}" for k, v in report.stats.items()))
    for finding in report.findings:
        if finding.severity is Severity.INFO and not verbose:
            continue
        print(f"  [{finding.severity.value}] {finding.where}: {finding.message}")


def _courses_path(args: argparse.Namespace) -> Path:
    from app.settings import get_settings

    return Path(args.courses) if args.courses else get_settings().courses_file


def _package_paths(args: argparse.Namespace) -> list[Path]:
    from app.settings import get_settings

    if getattr(args, "paths", None):
        return [Path(p) for p in args.paths]
    root = Path(args.directory) if getattr(args, "directory", None) else get_settings().data_dir
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

    from app.db import make_engine, make_session_factory
    from app.models import ProgramRow
    from app.settings import get_settings

    try:
        course_list: CourseList = load_courses(_courses_path(args))
    except PackageError as error:
        print(f"\nCourse catalog cannot be read: {error}")
        return 1
    packages, failed = _load(paths)
    factory = make_session_factory(make_engine(get_settings().database_url))
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

    from app.db import make_engine, make_session_factory
    from app.models import ProgramRow
    from app.settings import get_settings

    if args.only_if_empty:
        with make_session_factory(make_engine(get_settings().database_url))() as session:
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
    from app.db import make_engine, make_session_factory
    from app.settings import get_settings

    return make_session_factory(make_engine(get_settings().database_url))


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

    args = parser.parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    sys.exit(main())

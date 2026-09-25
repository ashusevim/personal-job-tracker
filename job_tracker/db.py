"""Database engine, schema initialization, and CLI commands."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone

import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy import Engine, create_engine, func, insert, inspect, select, text

from .models import jobs, metadata


def get_engine() -> Engine:
    engine = current_app.extensions.get("job_tracker_engine")
    if engine is None:
        raise RuntimeError("The database engine has not been initialized.")
    return engine


def init_engine() -> None:
    if "job_tracker_engine" in current_app.extensions:
        return

    database_url = _normalize_database_url(current_app.config["DATABASE_URL"])
    engine_options: dict = {
        "pool_pre_ping": True,
        "pool_use_lifo": True,
    }

    if database_url.startswith("sqlite"):
        engine_options["connect_args"] = {"check_same_thread": False}
    elif database_url.startswith("postgresql+psycopg"):
        # Neon's pooled endpoint uses transaction pooling. Disabling prepared
        # statements keeps psycopg compatible with PgBouncer transaction mode.
        engine_options["connect_args"] = {"prepare_threshold": None}

    current_app.extensions["job_tracker_engine"] = create_engine(
        database_url, **engine_options
    )


def init_db() -> None:
    init_engine()
    engine = get_engine()
    metadata.create_all(engine)
    _migrate_legacy_sqlite(engine)


def _migrate_legacy_sqlite(engine: Engine) -> None:
    """Convert timestamp and empty-date values from the original SQLite schema."""
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    if "jobs" not in inspector.get_table_names():
        return

    columns = {column["name"]: column for column in inspector.get_columns("jobs")}
    legacy_dates = (
        columns.get("applied_date", {}).get("type") is not None
        and str(columns["applied_date"]["type"]).upper() == "TEXT"
    )
    legacy_times = (
        columns.get("created_at", {}).get("type") is not None
        and str(columns["created_at"]["type"]).upper() == "TEXT"
    )
    if not legacy_dates and not legacy_times:
        return

    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS jobs_legacy_migration"))
        connection.execute(
            text(
                """
                CREATE TABLE jobs_legacy_migration (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company VARCHAR(120) NOT NULL,
                    role VARCHAR(120) NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    job_url VARCHAR(2000) NOT NULL,
                    salary VARCHAR(80) NOT NULL,
                    location VARCHAR(120) NOT NULL,
                    applied_date DATE,
                    notes TEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    CONSTRAINT ck_jobs_status CHECK (
                        status IN ('Saved', 'Applied', 'Interview', 'Offer', 'Rejected')
                    )
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO jobs_legacy_migration (
                    id, company, role, status, job_url, salary, location,
                    applied_date, notes, created_at, updated_at
                )
                SELECT
                    id, company, role, status, job_url, salary, location,
                    NULLIF(applied_date, ''), notes,
                    strftime('%Y-%m-%d %H:%M:%f', created_at) || '000',
                    strftime('%Y-%m-%d %H:%M:%f', updated_at) || '000'
                FROM jobs
                """
            )
        )
        connection.execute(text("DROP TABLE jobs"))
        connection.execute(text("ALTER TABLE jobs_legacy_migration RENAME TO jobs"))
        connection.execute(text("CREATE INDEX idx_jobs_status ON jobs(status)"))
        connection.execute(
            text("CREATE INDEX idx_jobs_applied_date ON jobs(applied_date DESC)")
        )


def seed_demo_data() -> int:
    engine = get_engine()
    with engine.connect() as connection:
        existing_count = connection.execute(select(func.count(jobs.c.id))).scalar_one()
    if existing_count:
        raise RuntimeError("The database already contains applications.")

    now = datetime.now(timezone.utc)
    today = date.today()
    rows = [
        {
            "company": "Northstar Labs",
            "role": "Senior Product Designer",
            "status": "Interview",
            "job_url": "https://example.com/jobs/northstar-product-designer",
            "salary": "$145k–$170k",
            "location": "Remote — US",
            "applied_date": today,
            "notes": "Portfolio review scheduled for next Tuesday.",
            "created_at": now,
            "updated_at": now,
        },
        {
            "company": "Cedar Health",
            "role": "Product Designer",
            "status": "Applied",
            "job_url": "https://example.com/jobs/cedar-product-designer",
            "salary": "$125k–$150k",
            "location": "Austin, TX",
            "applied_date": today,
            "notes": "Applied through the company careers page.",
            "created_at": now,
            "updated_at": now,
        },
        {
            "company": "Field Notes Co.",
            "role": "Design Lead",
            "status": "Saved",
            "job_url": "https://example.com/jobs/field-notes-design-lead",
            "salary": "$160k",
            "location": "New York, NY",
            "applied_date": None,
            "notes": "Ask Sam for a referral before applying.",
            "created_at": now,
            "updated_at": now,
        },
    ]

    with engine.begin() as connection:
        connection.execute(insert(jobs), rows)
    return len(rows)


def import_sqlite(path: str) -> int:
    """Import a local job-tracker SQLite file into the configured database."""
    engine = get_engine()
    with engine.connect() as connection:
        existing_count = connection.execute(select(func.count(jobs.c.id))).scalar_one()
    if existing_count:
        raise RuntimeError("The target database already contains applications.")

    from .repository import JobInput, create_job

    source = sqlite3.connect(path)
    source.row_factory = sqlite3.Row
    try:
        source_rows = source.execute("SELECT * FROM jobs ORDER BY id").fetchall()
        for row in source_rows:
            create_job(
                JobInput(
                    company=row["company"],
                    role=row["role"],
                    status=row["status"],
                    job_url=row["job_url"],
                    salary=row["salary"],
                    location=row["location"],
                    applied_date=row["applied_date"] or "",
                    notes=row["notes"],
                )
            )
    finally:
        source.close()
    return len(source_rows)


def register_commands(app: object) -> None:
    app.cli.add_command(_init_db_command)
    app.cli.add_command(_seed_demo_command)
    app.cli.add_command(_import_sqlite_command)
    app.cli.add_command(_hash_password_command)


@click.command("init-db")
@with_appcontext
def _init_db_command() -> None:
    """Create database tables if they do not already exist."""
    init_db()
    click.echo("Database initialized.")


@click.command("seed-demo")
@with_appcontext
def _seed_demo_command() -> None:
    """Add three fictional job applications to an empty database."""
    try:
        inserted = seed_demo_data()
    except RuntimeError as error:
        raise click.ClickException(str(error)) from error
    click.echo(f"Added {inserted} demo applications.")


@click.command("import-sqlite")
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@with_appcontext
def _import_sqlite_command(path: str) -> None:
    """Import local SQLite applications into the configured database."""
    try:
        imported = import_sqlite(path)
    except RuntimeError as error:
        raise click.ClickException(str(error)) from error
    click.echo(f"Imported {imported} applications from {path}.")


@click.command("hash-password")
def _hash_password_command() -> None:
    """Generate a master-password hash for JOB_TRACKER_PASSWORD_HASH."""
    import shlex

    from werkzeug.security import generate_password_hash

    password = click.prompt(
        "Master password", hide_input=True, confirmation_prompt=True
    )
    if len(password) < 12:
        raise click.ClickException(
            "Use at least 12 characters for the master password."
        )

    password_hash = generate_password_hash(password)
    click.echo("\nAdd this value to Vercel as JOB_TRACKER_PASSWORD_HASH:\n")
    click.echo(f"export JOB_TRACKER_PASSWORD_HASH={shlex.quote(password_hash)}")


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = "postgresql://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url

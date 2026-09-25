"""Portable database schema definitions."""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)

metadata = MetaData()

jobs = Table(
    "jobs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("company", String(120), nullable=False),
    Column("role", String(120), nullable=False),
    Column("status", String(20), nullable=False),
    Column("job_url", String(2000), nullable=False),
    Column("salary", String(80), nullable=False),
    Column("location", String(120), nullable=False),
    Column("applied_date", Date, nullable=True),
    Column("notes", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(
        "status IN ('Saved', 'Applied', 'Interview', 'Offer', 'Rejected')",
        name="ck_jobs_status",
    ),
    Index("idx_jobs_status", "status"),
    Index("idx_jobs_applied_date", "applied_date"),
)

login_attempts = Table(
    "login_attempts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("client_key", String(64), nullable=False),
    Column("attempted_at", DateTime(timezone=True), nullable=False),
    Index("idx_login_attempts_client_time", "client_key", "attempted_at"),
)

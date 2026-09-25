"""Persistence operations for job applications."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import RowMapping, delete, func, insert, select, update

from .db import get_engine
from .models import jobs

STATUSES = ("Saved", "Applied", "Interview", "Offer", "Rejected")


@dataclass(frozen=True, slots=True)
class JobInput:
    company: str
    role: str
    status: str
    job_url: str
    salary: str
    location: str
    applied_date: str
    notes: str


def list_jobs() -> list[RowMapping]:
    engine = get_engine()
    effective_date = func.coalesce(jobs.c.applied_date, func.date(jobs.c.created_at))
    with engine.connect() as connection:
        return (
            connection.execute(
                select(jobs).order_by(
                    effective_date.desc(), func.lower(jobs.c.company).asc()
                )
            )
            .mappings()
            .all()
        )


def get_job(job_id: int) -> RowMapping | None:
    engine = get_engine()
    with engine.connect() as connection:
        return (
            connection.execute(select(jobs).where(jobs.c.id == job_id))
            .mappings()
            .first()
        )


def status_counts() -> dict[str, int]:
    counts = {status: 0 for status in STATUSES}
    engine = get_engine()
    with engine.connect() as connection:
        rows = connection.execute(
            select(jobs.c.status, func.count(jobs.c.id)).group_by(jobs.c.status)
        ).all()
    for status, count in rows:
        counts[status] = count
    return counts


def create_job(values: JobInput) -> RowMapping:
    engine = get_engine()
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        result = connection.execute(
            insert(jobs).values(
                company=values.company,
                role=values.role,
                status=values.status,
                job_url=values.job_url,
                salary=values.salary,
                location=values.location,
                applied_date=_parse_date(values.applied_date),
                notes=values.notes,
                created_at=now,
                updated_at=now,
            )
        )
        job_id = result.inserted_primary_key[0]
    job = get_job(job_id)
    if job is None:
        raise RuntimeError("The job was created but could not be read back.")
    return job


def update_job(job_id: int, values: JobInput) -> RowMapping | None:
    engine = get_engine()
    with engine.begin() as connection:
        result = connection.execute(
            update(jobs)
            .where(jobs.c.id == job_id)
            .values(
                company=values.company,
                role=values.role,
                status=values.status,
                job_url=values.job_url,
                salary=values.salary,
                location=values.location,
                applied_date=_parse_date(values.applied_date),
                notes=values.notes,
                updated_at=datetime.now(timezone.utc),
            )
        )
        if result.rowcount == 0:
            return None
    return get_job(job_id)


def delete_job(job_id: int) -> bool:
    engine = get_engine()
    with engine.begin() as connection:
        result = connection.execute(delete(jobs).where(jobs.c.id == job_id))
        return result.rowcount > 0


def _parse_date(value: str) -> date | None:
    return date.fromisoformat(value) if value else None

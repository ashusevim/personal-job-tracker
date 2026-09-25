"""Validation for job application form input."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from urllib.parse import urlparse

from .repository import STATUSES, JobInput


@dataclass(frozen=True, slots=True)
class ValidatedJob:
    values: JobInput
    errors: dict[str, str]


def validate_job_form(form: Any) -> ValidatedJob:
    values = {
        "company": form.get("company", "").strip(),
        "role": form.get("role", "").strip(),
        "status": form.get("status", "").strip(),
        "job_url": form.get("job_url", "").strip(),
        "salary": form.get("salary", "").strip(),
        "location": form.get("location", "").strip(),
        "applied_date": form.get("applied_date", "").strip(),
        "notes": form.get("notes", "").strip(),
    }
    errors: dict[str, str] = {}

    _validate_required(values, "company", "Company", 120, errors)
    _validate_required(values, "role", "Role title", 120, errors)
    _validate_limit(values, "salary", "Salary", 80, errors)
    _validate_limit(values, "location", "Location", 120, errors)
    _validate_limit(values, "notes", "Notes", 5000, errors)
    _validate_limit(values, "job_url", "Job URL", 2000, errors)

    if values["status"] not in STATUSES:
        errors["status"] = "Choose a valid status."

    if values["job_url"] and not _is_http_url(values["job_url"]):
        errors["job_url"] = "Enter a complete URL beginning with http:// or https://."

    if values["applied_date"]:
        try:
            parsed_date = date.fromisoformat(values["applied_date"])
        except ValueError:
            errors["applied_date"] = "Enter a valid date in YYYY-MM-DD format."
        else:
            if parsed_date > date.today():
                errors["applied_date"] = "Applied date cannot be in the future."

    return ValidatedJob(JobInput(**values), errors)


def _validate_required(
    values: dict[str, str],
    field: str,
    label: str,
    maximum: int,
    errors: dict[str, str],
) -> None:
    if not values[field]:
        errors[field] = f"{label} is required."
    elif len(values[field]) > maximum:
        errors[field] = f"{label} must be {maximum} characters or fewer."


def _validate_limit(
    values: dict[str, str],
    field: str,
    label: str,
    maximum: int,
    errors: dict[str, str],
) -> None:
    if len(values[field]) > maximum:
        errors[field] = f"{label} must be {maximum} characters or fewer."


def _is_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

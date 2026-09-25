from werkzeug.datastructures import MultiDict

from job_tracker.validation import validate_job_form


def valid_form(**overrides) -> MultiDict:
    values = {
        "company": "Acme",
        "role": "Designer",
        "status": "Applied",
        "job_url": "https://example.com/job",
        "salary": "$120k",
        "location": "Remote",
        "applied_date": "2026-01-15",
        "notes": "Great team.",
    }
    values.update(overrides)
    return MultiDict(values)


def test_valid_form_returns_cleaned_values():
    result = validate_job_form(valid_form(company="  Acme  ", notes=" Great team. "))

    assert result.errors == {}
    assert result.values.company == "Acme"
    assert result.values.notes == "Great team."


def test_required_status_and_url_are_validated():
    result = validate_job_form(
        valid_form(company="", role="", status="Unknown", job_url="javascript:alert(1)")
    )

    assert "company" in result.errors
    assert "role" in result.errors
    assert "status" in result.errors
    assert "job_url" in result.errors


def test_future_and_malformed_dates_are_rejected():
    future = validate_job_form(valid_form(applied_date="2999-01-01"))
    malformed = validate_job_form(valid_form(applied_date="15/01/2026"))

    assert "applied_date" in future.errors
    assert "applied_date" in malformed.errors


def test_overlong_fields_are_rejected():
    result = validate_job_form(valid_form(company="A" * 121, notes="B" * 5001))

    assert "company" in result.errors
    assert "notes" in result.errors

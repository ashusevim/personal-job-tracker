from job_tracker.repository import (
    JobInput,
    create_job,
    delete_job,
    get_job,
    list_jobs,
    status_counts,
    update_job,
)


def sample_input(**overrides) -> JobInput:
    values = {
        "company": "Acme Inc",
        "role": "Product Designer",
        "status": "Applied",
        "job_url": "https://example.com/jobs/1",
        "salary": "$120k",
        "location": "Remote",
        "applied_date": "2026-01-15",
        "notes": "Referred by a friend.",
    }
    values.update(overrides)
    return JobInput(**values)


def test_create_get_list_and_count_job(app):
    with app.app_context():
        created = create_job(sample_input())

        assert created["id"] > 0
        assert get_job(created["id"])["company"] == "Acme Inc"
        assert [job["id"] for job in list_jobs()] == [created["id"]]
        assert status_counts()["Applied"] == 1


def test_update_and_delete_job(app):
    with app.app_context():
        created = create_job(sample_input())
        updated = update_job(
            created["id"],
            sample_input(status="Interview", applied_date="2026-02-20"),
        )

        assert updated["status"] == "Interview"
        assert str(updated["applied_date"]) == "2026-02-20"
        assert updated["updated_at"] >= created["updated_at"]

        assert delete_job(created["id"]) is True
        assert delete_job(created["id"]) is False
        assert get_job(created["id"]) is None


def test_jobs_are_sorted_by_newest_application_date(app):
    with app.app_context():
        older = create_job(sample_input(company="Zeta", applied_date="2026-01-01"))
        newer = create_job(sample_input(company="Alpha", applied_date="2026-02-01"))

        jobs = list_jobs()

        assert [job["id"] for job in jobs] == [newer["id"], older["id"]]

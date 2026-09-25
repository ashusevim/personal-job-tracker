import sqlite3
from pathlib import Path

from job_tracker.db import _normalize_database_url


def test_database_url_normalizes_to_psycopg_driver():
    assert (
        _normalize_database_url("postgresql://user:pass@host/db")
        == "postgresql+psycopg://user:pass@host/db"
    )
    assert (
        _normalize_database_url("postgres://user:pass@host/db")
        == "postgresql+psycopg://user:pass@host/db"
    )
    assert _normalize_database_url("sqlite:///jobs.db") == "sqlite:///jobs.db"


def test_legacy_sqlite_schema_is_migrated_on_startup(tmp_path):
    from job_tracker import create_app
    from job_tracker.repository import list_jobs

    database_path = tmp_path / "legacy-target.db"
    source = sqlite3.connect(database_path)
    source.executescript(
        """
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            role TEXT NOT NULL,
            status TEXT NOT NULL,
            job_url TEXT NOT NULL DEFAULT '',
            salary TEXT NOT NULL DEFAULT '',
            location TEXT NOT NULL DEFAULT '',
            applied_date TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX idx_jobs_status ON jobs(status);
        CREATE INDEX idx_jobs_applied_date ON jobs(applied_date DESC);
        """
    )
    source.executemany(
        """
        INSERT INTO jobs (
            company, role, status, job_url, salary, location,
            applied_date, notes, created_at, updated_at
        ) VALUES (?, ?, ?, '', '', '', ?, ?, ?, ?)
        """,
        [
            (
                "Legacy Co.",
                "Engineer",
                "Saved",
                "",
                "No date.",
                "2026-01-15T10:00:00+00:00",
                "2026-01-15T10:00:00+00:00",
            ),
            (
                "Applied Co.",
                "Designer",
                "Applied",
                "2026-01-16",
                "Has a date.",
                "2026-01-16T10:00:00+00:00",
                "2026-01-16T10:00:00+00:00",
            ),
        ],
    )
    source.commit()
    source.close()

    app = create_app(
        {
            "TESTING": True,
            "AUTH_ENABLED": False,
            "DATABASE_URL": f"sqlite:///{database_path}",
            "PASSWORD_HASH": "",
            "SECRET_KEY": "test-secret",
        }
    )

    with app.app_context():
        jobs = list_jobs()

    assert [job["company"] for job in jobs] == ["Applied Co.", "Legacy Co."]
    assert jobs[0]["applied_date"] is not None
    assert jobs[1]["applied_date"] is None


def test_vercel_fails_closed_without_required_secrets(monkeypatch, tmp_path):
    from job_tracker import create_app

    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("JOB_TRACKER_PASSWORD_HASH", raising=False)

    try:
        create_app({"DATABASE_URL": "", "SECRET_KEY": "", "PASSWORD_HASH": ""})
    except RuntimeError as error:
        assert "DATABASE_URL" in str(error)
    else:
        raise AssertionError("Expected a missing-secret error.")


def test_vercel_configuration_uses_secure_cookies_and_trusted_proxy(
    monkeypatch, tmp_path
):
    from werkzeug.security import generate_password_hash

    from job_tracker import create_app

    monkeypatch.setenv("VERCEL", "1")
    original_mkdir = Path.mkdir

    def reject_instance_writes(path, *args, **kwargs):
        if path.name == "instance":
            raise AssertionError("Vercel startup must not write to the instance path")
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", reject_instance_writes)
    app = create_app(
        {
            "DATABASE_URL": f"sqlite:///{tmp_path / 'vercel-test.db'}",
            "PASSWORD_HASH": generate_password_hash("deployment-master-password"),
            "SECRET_KEY": "vercel-test-secret",
        }
    )

    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["TRUST_PROXY"] is True
    assert app.test_client().get("/").status_code == 302


def test_import_sqlite_preserves_applications(app, tmp_path):
    from job_tracker.db import import_sqlite
    from job_tracker.repository import list_jobs

    source_path = tmp_path / "legacy.db"
    source = sqlite3.connect(source_path)
    source.execute(
        """
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            role TEXT NOT NULL,
            status TEXT NOT NULL,
            job_url TEXT NOT NULL DEFAULT '',
            salary TEXT NOT NULL DEFAULT '',
            location TEXT NOT NULL DEFAULT '',
            applied_date TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    source.execute(
        """
        INSERT INTO jobs (
            company, role, status, job_url, salary, location,
            applied_date, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "Legacy Co.",
            "Engineer",
            "Applied",
            "https://example.com/legacy",
            "$140k",
            "Remote",
            "2026-01-15",
            "Imported from SQLite.",
            "2026-01-15T10:00:00+00:00",
            "2026-01-15T10:00:00+00:00",
        ),
    )
    source.commit()
    source.close()

    with app.app_context():
        imported = import_sqlite(str(source_path))
        jobs = list_jobs()

    assert imported == 1
    assert jobs[0]["company"] == "Legacy Co."
    assert str(jobs[0]["applied_date"]) == "2026-01-15"

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from job_tracker import create_app
from job_tracker.auth import password_fingerprint

TEST_PASSWORD = "correct-horse-battery-staple"
TEST_PASSWORD_HASH = generate_password_hash(TEST_PASSWORD)


@pytest.fixture
def app(tmp_path: Path):
    return create_app(
        {
            "TESTING": True,
            "AUTH_ENABLED": True,
            "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}",
            "PASSWORD_HASH": TEST_PASSWORD_HASH,
            "SECRET_KEY": "test-secret",
            "SESSION_COOKIE_SECURE": False,
            "TRUST_PROXY": False,
        }
    )


@pytest.fixture
def client(app):
    test_client = app.test_client()
    with test_client.session_transaction() as session:
        session["authenticated"] = True
        session["auth_fingerprint"] = password_fingerprint(TEST_PASSWORD_HASH)
        session["csrf_token"] = "authenticated-test-token"
    return test_client


@pytest.fixture
def anonymous_client(app):
    return app.test_client()


def csrf_token(client) -> str:
    response = client.get("/login" if not is_authenticated(client) else "/jobs/new")
    match = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)
    assert match is not None
    return match.group(1).decode()


def is_authenticated(client) -> bool:
    with client.session_transaction() as session:
        return session.get("authenticated") is True

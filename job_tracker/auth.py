"""Master-password authentication and login throttling."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from flask import current_app
from sqlalchemy import delete, func, insert, select
from werkzeug.security import check_password_hash

from .db import get_engine
from .models import login_attempts


def is_authenticated() -> bool:
    if not current_app.config.get("AUTH_ENABLED"):
        return True
    from flask import session

    return session.get("authenticated") is True and session.get(
        "auth_fingerprint"
    ) == password_fingerprint(current_app.config.get("PASSWORD_HASH", ""))


def password_fingerprint(password_hash: str) -> str:
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()


def verify_master_password(password: str) -> bool:
    password_hash = current_app.config.get("PASSWORD_HASH", "")
    if not password_hash:
        return False
    return check_password_hash(password_hash, password)


def client_fingerprint(remote_address: str) -> str:
    return hashlib.sha256(remote_address.encode("utf-8")).hexdigest()


def retry_after_seconds(client_key: str) -> int:
    """Return remaining block time, or zero when another attempt is allowed."""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=current_app.config["LOGIN_WINDOW_MINUTES"])
    engine = get_engine()

    with engine.connect() as connection:
        attempts = connection.execute(
            select(func.count(login_attempts.c.id)).where(
                login_attempts.c.client_key == client_key,
                login_attempts.c.attempted_at >= window_start,
            )
        ).scalar_one()

    if attempts < current_app.config["LOGIN_MAX_ATTEMPTS"]:
        return 0

    block_minutes = current_app.config["LOGIN_BLOCK_MINUTES"]
    with engine.connect() as connection:
        newest = connection.execute(
            select(func.max(login_attempts.c.attempted_at)).where(
                login_attempts.c.client_key == client_key,
                login_attempts.c.attempted_at >= window_start,
            )
        ).scalar_one()

    if newest is None:
        return 0

    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=timezone.utc)
    retry_at = newest + timedelta(minutes=block_minutes)
    return max(1, int((retry_at - now).total_seconds()))


def record_failed_attempt(client_key: str) -> None:
    engine = get_engine()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=1)

    with engine.begin() as connection:
        connection.execute(
            delete(login_attempts).where(login_attempts.c.attempted_at < cutoff)
        )
        connection.execute(
            insert(login_attempts).values(client_key=client_key, attempted_at=now)
        )


def clear_failed_attempts(client_key: str) -> None:
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(
            delete(login_attempts).where(login_attempts.c.client_key == client_key)
        )

"""Application factory for the personal job tracker."""

from __future__ import annotations

import os
import secrets
from datetime import timedelta
from pathlib import Path

from flask import Flask, Response
from werkzeug.middleware.proxy_fix import ProxyFix

from . import db
from .errors import register_error_handlers
from .formatters import register_formatters
from .routes import bp


def create_app(test_config: dict | None = None) -> Flask:
    is_vercel = os.environ.get("VERCEL") == "1"
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DATABASE_URL=os.environ.get("DATABASE_URL", ""),
        PASSWORD_HASH=os.environ.get("JOB_TRACKER_PASSWORD_HASH", ""),
        SECRET_KEY=os.environ.get("SECRET_KEY", ""),
        LOGIN_BLOCK_MINUTES=15,
        LOGIN_MAX_ATTEMPTS=5,
        LOGIN_WINDOW_MINUTES=15,
        MAX_CONTENT_LENGTH=32 * 1024,
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_NAME="job_tracker_session",
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=is_vercel,
        TRUST_PROXY=is_vercel or _env_flag("TRUST_PROXY"),
    )

    if test_config:
        app.config.update(test_config)

    instance_path = Path(app.instance_path)
    if is_vercel:
        if not app.config.get("DATABASE_URL"):
            raise RuntimeError("DATABASE_URL is required on Vercel.")
        if not app.config.get("SECRET_KEY"):
            raise RuntimeError("SECRET_KEY is required on Vercel.")
    else:
        instance_path.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(instance_path, 0o700)
        if not app.config.get("DATABASE_URL"):
            app.config["DATABASE_URL"] = f"sqlite:///{instance_path / 'jobs.db'}"
        if not app.config.get("SECRET_KEY"):
            app.config["SECRET_KEY"] = _load_or_create_secret_key(str(instance_path))

    if not app.config.get("PASSWORD_HASH") and is_vercel:
        raise RuntimeError("JOB_TRACKER_PASSWORD_HASH is required on Vercel.")
    app.config.setdefault("AUTH_ENABLED", bool(app.config.get("PASSWORD_HASH")))

    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    app.register_blueprint(bp)
    register_formatters(app)
    db.register_commands(app)
    register_error_handlers(app)
    app.after_request(_set_security_headers)

    with app.app_context():
        db.init_db()

    return app


def _set_security_headers(response: Response) -> Response:
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self'; "
        "script-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'self'"
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    if os.environ.get("VERCEL") == "1":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    return response


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes"}


def _load_or_create_secret_key(instance_path: str) -> str:
    """Keep local sessions valid across restarts without committing a secret."""
    secret_path = Path(instance_path) / "secret_key"
    if secret_path.exists():
        return secret_path.read_text(encoding="utf-8").strip()

    try:
        descriptor = os.open(
            secret_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError:
        return secret_path.read_text(encoding="utf-8").strip()

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as secret_file:
            secret_file.write(secrets.token_hex(32))
    except BaseException:
        secret_path.unlink(missing_ok=True)
        raise

    return secret_path.read_text(encoding="utf-8").strip()

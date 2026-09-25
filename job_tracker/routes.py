"""HTML routes and authentication boundaries."""

from __future__ import annotations

import hmac
import secrets
from datetime import date
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import text

from .auth import (
    clear_failed_attempts,
    client_fingerprint,
    is_authenticated,
    password_fingerprint,
    record_failed_attempt,
    retry_after_seconds,
    verify_master_password,
)
from .db import get_engine
from .repository import (
    STATUSES,
    create_job,
    delete_job,
    get_job,
    list_jobs,
    status_counts,
    update_job,
)
from .validation import validate_job_form

bp = Blueprint("jobs", __name__)
PUBLIC_ENDPOINTS = {"jobs.login", "jobs.healthz"}


@bp.before_request
def protect_requests() -> None:
    if request.endpoint not in PUBLIC_ENDPOINTS and not is_authenticated():
        return redirect(url_for("jobs.login", next=_current_relative_url()))

    if request.endpoint != "jobs.healthz" and "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)

    if request.method == "POST":
        submitted_token = request.form.get("csrf_token", "")
        expected_token = session["csrf_token"]
        if not submitted_token or not hmac.compare_digest(
            submitted_token, expected_token
        ):
            abort(
                400,
                description="The form session expired. Go back, refresh, and try again.",
            )


@bp.context_processor
def inject_template_helpers() -> dict:
    return {
        "authenticated": is_authenticated(),
        "csrf_token": session.get("csrf_token", ""),
        "statuses": STATUSES,
        "today": date.today().isoformat(),
    }


@bp.route("/login", methods=["GET", "POST"])
def login():
    if is_authenticated():
        return redirect(url_for("jobs.index"))

    next_url = _safe_next(request.values.get("next", ""))
    if request.method == "POST":
        fingerprint = client_fingerprint(request.remote_addr or "unknown")
        retry_after = retry_after_seconds(fingerprint)
        if retry_after:
            response = render_template(
                "login.html",
                next_url=next_url,
                error=_retry_message(retry_after),
            )
            return response, 429, {"Retry-After": str(retry_after)}

        password = request.form.get("password", "")
        if len(password) <= 1024 and verify_master_password(password):
            clear_failed_attempts(fingerprint)
            session.clear()
            session["authenticated"] = True
            session["auth_fingerprint"] = password_fingerprint(
                current_app.config["PASSWORD_HASH"]
            )
            session["csrf_token"] = secrets.token_urlsafe(32)
            session.permanent = True
            return redirect(next_url)

        record_failed_attempt(fingerprint)
        return render_template(
            "login.html",
            next_url=next_url,
            error="The master password is incorrect.",
        ), 401

    return render_template("login.html", next_url=next_url, error=None)


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("jobs.login"))


@bp.get("/healthz")
def healthz():
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return jsonify({"status": "unhealthy"}), 503
    return jsonify({"status": "ok"})


@bp.get("/")
def index():
    jobs = list_jobs()
    counts = status_counts()
    counts["Total"] = len(jobs)
    requested_view = request.args.get("view", "list")
    view = requested_view if requested_view in {"list", "table"} else "list"
    return render_template("index.html", jobs=jobs, counts=counts, view=view)


@bp.route("/jobs/new", methods=["GET", "POST"])
def new_job():
    if request.method == "POST":
        validated = validate_job_form(request.form)
        if validated.errors:
            return render_template(
                "jobs/form.html",
                mode="new",
                job=None,
                form_values=request.form,
                errors=validated.errors,
            ), 422

        job = create_job(validated.values)
        flash(f"{job['company']} was added to your tracker.", "success")
        return redirect(url_for("jobs.index"))

    return render_template(
        "jobs/form.html", mode="new", job=None, form_values={}, errors={}
    )


@bp.route("/jobs/<int:job_id>/edit", methods=["GET", "POST"])
def edit_job(job_id: int):
    job = get_job(job_id)
    if job is None:
        abort(404)

    if request.method == "POST":
        validated = validate_job_form(request.form)
        if validated.errors:
            return render_template(
                "jobs/form.html",
                mode="edit",
                job=job,
                form_values=request.form,
                errors=validated.errors,
            ), 422

        update_job(job_id, validated.values)
        flash(f"{validated.values.company} was updated.", "success")
        return redirect(url_for("jobs.index"))

    return render_template(
        "jobs/form.html", mode="edit", job=job, form_values={}, errors={}
    )


@bp.post("/jobs/<int:job_id>/delete")
def remove_job(job_id: int):
    job = get_job(job_id)
    if job is None:
        abort(404)

    delete_job(job_id)
    flash(f"{job['company']} was removed.", "success")
    return redirect(url_for("jobs.index"))


def _current_relative_url() -> str:
    if not request.query_string:
        return request.path
    return f"{request.path}?{request.query_string.decode('utf-8')}"


def _safe_next(candidate: str) -> str:
    if not candidate:
        return url_for("jobs.index")
    parsed = urlsplit(candidate)
    if not candidate.startswith("/") or parsed.scheme or parsed.netloc:
        return url_for("jobs.index")
    return candidate


def _retry_message(retry_after: int) -> str:
    minutes = max(1, (retry_after + 59) // 60)
    suffix = "minute" if minutes == 1 else "minutes"
    return f"Too many attempts. Try again in {minutes} {suffix}."

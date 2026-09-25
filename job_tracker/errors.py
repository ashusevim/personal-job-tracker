"""User-facing HTTP error pages."""

from __future__ import annotations

from flask import Flask, render_template


def register_error_handlers(app: Flask) -> None:
    app.register_error_handler(400, _bad_request)
    app.register_error_handler(404, _not_found)
    app.register_error_handler(500, _server_error)


def _bad_request(error: object):
    message = str(getattr(error, "description", "The request could not be processed."))
    return render_template("error.html", code=400, message=message), 400


def _not_found(_error: object):
    return render_template(
        "error.html", code=404, message="That page could not be found."
    ), 404


def _server_error(_error: object):
    return render_template(
        "error.html",
        code=500,
        message="Something went wrong while loading this page.",
    ), 500

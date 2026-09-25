"""Jinja display filters."""

from __future__ import annotations

from datetime import date, datetime

from flask import Flask


def register_formatters(app: Flask) -> None:
    app.add_template_filter(_format_date, "display_date")


def _format_date(value: str | date | datetime | None) -> str:
    if not value:
        return "Not applied"
    if isinstance(value, (date, datetime)):
        parsed = value.date() if isinstance(value, datetime) else value
    else:
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            return value
    return f"{parsed.strftime('%b')} {parsed.day}, {parsed.year}"

"""WSGI entry point for Vercel and local WSGI servers."""

from job_tracker import create_app

app = create_app()

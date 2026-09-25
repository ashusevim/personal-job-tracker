# Job Tracker

A private, single-user job application tracker. It runs locally with SQLite and on Vercel with Neon Postgres. The deployed app is protected by one master password.

## Features

- Add, edit, and delete applications
- Track status: Saved, Applied, Interview, Offer, or Rejected
- Record company, role, URL, salary, location, application date, and notes
- Status totals plus list and compact table views
- Password-only login with server-side hash verification
- Persistent 30-day sessions, CSRF protection, and login throttling
- Responsive, keyboard-accessible interface
- Portable SQLAlchemy data layer for SQLite and PostgreSQL

## Local setup

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
flask --app job_tracker hash-password
```

The password command prompts without echoing and prints an export line. Put the generated hash in `.env`:

```dotenv
JOB_TRACKER_PASSWORD_HASH=scrypt:32768:8:1$...
```

`.env` is ignored by Git. Then run:

```bash
flask --app job_tracker run --debug
```

Open <http://127.0.0.1:5000>. Local data is stored in `instance/jobs.db`; the session signing key is stored in `instance/secret_key`.

If `JOB_TRACKER_PASSWORD_HASH` is not set, authentication is disabled for local development only. Vercel refuses to start without it.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

## Deploy to Vercel with Neon

Vercel functions do not provide a persistent local filesystem. Production therefore uses Neon Postgres rather than SQLite.

### 1. Install the Vercel CLI and link the project

```bash
npm install -g vercel
vercel link
```

### 2. Provision Neon

Use the current Neon integration from the Vercel Marketplace. The CLI equivalent is:

```bash
vercel install neon
```

Select a region close to you and connect the database to the Production and Preview environments. Neon injects `DATABASE_URL` into Vercel. Enable Preview Branching so preview deployments receive isolated database copies.

### 3. Generate the authentication secrets

Generate a password hash locally. The prompt is hidden:

```bash
.venv/bin/flask --app job_tracker hash-password
```

Generate a long session signing key:

```bash
.venv/bin/python -c "import secrets; print(secrets.token_hex(32))"
```

Add both values to Vercel. The password command prints the exact `JOB_TRACKER_PASSWORD_HASH` export value:

```bash
vercel env add JOB_TRACKER_PASSWORD_HASH production
vercel env add SECRET_KEY production
```

Required environment variables:

| Variable | Source | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | Neon integration | Pooled PostgreSQL connection string |
| `JOB_TRACKER_PASSWORD_HASH` | Your secret | Werkzeug password hash; plaintext is never stored |
| `SECRET_KEY` | Your secret | Signs session cookies |

### 4. Import existing local data

Skip this step if the local tracker is empty. The import refuses to run unless the target database is empty, preventing accidental duplication.

```bash
vercel env pull .env.local --environment=production
set -a
source .env.local
set +a
.venv/bin/flask --app job_tracker import-sqlite instance/jobs.db
```

### 5. Deploy

```bash
vercel --prod
```

`vercel.json` points Vercel to `main:app`. The application creates missing database tables when the production function cold-starts, so no database credentials are needed during Vercel's build step. The public health endpoint is `/healthz`.

## Change the master password

1. Run `flask --app job_tracker hash-password` and enter the new password.
2. Update `JOB_TRACKER_PASSWORD_HASH` in Vercel.
3. Redeploy.

Changing the hash invalidates every existing session immediately.

## Backups

For local SQLite data, stop the server and copy `instance/jobs.db` somewhere outside the project.

For production, use Neon point-in-time recovery and the retention settings configured for the Vercel-managed database.

## Security notes

- Passwords are verified against a scrypt hash supplied through an environment secret.
- Failed attempts are throttled per client address: five attempts in 15 minutes triggers a 15-minute block.
- Sessions use `HttpOnly`, `SameSite=Lax`, and `Secure` cookies on Vercel.
- The app sends HSTS, CSP, clickjacking, MIME-sniffing, and referrer headers.
- Authentication is password-only because this is deliberately a single-user application.
- Never put the master password or generated secrets in source control, logs, or screenshots.

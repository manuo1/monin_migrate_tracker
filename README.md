# MoninMigrateTracker (MMT)

Internal web tool to follow the migration of an application to a new version delivered by a vendor.
Testers report **feedbacks** (bug, successful test, suggestion) about a page of the migrated application.
The maintainer triages them, groups them, and links them to the **vendor tickets** (Jira) that track the fixes.

> Code and documentation are in English, the end-user interface is in French (default) and English.

## Features

- Feedbacks: create (with drag & drop / paste of attachments), copy, duplicate detection, comments, full history timeline.
- Staff triage: status, closure reason, links to vendor tickets, protected against concurrent edits (optimistic locking).
- Retest: the author of a feedback answers OK / KO when a retest is requested.
- Vendor tickets: list, detail, creation from a feedback (pre-filled title and description), association, link to Jira.
- Page / tab reference lists (suggestions on inputs, free entry allowed), imported from CSV in the admin.
- Security: login throttling, strict Content Security Policy, attachments served only to authenticated users.
- Interface in French and English (FR / EN switch in the navigation bar).
- Operations: Docker (app + PostgreSQL), structured JSON logs, backup and restore scripts.

## Stack

Python 3.13, Django 5.2, PostgreSQL (SQLite in development), gunicorn + WhiteNoise, Bootstrap and Tom Select
(served locally, no CDN), pytest + Playwright, ruff, pre-commit, GitHub Actions.

## Quick start (development)

```bash
python -m venv .venv
source .venv/Scripts/activate        # Git Bash. PowerShell: .venv\Scripts\activate. Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
pre-commit install
cp .env.example .env                 # then edit the values
python manage.py migrate
python manage.py compilemessages     # translations; needs the GNU gettext tools (see docs/development.md)
python manage.py createsuperuser
python manage.py runserver
```

Then open http://localhost:8000/. Users are created in the admin (`/admin/`); staff members triage, other users
report and answer retests.

## Common commands

```bash
pytest                               # unit and integration tests (hermetic, no .env needed; run compilemessages first)
playwright install chromium          # once, for the browser tests
pytest -m e2e                        # browser journeys (add --headed --slowmo 700 to watch)
ruff check .
ruff format .
```

More in [docs/development.md](docs/development.md).

## Configuration

Every private value (secret key, database, Jira URLs and reference prefix, media path) comes from environment
variables. See [`.env.example`](.env.example) for the full list. This repository is public: never commit real values,
data or screenshots.

## Documentation

- [docs/deployment.md](docs/deployment.md): run it with Docker, reverse proxy, updates, backup and restore.
- [docs/architecture.md](docs/architecture.md): code layers, business rules, permissions, design decisions.
- [docs/development.md](docs/development.md): tests, linting, CI, known pitfalls.

## Project layout

```
config/            Django project (settings: base, dev, prod, test)
tracker/           the application (models, rules, services, history, statuses, views, templates, static)
locale/            translations (fr, en): .po files versioned, .mo compiled locally
tests/             unit and integration tests; tests/e2e for the browser journeys
scripts/           backup.sh and restore.sh
docs/              deployment, architecture and development guides
Dockerfile, docker-compose.yml
```

## License

[MIT](LICENSE).

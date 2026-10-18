# MoninMigrateTracker (MMT)

Internal tool to follow the migration of an application to a new vendor version: testers report feedbacks
(bugs, successful tests, suggestions), the maintainer triages them and links them to the vendor's Jira tickets.

> Work in progress. Project notes (context, business rules, decisions, state, backlog) are kept locally by the maintainer and are not published.

## Quick start (development)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
pre-commit install
copy .env.example .env   # then edit the values
```

The Django project, test and run commands are added as the skeleton progresses.

## Configuration

All private values (secret key, database, Jira URLs and reference prefix, media path) come from environment variables.
See [`.env.example`](.env.example). This repository is public: never commit real values, data or screenshots.

## License

To be decided.

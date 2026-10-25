# Development

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate        # Git Bash. PowerShell: .venv\Scripts\activate. Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
pre-commit install
cp .env.example .env                 # then edit the values
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver           # development settings, reads .env
```

## Conventions

- Code, comments, commit messages and documentation in English. The end-user interface is available in French (default)
  and English: see [Translations](#translations).
- Commit messages use a prefix: `feat:`, `fix:`, `test:`, `docs:`, `chore:`.
- Style and lint with ruff (line length 120). `pre-commit` runs it, plus whitespace fixers and gitleaks.
- One small vertical slice at a time: failing test, code, green tests, commit. No business behaviour change while
  refactoring. New behaviour is written test first.
- The repository is public: no real data, names, URLs or secrets in code, tests, fixtures, screenshots or docs. Test
  data is fake. See `.env.example` for what goes in the environment.

## Tests

```bash
pytest                               # unit and integration tests, e2e excluded
pytest -m e2e                        # browser journeys (Playwright)
playwright install chromium          # once, before the first e2e run
pytest -m e2e --headed --slowmo 700  # watch a journey
```

- Test settings (`config.settings.test`) are hermetic: they never read `.env`, and force fake Jira values even if your
  shell exports real ones. The database is in-memory SQLite unless `DATABASE_URL` is set (CI sets PostgreSQL).
- Layout: `tests/tracker/` for the application (rules, services, models, history, views, permission matrix, admin,
  CSP, error pages), `tests/test_*.py` for project-level checks (production settings, logging, login throttling), and
  `tests/e2e/` for the browser journeys (login and creation, staff triage, retest answer, vendor ticket creation,
  language switch).
- `tests/tracker/test_query_counts.py` guards against N+1 queries: the query count of the main pages must not grow
  with the number of rows.
- `tests/test_prod_settings.py` loads the production settings in a clean subprocess to pin their security-relevant
  values.
- A browser journey must not trigger any Content Security Policy console message (an autouse fixture fails it).

## Translations

The interface exists in French (default) and English, switched with the FR / EN buttons in the navigation bar (Django
i18n, choice kept in a cookie; the browser's `Accept-Language` is ignored on purpose).

- Source strings (msgids) are in English in the code and templates (`gettext`, `gettext_lazy`, `{% translate %}`).
  The French text lives in `locale/fr/LC_MESSAGES/django.po`; `locale/en/` maps each msgid to itself.
- `.po` files are versioned, compiled `.mo` files are git-ignored. After editing a `.po` file, run
  `python manage.py compilemessages` before `pytest`, otherwise new strings show up untranslated. This needs the GNU
  gettext tools (`msgfmt`): on Windows `winget install -e --id mlocati.GetText` (open a new terminal afterwards), on
  Debian/Ubuntu `apt-get install gettext`. CI and the Docker build install gettext and compile the messages.
- When adding a user-visible string: write it in English, add the msgid to both catalogues (the `fr` entry must be
  translated), compile, run the tests. `tests/test_catalogues.py` fails on an empty `msgstr` or on a msgid present in
  only one catalogue.
- Texts that are not translated, on purpose: what users write (descriptions, comments, vendor ticket fields), the
  history events stored in the database (English only, identical for everyone, see `history.py`), the description
  built for Jira, and the words "Monin" and "Aptean".
- Strings needed by static JavaScript go through data attributes rendered by `_js_strings.html`: no accented text in
  `static/tracker/*.js`.
- `makemigrations` runs with translations deactivated, so lazy `verbose_name` values are serialized as their English
  msgid.

## Checks before pushing

```bash
pytest
ruff check .
ruff format .
# production check, needs SECRET_KEY and ALLOWED_HOSTS in the environment:
python manage.py check --deploy --settings=config.settings.prod --fail-level WARNING
```

If a pre-commit hook modifies files (for example the end-of-file fixer), `git add` again and recommit.

## Continuous integration

`.github/workflows/ci.yml` runs five jobs on every push to `main` and on pull requests:

- `lint`: `ruff check` and `ruff format --check`.
- `test`: `compilemessages` then `pytest` on PostgreSQL.
- `e2e`: `compilemessages` then Playwright journeys on PostgreSQL.
- `deploy-check`: `check --deploy --fail-level WARNING`. A new third-party app can add warnings that fail this job:
  fix them, or silence them on purpose with a comment.
- `secrets`: gitleaks on the full history.

Look at the whole Actions history after a push, not only the latest run: a red job stays red on the following commits
until its cause is fixed.

## Known pitfalls

- `DJANGO_SETTINGS_MODULE` is not read from `.env`. `manage.py` defaults to `config.settings.dev`, pytest to
  `config.settings.test`, wsgi and asgi to `config.settings.prod`.
- After pulling a migration, run `python manage.py migrate`.
- SQLite and PostgreSQL differ (case sensitivity, accent collation, no row locks on SQLite): CI runs on PostgreSQL.
- Excel saves CSV files as cp1252, not UTF-8. The admin import handles UTF-8 and cp1252, refuses `.xlsx` files with
  a message, and detects UTF-16 by its byte order mark.
- With django-axes, `client.login()` fails in tests (there is no request): use `force_login`. A locked account answers
  HTTP 429.
- Any new `URLField` in a form needs `assume_scheme="https"` (silences a Django 6 deprecation warning).
- Browser tests: the Playwright sync API needs `DJANGO_ALLOW_ASYNC_UNSAFE=true` to touch the ORM (set in
  `tests/e2e/conftest.py`). A `click()` that navigates only waits for the navigation to start: call
  `page.wait_for_load_state()` before typing into a field driven by JavaScript.
- Vendored front-end files (`tracker/static/vendor/`) must end with a newline, otherwise the end-of-file hook rewrites
  them at commit time.
- Git Bash on Windows rewrites paths such as `/data/media` passed to `docker` commands: the scripts in `scripts/`
  set `MSYS_NO_PATHCONV=1`, do the same when you type such commands by hand.

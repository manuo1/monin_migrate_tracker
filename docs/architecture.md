# Architecture

## Domain

- **Feedback**: a report from a tester about a page and tab of the migrated application. Type: `bug`, `test_passed` or
  `suggestion`. The text written by the tester is authoritative and read-only; corrections go in comments.
- **VendorTicket**: a ticket on the vendor's side (Jira). Its reference (`ref`) is nullable and unique. One vendor
  ticket may cover several feedbacks, and a feedback may be linked to several vendor tickets.
- **Page / Tab**: reference lists used as suggestions on inputs. The fields on feedbacks and tickets stay free text.
- **Attachment**, **Comment**: attached to a feedback.
- **FeedbackEvent**, **VendorTicketEvent**, **StatusChange**: the history. The first status change row is the creation.

Feedback statuses (display order = list order): `new`, `in_analysis`, `to_replay_with_user`, `sent_to_vendor`,
`retest_staff`, `retest_user`, `test_failed`, `test_passed` (final), `closed` (final). Closure reasons: `fixed`,
`not_reproduced`, `product_evolution`, `rejected`.

Vendor ticket statuses: `in_progress`, `to_test`, `closed`, `blocked`, or empty.

## Code layers

All the application code is in the `tracker` package.

- `statuses.py`, `choices.py`: status definitions (code, label, colour, category) and choices, as code, not as database
  tables.
- `rules.py`: pure functions that **decide** state changes. They never write to the database.
- `services.py`: applies the decisions inside transactions. It writes only through `history`.
- `history.py`: the only module allowed to write history rows.
- `models.py`: data model.
- `forms.py`, `views/`, `templates/`, `static/`: the web layer. Views are thin and check permissions.
- `timeline.py`: builds the merged history shown on a feedback page.
- `admin.py`: Django admin with the reference-list CSV import and the "out of reference" filter.
- `middleware.py`: Content Security Policy header. `logs.py`: JSON log formatter.
  `context_processors.py`: reference lists for the inputs.

The rule behind this split: a decision can be tested without a database (`rules`), a change always goes through one
transaction (`services`), and the history cannot be bypassed (`history`).

## Business rules

Only two behaviours are automatic. Everything else is manual by design: the maintainer follows the vendor's Jira and
judges case by case.

- **T1, transmission**: when a vendor ticket is added to a feedback in status `new`, the feedback becomes
  `sent_to_vendor`. It holds whatever the way the link is made (creation from a feedback, association, triage). A status
  explicitly chosen by staff during triage is respected.
- **T2, retest answer**: on a feedback in `retest_user`, its author (or staff) can answer. OK moves it to
  `test_passed` with the closure reason `fixed` (comment optional). KO moves it to `test_failed` (comment mandatory).
  This is the only way for a non-staff user to change a status. Moving a feedback to `retest_user` is manual (triage).

Earlier automatic rules (automatic closing, status propagation from the vendor ticket, mandatory reasons) were tried
and dropped.

## Permissions

Four levels: anonymous, logged-in user, author of the feedback, staff.

- Anonymous: login page only.
- Logged-in user: list and read feedbacks (a non-staff user's list defaults to their own feedbacks, the author filter
  can widen it), create or copy a feedback, comment, read vendor tickets.
- Author (or staff): add attachments to the feedback, answer a retest request.
- Staff only: edit a feedback, triage, remove an attachment, create, edit and associate vendor tickets, see the Jira
  link on the vendor ticket list.
- Django admin: staff accounts with the right model permissions. It is an emergency and reference-data tool and is not
  traced in the history.

Attachments have no public URL: an authenticated view serves them (a whitelist of types is displayed inline, anything
else is forced to download).

## Design decisions

- Copying a feedback copies its fields and its attachments (by reference), not its comments or history.
- Attachments are never deleted from disk: this keeps the history and avoids duplicating files on copy.
- A feedback with the same page, tab and description as an existing one is refused, with a link to the existing one.
- Creating a vendor ticket from a feedback pre-fills the title and description (Jira format) and requires the Jira
  reference. The Jira link is always rebuilt from the configured base URL and the reference.
- Triage uses optimistic locking: a token derived from the status, closure reason and linked tickets is checked under a
  row lock, and a stale form gets an HTTP 409 with its typed explanation kept. The other forms are not locked.
- Static JavaScript only: no inline script or event handler, which allows a strict `script-src 'self'` policy.
  Bootstrap and Tom Select are vendored under `tracker/static/vendor/` (see its README for versions and upgrade steps).
- Storage goes through Django `STORAGES`, so moving attachments to object storage later is a configuration change.
- Not built on purpose: notifications (staff communicates with users directly), dashboards, status age, pagination
  (the expected volume is around 1000 feedbacks), attachment size or type limits.

## Configuration and environments

- `config/settings/base.py`: shared settings, read from environment variables (`django-environ`).
- `dev.py`: local development (`manage.py` default). `test.py`: hermetic tests (`pytest` default).
  `prod.py`: production (`wsgi`/`asgi` default): secure cookies, HTTPS redirect, HSTS, WhiteNoise, JSON logs.
- `DJANGO_SETTINGS_MODULE` is not read from `.env`: it is too late for that.
- SQLite in development, PostgreSQL in production and in CI.

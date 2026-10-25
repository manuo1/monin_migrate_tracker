# Deployment

MMT runs as two containers started by `docker-compose.yml`:

- `db`: PostgreSQL 16, data in the named volume `pgdata`.
- `web`: the Django app served by gunicorn (3 workers), static files served by WhiteNoise, attachments in the named
  volume `media` (mounted on `/data/media`). Migrations are applied at each start.

The `web` port is published on `127.0.0.1:8000` only. TLS is **not** handled by the stack: put a reverse proxy in
front of it (see below).

## Requirements

- Docker with the Compose plugin (`docker compose version`).
- A reverse proxy terminating HTTPS (nginx, Caddy, Apache, the company's load balancer...).
- A public host name for the application.

## 1. Configuration

Copy the template and edit it. The `.env` file is read by Compose; it must stay out of git and be readable only by
the account that runs Docker.

```bash
cp .env.example .env
```

Values to set for a real deployment:

- `SECRET_KEY`: long random string. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(60))"`.
- `ALLOWED_HOSTS`: the public host name, e.g. `mmt.example.com`. The app refuses to start without it.
- `CSRF_TRUSTED_ORIGINS`: the public origin with scheme, e.g. `https://mmt.example.com`.
- `BEHIND_PROXY=True`: trust the `X-Forwarded-Proto` header sent by the reverse proxy. Only enable it when a trusted
  proxy really sets it (and the container port is not reachable from elsewhere).
- `POSTGRES_PASSWORD`: letters and digits only, because it is embedded in a database URL.
- `JIRA_BASE_URL`, `JIRA_CREATE_FORM_URL`, `JIRA_REF_PREFIX`: the vendor Jira values.

Optional values:

- `AXES_FAILURE_LIMIT` (default 5) and `AXES_COOLOFF_MINUTES` (default 15): login lockout per user name.
- `LOG_FORMAT` (`json` by default in the container, or `plain`) and `LOG_LEVEL` (default `INFO`).
- `SECURE_SSL_REDIRECT` (default `True`) and `SECURE_HSTS_SECONDS` (default one year).

`DEBUG` and `DATABASE_URL` in `.env` are ignored by the container: production settings force `DEBUG=False`, and
`docker-compose.yml` builds the database URL from `POSTGRES_PASSWORD`.

HSTS tells browsers to refuse plain HTTP on the host name for the given duration. When testing a new host name, start
with a short value (e.g. `SECURE_HSTS_SECONDS=300`) and raise it once everything works.

Testing over plain HTTP on `localhost` only: set `SECURE_SSL_REDIRECT=False` and `SECURE_HSTS_SECONDS=0`. Never do
this on a real deployment.

## 2. First start

```bash
docker compose up --build -d
docker compose logs --no-color web | tail -30
docker compose exec web python manage.py createsuperuser
```

Check that static files are served and that the login page works. Then create the users in the admin
(`/admin/`) and, optionally, import the page and tab reference lists there (CSV, first column).

## 3. Reverse proxy

The proxy forwards to `127.0.0.1:8000`, sets `X-Forwarded-Proto` and must allow the size of the attachments.
Example for nginx (adapt the host name and certificate paths):

```nginx
server {
    listen 443 ssl;
    server_name mmt.example.com;
    ssl_certificate     /etc/ssl/certs/mmt.pem;
    ssl_certificate_key /etc/ssl/private/mmt.key;

    client_max_body_size 50m;   # nginx default is 1m: attachments would be refused

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
}
```

Also redirect port 80 to 443 at the proxy.

## 4. Updating

Make a backup first (section 5), then:

```bash
git pull
docker compose up --build -d
docker compose logs --no-color web | tail -30
```

Migrations run automatically when the `web` container starts. The `pgdata` and `media` volumes are kept.

## 5. Backup and restore

What must be saved: the database and the attachments (the `media` volume). The scripts do both.

```bash
bash scripts/backup.sh                       # into ./backups, keeps 30 days
bash scripts/backup.sh /var/backups/mmt 60   # custom folder and retention (0 = keep everything)
```

Each run produces `mmt-db-<date>.dump` (PostgreSQL custom format) and `mmt-media-<date>.tar.gz`. Files are written
under a temporary name and renamed at the end, so a failed run never leaves a truncated backup that looks valid.

Restore (destructive: replaces the database and the attachments, asks for confirmation, stops `web` during the
operation):

```bash
bash scripts/restore.sh backups/mmt-db-<date>.dump backups/mmt-media-<date>.tar.gz
```

Recommendations:

- Schedule the backup, for example with cron: `0 2 * * * cd /path/to/monin_migrate_tracker && bash scripts/backup.sh /var/backups/mmt 30`.
- Copy the backups to another machine or storage: a backup on the same disk does not survive a disk failure.
- The backups contain real data and attachments: restrict access to them.
- Test a restore on a spare machine from time to time. A backup that was never restored is not proven.

## 6. Operations

- Logs go to stdout, one JSON object per line: `docker compose logs --no-color web`.
- Restart: `docker compose restart web`. Stop everything: `docker compose down` (volumes are kept; `down -v` would
  delete the data).
- The Django admin (`/admin/`) is an emergency and reference-data tool. Its changes are deliberately not traced in
  the feedback history.

## Security notes

- Login is throttled per user name: after too many failures the account is locked for a while. Someone can therefore
  lock a given account temporarily; the cost was accepted because the client IP is unreliable behind a proxy.
- Attachments have no public URL: they are served by an authenticated view.
- The app sends a strict Content Security Policy on every page except `/admin/`.
- Session, CSRF and language cookies are `Secure`, so the application must be reached over HTTPS (the proxy provides it).
- The interface language (French by default, English on request) is stored in a cookie; the browser's language is
  ignored on purpose.

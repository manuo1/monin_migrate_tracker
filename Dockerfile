FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    DJANGO_READ_DOT_ENV_FILE=False \
    MEDIA_ROOT=/data/media

RUN useradd --system --create-home --uid 1000 app \
    && mkdir -p /data/media \
    && chown app:app /data/media

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app . .

# Throwaway values: collectstatic and compilemessages only need settings to import, nothing is stored in the image.
# gettext is needed only to compile the .mo files (git-ignored): installed then removed in the same layer.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gettext \
    && SECRET_KEY=build-only ALLOWED_HOSTS=build-only python manage.py compilemessages \
    && apt-get purge -y --auto-remove gettext \
    && rm -rf /var/lib/apt/lists/*

RUN SECRET_KEY=build-only ALLOWED_HOSTS=build-only python manage.py collectstatic --noinput \
    && chown -R app:app /app/staticfiles

USER app

EXPOSE 8000

# Single replica: running migrations at start is safe here.
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile -"]

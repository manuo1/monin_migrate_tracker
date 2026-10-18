import os

# Hermetic test settings: never read a local .env, never depend on private values.
os.environ["DJANGO_READ_DOT_ENV_FILE"] = "False"
os.environ.setdefault("SECRET_KEY", "test-only-not-a-secret")
os.environ.setdefault("JIRA_BASE_URL", "https://jira.example.com/browse/")
os.environ.setdefault("JIRA_CREATE_FORM_URL", "https://jira.example.com/form/00000000")
os.environ.setdefault("JIRA_REF_PREFIX", "TEST-")
# CI sets DATABASE_URL to PostgreSQL; locally the default is in-memory SQLite.
os.environ.setdefault("DATABASE_URL", "sqlite://:memory:")

from .base import *

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

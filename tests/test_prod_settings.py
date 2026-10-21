"""Characterization of the production settings, loaded in a clean subprocess
(hermetic: no .env, no inherited values)."""

import json
import os
import subprocess  # noqa: S404
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SETTING_NAMES = [
    "DEBUG",
    "SECURE_SSL_REDIRECT",
    "SESSION_COOKIE_SECURE",
    "SESSION_COOKIE_HTTPONLY",
    "SESSION_COOKIE_SAMESITE",
    "CSRF_COOKIE_SECURE",
    "SECURE_HSTS_SECONDS",
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    "SECURE_HSTS_PRELOAD",
    "SECURE_CONTENT_TYPE_NOSNIFF",
    "SECURE_PROXY_SSL_HEADER",
    "LOGGING",
]

# Variables a developer shell may already export: always cleared before each run.
CLEARED_ENV = [
    "BEHIND_PROXY",
    "SECURE_SSL_REDIRECT",
    "SECURE_HSTS_SECONDS",
    "ALLOWED_HOSTS",
    "DEBUG",
    "LOG_FORMAT",
    "LOG_LEVEL",
]


def load_prod_settings(**env_overrides):
    env = {k: v for k, v in os.environ.items() if k not in CLEARED_ENV}
    env.update(
        DJANGO_SETTINGS_MODULE="config.settings.prod",
        DJANGO_READ_DOT_ENV_FILE="False",
        SECRET_KEY="prod-settings-test-not-a-secret",
        ALLOWED_HOSTS="example.com",
    )
    env.update(env_overrides)
    code = (
        "import json; from django.conf import settings; "
        f"print(json.dumps({{n: getattr(settings, n) for n in {SETTING_NAMES!r}}}))"
    )
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], env=env, cwd=BASE_DIR, capture_output=True, text=True, check=False
    )


def test_prod_defaults_are_secure():
    result = load_prod_settings()
    assert result.returncode == 0, result.stderr
    s = json.loads(result.stdout)
    assert s["DEBUG"] is False
    assert s["SECURE_SSL_REDIRECT"] is True
    assert s["SESSION_COOKIE_SECURE"] is True
    assert s["SESSION_COOKIE_HTTPONLY"] is True
    assert s["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert s["CSRF_COOKIE_SECURE"] is True
    assert s["SECURE_HSTS_SECONDS"] == 31536000
    assert s["SECURE_HSTS_INCLUDE_SUBDOMAINS"] is True
    assert s["SECURE_HSTS_PRELOAD"] is False
    assert s["SECURE_CONTENT_TYPE_NOSNIFF"] is True


def test_prod_trusts_no_proxy_header_by_default():
    s = json.loads(load_prod_settings().stdout)
    assert s["SECURE_PROXY_SSL_HEADER"] is None


def test_prod_trusts_forwarded_proto_only_behind_proxy():
    s = json.loads(load_prod_settings(BEHIND_PROXY="True").stdout)
    assert s["SECURE_PROXY_SSL_HEADER"] == ["HTTP_X_FORWARDED_PROTO", "https"]


def test_prod_hsts_and_redirect_can_be_tuned_by_env():
    s = json.loads(load_prod_settings(SECURE_HSTS_SECONDS="300", SECURE_SSL_REDIRECT="False").stdout)
    assert s["SECURE_HSTS_SECONDS"] == 300
    assert s["SECURE_SSL_REDIRECT"] is False


def test_prod_refuses_to_start_without_allowed_hosts():
    result = load_prod_settings(ALLOWED_HOSTS="")
    assert result.returncode != 0
    assert "ALLOWED_HOSTS must be set in production" in result.stderr


def test_prod_logs_json_to_stdout_at_info_by_default():
    logging_config = json.loads(load_prod_settings().stdout)["LOGGING"]
    assert logging_config["handlers"]["console"]["formatter"] == "json"
    assert logging_config["root"]["level"] == "INFO"
    assert logging_config["root"]["handlers"] == ["console"]


def test_prod_log_format_and_level_can_be_tuned_by_env():
    logging_config = json.loads(load_prod_settings(LOG_FORMAT="plain", LOG_LEVEL="warning").stdout)["LOGGING"]
    assert logging_config["handlers"]["console"]["formatter"] == "plain"
    assert logging_config["root"]["level"] == "WARNING"


def test_an_unknown_log_format_is_refused():
    result = load_prod_settings(LOG_FORMAT="xml")
    assert result.returncode != 0
    assert "LOG_FORMAT must be" in result.stderr

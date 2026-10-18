import pytest
from django.conf import settings
from django.core.management import call_command


def test_system_check_passes():
    call_command("check")


@pytest.mark.django_db
def test_no_missing_migrations():
    call_command("makemigrations", "--check", "--dry-run")


def test_test_settings_are_hermetic():
    assert settings.DEBUG is False
    assert settings.JIRA_REF_PREFIX == "TEST-"

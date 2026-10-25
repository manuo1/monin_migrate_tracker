import pytest
from django.utils import translation


@pytest.fixture(autouse=True)
def _isolated_media_root(settings, tmp_path):
    """Uploaded test files go to a throwaway folder, never to the real MEDIA_ROOT."""
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture(autouse=True)
def _default_language(settings):
    """LocaleMiddleware leaves the last request's language active in the thread: start and end every test in the
    default language so that a test switching to another language cannot leak into the next ones."""
    translation.activate(settings.LANGUAGE_CODE)
    yield
    translation.activate(settings.LANGUAGE_CODE)

import pytest


@pytest.fixture(autouse=True)
def _isolated_media_root(settings, tmp_path):
    """Uploaded test files go to a throwaway folder, never to the real MEDIA_ROOT."""
    settings.MEDIA_ROOT = tmp_path

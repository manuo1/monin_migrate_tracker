import re
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

STATIC_JS = Path(settings.BASE_DIR) / "tracker" / "static" / "tracker"
BLOCK = re.compile(r'<div id="js-strings".*?></div>', re.S)
ATTRIBUTE = re.compile(r'(data-[a-z-]+)="([^"]*)"')
# Same word in both languages.
SAME_IN_BOTH = {"data-label-default"}


def js_strings(client, language):
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = language
    content = client.get(reverse("login")).content.decode()
    return dict(ATTRIBUTE.findall(BLOCK.search(content).group(0)))


@pytest.mark.django_db
def test_js_strings_are_translated_in_the_page(client):
    french = js_strings(client, "fr")
    english = js_strings(client, "en")
    assert french["data-copied"] == "Copié"
    assert french["data-confirm-delete"] == "Supprimer cette pièce jointe ?"
    assert english["data-copied"] == "Copied"
    assert english["data-confirm-delete"] == "Delete this attachment?"


@pytest.mark.django_db
def test_js_strings_have_no_empty_value_and_all_differ_between_languages(client):
    french = js_strings(client, "fr")
    english = js_strings(client, "en")
    assert len(english) >= 15
    assert all(value.strip() for value in english.values())
    assert french.keys() == english.keys()
    untranslated = [key for key in english if french[key] == english[key] and key not in SAME_IN_BOTH]
    assert untranslated == []


def test_static_js_files_hold_no_hardcoded_french():
    accented = re.compile(r"[À-ÖØ-öø-ÿ]")
    offenders = [
        f"{path.name}:{number}"
        for path in STATIC_JS.glob("*.js")
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if accented.search(line)
    ]
    assert offenders == []

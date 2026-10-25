import ast
import re
from pathlib import Path

import pytest
from django.conf import settings

LANGUAGES = [code for code, _ in settings.LANGUAGES]


def _unquote(lines):
    return "".join(ast.literal_eval(line) for line in lines)


def _catalogue(language):
    """{msgid: msgstr} read from the .po file (no polib dependency). Header entry excluded."""
    path = Path(settings.BASE_DIR) / "locale" / language / "LC_MESSAGES" / "django.po"
    entries = {}
    for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8")):
        msgid, msgstr, current = [], [], None
        for line in block.splitlines():
            line = line.strip()
            if line.startswith("msgid "):
                current = msgid
                line = line[len("msgid ") :]
            elif line.startswith("msgstr "):
                current = msgstr
                line = line[len("msgstr ") :]
            elif not line.startswith('"'):
                continue
            current.append(line)
        if msgid and _unquote(msgid):
            entries[_unquote(msgid)] = _unquote(msgstr)
    return entries


@pytest.mark.parametrize("language", LANGUAGES)
def test_no_empty_msgstr(language):
    empty = [msgid for msgid, msgstr in _catalogue(language).items() if not msgstr.strip()]
    assert empty == []


def test_catalogues_have_the_same_msgids():
    first, *others = (set(_catalogue(language)) for language in LANGUAGES)
    for other in others:
        assert first == other

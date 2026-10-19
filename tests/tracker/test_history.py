import datetime
from types import SimpleNamespace

from tracker import history


def feedback_like(**overrides):
    values = {"type": "bug", "page": "Articles", "tab": "", "article_id": "", "description": "Text"}
    return SimpleNamespace(**{**values, **overrides})


def vendor_like(**overrides):
    values = {
        "ref": "TEST-1",
        "title": "Title",
        "description": "",
        "page": "",
        "tab": "",
        "status": "",
        "url": "",
        "created_on": None,
    }
    return SimpleNamespace(**{**values, **overrides})


def test_no_text_when_nothing_changed():
    assert history.diff_texts(feedback_like(), feedback_like()) == []


def test_changed_field_is_described_with_old_and_new_value():
    texts = history.diff_texts(feedback_like(page="Articles"), feedback_like(page="Clients"))
    assert texts == ['Page modifié : "Articles" → "Clients"']


def test_empty_values_are_shown_as_empty():
    texts = history.diff_texts(feedback_like(tab=""), feedback_like(tab="Prix"))
    assert texts == ['Onglet modifié : "(vide)" → "Prix"']


def test_type_is_shown_with_its_label():
    texts = history.diff_texts(feedback_like(type="bug"), feedback_like(type="suggestion"))
    assert texts == ['Type modifié : "Anomalie" → "Proposition"']


def test_one_text_per_changed_field_in_declaration_order():
    texts = history.diff_texts(feedback_like(), feedback_like(page="Clients", description="Other"))
    assert texts == ['Page modifié : "Articles" → "Clients"', 'Description modifié : "Text" → "Other"']


def test_vendor_status_is_shown_with_its_label():
    texts = history.vendor_diff_texts(vendor_like(status=""), vendor_like(status="to_test"))
    assert texts == ['Statut : "(vide)" → "À tester"']


def test_vendor_date_is_shown_day_first():
    after = vendor_like(created_on=datetime.date(2026, 10, 5))
    assert history.vendor_diff_texts(vendor_like(), after) == ['Date de création : "(vide)" → "05/10/2026"']

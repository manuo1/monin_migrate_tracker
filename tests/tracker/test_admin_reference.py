import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.urls import reverse

from tests.tracker.factories import FeedbackFactory, StaffFactory, VendorTicketFactory
from tracker.models import Page, Tab

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client):
    client.force_login(get_user_model().objects.create_superuser("root", password="x"))
    return client


def _import_url(model):
    return reverse(f"admin:tracker_{model}_import")


def _upload(client, model, content, name="values.csv"):
    return client.post(_import_url(model), {"file": SimpleUploadedFile(name, content)})


# --- Models ---


def test_reference_names_are_unique():
    Page.objects.create(name="Articles")
    with pytest.raises(IntegrityError), transaction.atomic():
        Page.objects.create(name="Articles")


# --- CSV import ---


def test_import_page_is_reserved_to_users_allowed_to_add(client):
    assert client.get(_import_url("page")).status_code == 302  # anonymous -> admin login

    client.force_login(StaffFactory())  # staff without model permissions
    assert client.get(_import_url("page")).status_code == 403
    assert _upload(client, "page", b"Articles").status_code == 403
    assert not Page.objects.exists()


def test_import_creates_one_value_per_line_from_the_first_column(admin_client):
    response = _upload(admin_client, "page", b"Articles\nClients\n")
    assert response.status_code == 302
    assert set(Page.objects.values_list("name", flat=True)) == {"Articles", "Clients"}
    assert not Tab.objects.exists()


@pytest.mark.parametrize("delimiter", [";", ",", "\t"])
def test_import_accepts_the_usual_delimiters(admin_client, delimiter):
    _upload(admin_client, "tab", f"Adresses{delimiter}ignored\nContacts{delimiter}ignored\n".encode())
    assert set(Tab.objects.values_list("name", flat=True)) == {"Adresses", "Contacts"}


def test_import_accepts_utf8_with_bom_and_excel_cp1252(admin_client):
    _upload(admin_client, "page", "Précédent\n".encode("utf-8-sig"))
    _upload(admin_client, "page", "Résumé\n".encode("cp1252"))
    assert set(Page.objects.values_list("name", flat=True)) == {"Précédent", "Résumé"}


def test_import_ignores_duplicates_blank_lines_and_existing_values(admin_client):
    Page.objects.create(name="Articles")
    response = _upload(admin_client, "page", b"Articles\n\n  Clients  \nClients\n", name="v.csv")
    assert response.status_code == 302
    assert sorted(Page.objects.values_list("name", flat=True)) == ["Articles", "Clients"]


def test_import_skips_values_too_long_for_the_field(admin_client):
    _upload(admin_client, "page", ("x" * 201 + "\nShort\n").encode())
    assert list(Page.objects.values_list("name", flat=True)) == ["Short"]


# --- "Out of reference" filter, highlighting and "add to reference" action ---


def test_out_of_reference_filter_on_feedbacks(admin_client):
    Page.objects.create(name="Articles")
    Tab.objects.create(name="Adresses")
    known = FeedbackFactory(page="Articles", tab="Adresses")
    no_tab = FeedbackFactory(page="Articles", tab="")
    unknown_page = FeedbackFactory(page="Typed by hand", tab="")
    unknown_tab = FeedbackFactory(page="Articles", tab="Typed too")

    response = admin_client.get(reverse("admin:tracker_feedback_changelist"), {"ref": "hors"})

    shown = {f.pk for f in response.context["cl"].result_list}
    assert shown == {unknown_page.pk, unknown_tab.pk}
    assert known.pk not in shown and no_tab.pk not in shown


def test_out_of_reference_filter_on_vendor_tickets(admin_client):
    Page.objects.create(name="Articles")
    known = VendorTicketFactory(page="Articles", tab="")
    unknown = VendorTicketFactory(page="Typed by hand", tab="")

    response = admin_client.get(reverse("admin:tracker_vendorticket_changelist"), {"ref": "hors"})

    shown = {t.pk for t in response.context["cl"].result_list}
    assert shown == {unknown.pk}
    assert known.pk not in shown


def test_out_of_reference_values_are_highlighted(admin_client):
    Page.objects.create(name="Articles")
    FeedbackFactory(page="Articles")
    FeedbackFactory(page="Typed by hand")

    content = admin_client.get(reverse("admin:tracker_feedback_changelist")).content.decode()

    assert content.count("Hors référentiel") == 1
    assert "Typed by hand" in content


def test_add_to_reference_action_creates_missing_pages_and_tabs(admin_client):
    Page.objects.create(name="Articles")
    first = FeedbackFactory(page="Articles", tab="Adresses")
    second = FeedbackFactory(page="  New page  ", tab="")

    response = admin_client.post(
        reverse("admin:tracker_feedback_changelist"),
        {"action": "add_to_reference", "_selected_action": [first.pk, second.pk]},
    )

    assert response.status_code == 302
    assert sorted(Page.objects.values_list("name", flat=True)) == ["Articles", "New page"]
    assert list(Tab.objects.values_list("name", flat=True)) == ["Adresses"]

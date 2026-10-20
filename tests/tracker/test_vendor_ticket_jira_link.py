import pytest
from django.conf import settings
from django.urls import reverse

from tests.tracker.factories import StaffFactory, VendorTicketFactory

pytestmark = pytest.mark.django_db

SCRIPT = "tracker/jira_link.js"


def _pages():
    ticket = VendorTicketFactory()
    return {
        "edit": reverse("vendor_ticket_edit", args=[ticket.pk]),
        "create": reverse("vendor_ticket_create"),
    }


@pytest.mark.parametrize("page", ["edit", "create"])
def test_ref_widget_carries_the_jira_settings_for_the_live_link(client, page):
    client.force_login(StaffFactory())
    content = client.get(_pages()[page]).content.decode()
    assert f'data-jira-base="{settings.JIRA_BASE_URL}"' in content
    assert f'data-ref-prefix="{settings.JIRA_REF_PREFIX}"' in content
    assert 'data-link-target="id_url"' in content


@pytest.mark.parametrize("page", ["edit", "create"])
def test_page_loads_the_live_link_script(client, page):
    client.force_login(StaffFactory())
    assert SCRIPT in client.get(_pages()[page]).content.decode()

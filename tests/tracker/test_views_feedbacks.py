import pytest
from django.urls import reverse

from tests.tracker.factories import FeedbackFactory, StaffFactory, UserFactory, VendorTicketFactory
from tracker.choices import FeedbackType
from tracker.statuses import CLOSED, IN_ANALYSIS, NEW, SENT_TO_VENDOR

pytestmark = pytest.mark.django_db


def ids(response):
    return [f.pk for f in response.context["feedbacks"]]


@pytest.fixture
def user(client):
    account = UserFactory()
    client.force_login(account)
    return account


@pytest.fixture
def staff(client):
    account = StaffFactory()
    client.force_login(account)
    return account


# --- Access matrix: login required, then open to every logged-in user ---


@pytest.mark.parametrize("role", ["anonymous", "user", "author", "staff"])
@pytest.mark.parametrize("view_name", ["feedback_list", "feedback_detail"])
def test_read_pages_access_matrix(client, role, view_name):
    feedback = FeedbackFactory()
    accounts = {"user": UserFactory(), "author": feedback.author, "staff": StaffFactory()}
    if role != "anonymous":
        client.force_login(accounts[role])
    url = reverse(view_name, args=[feedback.pk]) if view_name == "feedback_detail" else reverse(view_name)

    response = client.get(url)

    if role == "anonymous":
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))
    else:
        assert response.status_code == 200


def test_unknown_feedback_is_a_404(user, client):
    assert client.get(reverse("feedback_detail", args=[999999])).status_code == 404


# --- List: default scope, filters, sorting ---


def test_a_user_sees_only_their_own_feedbacks_by_default(user, client):
    mine = FeedbackFactory(author=user)
    FeedbackFactory()
    assert ids(client.get(reverse("feedback_list"))) == [mine.pk]


def test_staff_sees_every_feedback_by_default(staff, client):
    a, b = FeedbackFactory(), FeedbackFactory()
    assert set(ids(client.get(reverse("feedback_list")))) == {a.pk, b.pk}


def test_a_user_can_widen_the_author_filter_to_everyone(user, client):
    mine, other = FeedbackFactory(author=user), FeedbackFactory()
    assert set(ids(client.get(reverse("feedback_list"), {"author": ""}))) == {mine.pk, other.pk}


def test_filter_by_author_id(staff, client):
    wanted, other = FeedbackFactory(), FeedbackFactory()
    response = client.get(reverse("feedback_list"), {"author": wanted.author_id})
    assert ids(response) == [wanted.pk]
    assert other.pk not in ids(response)


def test_filter_by_type_status_page_and_tab(staff, client):
    wanted = FeedbackFactory(type=FeedbackType.SUGGESTION, status=IN_ANALYSIS, page="Clients", tab="Adresses")
    FeedbackFactory(type=FeedbackType.BUG, status=IN_ANALYSIS, page="Clients", tab="Adresses")
    FeedbackFactory(type=FeedbackType.SUGGESTION, status=NEW, page="Clients", tab="Adresses")
    FeedbackFactory(type=FeedbackType.SUGGESTION, status=IN_ANALYSIS, page="Articles", tab="Adresses")
    FeedbackFactory(type=FeedbackType.SUGGESTION, status=IN_ANALYSIS, page="Clients", tab="Contacts")
    response = client.get(
        reverse("feedback_list"),
        {"type": "suggestion", "status": IN_ANALYSIS, "page": "Clients", "tab": "Adresses"},
    )
    assert ids(response) == [wanted.pk]


def test_unknown_status_filter_is_ignored(staff, client):
    feedback = FeedbackFactory()
    assert ids(client.get(reverse("feedback_list"), {"status": "nonsense"})) == [feedback.pk]


def test_text_search_covers_page_tab_article_and_description(staff, client):
    by_description = FeedbackFactory(description="Le montant TTC est faux")
    by_article = FeedbackFactory(article_id="ZX-4242")
    FeedbackFactory(description="Autre chose")
    assert ids(client.get(reverse("feedback_list"), {"q": "montant"})) == [by_description.pk]
    assert ids(client.get(reverse("feedback_list"), {"q": "zx-42"})) == [by_article.pk]


def test_tab_choices_are_limited_to_the_selected_page(staff, client):
    FeedbackFactory(page="Clients", tab="Adresses")
    FeedbackFactory(page="Articles", tab="Prix")
    response = client.get(reverse("feedback_list"), {"page": "Clients"})
    assert response.context["pages"] == ["Articles", "Clients"]
    assert response.context["tabs"] == ["Adresses"]


def test_default_sort_is_newest_first(staff, client):
    older, newer = FeedbackFactory(), FeedbackFactory()
    assert ids(client.get(reverse("feedback_list"))) == [newer.pk, older.pk]


def test_sort_by_status_follows_the_workflow_order_not_the_alphabet(staff, client):
    closed = FeedbackFactory(status=CLOSED)
    sent = FeedbackFactory(status=SENT_TO_VENDOR)
    new = FeedbackFactory(status=NEW)
    response = client.get(reverse("feedback_list"), {"sort": "status", "order": "asc"})
    assert ids(response) == [new.pk, sent.pk, closed.pk]
    response = client.get(reverse("feedback_list"), {"sort": "status", "order": "desc"})
    assert ids(response) == [closed.pk, sent.pk, new.pk]


def test_sort_by_vendor_reference(staff, client):
    b = FeedbackFactory()
    b.vendor_tickets.add(VendorTicketFactory(ref="TEST-B"))
    a = FeedbackFactory()
    a.vendor_tickets.add(VendorTicketFactory(ref="TEST-A"))
    response = client.get(reverse("feedback_list"), {"sort": "vendor", "order": "asc"})
    assert ids(response) == [a.pk, b.pk]


def test_unknown_sort_falls_back_to_date(staff, client):
    response = client.get(reverse("feedback_list"), {"sort": "nonsense"})
    assert response.status_code == 200
    assert response.context["sort"] == "date"


def test_the_list_url_is_remembered_for_the_back_button(staff, client):
    feedback = FeedbackFactory()
    client.get(reverse("feedback_list"), {"status": "new", "sort": "page"})
    response = client.get(reverse("feedback_detail", args=[feedback.pk]))
    assert response.context["back_url"] == reverse("feedback_list") + "?status=new&sort=page"


def test_back_button_defaults_to_the_list(staff, client):
    feedback = FeedbackFactory()
    response = client.get(reverse("feedback_detail", args=[feedback.pk]))
    assert response.context["back_url"] == reverse("feedback_list")


def test_list_page_renders_vendor_tickets_and_status(staff, client):
    feedback = FeedbackFactory(status=SENT_TO_VENDOR)
    feedback.vendor_tickets.add(VendorTicketFactory(ref="TEST-77"))
    content = client.get(reverse("feedback_list")).content.decode()
    assert "TEST-77" in content
    assert "Transmis Aptean" in content


# --- Detail ---


def test_detail_shows_the_feedback_its_description_and_its_timeline(staff, client):
    feedback = FeedbackFactory(description="Détail précis du problème")
    feedback.events.create(author=staff, text="Un événement tracé")
    content = client.get(reverse("feedback_detail", args=[feedback.pk])).content.decode()
    assert "Détail précis du problème" in content
    assert "Un événement tracé" in content

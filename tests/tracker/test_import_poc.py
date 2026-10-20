import hashlib
import io
import sqlite3
from datetime import UTC, date, datetime

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from tests.tracker.factories import FeedbackFactory
from tracker.models import (
    Attachment,
    Comment,
    Feedback,
    FeedbackEvent,
    Page,
    StatusChange,
    Tab,
    VendorTicket,
    VendorTicketEvent,
)

pytestmark = pytest.mark.django_db

User = get_user_model()

SCHEMA = """
CREATE TABLE auth_user (id integer PRIMARY KEY, password text, last_login text, is_superuser bool, username text,
    first_name text, last_name text, email text, is_staff bool, is_active bool, date_joined text);
CREATE TABLE suivi_page (id integer PRIMARY KEY, nom text);
CREATE TABLE suivi_onglet (id integer PRIMARY KEY, nom text);
CREATE TABLE suivi_ticketediteur (id integer PRIMARY KEY, ref text, titre text, description text, page text,
    onglet text, statut text, url text, date_creation text);
CREATE TABLE suivi_evenementediteur (id integer PRIMARY KEY, ticket_id integer, auteur_id integer, date text,
    texte text);
CREATE TABLE suivi_retour (id integer PRIMARY KEY, type text, statut text, motif_cloture text, page text,
    onglet text, article_id text, description text, auteur_id integer, created_at text);
CREATE TABLE suivi_retour_tickets_editeur (id integer PRIMARY KEY, retour_id integer, ticketediteur_id integer);
CREATE TABLE suivi_piecejointe (id integer PRIMARY KEY, retour_id integer, fichier text, created_at text);
CREATE TABLE suivi_commentaire (id integer PRIMARY KEY, retour_id integer, auteur_id integer, texte text,
    created_at text);
CREATE TABLE suivi_evenement (id integer PRIMARY KEY, retour_id integer, auteur_id integer, date text, texte text);
CREATE TABLE suivi_changementstatut (id integer PRIMARY KEY, retour_id integer, statut text, auteur_id integer,
    date text);
"""

JOINED = "2026-01-05 08:00:00.000000"


def build_poc(path, *, feedback_status="transmis_aptean"):
    """A fake POC database: fictional data only."""
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    db.executemany(
        "INSERT INTO auth_user VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [
            (1, "hash-alice", None, 1, "alice", "Alice", "A", "alice@example.com", 1, 1, JOINED),
            (2, "hash-bob", "2026-03-02 10:00:00.000000", 0, "bob", "", "", "", 0, 1, JOINED),
        ],
    )
    db.execute("INSERT INTO suivi_page VALUES (1, 'Articles')")
    db.execute("INSERT INTO suivi_onglet VALUES (1, 'Adresses')")
    db.executemany(
        "INSERT INTO suivi_ticketediteur VALUES (?,?,?,?,?,?,?,?,?)",
        [
            (
                7,
                "TEST-7",
                "Titre",
                "Détail",
                "Articles",
                "Adresses",
                "en_cours",
                "https://jira.example.com/7",
                "2026-03-02",
            ),
            (8, None, "", "", "", "", "", "", None),
        ],
    )
    db.execute("INSERT INTO suivi_evenementediteur VALUES (1, 7, 1, '2026-03-02 11:00:00.000000', 'Statut : En cours')")
    db.executemany(
        "INSERT INTO suivi_retour VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            (
                12,
                "anomalie",
                feedback_status,
                "",
                "Articles",
                "Adresses",
                "A1",
                "Ça plante",
                2,
                "2026-03-01 09:30:00.000000",
            ),
            (13, "test_ok", "clos", "corrige", "Articles", "", "", "Ça marche", 2, "2026-03-03 14:00:00.000000"),
            (14, "proposition", "nouveau", "", "Clients", "", "", "Idée", 2, "2026-03-04 15:00:00.000000"),
        ],
    )
    db.execute("INSERT INTO suivi_retour_tickets_editeur VALUES (1, 12, 7)")
    db.execute("INSERT INTO suivi_piecejointe VALUES (1, 12, 'retours/2026/03/shot.png', '2026-03-01 09:31:00.000000')")
    db.execute("INSERT INTO suivi_commentaire VALUES (1, 12, 1, 'Vu', '2026-03-02 09:00:00.000000')")
    db.execute("INSERT INTO suivi_evenement VALUES (1, 12, 1, '2026-03-02 09:05:00.000000', 'Lien ajouté')")
    db.executemany(
        "INSERT INTO suivi_changementstatut VALUES (?,?,?,?,?)",
        [
            (1, 12, "nouveau", 2, "2026-03-01 09:30:00.000000"),
            (2, 12, "transmis_aptean", 1, "2026-03-02 09:06:00.000000"),
        ],
    )
    db.commit()
    db.close()
    return path


@pytest.fixture
def poc(tmp_path):
    return build_poc(tmp_path / "poc.sqlite3")


@pytest.fixture
def poc_media(tmp_path):
    folder = tmp_path / "poc_media" / "retours" / "2026" / "03"
    folder.mkdir(parents=True)
    (folder / "shot.png").write_bytes(b"png-bytes")
    return tmp_path / "poc_media"


@pytest.fixture
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT


def run(*args):
    out = io.StringIO()
    call_command("import_poc", *map(str, args), stdout=out)
    return out.getvalue()


# --- Full import ---


def test_import_brings_everything_over_keeping_ids_and_dates(poc, poc_media, media_root):
    existing = User.objects.create_user("alice", password="x", is_staff=False)

    run(poc, "--poc-media", poc_media)

    # Users: matched by username (existing one reused and left untouched), others created with their hash.
    assert User.objects.count() == 2
    existing.refresh_from_db()
    assert existing.is_staff is False
    bob = User.objects.get(username="bob")
    assert bob.password == "hash-bob"

    assert set(Page.objects.values_list("name", flat=True)) == {"Articles"}
    assert set(Tab.objects.values_list("name", flat=True)) == {"Adresses"}

    ticket = VendorTicket.objects.get(pk=7)
    assert (ticket.ref, ticket.title, ticket.status, ticket.tab) == ("TEST-7", "Titre", "in_progress", "Adresses")
    assert ticket.created_on == date(2026, 3, 2)
    assert ticket.url == "https://jira.example.com/7"
    bare = VendorTicket.objects.get(pk=8)
    assert (bare.ref, bare.status, bare.created_on) == (None, "", None)
    event = VendorTicketEvent.objects.get(ticket=ticket)
    assert (event.author, event.text) == (existing, "Statut : En cours")
    assert event.date == datetime(2026, 3, 2, 11, 0, tzinfo=UTC)

    feedback = Feedback.objects.get(pk=12)
    assert (feedback.type, feedback.status, feedback.closure_reason) == ("bug", "sent_to_vendor", "")
    assert (feedback.page, feedback.tab, feedback.article_id, feedback.author) == ("Articles", "Adresses", "A1", bob)
    assert feedback.created_at == datetime(2026, 3, 1, 9, 30, tzinfo=UTC)
    closed = Feedback.objects.get(pk=13)
    assert (closed.type, closed.status, closed.closure_reason) == ("test_passed", "closed", "fixed")
    assert Feedback.objects.get(pk=14).type == "suggestion"
    assert list(feedback.vendor_tickets.values_list("pk", flat=True)) == [7]

    comment = Comment.objects.get(feedback=feedback)
    assert (comment.text, comment.author) == ("Vu", existing)
    assert comment.created_at == datetime(2026, 3, 2, 9, 0, tzinfo=UTC)
    assert FeedbackEvent.objects.get(feedback=feedback).text == "Lien ajouté"
    history = list(StatusChange.objects.filter(feedback=feedback).values_list("status", "date"))
    assert history == [
        ("new", datetime(2026, 3, 1, 9, 30, tzinfo=UTC)),
        ("sent_to_vendor", datetime(2026, 3, 2, 9, 6, tzinfo=UTC)),
    ]

    attachment = Attachment.objects.get(feedback=feedback)
    assert attachment.file.name == "feedbacks/2026/03/shot.png"
    assert (media_root / "feedbacks" / "2026" / "03" / "shot.png").read_bytes() == b"png-bytes"

    # New rows created afterwards must not collide with the imported ids.
    assert FeedbackFactory().pk > 14


def test_import_without_poc_media_keeps_rows_and_reports_uncopied_files(poc, media_root):
    output = run(poc)
    assert Attachment.objects.count() == 1
    assert not media_root.exists()
    assert "0 file(s) copied" in output


def test_existing_files_are_never_overwritten(poc, poc_media, media_root):
    target = media_root / "feedbacks" / "2026" / "03"
    target.mkdir(parents=True)
    (target / "shot.png").write_bytes(b"already-there")

    run(poc, "--poc-media", poc_media)

    assert (target / "shot.png").read_bytes() == b"already-there"


# --- Safety ---


def test_refuses_a_target_that_already_holds_data(poc):
    FeedbackFactory()
    with pytest.raises(CommandError, match="not empty"):
        run(poc)


def test_unknown_status_aborts_and_imports_nothing(tmp_path):
    poc = build_poc(tmp_path / "bad.sqlite3", feedback_status="weird")
    with pytest.raises(CommandError, match="weird"):
        run(poc)
    assert not Feedback.objects.exists()
    assert not VendorTicket.objects.exists()
    assert not User.objects.exists()


def test_dry_run_changes_nothing(poc, poc_media, media_root):
    output = run(poc, "--poc-media", poc_media, "--dry-run")
    assert not Feedback.objects.exists()
    assert not User.objects.exists()
    assert not media_root.exists()
    assert "dry run" in output.lower()


def test_the_poc_database_is_never_modified(poc, poc_media, media_root):
    before = hashlib.sha256(poc.read_bytes()).hexdigest()
    run(poc, "--poc-media", poc_media)
    assert hashlib.sha256(poc.read_bytes()).hexdigest() == before


def test_missing_poc_database_is_an_error(tmp_path):
    with pytest.raises(CommandError, match="not found"):
        run(tmp_path / "nope.sqlite3")

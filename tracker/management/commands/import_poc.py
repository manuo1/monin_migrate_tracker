"""Import the data of the POC database (SQLite, French schema) into this project.

Local use only: the POC database holds real data, which must never reach the public repository.
The POC database is opened read-only. Ids of feedbacks and vendor tickets are kept; users are matched by username.

    python manage.py import_poc <path to POC db.sqlite3> --poc-media <path to POC media folder> [--dry-run]
"""

import shutil
import sqlite3
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connection, transaction
from django.utils import timezone

from tracker import statuses
from tracker.choices import ClosureReason, FeedbackType
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

FEEDBACK_TYPES = {
    "anomalie": FeedbackType.BUG,
    "test_ok": FeedbackType.TEST_PASSED,
    "proposition": FeedbackType.SUGGESTION,
}
CLOSURE_REASONS = {
    "": "",
    "corrige": ClosureReason.FIXED,
    "non_reproduit": ClosureReason.NOT_REPRODUCED,
    "evolution": ClosureReason.PRODUCT_EVOLUTION,
    "rejete": ClosureReason.REJECTED,
}
FEEDBACK_STATUSES = {
    "nouveau": statuses.NEW,
    "en_analyse": statuses.IN_ANALYSIS,
    "a_rejouer": statuses.TO_REPLAY_WITH_USER,
    "transmis_aptean": statuses.SENT_TO_VENDOR,
    "retest_staff": statuses.RETEST_STAFF,
    "retest_user": statuses.RETEST_USER,
    "test_ko": statuses.TEST_FAILED,
    "test_ok": statuses.TEST_PASSED,
    "clos": statuses.CLOSED,
}
VENDOR_STATUSES = {
    "": "",
    "en_cours": statuses.VENDOR_IN_PROGRESS,
    "a_tester": statuses.VENDOR_TO_TEST,
    "clos": statuses.VENDOR_CLOSED,
    "bloque": statuses.VENDOR_BLOCKED,
}

POC_ATTACHMENT_FOLDER = "retours/"
ATTACHMENT_FOLDER = "feedbacks/"


class DryRunError(Exception):
    """Raised at the end of a dry run to roll the transaction back."""


def convert(mapping, value, what):
    try:
        return mapping[value or ""]
    except KeyError:
        raise CommandError(f"Unknown {what} {value!r} in the POC data.") from None


def parse_datetime(value):
    """POC timestamps are stored in UTC (Django with USE_TZ=True)."""
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


@contextmanager
def keep_dates(*fields):
    """Let imported rows keep their original dates (auto_now_add would overwrite them with the current time)."""
    saved = [(field, field.auto_now_add) for field in fields]
    for field, _ in saved:
        field.auto_now_add = False
    try:
        yield
    finally:
        for field, value in saved:
            field.auto_now_add = value


class Command(BaseCommand):
    help = "Import the POC database (read-only) into this project. Local use only, never commit the data."

    def add_arguments(self, parser):
        parser.add_argument("poc_db", help="Path to the POC SQLite database.")
        parser.add_argument("--poc-media", help="Path to the POC media folder (attachment files are copied from it).")
        parser.add_argument("--dry-run", action="store_true", help="Run everything, then roll back and copy no file.")

    def handle(self, *args, poc_db, poc_media=None, dry_run=False, **options):
        path = Path(poc_db)
        if not path.is_file():
            raise CommandError(f"POC database not found: {path}")
        if Feedback.objects.exists() or VendorTicket.objects.exists():
            raise CommandError(
                "The target database is not empty (feedbacks or vendor tickets exist): nothing imported."
            )

        # Read-only: the POC database is never written to.
        source = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        source.row_factory = sqlite3.Row
        copies = []
        try:
            with transaction.atomic():
                self._import_all(source, copies)
                if dry_run:
                    raise DryRunError
        except DryRunError:
            self.stdout.write("Dry run: everything rolled back, no file copied.")
            return
        finally:
            source.close()
        self._copy_files(copies, Path(poc_media) if poc_media else None)

    def _rows(self, source, table):
        # Table names are constants of this module, never user input.
        return source.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()  # noqa: S608

    def _import_all(self, source, copies):
        users = self._users(source)
        self._references(source)
        self._vendor_tickets(source, users)
        self._feedbacks(source, users, copies)
        self._reset_sequences()

    def _report(self, label, count):
        self.stdout.write(f"{label}: {count}")

    def _users(self, source):
        """POC user id -> user. Users are matched by username; an existing one is reused and left untouched."""
        user_model = get_user_model()
        mapping = {}
        created = 0
        for row in self._rows(source, "auth_user"):
            user, was_created = user_model.objects.get_or_create(
                username=row["username"],
                defaults={
                    "password": row["password"],
                    "last_login": parse_datetime(row["last_login"]),
                    "is_superuser": bool(row["is_superuser"]),
                    "first_name": row["first_name"],
                    "last_name": row["last_name"],
                    "email": row["email"],
                    "is_staff": bool(row["is_staff"]),
                    "is_active": bool(row["is_active"]),
                    "date_joined": parse_datetime(row["date_joined"]) or timezone.now(),
                },
            )
            mapping[row["id"]] = user
            created += was_created
        self._report("Users created", created)
        self._report("Users matched by username", len(mapping) - created)
        return mapping

    def _references(self, source):
        pages = sum(Page.objects.get_or_create(name=r["nom"])[1] for r in self._rows(source, "suivi_page"))
        tabs = sum(Tab.objects.get_or_create(name=r["nom"])[1] for r in self._rows(source, "suivi_onglet"))
        self._report("Pages (reference)", pages)
        self._report("Tabs (reference)", tabs)

    def _vendor_tickets(self, source, users):
        tickets = [
            VendorTicket(
                id=row["id"],
                ref=row["ref"],
                title=row["titre"],
                description=row["description"],
                page=row["page"],
                tab=row["onglet"],
                status=convert(VENDOR_STATUSES, row["statut"], "vendor ticket status"),
                url=row["url"],
                created_on=date.fromisoformat(row["date_creation"]) if row["date_creation"] else None,
            )
            for row in self._rows(source, "suivi_ticketediteur")
        ]
        VendorTicket.objects.bulk_create(tickets)
        events = [
            VendorTicketEvent(
                ticket_id=row["ticket_id"],
                author=users[row["auteur_id"]],
                date=parse_datetime(row["date"]),
                text=row["texte"],
            )
            for row in self._rows(source, "suivi_evenementediteur")
        ]
        VendorTicketEvent.objects.bulk_create(events)
        self._report("Vendor tickets", len(tickets))
        self._report("Vendor ticket events", len(events))

    def _feedbacks(self, source, users, copies):
        feedbacks = [
            Feedback(
                id=row["id"],
                type=convert(FEEDBACK_TYPES, row["type"], "feedback type"),
                status=convert(FEEDBACK_STATUSES, row["statut"], "feedback status"),
                closure_reason=convert(CLOSURE_REASONS, row["motif_cloture"], "closure reason"),
                page=row["page"],
                tab=row["onglet"],
                article_id=row["article_id"],
                description=row["description"],
                author=users[row["auteur_id"]],
                created_at=parse_datetime(row["created_at"]),
            )
            for row in self._rows(source, "suivi_retour")
        ]
        links = [
            Feedback.vendor_tickets.through(feedback_id=row["retour_id"], vendorticket_id=row["ticketediteur_id"])
            for row in self._rows(source, "suivi_retour_tickets_editeur")
        ]
        attachments = []
        for row in self._rows(source, "suivi_piecejointe"):
            old_name = row["fichier"]
            new_name = ATTACHMENT_FOLDER + old_name.removeprefix(POC_ATTACHMENT_FOLDER)
            copies.append((old_name, new_name))
            attachments.append(
                Attachment(feedback_id=row["retour_id"], file=new_name, created_at=parse_datetime(row["created_at"]))
            )
        comments = [
            Comment(
                feedback_id=row["retour_id"],
                author=users[row["auteur_id"]],
                text=row["texte"],
                created_at=parse_datetime(row["created_at"]),
            )
            for row in self._rows(source, "suivi_commentaire")
        ]
        events = [
            FeedbackEvent(
                feedback_id=row["retour_id"],
                author=users[row["auteur_id"]],
                date=parse_datetime(row["date"]),
                text=row["texte"],
            )
            for row in self._rows(source, "suivi_evenement")
        ]
        history = [
            StatusChange(
                feedback_id=row["retour_id"],
                status=convert(FEEDBACK_STATUSES, row["statut"], "feedback status"),
                author=users[row["auteur_id"]],
                date=parse_datetime(row["date"]),
            )
            for row in self._rows(source, "suivi_changementstatut")
        ]

        created_at = Feedback._meta.get_field("created_at")
        comment_created_at = Comment._meta.get_field("created_at")
        status_date = StatusChange._meta.get_field("date")
        with keep_dates(created_at, comment_created_at, status_date):
            Feedback.objects.bulk_create(feedbacks)
            Comment.objects.bulk_create(comments)
            StatusChange.objects.bulk_create(history)
        Feedback.vendor_tickets.through.objects.bulk_create(links)
        Attachment.objects.bulk_create(attachments)
        FeedbackEvent.objects.bulk_create(events)

        self._report("Feedbacks", len(feedbacks))
        self._report("Feedback <-> vendor ticket links", len(links))
        self._report("Attachments", len(attachments))
        self._report("Comments", len(comments))
        self._report("Feedback events", len(events))
        self._report("Status changes", len(history))

    def _reset_sequences(self):
        """Ids were imported explicitly: make the database sequences continue after them (needed on PostgreSQL)."""
        statements = connection.ops.sequence_reset_sql(no_style(), [VendorTicket, Feedback])
        with connection.cursor() as cursor:
            for statement in statements:
                cursor.execute(statement)

    def _copy_files(self, copies, poc_media):
        """Copy attachment files after the commit. Existing files are never overwritten."""
        copied = already = missing = 0
        if poc_media is not None:
            for old_name, new_name in copies:
                source, target = poc_media / old_name, Path(settings.MEDIA_ROOT) / new_name
                if target.exists():
                    already += 1
                elif source.is_file():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                    copied += 1
                else:
                    missing += 1
        self.stdout.write(f"Attachment files: {copied} file(s) copied, {already} already present, {missing} missing.")
        if poc_media is None and copies:
            self.stdout.write("No --poc-media given: copy the attachment files by hand (retours/ -> feedbacks/).")

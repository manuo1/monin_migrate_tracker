"""Labels of statuses and choices in both languages (needs the compiled catalogues: `compilemessages`)."""

import pytest
from django.utils import translation

from tracker.choices import ClosureReason, FeedbackType
from tracker.statuses import FEEDBACK_STATUSES, VENDOR_STATUSES

FEEDBACK_STATUS_LABELS = {
    "fr": [
        "Nouveau",
        "En analyse",
        "À rejouer avec l'utilisateur",
        "Transmis Aptean",
        "À retester (staff)",
        "À retester (utilisateur)",
        "Test KO",
        "Test OK",
        "Clos",
    ],
    "en": [
        "New",
        "In analysis",
        "To replay with the user",
        "Sent to Aptean",
        "To retest (staff)",
        "To retest (user)",
        "Test failed",
        "Test passed",
        "Closed",
    ],
}
VENDOR_STATUS_LABELS = {
    "fr": ["En cours", "À tester", "Clos", "Bloqué"],
    "en": ["In progress", "To test", "Closed", "Blocked"],
}
FEEDBACK_TYPE_LABELS = {
    "fr": ["Anomalie", "Test OK", "Proposition"],
    "en": ["Bug", "Test passed", "Suggestion"],
}
CLOSURE_REASON_LABELS = {
    "fr": [
        "Corrigé",
        "Non reproduit (accord utilisateur)",
        "Évolution produit (pas une anomalie)",
        "Rejeté",
    ],
    "en": ["Fixed", "Not reproduced (user agreed)", "Product evolution (not a bug)", "Rejected"],
}


@pytest.mark.parametrize("language", ["fr", "en"])
def test_feedback_status_labels(language):
    with translation.override(language):
        assert [str(s.label) for s in FEEDBACK_STATUSES] == FEEDBACK_STATUS_LABELS[language]


@pytest.mark.parametrize("language", ["fr", "en"])
def test_vendor_status_labels(language):
    with translation.override(language):
        assert [str(s.label) for s in VENDOR_STATUSES] == VENDOR_STATUS_LABELS[language]


@pytest.mark.parametrize("language", ["fr", "en"])
def test_feedback_type_labels(language):
    with translation.override(language):
        assert [str(label) for label in FeedbackType.labels] == FEEDBACK_TYPE_LABELS[language]


@pytest.mark.parametrize("language", ["fr", "en"])
def test_closure_reason_labels(language):
    with translation.override(language):
        assert [str(label) for label in ClosureReason.labels] == CLOSURE_REASON_LABELS[language]

"""Choice enums shared by models, forms and business rules (no database access).

Labels are English msgids (`gettext_lazy`), translated in `locale/<lang>/LC_MESSAGES/django.po`.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class FeedbackType(models.TextChoices):
    BUG = "bug", _("Bug")
    TEST_PASSED = "test_passed", _("Test passed")
    SUGGESTION = "suggestion", _("Suggestion")


class ClosureReason(models.TextChoices):
    FIXED = "fixed", _("Fixed")
    NOT_REPRODUCED = "not_reproduced", _("Not reproduced (user agreed)")
    PRODUCT_EVOLUTION = "product_evolution", _("Product evolution (not a bug)")
    REJECTED = "rejected", _("Rejected")

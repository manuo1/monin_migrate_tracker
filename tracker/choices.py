"""Choice enums shared by models, forms and business rules (no database access)."""

from django.db import models


class FeedbackType(models.TextChoices):
    BUG = "bug", "Anomalie"
    TEST_PASSED = "test_passed", "Test OK"
    SUGGESTION = "suggestion", "Proposition"


class ClosureReason(models.TextChoices):
    FIXED = "fixed", "Corrigé"
    NOT_REPRODUCED = "not_reproduced", "Non reproduit (accord utilisateur)"
    PRODUCT_EVOLUTION = "product_evolution", "Évolution produit (pas une anomalie)"
    REJECTED = "rejected", "Rejeté"

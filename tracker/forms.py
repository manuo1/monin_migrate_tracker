from django import forms
from django.conf import settings

from .choices import ClosureReason, FeedbackType
from .models import Comment, Feedback, VendorTicket
from .statuses import FEEDBACK_STATUS_CHOICES

# Enables the browser spell checker (French) on free-text fields.
SPELLCHECK = {"spellcheck": "true", "lang": "fr"}
SMALL = "form-control form-control-sm"
# Page/tab inputs use the reference datalists of _reference_lists.html (see static/tracker/reference_lists.js).
PAGES_LIST = "reference-pages"
TABS_LIST = "reference-tabs"


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["text"]
        labels = {"text": "Ajouter un commentaire"}
        widgets = {"text": forms.Textarea(attrs={"rows": 3, "class": "form-control", **SPELLCHECK})}


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """File field accepting several files; cleaned value is a list (possibly empty)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"class": "form-control"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single = super().clean
        if isinstance(data, list | tuple):
            return [single(d, initial) for d in data if d]
        return [single(data, initial)] if data else []


def _normalize(text):
    return text.replace("\r\n", "\n").strip()


class FeedbackForm(forms.ModelForm):
    """Creation of a feedback. A feedback with the same page, tab and description is refused."""

    files = MultipleFileField(required=False, label="Captures / vidéos / documents")

    class Meta:
        model = Feedback
        fields = ["type", "page", "tab", "article_id", "description"]
        labels = {
            "type": "Type",
            "page": "Page",
            "tab": "Onglet",
            "article_id": "ID de l'article",
            "description": "Description",
        }
        widgets = {
            "type": forms.Select(attrs={"class": "form-select"}),
            "page": forms.TextInput(
                attrs={"class": "form-control", "autocomplete": "off", "list": PAGES_LIST, **SPELLCHECK}
            ),
            "tab": forms.TextInput(
                attrs={"class": "form-control", "autocomplete": "off", "list": TABS_LIST, **SPELLCHECK}
            ),
            "article_id": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 5, **SPELLCHECK}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.duplicate = None
        # No empty choice: a type is always selected.
        self.fields["type"].choices = FeedbackType.choices

    def clean(self):
        cleaned = super().clean()
        page, tab, description = cleaned.get("page"), cleaned.get("tab") or "", cleaned.get("description")
        if page and description:
            for feedback in Feedback.objects.filter(page=page, tab=tab):
                if _normalize(feedback.description) == _normalize(description):
                    self.duplicate = feedback
                    raise forms.ValidationError(
                        f"Un ticket identique (même page, onglet et description) existe déjà : #{feedback.pk}. "
                        "Modifiez l'un de ces trois champs pour créer un nouveau ticket."
                    )
        return cleaned


class FeedbackStaffForm(forms.ModelForm):
    """Manual edit of a feedback by staff (each change is traced). The description is the user's: read-only."""

    class Meta:
        model = Feedback
        fields = ["type", "page", "tab", "article_id"]
        labels = {"type": "Type", "page": "Page", "tab": "Onglet", "article_id": "Article testé"}
        widgets = {
            "type": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "page": forms.TextInput(attrs={"class": SMALL, "autocomplete": "off", "list": PAGES_LIST, **SPELLCHECK}),
            "tab": forms.TextInput(attrs={"class": SMALL, "autocomplete": "off", "list": TABS_LIST, **SPELLCHECK}),
            "article_id": forms.TextInput(attrs={"class": SMALL}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["type"].choices = FeedbackType.choices


class TriageForm(forms.Form):
    """Staff triage: status, closure reason, linked vendor tickets and a public explanation (posted as a comment)."""

    status = forms.ChoiceField(
        choices=FEEDBACK_STATUS_CHOICES,
        label="Statut",
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    vendor_tickets = forms.ModelMultipleChoiceField(
        queryset=VendorTicket.objects.all(),
        required=False,
        label="Tickets Aptean",
        widget=forms.SelectMultiple(attrs={"class": "form-select form-select-sm", "size": 5}),
    )
    closure_reason = forms.ChoiceField(
        choices=[("", "---")] + ClosureReason.choices,
        required=False,
        label="Motif de clôture",
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    explanation = forms.CharField(
        required=False,
        label="Explication (publiée en commentaire)",
        widget=forms.Textarea(attrs={"class": SMALL, "rows": 3, **SPELLCHECK}),
    )
    # Optimistic locking: fingerprint of the feedback when the form was displayed (see services.triage_state).
    state = forms.CharField(widget=forms.HiddenInput)


class VendorTicketForm(forms.ModelForm):
    """Manual edit of a vendor ticket by staff (each change is traced).

    The link is always derived from the Jira reference when there is one; without a reference it is kept as typed.
    """

    # Explicit scheme assumption (the Django 6.0 default), which also silences the Django 5.x deprecation warning.
    url = forms.URLField(
        required=False, assume_scheme="https", label="Lien", widget=forms.URLInput(attrs={"class": SMALL})
    )

    class Meta:
        model = VendorTicket
        fields = ["ref", "title", "description", "page", "tab", "status", "url", "created_on"]
        labels = {
            "ref": "Référence Jira (à saisir une fois le ticket créé dans Jira)",
            "title": "Titre du problème",
            "description": "Description",
            "page": "Page",
            "tab": "Onglet",
            "status": "Statut chez Aptean",
            "url": "Lien",
            "created_on": "Date de création chez Aptean",
        }
        widgets = {
            "ref": forms.TextInput(attrs={"class": SMALL, "autocomplete": "off", "data-focus-end": ""}),
            "title": forms.TextInput(attrs={"class": SMALL, **SPELLCHECK}),
            "description": forms.Textarea(attrs={"class": SMALL, "rows": 10, **SPELLCHECK}),
            "page": forms.TextInput(attrs={"class": SMALL, "autocomplete": "off", "list": PAGES_LIST, **SPELLCHECK}),
            "tab": forms.TextInput(attrs={"class": SMALL, "autocomplete": "off", "list": TABS_LIST, **SPELLCHECK}),
            "status": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "created_on": forms.DateInput(attrs={"class": SMALL, "type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, ref_required=False, **kwargs):
        super().__init__(*args, **kwargs)
        # Read by static/tracker/jira_link.js to keep the link field in sync while the reference is typed.
        self.fields["ref"].widget.attrs.update(
            {
                "data-jira-base": settings.JIRA_BASE_URL,
                "data-ref-prefix": settings.JIRA_REF_PREFIX,
                "data-link-target": self["url"].id_for_label,
            }
        )
        if ref_required:
            # Creation from a feedback: the Jira ticket is created at the same time, its number is typed here.
            self.fields["ref"].required = True
            self.fields["ref"].label = "Référence Jira"

    def clean_ref(self):
        """The bare Jira prefix (number not typed yet) is not a reference; empty means no reference (NULL)."""
        ref = (self.cleaned_data.get("ref") or "").strip()
        if ref == settings.JIRA_REF_PREFIX:
            if self.fields["ref"].required:
                raise forms.ValidationError(f"Indiquez le numéro du ticket après « {settings.JIRA_REF_PREFIX} ».")
            return None
        return ref or None

    def clean(self):
        cleaned = super().clean()
        ref = cleaned.get("ref")
        if ref:
            cleaned["url"] = settings.JIRA_BASE_URL + ref
        return cleaned

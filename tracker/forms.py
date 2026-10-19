from django import forms

from .choices import FeedbackType
from .models import Comment, Feedback

# Enables the browser spell checker (French) on free-text fields.
SPELLCHECK = {"spellcheck": "true", "lang": "fr"}


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
            "page": forms.TextInput(attrs={"class": "form-control", "autocomplete": "off", **SPELLCHECK}),
            "tab": forms.TextInput(attrs={"class": "form-control", "autocomplete": "off", **SPELLCHECK}),
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

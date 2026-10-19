from django import forms

from .models import Comment

# Enables the browser spell checker (French) on free-text fields.
SPELLCHECK = {"spellcheck": "true", "lang": "fr"}


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["text"]
        labels = {"text": "Ajouter un commentaire"}
        widgets = {"text": forms.Textarea(attrs={"rows": 3, "class": "form-control", **SPELLCHECK})}

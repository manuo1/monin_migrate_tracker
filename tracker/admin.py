import csv
import io

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import path
from django.utils.html import format_html

from .models import (
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

# Statuses (feedback and vendor) are defined in tracker/statuses.py and exposed to the fields through `choices`.
# The admin is an emergency tool (the only place where a ticket can be deleted). What is done here is deliberately NOT
# traced: normal follow-up goes through the application (services.py + history.py).

NAME_MAX_LENGTH = Page._meta.get_field("name").max_length


# --- Page / tab reference lists: spot the values typed by hand (out of reference) ---


def out_of_reference(queryset):
    """Rows whose page or tab is filled but absent from the reference lists (exact comparison, like the input)."""
    pages = Page.objects.values_list("name", flat=True)
    tabs = Tab.objects.values_list("name", flat=True)
    return queryset.filter((~Q(page="") & ~Q(page__in=pages)) | (~Q(tab="") & ~Q(tab__in=tabs)))


class OutOfReferenceFilter(admin.SimpleListFilter):
    title = "référentiel"
    parameter_name = "ref"

    def lookups(self, request, model_admin):
        return [("hors", "Page ou onglet hors référentiel")]

    def queryset(self, request, queryset):
        return out_of_reference(queryset) if self.value() == "hors" else queryset


class ReferenceMixin:
    """Page/tab columns highlighted when the value is not in the reference lists + "add to reference" action."""

    actions = ["add_to_reference"]

    def _mark(self, value, known):
        if value and value not in known:
            return format_html(
                '<span style="background:#fff3cd;padding:1px 4px;border-radius:3px" title="Hors référentiel">{}</span>',
                value,
            )
        return value

    @admin.display(description="page", ordering="page")
    def page_ref(self, obj):
        return self._mark(obj.page, set(Page.objects.values_list("name", flat=True)))

    @admin.display(description="onglet", ordering="tab")
    def tab_ref(self, obj):
        return self._mark(obj.tab, set(Tab.objects.values_list("name", flat=True)))

    @admin.action(description="Ajouter les pages/onglets sélectionnés au référentiel")
    def add_to_reference(self, request, queryset):
        added_pages = added_tabs = 0
        for name in {p.strip() for p in queryset.values_list("page", flat=True) if p.strip()}:
            added_pages += Page.objects.get_or_create(name=name)[1]
        for name in {t.strip() for t in queryset.values_list("tab", flat=True) if t.strip()}:
            added_tabs += Tab.objects.get_or_create(name=name)[1]
        self.message_user(
            request, f"Référentiel : {added_pages} page(s) et {added_tabs} onglet(s) ajouté(s).", messages.SUCCESS
        )


@admin.register(VendorTicket)
class VendorTicketAdmin(ReferenceMixin, admin.ModelAdmin):
    list_display = ("ref", "title", "description", "page_ref", "tab_ref", "status", "created_on")
    list_filter = ("status", OutOfReferenceFilter)
    search_fields = ("ref", "title", "description", "page", "tab")


@admin.register(Feedback)
class FeedbackAdmin(ReferenceMixin, admin.ModelAdmin):
    list_display = ("id", "type", "page_ref", "tab_ref", "article_id", "status", "author", "created_at")
    list_filter = ("type", "status", OutOfReferenceFilter)
    search_fields = ("page", "tab", "article_id", "description")
    readonly_fields = ("description",)  # the description cannot be changed once the feedback is submitted


# --- Reference lists editing (+ CSV import) ---


class CsvImportForm(forms.Form):
    file = forms.FileField(label="Fichier CSV (une valeur par ligne, première colonne)")


def read_csv_names(raw):
    """First column of every non-empty line, stripped, without duplicates. utf-8 (BOM allowed) or Excel cp1252."""
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")  # CSV saved from Excel (Windows)
    delimiter = ";" if ";" in text else ("\t" if "\t" in text else ",")
    rows = csv.reader(io.StringIO(text), delimiter=delimiter)
    return list(dict.fromkeys(row[0].strip() for row in rows if row and row[0].strip()))


class ReferenceAdmin(admin.ModelAdmin):
    """The only place where the reference lists are edited: suggested on input, out-of-list values flagged to staff."""

    search_fields = ("name",)
    change_list_template = "admin/tracker/reference_change_list.html"

    def get_urls(self):
        name = f"tracker_{self.model._meta.model_name}_import"
        return [path("import-csv/", self.admin_site.admin_view(self.import_csv), name=name), *super().get_urls()]

    def import_csv(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        form = CsvImportForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            names = read_csv_names(form.cleaned_data["file"].read())
            valid = [n for n in names if len(n) <= NAME_MAX_LENGTH]
            added = sum(self.model.objects.get_or_create(name=n)[1] for n in valid)
            message = f"{added} valeur(s) ajoutée(s) ({len(valid) - added} déjà présente(s))."
            if len(valid) < len(names):
                message += f" {len(names) - len(valid)} valeur(s) ignorée(s) : plus de {NAME_MAX_LENGTH} caractères."
            self.message_user(request, message, messages.SUCCESS)
            return redirect("..")
        context = {
            **self.admin_site.each_context(request),
            "form": form,
            "opts": self.model._meta,
            "title": f"Importer des {self.model._meta.verbose_name_plural}",
        }
        return render(request, "admin/tracker/reference_import.html", context)


admin.site.register(Page, ReferenceAdmin)
admin.site.register(Tab, ReferenceAdmin)

admin.site.register(Attachment)
admin.site.register(Comment)
admin.site.register(StatusChange)
admin.site.register(FeedbackEvent)
admin.site.register(VendorTicketEvent)

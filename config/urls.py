from django.contrib import admin
from django.urls import include, path

# Attachments are NOT exposed as a public media URL: they go through an authenticated view (tracker.views.attachments).
urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),  # set_language (POST), used by the navbar switch
    path("", include("django.contrib.auth.urls")),
    path("", include("tracker.urls")),
]

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", RedirectView.as_view(pattern_name="customers:list", permanent=False)),
    path("accounts/", include("accounts.urls")),
    path("customers/", include("customers.urls")),
    path("documents/", include("documents.urls")),
    path("loans/", include("loans.urls")),
    path("payments/", include("payments.urls")),
    path("settings/", include("core.urls")),
    path("reports/", include("reports.urls")),
    path("investments/", include("investments.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

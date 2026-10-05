from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("public.urls")),
    path("accounts/", include("accounts.urls")),
    path("customers/", include("customers.urls")),
    path("staff/", include("staff.urls")),
    path("documents/", include("documents.urls")),
    path("loans/", include("loans.urls")),
    path("payments/", include("payments.urls")),
    path("settings/", include("core.urls")),
    path("reports/", include("reports.urls")),
    path("investments/", include("investments.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

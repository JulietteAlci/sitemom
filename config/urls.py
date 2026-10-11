from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from apps.blog.sitemaps import BlogPostSitemap
from apps.catalog.sitemaps import RingSitemap
from apps.core.sitemaps import StaticViewSitemap

sitemaps = {
    "static": StaticViewSitemap,
    "alliances": RingSitemap,
    "journal": BlogPostSitemap,
}

admin.site.site_header = f"{settings.SITE_NAME}"
admin.site.site_title = f"{settings.SITE_NAME} — administration"
admin.site.index_title = "Tableau de bord"

urlpatterns = [
    path("admin/taches/", include("apps.backoffice.urls")),
    path("admin/", admin.site.urls),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path("", include("apps.core.urls")),
    path("alliances/", include("apps.catalog.urls")),
    path("journal/", include("apps.blog.urls")),
    path("coffret-essai/", include("apps.trialkit.urls")),
    path("", include("apps.orders.urls")),
    path("cours-de-l-or/", include("apps.pricing.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

from django.contrib.sitemaps import Sitemap

from .models import Ring


class RingSitemap(Sitemap):
    changefreq = "daily"  # prices follow the gold spot
    priority = 0.8

    def items(self):
        return Ring.objects.filter(is_active=True)

    def lastmod(self, obj):
        return obj.updated_at

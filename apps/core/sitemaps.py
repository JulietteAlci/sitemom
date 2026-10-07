from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    changefreq = "daily"

    def items(self):
        return ["core:home", "catalog:men", "catalog:women", "trialkit:start", "blog:post_list", "pricing:gold_price"]

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return 1.0 if item == "core:home" else 0.9

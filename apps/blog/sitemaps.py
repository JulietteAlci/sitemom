from django.contrib.sitemaps import Sitemap

from .models import Post


class BlogPostSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return Post.published.all()

    def lastmod(self, obj):
        return obj.updated_at

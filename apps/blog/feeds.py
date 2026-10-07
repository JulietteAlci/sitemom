from django.conf import settings
from django.contrib.syndication.views import Feed
from django.urls import reverse_lazy

from .models import Post


class LatestPostsFeed(Feed):
    title = f"{settings.SITE_NAME} — Journal"
    link = reverse_lazy("blog:post_list")
    description = "Conseils, savoir-faire et guides pour choisir son alliance en or."

    def items(self):
        return Post.published.all()[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.excerpt

    def item_pubdate(self, item):
        return item.published_at

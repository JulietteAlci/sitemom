from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import FAQ, Post


class BlogTests(TestCase):
    def setUp(self):
        self.post = Post.objects.create(
            title="Choisir sa largeur",
            slug="choisir-sa-largeur",
            excerpt="Résumé.",
            body="<h2>Intro</h2><p>Texte</p>",
            key_takeaways="Point 1\n\nPoint 2",
            status=Post.Status.PUBLISHED,
        )
        FAQ.objects.create(post=self.post, question="Quelle largeur ?", answer="2 mm </script>")
        Post.objects.create(title="Brouillon", slug="brouillon", excerpt="x", body="x")
        Post.objects.create(
            title="Futur", slug="futur", excerpt="x", body="x", status=Post.Status.PUBLISHED,
            published_at=timezone.now() + timedelta(days=1),
        )

    def test_list_only_shows_published(self):
        response = self.client.get(reverse("blog:post_list"))
        self.assertEqual(list(response.context["page_obj"]), [self.post])

    def test_unpublished_posts_are_404(self):
        for slug in ("brouillon", "futur"):
            self.assertEqual(self.client.get(reverse("blog:post_detail", args=[slug])).status_code, 404)

    def test_detail_has_seo_and_geo_markup(self):
        response = self.client.get(self.post.get_absolute_url())
        self.assertContains(response, '"@type": "BlogPosting"')
        self.assertContains(response, '"@type": "FAQPage"')
        self.assertContains(response, '"@type": "BreadcrumbList"')
        self.assertContains(response, "À retenir")
        self.assertEqual(self.post.takeaways, ["Point 1", "Point 2"])
        # JSON-LD must not allow breaking out of the <script> tag
        self.assertNotContains(response, "2 mm </script>")

    def test_feed(self):
        response = self.client.get(reverse("blog:feed"))
        self.assertContains(response, "Choisir sa largeur")
        self.assertNotContains(response, "Brouillon")

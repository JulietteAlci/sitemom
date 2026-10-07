from django.db import models
from django.urls import reverse
from django.utils import timezone


class Category(models.Model):
    name = models.CharField("nom", max_length=80)
    slug = models.SlugField(unique=True)
    description = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "catégorie"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("blog:category", kwargs={"slug": self.slug})


class PublishedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status=Post.Status.PUBLISHED, published_at__lte=timezone.now())


class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        PUBLISHED = "published", "Publié"

    title = models.CharField("titre", max_length=160)
    slug = models.SlugField(unique=True, max_length=180)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="posts")
    author_name = models.CharField("auteur", max_length=80, default="L'atelier")
    excerpt = models.TextField(
        "chapô",
        max_length=400,
        help_text="Résumé factuel de 2-3 phrases : repris par Google et par les moteurs IA (GEO).",
    )
    body = models.TextField("contenu (HTML)", help_text="HTML saisi par l'équipe éditoriale (h2, p, ul, a…).")
    key_takeaways = models.TextField(
        "à retenir",
        blank=True,
        help_text="Une idée par ligne. Affiché en encadré en haut d'article : format idéal pour les IA génératives.",
    )
    cover = models.ImageField(upload_to="blog/", blank=True)
    related_rings = models.ManyToManyField("catalog.Ring", blank=True, related_name="posts")

    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField("publié le", default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    published = PublishedManager()

    class Meta:
        ordering = ["-published_at"]
        verbose_name = "article"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("blog:post_detail", kwargs={"slug": self.slug})

    @property
    def seo_title(self):
        return self.meta_title or self.title

    @property
    def seo_description(self):
        return self.meta_description or self.excerpt[:160]

    @property
    def takeaways(self):
        return [line.strip() for line in self.key_takeaways.splitlines() if line.strip()]


class FAQ(models.Model):
    """Question/answer pairs rendered on the page and as FAQPage JSON-LD (rich results & GEO)."""

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="faqs")
    question = models.CharField(max_length=255)
    answer = models.TextField()
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        verbose_name = "question fréquente"
        verbose_name_plural = "questions fréquentes"

    def __str__(self):
        return self.question

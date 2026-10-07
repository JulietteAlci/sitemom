from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.cache import cache_page

from apps.blog.models import Post
from apps.catalog.models import Ring

HOME_FAQ = [
    (
        "Comment le prix de vos alliances est-il calculé ?",
        "Chaque alliance est vendue au poids réel de l'or qu'elle contient, valorisé au cours spot "
        "de l'or du jour, auquel s'ajoutent la façon de l'atelier et la TVA. Le prix affiché est "
        "garanti 30 minutes pendant le paiement.",
    ),
    (
        "Comment fonctionne le coffret d'essai ?",
        "Vous choisissez de 8 à 12 modèles, nous vous envoyons des répliques fidèles ainsi qu'un "
        "baguier. Vous les essayez chez vous pendant 5 jours puis les renvoyez avec l'étiquette "
        "prépayée ; la caution vous est intégralement remboursée.",
    ),
    (
        "En quel or sont fabriquées vos alliances ?",
        "En or 18 carats (750 ‰) recyclé et certifié, fondu et façonné en France. Chaque alliance "
        "porte le poinçon de garantie et le poinçon de maître.",
    ),
]


def home(request):
    featured = Ring.objects.filter(is_active=True, is_featured=True)[:6]
    return render(
        request,
        "core/home.html",
        {
            "featured": [(ring, ring.starting_price) for ring in featured],
            "latest_posts": Post.published.all()[:3],
            "faqs": HOME_FAQ,
        },
    )


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /panier/",
        "Disallow: /commande/",
        "Disallow: /stripe/",
        "Allow: /",
        "",
        f"Sitemap: {settings.SITE_URL}{reverse('django.contrib.sitemaps.views.sitemap')}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


@cache_page(60 * 15)
def llms_txt(request):
    """llms.txt (https://llmstxt.org): a Markdown digest of the site for generative engines (GEO)."""
    content = render_to_string(
        "core/llms.txt",
        {
            "rings": Ring.objects.filter(is_active=True),
            "posts": Post.published.all()[:50],
            "faqs": HOME_FAQ,
        },
        request=request,
    )
    return HttpResponse(content, content_type="text/markdown; charset=utf-8")

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.cache import cache_page

from apps.blog.models import Post
from apps.catalog.models import Ring


def trial_kit_price() -> int:
    return settings.TRIAL_KIT_PRICE_CENTS // 100


def how_it_works_steps():
    """The customer journey, shared by the "Comment ça fonctionne" page, the home page and llms.txt."""
    price = trial_kit_price()
    return [
        (
            f"Commandez votre coffret d'essai à {price}\u00a0€",
            f"Sélectionnez de {settings.TRIAL_KIT_MIN} à {settings.TRIAL_KIT_MAX} alliances parmi nos modèles homme et "
            f"femme et réglez {price}\u00a0€ en ligne. Vous recevez un code unique, personnel, associé à votre coffret.",
        ),
        (
            "Essayez les alliances chez vous",
            "Votre coffret arrive à domicile avec un baguier pour mesurer votre tour de doigt. Comparez largeurs, "
            "profils et teintes à votre rythme, à la lumière de tous les jours.",
        ),
        (
            "Renvoyez le coffret d'essai",
            "Replacez les alliances dans le coffret et renvoyez-le avec l'étiquette retour fournie.",
        ),
        (
            "Commandez vos alliances sur le site",
            f"Choisissez vos modèles et vos tailles, puis saisissez votre code unique dans le panier : les {price}\u00a0€ du "
            "coffret sont déduits du montant de votre commande.",
        ),
        (
            "Recevez vos alliances",
            "Vos alliances sont façonnées à la main dans notre atelier, poinçonnées, gravées si vous le souhaitez, "
            "puis livrées chez vous.",
        ),
    ]


def how_it_works(request):
    price = trial_kit_price()
    faqs = [
        (
            "Le prix du coffret d'essai est-il remboursé ?",
            f"Les {price}\u00a0€ du coffret sont intégralement déduits de votre commande d'alliances grâce à votre code "
            f"unique. Si vous ne commandez pas d'alliances sur le site, ce montant n'est pas remboursé.",
        ),
        (
            "Où trouver mon code unique ?",
            "Il s'affiche sur la page de confirmation de commande du coffret. Il est valable pour une seule commande.",
        ),
        (
            "Puis-je utiliser mon code pour plusieurs commandes ?",
            "Non : le code est à usage unique. Le montant du coffret est déduit en une fois.",
        ),
        (
            "Les alliances du coffret sont-elles celles que je vais recevoir ?",
            "Non, le coffret contient des modèles d'essai. Vos alliances sont fabriquées à la commande, dans votre "
            "taille, au prix du cours de l'or du jour de la commande.",
        ),
    ]
    return render(
        request,
        "core/how_it_works.html",
        {"steps": how_it_works_steps(), "faqs": faqs, "kit_price": price},
    )


def home_faq():
    price = trial_kit_price()
    return [
        (
            "Comment le prix de vos alliances est-il calculé ?",
            "Chaque alliance est vendue au poids réel de l'or qu'elle contient, valorisé au cours spot "
            "de l'or du jour, auquel s'ajoutent la façon de l'atelier et la TVA. Le prix affiché est "
            "garanti 30 minutes pendant le paiement.",
        ),
        (
            "Comment fonctionne le coffret d'essai ?",
            f"Vous choisissez de {settings.TRIAL_KIT_MIN} à {settings.TRIAL_KIT_MAX} modèles et réglez le coffret "
            f"{price}\u00a0€. Vous essayez les alliances chez vous avec un baguier, renvoyez le coffret, puis commandez "
            f"vos alliances : votre code unique déduit les {price}\u00a0€ de la commande. Sans commande, le prix du "
            "coffret n'est pas remboursé.",
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
            "faqs": home_faq(),
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
            "steps": how_it_works_steps(),
            "faqs": home_faq(),
        },
        request=request,
    )
    return HttpResponse(content, content_type="text/markdown; charset=utf-8")

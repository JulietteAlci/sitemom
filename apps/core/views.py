from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.cache import cache_page

from apps.blog.models import Post
from apps.catalog.models import Ring
from apps.trialkit.models import kit_size_label


def euros(cents: int) -> str:
    return f"{cents // 100}\u00a0€"


def kit_amounts() -> dict:
    return {
        "price": euros(settings.TRIAL_KIT_PRICE_CENTS),
        "credit": euros(settings.TRIAL_KIT_CREDIT_CENTS),
        "refund": euros(settings.TRIAL_KIT_REFUND_CENTS),
        "size": kit_size_label(),
        "days": settings.TRIAL_KIT_RETURN_DAYS,
    }


def how_it_works_steps():
    """The customer journey, shared by the "Comment ça fonctionne" page, the home page and llms.txt."""
    k = kit_amounts()
    return [
        (
            f"Commandez votre coffret d'essai à {k['price']}",
            f"Choisissez {k['size']} alliances parmi nos modèles homme et femme, indiquez vos coordonnées et votre "
            f"adresse, et réglez {k['price']} en ligne. Un e-mail confirme votre commande avec votre code unique.",
        ),
        (
            "Essayez les alliances chez vous",
            "Votre coffret arrive à domicile avec un baguier. Les alliances d'essai sont des modèles fidèles à nos "
            "vraies alliances en or : comparez largeurs, profils et teintes à votre rythme.",
        ),
        (
            f"Renvoyez le coffret sous {k['days']} jours",
            f"Utilisez l'étiquette retour reçue par e-mail. Après réception et contrôle du coffret, nous vous "
            f"remboursons {k['refund']}.",
        ),
        (
            "Commandez vos alliances sur le site",
            f"Choisissez vos modèles et vos tailles, puis saisissez votre code unique dans le panier : "
            f"{k['credit']} sont déduits de votre commande.",
        ),
        (
            "Recevez vos alliances",
            "Vos alliances sont façonnées à la main dans notre atelier, poinçonnées, gravées si vous le souhaitez, "
            "puis livrées chez vous.",
        ),
    ]


def how_it_works(request):
    k = kit_amounts()
    faqs = [
        (
            "Que devient le prix du coffret d'essai ?",
            f"Sur les {k['price']} payés, {k['refund']} vous sont remboursés au retour du coffret, après contrôle. "
            f"Les {k['credit']} restants sont déduits de votre commande d'alliances grâce à votre code unique. "
            f"Si vous ne commandez pas d'alliances sur le site, ces {k['credit']} ne sont pas remboursés.",
        ),
        (
            "Combien de temps puis-je garder le coffret ?",
            f"{k['days']} jours après sa livraison. Nous vous envoyons un rappel par e-mail tous les "
            f"{settings.TRIAL_KIT_REMINDER_EVERY_DAYS} jours jusqu'à son retour.",
        ),
        (
            "Où trouver mon code unique ?",
            "Dans l'e-mail de confirmation de votre coffret et sur la page de confirmation. Il est valable pour une "
            "seule commande.",
        ),
        (
            "Les alliances du coffret sont-elles celles que je vais recevoir ?",
            "Non, le coffret contient des modèles d'essai, fidèles aux vraies alliances. Vos alliances en or sont "
            "fabriquées à la commande, dans votre taille, au prix du cours de l'or du jour de la commande.",
        ),
    ]
    return render(
        request,
        "core/how_it_works.html",
        {"steps": how_it_works_steps(), "faqs": faqs, "kit": k},
    )


def home_faq():
    k = kit_amounts()
    return [
        (
            "Comment le prix de vos alliances est-il calculé ?",
            "Chaque alliance est vendue au poids réel de l'or qu'elle contient, valorisé au cours spot "
            "de l'or du jour, auquel s'ajoutent la façon de l'atelier et la TVA. Le prix affiché est "
            "garanti 30 minutes pendant le paiement.",
        ),
        (
            "Comment fonctionne le coffret d'essai ?",
            f"Vous choisissez {k['size']} modèles et réglez {k['price']}. Vous essayez les alliances chez vous, "
            f"renvoyez le coffret sous {k['days']} jours et nous vous remboursons {k['refund']}. Les {k['credit']} "
            "restants sont déduits de votre commande d'alliances avec votre code unique (non remboursés sans commande).",
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

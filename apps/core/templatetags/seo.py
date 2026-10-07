"""Structured data (schema.org JSON-LD) helpers for SEO and generative engines (GEO)."""
import json

from django import template
from django.conf import settings
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe

register = template.Library()


def _abs(url: str) -> str:
    return url if url.startswith("http") else settings.SITE_URL + url


def _script(data) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    # Prevent "</script>" injection from editorial content.
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return mark_safe(f'<script type="application/ld+json">{payload}</script>')


@register.simple_tag
def organization_jsonld():
    return _script(
        {
            "@context": "https://schema.org",
            "@type": "JewelryStore",
            "name": settings.SITE_NAME,
            "url": settings.SITE_URL,
            "description": (
                "Joaillier français d'alliances en or 18 carats, au prix indexé sur le cours de l'or, "
                "avec coffret d'essai à domicile."
            ),
            "currenciesAccepted": "EUR",
            "areaServed": ["FR", "BE", "LU", "CH", "MC"],
        }
    )


@register.simple_tag
def breadcrumb_jsonld(*crumbs):
    """Usage: {% breadcrumb_jsonld "Accueil" "/" "Alliances homme" "/alliances/homme/" %}"""
    pairs = list(zip(crumbs[::2], crumbs[1::2]))
    return _script(
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": i, "name": name, "item": _abs(url)}
                for i, (name, url) in enumerate(pairs, start=1)
            ],
        }
    )


@register.simple_tag
def product_jsonld(ring, breakdown):
    data = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": ring.name,
        "description": ring.seo_description,
        "sku": ring.slug,
        "brand": {"@type": "Brand", "name": settings.SITE_NAME},
        "material": f"{ring.get_color_display()} {ring.get_purity_display()}",
        "url": _abs(ring.get_absolute_url()),
        "additionalProperty": [
            {"@type": "PropertyValue", "name": "Largeur", "value": f"{ring.width_mm} mm"},
            {"@type": "PropertyValue", "name": "Profil", "value": ring.get_profile_display()},
            {"@type": "PropertyValue", "name": "Finition", "value": ring.get_finish_display()},
        ],
    }
    if ring.image:
        data["image"] = _abs(ring.image.url)
    if breakdown:
        data["offers"] = {
            "@type": "Offer",
            "price": str(breakdown.price_ttc),
            "priceCurrency": "EUR",
            "availability": "https://schema.org/MadeToOrder",
            "url": _abs(ring.get_absolute_url()),
        }
    return _script(data)


@register.simple_tag
def article_jsonld(post):
    data = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": post.title,
        "description": post.seo_description,
        "datePublished": post.published_at.isoformat(),
        "dateModified": post.updated_at.isoformat(),
        "author": {"@type": "Person", "name": post.author_name},
        "publisher": {"@type": "Organization", "name": settings.SITE_NAME, "url": settings.SITE_URL},
        "mainEntityOfPage": _abs(post.get_absolute_url()),
        "inLanguage": "fr-FR",
    }
    if post.cover:
        data["image"] = _abs(post.cover.url)
    return _script(data)


@register.simple_tag
def faq_jsonld(faqs):
    faqs = list(faqs)
    if not faqs:
        return ""
    return _script(
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": faq.question,
                    "acceptedAnswer": {"@type": "Answer", "text": strip_tags(faq.answer)},
                }
                for faq in faqs
            ],
        }
    )


@register.filter
def euros(value):
    """Format a Decimal as French currency: 1 234 €."""
    if value is None:
        return "—"
    amount = f"{value:,.0f}" if value == int(value) else f"{value:,.2f}"
    return amount.replace(",", " ").replace(".", ",") + " €"

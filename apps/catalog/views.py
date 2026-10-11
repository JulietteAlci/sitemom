from django.db.models import Avg, Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from apps.orders.forms import AddToCartForm

from .models import Collection, ProductFAQ, Reassurance, Review, Ring
from .selection import resolve_selection, selectors

GENDER_PAGES = {
    Ring.Gender.MEN: {
        "title": "Alliances homme en or",
        "meta_description": (
            "Alliances homme en or 18 carats, fabriquées en France. Prix indexé en temps réel "
            "sur le cours de l'or, coffret d'essai à domicile."
        ),
        "intro": (
            "Des lignes franches, un or massif généreux : nos alliances homme sont façonnées "
            "à la main dans notre atelier, en or 18 carats recyclé."
        ),
    },
    Ring.Gender.WOMEN: {
        "title": "Alliances femme en or",
        "meta_description": (
            "Alliances femme en or 18 carats, pavées ou lisses, fabriquées en France. Prix indexé "
            "sur le cours de l'or, coffret d'essai de 8 à 12 alliances."
        ),
        "intro": (
            "Fines, pavées de diamants ou d'une pureté minimaliste : des alliances femme pensées "
            "pour se porter toute une vie."
        ),
    },
}

ALL_RINGS_PAGE = {
    "title": "Toutes nos alliances en or",
    "meta_description": (
        "Alliances homme et femme en or 18 carats fabriquées en France, au prix indexé sur le "
        "cours de l'or. Essayez 8 à 12 modèles chez vous avec notre coffret d'essai."
    ),
    "intro": "L'ensemble de nos alliances, homme et femme, façonnées en or massif.",
}

FILTERS = {
    "couleur": ("metals__code", Ring.Color.choices),
    "titre": ("purity", Ring.Purity.choices),
    "profil": ("profile", Ring.Profile.choices),
}

SORTS = {
    "": ("Notre sélection", None),
    "prix-asc": ("Prix croissant", False),
    "prix-desc": ("Prix décroissant", True),
}


def _apply_filters(queryset, params):
    active = {}
    for param, (field, choices) in FILTERS.items():
        value = params.get(param)
        valid = {str(key) for key, _ in choices}
        if value in valid:
            if param == "couleur":
                # Metals offered, or the default colour when no metal list is set.
                condition = Q(metals__code=value) | Q(metals__isnull=True, color=value)
            else:
                condition = Q(**{field: value})
            queryset = queryset.filter(condition).distinct()
            active[param] = value
    return queryset, active


def ring_list(request, gender=None):
    rings = Ring.objects.filter(is_active=True)
    page = None
    if gender is not None:
        if gender not in GENDER_PAGES:
            raise Http404
        page = GENDER_PAGES[gender]
        rings = rings.filter(Q(gender=gender) | Q(gender=Ring.Gender.UNISEX))
    rings, active_filters = _apply_filters(rings, request.GET)

    items = [(ring, ring.starting_price) for ring in rings]
    sort = request.GET.get("tri", "")
    if sort in SORTS and SORTS[sort][1] is not None:
        items.sort(key=lambda item: item[1].price_ttc if item[1] else 0, reverse=SORTS[sort][1])
    else:
        sort = ""

    filter_groups = [
        {"param": param, "label": label, "choices": FILTERS[param][1], "active": active_filters.get(param)}
        for param, label in (("couleur", "Couleur"), ("titre", "Titre"), ("profil", "Profil"))
    ]
    return render(
        request,
        "catalog/ring_list.html",
        {
            "items": items,
            "gender": gender,
            "page": page or ALL_RINGS_PAGE,
            "filter_groups": filter_groups,
            "sorts": [(key, label) for key, (label, _) in SORTS.items()],
            "current_sort": sort,
        },
    )


def ring_detail(request, slug):
    ring = get_object_or_404(
        Ring.objects.select_related("family", "jewelry_case").prefetch_related("metals", "images", "stone_options"),
        slug=slug,
        is_active=True,
    )
    selection = resolve_selection(ring, request.GET)
    breakdown = ring.price(selection.size, stone=selection.stone)
    form = AddToCartForm(
        ring=ring,
        initial={
            "size": selection.size,
            "metal": selection.metal.code if selection.metal else "",
            "stone": selection.stone.pk if selection.stone else None,
        },
    )
    siblings = (
        Ring.objects.filter(family=ring.family, is_active=True).exclude(pk=ring.pk).prefetch_related("metals")
        if ring.family_id
        else Ring.objects.none()
    )
    collection = ring.collections.first()
    same_collection = (
        collection.rings.filter(is_active=True).exclude(pk=ring.pk).prefetch_related("metals")[:8]
        if collection
        else Ring.objects.filter(is_active=True, category=ring.category).exclude(pk=ring.pk)[:8]
    )
    reviews = Review.objects.filter(is_published=True)
    review_stats = reviews.aggregate(count=Count("pk"), average=Avg("rating"))
    product_reviews = ring.reviews.filter(is_published=True).aggregate(count=Count("pk"), average=Avg("rating"))
    return render(
        request,
        "catalog/ring_detail.html",
        {
            "ring": ring,
            "selection": selection,
            "size": selection.size,
            "selectors": selectors(selection),
            "gallery": ring.gallery(selection.metal),
            "breakdown": breakdown,
            "form": form,
            "delivery_date": ring.delivery_date(),
            "trial_sample": ring.trial_sample(),
            "siblings": [(r, r.starting_price) for r in siblings],
            "collection": collection,
            "same_collection": [(r, r.starting_price) for r in same_collection],
            "reviews": reviews[:12],
            "review_stats": review_stats,
            "product_reviews": product_reviews,
            "faqs": ProductFAQ.objects.filter(is_active=True),
            "reassurances": Reassurance.objects.all(),
        },
    )


def collection_detail(request, slug):
    collection = get_object_or_404(Collection, slug=slug)
    rings = collection.rings.filter(is_active=True).prefetch_related("metals")
    return render(
        request,
        "catalog/ring_list.html",
        {
            "items": [(ring, ring.starting_price) for ring in rings],
            "page": {
                "title": collection.name,
                "meta_description": collection.meta_description or collection.description[:160],
                "intro": collection.description,
            },
            "filter_groups": [],
            "sorts": [],
            "current_sort": "",
        },
    )

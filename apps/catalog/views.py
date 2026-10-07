from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from apps.orders.forms import AddToCartForm

from .models import Ring

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
    "couleur": ("color", Ring.Color.choices),
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
            queryset = queryset.filter(**{field: value})
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
    ring = get_object_or_404(Ring, slug=slug, is_active=True)
    size = request.GET.get("taille")
    try:
        size = int(size)
    except (TypeError, ValueError):
        size = ring.reference_size
    if not ring.is_valid_size(size):
        size = ring.reference_size
    related = (
        Ring.objects.filter(is_active=True, gender__in=[ring.gender, Ring.Gender.UNISEX])
        .exclude(pk=ring.pk)
        .order_by("-is_featured", "position")[:4]
    )
    return render(
        request,
        "catalog/ring_detail.html",
        {
            "ring": ring,
            "size": size,
            "breakdown": ring.price(size),
            "form": AddToCartForm(ring=ring, initial={"size": size}),
            "related": [(r, r.starting_price) for r in related],
        },
    )

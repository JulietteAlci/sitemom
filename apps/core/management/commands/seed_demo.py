from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from apps.blog.models import FAQ, Category, Post
from apps.catalog.models import Ring
from apps.pricing.models import GoldPrice

RINGS = [
    # name, gender, color, width, thickness, profile, finish, weight@54, stones, stone_cost, featured
    ("Éternelle", "femme", "jaune", "2.0", "1.6", "demi-jonc", "poli", "2.60", "", 0, True),
    ("Constance", "femme", "blanc", "2.5", "1.7", "confort", "poli", "3.30", "", 0, True),
    ("Aurore pavée", "femme", "rose", "2.2", "1.8", "plat", "poli", "2.90", "11 diamants 0,11 ct G/VS", 420, True),
    ("Lumière", "femme", "jaune", "1.5", "1.5", "demi-jonc", "brosse", "1.80", "", 0, False),
    ("Sérénité", "femme", "blanc", "3.0", "1.7", "bombe", "poli", "4.10", "1 diamant 0,03 ct", 120, False),
    ("Héritage", "homme", "jaune", "5.0", "2.0", "confort", "poli", "7.80", "", 0, True),
    ("Atelier", "homme", "blanc", "6.0", "2.0", "plat", "brosse", "9.40", "", 0, True),
    ("Rivage", "homme", "jaune", "4.5", "1.8", "bombe", "martele", "6.20", "", 0, False),
    ("Monolithe", "homme", "bicolore", "7.0", "2.2", "plat", "sable", "11.50", "", 0, False),
    ("Essentielle", "mixte", "jaune", "3.5", "1.8", "confort", "poli", "5.00", "", 0, True),
    ("Écho", "mixte", "rose", "4.0", "1.8", "demi-jonc", "poli", "5.60", "", 0, False),
    ("Origine", "mixte", "blanc", "4.0", "1.9", "confort", "brosse", "5.90", "", 0, False),
]

POSTS = [
    {
        "title": "Comment le cours de l'or influence le prix d'une alliance",
        "category": ("Guides d'achat", "guides"),
        "excerpt": (
            "Le prix d'une alliance en or dépend d'abord du poids d'or fin qu'elle contient et du cours spot "
            "de l'or. Une alliance 18 carats de 5 g contient 3,75 g d'or pur."
        ),
        "takeaways": (
            "L'or 18 carats contient 75 % d'or pur.\n"
            "Le cours spot de l'or est coté en once troy (31,10 g).\n"
            "Le poids d'une alliance augmente avec la largeur, l'épaisseur et la taille."
        ),
        "body": (
            "<h2>Le poids d'or fin, base du prix</h2><p>Une alliance n'est jamais en or pur : l'or 18 carats est un "
            "alliage contenant 750 millièmes d'or fin. Le reste (argent, cuivre, palladium) donne la couleur et la "
            "dureté.</p><h2>Le cours spot</h2><p>Le cours spot est le prix de l'or pour une livraison immédiate. "
            "Nous l'actualisons plusieurs fois par jour pour que le prix de votre alliance reflète la valeur réelle "
            "de son métal.</p><h2>La façon de l'atelier</h2><p>À la valeur de l'or s'ajoute le travail de l'artisan : "
            "fonte, mise en forme, polissage, gravure et poinçonnage.</p>"
        ),
        "faqs": [
            ("Pourquoi le prix de mon alliance change-t-il chaque jour ?",
             "Parce qu'il est indexé sur le cours de l'or, qui varie en continu sur les marchés."),
            ("Combien d'or contient une alliance 18 carats ?",
             "75 % de son poids : une alliance de 4 g contient 3 g d'or pur."),
        ],
    },
    {
        "title": "Quelle largeur d'alliance choisir ?",
        "category": ("Guides d'achat", "guides"),
        "excerpt": (
            "Les alliances femme mesurent le plus souvent entre 1,5 et 3 mm, les alliances homme entre 4 et 6 mm. "
            "La bonne largeur dépend de la morphologie de la main et de la bague de fiançailles."
        ),
        "takeaways": "Femme : 1,5 à 3 mm.\nHomme : 4 à 6 mm.\nUn profil confort facilite le port des largeurs importantes.",
        "body": (
            "<h2>Proportions de la main</h2><p>Des doigts fins mettent en valeur une alliance étroite ; des doigts "
            "longs supportent des largeurs généreuses.</p><h2>Avec une bague de fiançailles</h2><p>Choisissez une "
            "largeur égale ou légèrement inférieure à celle de l'anneau de la bague de fiançailles.</p>"
        ),
        "faqs": [("Le coffret d'essai permet-il de comparer les largeurs ?",
                  "Oui, choisissez plusieurs largeurs d'un même modèle pour les comparer au doigt.")],
    },
]


class Command(BaseCommand):
    help = "Create demo rings, blog posts and a gold spot price."

    def handle(self, *args, **options):
        current = GoldPrice.current()
        if current is None or not current.is_fresh:
            # A stale quote blocks payments: re-date the demo quote so the purchase flow can be tested.
            price = current.price_per_oz_eur if current else Decimal("3500")
            GoldPrice.objects.create(price_per_oz_eur=price, source="manual", fetched_at=timezone.now())
            self.stdout.write(f"Cours de l'or de démonstration : {price:.0f} €/oz")

        for position, (name, gender, color, width, thickness, profile, finish, weight, stones, stone_cost, featured) in enumerate(RINGS):
            slug = slugify(f"alliance {name}")
            Ring.objects.update_or_create(
                slug=slug,
                defaults=dict(
                    name=name,
                    gender=gender,
                    color=color,
                    width_mm=Decimal(width),
                    thickness_mm=Decimal(thickness),
                    profile=profile,
                    finish=finish,
                    reference_weight_g=Decimal(weight),
                    stones=stones,
                    stone_cost=Decimal(stone_cost),
                    is_featured=featured,
                    position=position,
                    short_description=f"Alliance {gender} en {dict(Ring.Color.choices)[color].lower()} 18 carats, "
                    f"{width.replace('.', ',')} mm, profil {dict(Ring.Profile.choices)[profile].lower()}.",
                ),
            )
        self.stdout.write(f"{len(RINGS)} alliances créées ou mises à jour")

        for data in POSTS:
            category, _ = Category.objects.get_or_create(
                slug=data["category"][1], defaults={"name": data["category"][0]}
            )
            post, _ = Post.objects.update_or_create(
                slug=slugify(data["title"]),
                defaults=dict(
                    title=data["title"],
                    category=category,
                    excerpt=data["excerpt"],
                    key_takeaways=data["takeaways"],
                    body=data["body"],
                    status=Post.Status.PUBLISHED,
                ),
            )
            post.faqs.all().delete()
            FAQ.objects.bulk_create(
                FAQ(post=post, question=q, answer=a, position=i) for i, (q, a) in enumerate(data["faqs"])
            )
            post.related_rings.set(Ring.objects.filter(is_featured=True)[:4])
        self.stdout.write(self.style.SUCCESS(f"{len(POSTS)} articles créés ou mis à jour"))

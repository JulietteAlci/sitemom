from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from apps.blog.models import FAQ, Category, Post
from apps.catalog.models import (
    Collection,
    JewelryCase,
    Metal,
    ModelFamily,
    ProductFAQ,
    Reassurance,
    Review,
    Ring,
    StoneOption,
)
from apps.pricing.models import GoldPrice
from apps.trialkit.models import SampleRing

# Diamond cost per carat option (€ HT, purchase price): natural / lab-grown.
DIAMOND_CARATS = [
    ("0.10", 110, 40), ("0.15", 170, 55), ("0.20", 240, 70), ("0.25", 320, 90), ("0.30", 420, 110),
    ("0.40", 700, 160), ("0.50", 1050, 210), ("0.70", 1900, 320), ("0.90", 2800, 430), ("1.00", 3600, 520),
]
# Coloured centre stones: (main_stone, product label, cost per carat option).
GEMSTONES = [
    ("saphir", "saphir", [("0.30", 160), ("0.50", 300)]),
    ("rubis", "rubis", [("0.30", 190), ("0.50", 360)]),
    ("emeraude", "émeraude", [("0.30", 180), ("0.50", 340)]),
    ("diamant-noir", "diamant noir", [("0.30", 90), ("0.50", 150)]),
]

STORY = (
    "Chaque bijou est dessiné, fondu, serti et poli dans notre atelier, en or 18 carats recyclé. "
    "Nous maîtrisons toutes les étapes en interne pour garantir des lignes nettes, une tenue exemplaire "
    "et une finition irréprochable.\n\n"
    "Nos prix suivent le cours de l'or : vous payez le juste poids d'or de votre bijou, plus le travail de l'artisan."
)

PRODUCT_FAQ = [
    ("Comment connaître ma taille de bague ?",
     "Mesurez le tour d'une bague que vous portez déjà au même doigt, ou demandez notre coffret d'essai : "
     "il contient un baguier. Votre taille correspond à votre tour de doigt en millimètres."),
    ("Diamant naturel ou de synthèse : quelle différence ?",
     "Les deux ont la même composition et le même éclat. Le diamant de synthèse est créé en laboratoire, "
     "il est nettement moins cher à poids égal."),
    ("Pourquoi le prix change-t-il d'un jour à l'autre ?",
     "Le prix de l'or de votre bijou suit le cours de l'or. Le prix affiché est garanti 30 minutes une fois "
     "le paiement engagé."),
    ("Quels sont les délais de fabrication ?",
     "La date de livraison maximale est indiquée sur chaque fiche produit. Besoin d'aller plus vite ? Contactez-nous."),
    ("Comment mon bijou est-il livré ?",
     "Dans son écrin, avec son certificat d'authenticité, par envoi assuré et dans un colis neutre."),
]

REASSURANCES = [
    ("Livraison sécurisée offerte", "Envoi assuré dans un colis neutre, sans minimum d'achat.", "truck"),
    ("Gravure offerte", "Personnalisez l'intérieur de votre bijou sans frais.", "ring"),
    ("Prix au cours de l'or", "Vous payez le juste poids d'or de votre bijou.", "gold"),
    ("Fabrication française", "Chaque bijou est façonné à la main dans notre atelier.", "sparkle"),
]

# Demo reviews: clearly labelled, replace them with genuine customer reviews before going live.
DEMO_REVIEWS = [
    ("Avis de démonstration", 5, "Exemple d'avis client : remplacez-moi par un véritable avis dans l'administration."),
    ("Avis de démonstration", 5, "Les avis affichés doivent provenir de vrais clients (obligation légale)."),
    ("Avis de démonstration", 4, "Vous pouvez importer vos avis depuis votre outil d'avis vérifiés."),
]

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
        self.seed_product_structure()
        self.seed_samples()

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

    def seed_product_structure(self):
        metals = {metal.code: metal for metal in Metal.objects.all()}
        golds = [metals[code] for code in ("jaune", "blanc", "rose") if code in metals]
        bands, _ = Collection.objects.update_or_create(
            slug="alliances", defaults={"name": "Alliances", "position": 0,
                                        "description": "Alliances homme et femme en or 18 carats."}
        )
        solitaires, _ = Collection.objects.update_or_create(
            slug="bagues-solitaires", defaults={"name": "Bagues solitaires", "position": 1,
                                                "description": "Solitaires en or 18 carats, pierre centrale au choix."}
        )
        case, _ = JewelryCase.objects.update_or_create(
            name="Écrin de la maison",
            defaults={"description": "Écrin en bois laqué et velours, livré avec son certificat d'authenticité."},
        )
        for ring in Ring.objects.filter(category=Ring.Category.WEDDING_BAND):
            ring.collections.add(bands)
            if ring.color != "bicolore":
                ring.metals.set(golds)
            ring.jewelry_case = ring.jewelry_case or case
            ring.story = ring.story or STORY
            ring.save()

        family, _ = ModelFamily.objects.get_or_create(name="Éclat")
        common = dict(
            category=Ring.Category.SOLITAIRE, gender=Ring.Gender.WOMEN, family=family, color="jaune",
            width_mm=Decimal("1.8"), thickness_mm=Decimal("1.6"), profile="demi-jonc", finish="poli",
            reference_weight_g=Decimal("2.40"), labor_cost=Decimal("240"), engraving_max_length=100,
            lead_time_days=21, jewelry_case=case, story=STORY,
        )
        products = [("diamant", "diamant", None)] + GEMSTONES
        for position, (stone, label, carats) in enumerate(products):
            ring, _ = Ring.objects.update_or_create(
                slug=slugify(f"solitaire {label} eclat"),
                defaults=dict(
                    common,
                    name=f"Solitaire {label} Éclat",
                    main_stone=stone,
                    position=100 + position,
                    is_featured=stone == "diamant",
                    short_description=f"Solitaire en or 18 carats serti d'un {label} sur six griffes.",
                    description=(
                        f"Un anneau fin qui s'affine vers la pierre et un {label} tenu par six griffes : "
                        "un dessin intemporel, conçu pour s'accorder avec une alliance."
                    ),
                ),
            )
            ring.collections.set([solitaires])
            ring.metals.set(golds)
            ring.stone_options.all().delete()
            if stone == "diamant":
                options = []
                for carat, natural, lab in DIAMOND_CARATS:
                    options.append(StoneOption(ring=ring, stone_type="naturel", carat=Decimal(carat),
                                               price=Decimal(natural), color_grade="G", clarity="VS"))
                    options.append(StoneOption(ring=ring, stone_type="synthese", carat=Decimal(carat),
                                               price=Decimal(lab), color_grade="F", clarity="VS1"))
            else:
                options = [StoneOption(ring=ring, stone_type="naturel", carat=Decimal(carat), price=Decimal(cost))
                           for carat, cost in carats]
            StoneOption.objects.bulk_create(options)

        for position, (question, answer) in enumerate(PRODUCT_FAQ):
            ProductFAQ.objects.update_or_create(question=question, defaults={"answer": answer, "position": position})
        for position, (title, text, icon) in enumerate(REASSURANCES):
            Reassurance.objects.update_or_create(title=title, defaults={"text": text, "icon": icon, "position": position})
        if not Review.objects.exists():
            Review.objects.bulk_create(
                Review(author=author, rating=rating, text=text, verified_purchase=False)
                for author, rating, text in DEMO_REVIEWS
            )
        self.stdout.write("Collections, solitaires Éclat (5 pierres), FAQ, réassurance et avis de démonstration créés")

    def seed_samples(self):
        """Internal references for real rings + a stock of dummies for the trial kits."""
        created = 0
        for ring in Ring.objects.filter(is_active=True):
            prefix = "SOL" if ring.category == Ring.Category.SOLITAIRE else "ALL"
            if not ring.sku:
                ring.sku = f"{prefix}-{ring.pk:03d}"
                ring.save(update_fields=["sku"])
            # Dummies: 3 units per model, a single one for "Lumière" to show an out-of-stock model.
            _, was_created = SampleRing.objects.get_or_create(
                ring=ring,
                defaults={
                    "reference": f"FAC-{ring.sku}",
                    "quantity": 1 if ring.name == "Lumière" else 3,
                    "size": 54,
                },
            )
            created += was_created
        self.stdout.write(f"Références et stock de factices prêts ({created} factice(s) créé(s))")

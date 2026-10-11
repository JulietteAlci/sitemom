from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

from apps.pricing.services import compute_ring_price


class Metal(models.Model):
    """A gold colour offered by the "Métal" selector (all golds share the ring's purity)."""

    code = models.SlugField(unique=True, max_length=20)
    name = models.CharField("nom", max_length=40)
    swatch = models.CharField("pastille (couleur CSS)", max_length=20, default="#d4af37")
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "name"]
        verbose_name = "métal"

    def __str__(self):
        return self.name


class Collection(models.Model):
    """Merchandising group, e.g. "Bagues solitaires" ("Dans la même collection")."""

    name = models.CharField("nom", max_length=120)
    slug = models.SlugField(unique=True, max_length=140)
    description = models.TextField(blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    meta_description = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ["position", "name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("catalog:collection", kwargs={"slug": self.slug})


class ModelFamily(models.Model):
    """Same design declined with other stones ("Existe aussi en")."""

    name = models.CharField("nom", max_length=120)

    class Meta:
        verbose_name = "famille de modèle"
        verbose_name_plural = "familles de modèles"

    def __str__(self):
        return self.name


class JewelryCase(models.Model):
    """Presentation box shown in the "Écrin" tab."""

    name = models.CharField("nom", max_length=120)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="cases/", blank=True)

    class Meta:
        verbose_name = "écrin"

    def __str__(self):
        return self.name


class Ring(models.Model):
    class Category(models.TextChoices):
        WEDDING_BAND = "alliance", "Alliance"
        SOLITAIRE = "solitaire", "Solitaire"
        RING = "bague", "Bague"

    class MainStone(models.TextChoices):
        NONE = "", "Sans pierre centrale"
        DIAMOND = "diamant", "Diamant"
        BLACK_DIAMOND = "diamant-noir", "Diamant noir"
        SAPPHIRE = "saphir", "Saphir"
        RUBY = "rubis", "Rubis"
        EMERALD = "emeraude", "Émeraude"
        OTHER = "autre", "Autre pierre"

    class Gender(models.TextChoices):
        MEN = "homme", "Homme"
        WOMEN = "femme", "Femme"
        UNISEX = "mixte", "Mixte"

    class Purity(models.IntegerChoices):
        K9 = 375, "9 carats (375‰)"
        K14 = 585, "14 carats (585‰)"
        K18 = 750, "18 carats (750‰)"
        K22 = 916, "22 carats (916‰)"

    class Color(models.TextChoices):
        YELLOW = "jaune", "Or jaune"
        WHITE = "blanc", "Or blanc"
        ROSE = "rose", "Or rose"
        BICOLOR = "bicolore", "Bicolore"

    class Profile(models.TextChoices):
        FLAT = "plat", "Plat"
        HALF_ROUND = "demi-jonc", "Demi-jonc"
        COMFORT = "confort", "Confort"
        DOMED = "bombe", "Bombé"

    class Finish(models.TextChoices):
        POLISHED = "poli", "Poli miroir"
        BRUSHED = "brosse", "Brossé"
        HAMMERED = "martele", "Martelé"
        SANDBLASTED = "sable", "Sablé"

    name = models.CharField("nom", max_length=120)
    slug = models.SlugField(unique=True, max_length=140)
    sku = models.CharField(
        "référence", max_length=40, blank=True, db_index=True,
        help_text="Référence interne (ex. SOL-ECL-01) : sert à remplir les coffrets d'essai.",
    )
    category = models.CharField("catégorie", max_length=12, choices=Category.choices, default=Category.WEDDING_BAND)
    gender = models.CharField("genre", max_length=10, choices=Gender.choices, db_index=True)
    collections = models.ManyToManyField(Collection, blank=True, related_name="rings")
    family = models.ForeignKey(
        ModelFamily, on_delete=models.SET_NULL, null=True, blank=True, related_name="rings",
        verbose_name="famille de modèle", help_text="Regroupe les déclinaisons d'un même dessin (« Existe aussi en »).",
    )
    main_stone = models.CharField("pierre centrale", max_length=14, choices=MainStone.choices, blank=True)
    color = models.CharField(
        "couleur par défaut", max_length=10, choices=Color.choices, default=Color.YELLOW,
        help_text="Couleur présélectionnée et utilisée pour le visuel.",
    )
    metals = models.ManyToManyField(
        Metal, blank=True, related_name="rings", verbose_name="métaux proposés",
        help_text="Choix du sélecteur « Métal ». Vide = couleur par défaut uniquement.",
    )
    purity = models.PositiveSmallIntegerField("titre", choices=Purity.choices, default=Purity.K18)
    profile = models.CharField("profil", max_length=12, choices=Profile.choices, default=Profile.COMFORT)
    finish = models.CharField("finition", max_length=10, choices=Finish.choices, default=Finish.POLISHED)
    width_mm = models.DecimalField("largeur (mm)", max_digits=4, decimal_places=1)
    thickness_mm = models.DecimalField("épaisseur (mm)", max_digits=4, decimal_places=1)
    stones = models.CharField("pierres", max_length=200, blank=True, help_text="Ex. : 5 diamants 0,05 ct G/VS")

    short_description = models.CharField("accroche", max_length=200)
    description = models.TextField("onglet Description", blank=True)
    details = models.TextField("onglet Détails (complément)", blank=True, help_text="Ajouté sous le tableau technique.")
    story = models.TextField(
        "bloc « histoire »", blank=True, help_text="Texte de la section éditoriale sous la fiche (savoir-faire, atelier…).",
    )
    jewelry_case = models.ForeignKey(
        JewelryCase, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="écrin"
    )
    image = models.ImageField("visuel principal", upload_to="rings/", blank=True)
    lead_time_days = models.PositiveSmallIntegerField(
        "délai de fabrication et livraison (jours)", default=21,
        help_text="Sert à afficher « Livré au plus tard le … ».",
    )

    # --- Pricing inputs (price is indexed on the gold spot, never stored) ---
    reference_size = models.PositiveSmallIntegerField(
        "taille de référence",
        default=54,
        validators=[MinValueValidator(40), MaxValueValidator(75)],
        help_text="Tour de doigt (mm) pour lequel le poids de référence est mesuré.",
    )
    reference_weight_g = models.DecimalField(
        "poids de référence (g)",
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.1"))],
        help_text="Poids de l'alliance finie à la taille de référence.",
    )
    size_min = models.PositiveSmallIntegerField("taille min.", default=44)
    size_max = models.PositiveSmallIntegerField("taille max.", default=72)
    labor_cost = models.DecimalField("façon (€ HT)", max_digits=8, decimal_places=2, default=Decimal("180"))
    stone_cost = models.DecimalField(
        "petites pierres (€ HT)", max_digits=8, decimal_places=2, default=Decimal("0"),
        help_text="Pavage ou pierres fixes. La pierre centrale au choix se règle dans « Options de pierre ».",
    )
    gold_markup_rate = models.DecimalField(
        "prime métal",
        max_digits=4,
        decimal_places=3,
        default=Decimal("0.080"),
        help_text="Prime sur la valeur de l'or (pertes de fonte, affinage). 0,080 = 8 %.",
    )
    margin_rate = models.DecimalField(
        "marge", max_digits=4, decimal_places=3, default=Decimal("0.450"), help_text="0,450 = 45 %."
    )

    engravable = models.BooleanField("gravure possible", default=True)
    engraving_max_length = models.PositiveSmallIntegerField(
        "caractères de gravure max.", default=40, validators=[MaxValueValidator(100)]
    )
    is_featured = models.BooleanField("mise en avant", default=False)
    is_active = models.BooleanField("en ligne", default=True)
    position = models.PositiveIntegerField(default=0)

    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "name"]
        verbose_name = "bijou"
        verbose_name_plural = "bijoux"

    def __str__(self):
        return self.name

    def trial_sample(self):
        """An active dummy of this ring with at least one unit on the shelf, if any."""
        return self.samples.filter(is_active=True).with_availability().filter(available__gt=0).first()

    @property
    def reference(self) -> str:
        return self.sku or self.slug.upper()

    def clean(self):
        if self.size_min and self.size_max and self.size_min > self.size_max:
            raise ValidationError({"size_max": "La taille max. doit être supérieure à la taille min."})
        if self.reference_size and not (self.size_min <= self.reference_size <= self.size_max):
            raise ValidationError({"reference_size": "La taille de référence doit être dans la plage de tailles."})

    def get_absolute_url(self):
        return reverse("catalog:ring_detail", kwargs={"slug": self.slug})

    @property
    def sizes(self):
        return range(self.size_min, self.size_max + 1)

    def is_valid_size(self, size) -> bool:
        return isinstance(size, int) and self.size_min <= size <= self.size_max

    def weight_for_size(self, size: int) -> Decimal:
        """Weight grows linearly with the finger circumference (French size = circumference in mm)."""
        return self.reference_weight_g * Decimal(size) / Decimal(self.reference_size)

    def price(self, size: int | None = None, spot=None, stone=None):
        return compute_ring_price(self, size, spot, stone)

    @property
    def cheapest_stone(self):
        return self.stone_options.order_by("price", "carat").first()

    @property
    def starting_price(self):
        """Lowest price: smallest size with the cheapest stone option."""
        return self.price(self.size_min, stone=self.cheapest_stone)

    def available_metals(self) -> list[Metal]:
        metals = list(self.metals.all())
        if not metals:
            metals = list(Metal.objects.filter(code=self.color))
        return metals

    def default_metal(self) -> Metal | None:
        metals = self.available_metals()
        return next((m for m in metals if m.code == self.color), metals[0] if metals else None)

    def gallery(self, metal: Metal | None = None) -> list:
        """Images for the selected metal, plus the ones common to all metals."""
        images = [img for img in self.images.all() if img.metal_id in (None, getattr(metal, "pk", None))]
        return images or [img for img in self.images.all() if img.metal_id is None]

    @property
    def cover_image(self):
        if self.image:
            return self.image
        first = self.images.filter(metal__code=self.color).first() or self.images.first()
        return first.image if first else None

    def delivery_date(self, today=None):
        from datetime import timedelta

        from django.utils import timezone

        return (today or timezone.localdate()) + timedelta(days=self.lead_time_days)

    @property
    def carats(self) -> int:
        return round(self.purity * 24 / 1000)

    @property
    def seo_title(self):
        return self.meta_title or (
            f"{self.name} — {self.get_category_display().lower()} en {self.get_color_display().lower()} {self.carats} carats"
        )

    @property
    def seo_description(self):
        return self.meta_description or self.short_description


class StoneOption(models.Model):
    """One choice of the "Type de pierre" × "Poids carat" selectors, with its price."""

    class StoneType(models.TextChoices):
        NATURAL = "naturel", "Naturelle"
        LAB_GROWN = "synthese", "De synthèse"

    ring = models.ForeignKey(Ring, on_delete=models.CASCADE, related_name="stone_options")
    stone_type = models.CharField("type de pierre", max_length=10, choices=StoneType.choices, default=StoneType.NATURAL)
    carat = models.DecimalField("poids carat", max_digits=4, decimal_places=2)
    color_grade = models.CharField("couleur", max_length=10, blank=True, help_text="Ex. : G, F-G")
    clarity = models.CharField("pureté", max_length=10, blank=True, help_text="Ex. : VS1, SI")
    price = models.DecimalField(
        "coût de la pierre (€ HT)", max_digits=9, decimal_places=2,
        help_text="Prix d'achat : la marge et la TVA sont appliquées par le calcul.",
    )
    position = models.PositiveSmallIntegerField(default=0)

    CERTIFICATE_THRESHOLD = Decimal("0.30")

    class Meta:
        ordering = ["stone_type", "carat"]
        verbose_name = "option de pierre"
        verbose_name_plural = "options de pierre"
        constraints = [
            models.UniqueConstraint(fields=["ring", "stone_type", "carat"], name="unique_stone_option"),
        ]

    def __str__(self):
        return f"{self.type_label} {self.carat_label}"

    @property
    def type_label(self) -> str:
        stone = self.ring.get_main_stone_display() if self.ring.main_stone else "Pierre"
        suffix = "naturel" if self.stone_type == self.StoneType.NATURAL else "de synthèse"
        if self.ring.main_stone not in (Ring.MainStone.DIAMOND, Ring.MainStone.BLACK_DIAMOND):
            suffix = "naturelle" if self.stone_type == self.StoneType.NATURAL else "de synthèse"
        return f"{stone} {suffix}"

    @property
    def carat_label(self) -> str:
        return ("1 carat" if self.carat == 1 else f"{self.carat:.2f} carat".replace(".", ",")) if self.carat else ""

    @property
    def requires_lab_certificate(self) -> bool:
        return self.ring.main_stone == Ring.MainStone.DIAMOND and self.carat > self.CERTIFICATE_THRESHOLD


class RingImage(models.Model):
    ring = models.ForeignKey(Ring, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="rings/gallery/")
    alt = models.CharField("texte alternatif", max_length=200, blank=True)
    metal = models.ForeignKey(
        Metal, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Afficher seulement pour ce métal (vide = tous les métaux).",
    )
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "pk"]
        verbose_name = "photo"

    def __str__(self):
        return self.alt or self.image.name


class Review(models.Model):
    """Customer review. Shop-wide unless attached to a product. Only publish genuine reviews."""

    ring = models.ForeignKey(Ring, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviews")
    author = models.CharField("auteur", max_length=80, help_text="Ex. : Claire M.")
    rating = models.PositiveSmallIntegerField("note", validators=[MinValueValidator(1), MaxValueValidator(5)])
    text = models.TextField("avis")
    date = models.DateField(default=date.today)
    verified_purchase = models.BooleanField("achat vérifié", default=True)
    is_published = models.BooleanField("publié", default=True)

    class Meta:
        ordering = ["-date", "-pk"]
        verbose_name = "avis client"
        verbose_name_plural = "avis clients"

    def __str__(self):
        return f"{self.author} — {self.rating}/5"


class ProductFAQ(models.Model):
    """Questions shown at the bottom of every product page."""

    question = models.CharField(max_length=255)
    answer = models.TextField("réponse")
    position = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField("affichée", default=True)

    class Meta:
        ordering = ["position", "pk"]
        verbose_name = "question fréquente (fiches produit)"
        verbose_name_plural = "questions fréquentes (fiches produit)"

    def __str__(self):
        return self.question


class Reassurance(models.Model):
    """Reassurance block shown on product pages (free delivery, engraving…)."""

    class Icon(models.TextChoices):
        RING = "ring", "Bague"
        TRUCK = "truck", "Livraison"
        SHIELD = "shield", "Garantie"
        SPARKLE = "sparkle", "Étoile"
        GOLD = "gold", "Lingot"

    title = models.CharField("titre", max_length=80)
    text = models.CharField("texte", max_length=255)
    icon = models.CharField(max_length=10, choices=Icon.choices, default=Icon.SPARKLE)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "pk"]
        verbose_name = "bloc de réassurance"
        verbose_name_plural = "blocs de réassurance"

    def __str__(self):
        return self.title

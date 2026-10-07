from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

from apps.pricing.services import compute_ring_price


class Ring(models.Model):
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
    gender = models.CharField("genre", max_length=10, choices=Gender.choices, db_index=True)
    color = models.CharField("couleur", max_length=10, choices=Color.choices, default=Color.YELLOW)
    purity = models.PositiveSmallIntegerField("titre", choices=Purity.choices, default=Purity.K18)
    profile = models.CharField("profil", max_length=12, choices=Profile.choices, default=Profile.COMFORT)
    finish = models.CharField("finition", max_length=10, choices=Finish.choices, default=Finish.POLISHED)
    width_mm = models.DecimalField("largeur (mm)", max_digits=4, decimal_places=1)
    thickness_mm = models.DecimalField("épaisseur (mm)", max_digits=4, decimal_places=1)
    stones = models.CharField("pierres", max_length=200, blank=True, help_text="Ex. : 5 diamants 0,05 ct G/VS")

    short_description = models.CharField("accroche", max_length=200)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="rings/", blank=True)

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
    stone_cost = models.DecimalField("pierres (€ HT)", max_digits=8, decimal_places=2, default=Decimal("0"))
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
    available_for_trial = models.BooleanField("disponible en coffret d'essai", default=True)
    is_featured = models.BooleanField("mise en avant", default=False)
    is_active = models.BooleanField("en ligne", default=True)
    position = models.PositiveIntegerField(default=0)

    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "name"]
        verbose_name = "alliance"

    def __str__(self):
        return self.name

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

    def price(self, size: int | None = None, spot=None):
        return compute_ring_price(self, size, spot)

    @property
    def starting_price(self):
        """Lowest price across available sizes (smallest size)."""
        return self.price(self.size_min)

    @property
    def carats(self) -> int:
        return round(self.purity * 24 / 1000)

    @property
    def seo_title(self):
        return self.meta_title or f"{self.name} — alliance {self.get_color_display().lower()} {self.carats} carats"

    @property
    def seo_description(self):
        return self.meta_description or self.short_description

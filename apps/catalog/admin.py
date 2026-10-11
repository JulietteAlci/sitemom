from django.contrib import admin

from .models import (
    Collection,
    JewelryCase,
    Metal,
    ModelFamily,
    ProductFAQ,
    Reassurance,
    Review,
    Ring,
    RingImage,
    StoneOption,
)


class StoneOptionInline(admin.TabularInline):
    model = StoneOption
    extra = 0
    fields = ("stone_type", "carat", "color_grade", "clarity", "price", "position")


class RingImageInline(admin.TabularInline):
    model = RingImage
    extra = 1
    fields = ("image", "alt", "metal", "position")


@admin.register(Ring)
class RingAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "gender",
        "main_stone",
        "purity",
        "reference_weight_g",
        "current_price",
        "is_featured",
        "is_active",
        "position",
    )
    list_editable = ("is_featured", "is_active", "position")
    list_filter = ("category", "gender", "main_stone", "collections", "metals", "is_active", "available_for_trial")
    search_fields = ("name", "short_description")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("collections", "metals")
    autocomplete_fields = ("family",)
    inlines = [StoneOptionInline, RingImageInline]
    fieldsets = (
        (None, {"fields": ("name", "slug", "category", "gender", "collections", "family", "short_description")}),
        ("Onglets et textes", {"fields": ("description", "details", "jewelry_case", "story")}),
        ("Visuel", {"fields": ("image",)}),
        (
            "Caractéristiques",
            {"fields": ("metals", "color", "purity", "main_stone", "profile", "finish", "width_mm", "thickness_mm", "stones")},
        ),
        (
            "Prix indexé sur l'or",
            {
                "fields": (
                    ("reference_size", "reference_weight_g"),
                    ("size_min", "size_max"),
                    ("labor_cost", "stone_cost"),
                    ("gold_markup_rate", "margin_rate"),
                ),
                "description": "Le prix de vente n'est jamais saisi : il est recalculé à partir du dernier cours spot. "
                "Le coût de la pierre centrale choisie (options de pierre ci-dessous) s'y ajoute.",
            },
        ),
        (
            "Options",
            {
                "fields": (
                    ("engravable", "engraving_max_length"),
                    "lead_time_days",
                    "available_for_trial",
                    "is_featured",
                    "is_active",
                    "position",
                )
            },
        ),
        ("SEO", {"fields": ("meta_title", "meta_description"), "classes": ("collapse",)}),
    )

    @admin.display(description="Prix actuel (dès)")
    def current_price(self, obj):
        breakdown = obj.starting_price
        return f"{breakdown.price_ttc} €" if breakdown else "—"


@admin.register(Metal)
class MetalAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "swatch", "position")
    list_editable = ("position",)


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "position")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ModelFamily)
class ModelFamilyAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(JewelryCase)
class JewelryCaseAdmin(admin.ModelAdmin):
    list_display = ("name",)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("author", "rating", "date", "ring", "verified_purchase", "is_published")
    list_filter = ("rating", "is_published", "verified_purchase")
    list_editable = ("is_published",)
    search_fields = ("author", "text")


@admin.register(ProductFAQ)
class ProductFAQAdmin(admin.ModelAdmin):
    list_display = ("question", "position", "is_active")
    list_editable = ("position", "is_active")


@admin.register(Reassurance)
class ReassuranceAdmin(admin.ModelAdmin):
    list_display = ("title", "icon", "position")
    list_editable = ("position",)

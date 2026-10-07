from django.contrib import admin

from .models import Ring


@admin.register(Ring)
class RingAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "gender",
        "color",
        "purity",
        "width_mm",
        "reference_weight_g",
        "current_price",
        "is_featured",
        "is_active",
        "position",
    )
    list_editable = ("is_featured", "is_active", "position")
    list_filter = ("gender", "color", "purity", "is_active", "available_for_trial")
    search_fields = ("name", "short_description")
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        (None, {"fields": ("name", "slug", "gender", "short_description", "description", "image")}),
        ("Caractéristiques", {"fields": ("color", "purity", "profile", "finish", "width_mm", "thickness_mm", "stones")}),
        (
            "Prix indexé sur l'or",
            {
                "fields": (
                    ("reference_size", "reference_weight_g"),
                    ("size_min", "size_max"),
                    ("labor_cost", "stone_cost"),
                    ("gold_markup_rate", "margin_rate"),
                ),
                "description": "Le prix de vente n'est jamais saisi : il est recalculé à partir du dernier cours spot.",
            },
        ),
        ("Options", {"fields": ("engravable", "available_for_trial", "is_featured", "is_active", "position")}),
        ("SEO", {"fields": ("meta_title", "meta_description"), "classes": ("collapse",)}),
    )

    @admin.display(description="Prix actuel (taille réf.)")
    def current_price(self, obj):
        breakdown = obj.price()
        return f"{breakdown.price_ttc} €" if breakdown else "—"

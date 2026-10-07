from django.contrib import admin

from .models import GoldPrice


@admin.register(GoldPrice)
class GoldPriceAdmin(admin.ModelAdmin):
    list_display = ("fetched_at", "price_per_oz_eur", "price_per_gram", "source")
    list_filter = ("source",)
    date_hierarchy = "fetched_at"

    @admin.display(description="€/g (24 carats)")
    def price_per_gram(self, obj):
        return f"{obj.price_per_gram_eur:.2f}"

    def get_changeform_initial_data(self, request):
        return {"source": "manual"}

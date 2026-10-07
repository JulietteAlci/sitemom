from django.contrib import admin

from .models import FAQ, Category, Post


class FAQInline(admin.TabularInline):
    model = FAQ
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "status", "published_at")
    list_filter = ("status", "category")
    search_fields = ("title", "excerpt", "body")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("related_rings",)
    date_hierarchy = "published_at"
    inlines = [FAQInline]
    fieldsets = (
        (None, {"fields": ("title", "slug", "category", "author_name", "cover")}),
        ("Contenu", {"fields": ("excerpt", "key_takeaways", "body", "related_rings")}),
        ("SEO", {"fields": ("meta_title", "meta_description")}),
        ("Publication", {"fields": ("status", "published_at")}),
    )

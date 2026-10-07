from django.urls import path

from . import views

app_name = "pricing"

urlpatterns = [
    path("", views.gold_price_page, name="gold_price"),
    path("api/", views.gold_price_api, name="gold_price_api"),
]

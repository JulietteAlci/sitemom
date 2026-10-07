from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("panier/", views.cart_detail, name="cart"),
    path("panier/ajouter/<slug:slug>/", views.cart_add, name="cart_add"),
    path("panier/retirer/<str:line_id>/", views.cart_remove, name="cart_remove"),
    path("commande/paiement/", views.checkout, name="checkout"),
    path("commande/confirmation/", views.checkout_success, name="success"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
]

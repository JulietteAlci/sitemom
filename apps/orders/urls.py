from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("panier/", views.cart_detail, name="cart"),
    path("panier/ajouter/<slug:slug>/", views.cart_add, name="cart_add"),
    path("panier/code-coffret/", views.cart_trial_kit_code, name="cart_trial_kit_code"),
    path("panier/retirer/<str:line_id>/", views.cart_remove, name="cart_remove"),
    path("commande/paiement/", views.checkout, name="checkout"),
    path("commande/confirmation/", views.checkout_success, name="success"),
    path("paiement-demo/<str:session_id>/", views.demo_checkout, name="demo_checkout"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
]

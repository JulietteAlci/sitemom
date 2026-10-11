from django.urls import path

from . import views

app_name = "trialkit"

urlpatterns = [
    path("", views.trial_kit, name="start"),
    path("confirmation/", views.trial_kit_success, name="success"),
    path("etiquette-retour/<str:token>/", views.return_label, name="return_label"),
]

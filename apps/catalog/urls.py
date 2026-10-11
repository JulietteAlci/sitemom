from django.urls import path

from . import views
from .models import Ring

app_name = "catalog"

urlpatterns = [
    path("", views.ring_list, name="ring_list"),
    path("homme/", views.ring_list, {"gender": Ring.Gender.MEN}, name="men"),
    path("femme/", views.ring_list, {"gender": Ring.Gender.WOMEN}, name="women"),
    path("collection/<slug:slug>/", views.collection_detail, name="collection"),
    path("<slug:slug>/", views.ring_detail, name="ring_detail"),
]

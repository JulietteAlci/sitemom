from django.contrib import admin
from django.urls import path

from apps.trialkit import views as trialkit_views

from . import views

app_name = "backoffice"

urlpatterns = [
    path("", admin.site.admin_view(views.task_list), name="tasks"),
    path("action/", admin.site.admin_view(views.task_action), name="task_action"),
    path("coffret/<int:pk>/bon-envoi/", admin.site.admin_view(trialkit_views.packing_slip), name="kit_packing_slip"),
    path(
        "coffret/<int:pk>/etiquette-retour/",
        admin.site.admin_view(trialkit_views.return_label_staff),
        name="kit_return_label",
    ),
]

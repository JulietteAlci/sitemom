from django.contrib import admin
from django.urls import path

from . import views

app_name = "backoffice"

urlpatterns = [
    path("", admin.site.admin_view(views.task_list), name="tasks"),
    path("action/", admin.site.admin_view(views.task_action), name="task_action"),
]

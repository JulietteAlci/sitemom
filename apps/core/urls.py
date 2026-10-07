from django.urls import path
from django.views.generic import TemplateView

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("robots.txt", views.robots_txt, name="robots"),
    path("llms.txt", views.llms_txt, name="llms"),
    path("mentions-legales/", TemplateView.as_view(template_name="core/legal.html"), name="legal"),
    path("cgv/", TemplateView.as_view(template_name="core/terms.html"), name="terms"),
]

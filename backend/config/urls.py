from django.urls import path
from sme import views

urlpatterns = [
    path("api/fontes/catalogo/", views.source_catalog),
    path("api/indicadores/opcoes/", views.indicator_options),
    path("api/indicadores/", views.indicators),
    path("api/auth/password/", views.change_password),
    path("api/internal/coleta/", views.scheduled_collection),
    path("api/fontes/<int:source_id>/coletas/", views.source_collection),
    path("api/health/", views.health),
    path("api/auth/csrf/", views.csrf),
    path("api/auth/login/", views.sign_in),
    path("api/auth/register/", views.register),
    path("api/auth/logout/", views.sign_out),
    path("api/auth/me/", views.me),
    path("api/fontes/", views.sources),
    path("api/fontes/<int:source_id>/", views.source_detail),
]

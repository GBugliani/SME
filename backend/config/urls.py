from django.urls import path
from sme import views

urlpatterns = [
    path("api/health/", views.health),
    path("api/auth/csrf/", views.csrf),
    path("api/auth/login/", views.sign_in),
    path("api/auth/logout/", views.sign_out),
    path("api/auth/me/", views.me),
    path("api/fontes/", views.sources),
    path("api/fontes/<int:source_id>/", views.source_detail),
]

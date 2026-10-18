from django.urls import path
from sme import views
from sme import administration, exports
from sme import sprint4_views

urlpatterns = [
    path('api/deteccao/configuracoes/', sprint4_views.configurations),
    path('api/deteccao/configuracoes/<int:config_id>/reanalisar/', sprint4_views.reanalyze),
    path('api/deteccao/origens/<slug:indicator>/padrao/', sprint4_views.inherit_configuration),
    path('api/indicadores/comparar/', sprint4_views.compare),
    path('api/alertas/', sprint4_views.alerts),
    path('api/alertas/opcoes/', sprint4_views.alert_options),
    path('api/alertas/<int:alert_id>/ler/', sprint4_views.mark_read),
    path('api/administracao/usuarios/', administration.users),
    path('api/administracao/usuarios/<int:user_id>/', administration.user_detail),
    path('api/administracao/usuarios/<int:user_id>/senha/', administration.reset_password),
    path('api/administracao/perfis/', administration.profiles),
    path('api/administracao/perfis/<int:profile_id>/', administration.profile_detail),
    path('api/administracao/auditoria/', administration.audit_log),
    path('api/indicadores/exportar/', exports.export_data),
    path("api/fontes/catalogo/", views.source_catalog),
    path("api/indicadores/opcoes/", views.indicator_options),
    path("api/indicadores/", views.indicators),
    path("api/internal/coleta/", views.scheduled_collection),
    path("api/fontes/<int:source_id>/coletas/", views.source_collection),
    path("api/health/", views.health),
    path("api/auth/csrf/", views.csrf),
    path("api/auth/login/", views.sign_in),
    path("api/auth/logout/", views.sign_out),
    path("api/auth/me/", views.me),
    path("api/fontes/", views.sources),
    path("api/fontes/<int:source_id>/", views.source_detail),
]

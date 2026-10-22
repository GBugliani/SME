"""Permissões verificadas no servidor, sem confiar no perfil enviado pelo navegador."""
PERMISSIONS = {
    'gerenciar_fontes': 'Cadastrar, editar e arquivar fontes',
    'coletar_dados': 'Executar coletas manuais',
    'exportar_dados': 'Exportar dados',
}


def permissions_for(user):
    if not user.is_authenticated or not user.is_active:
        return []
    if user.is_staff or user.is_superuser:
        return list(PERMISSIONS)
    if user.perfil_id is None:
        return ['exportar_dados']
    return [p for p in user.perfil.permissoes if p in PERMISSIONS]


def can(user, permission):
    return permission in permissions_for(user)


def profile_name(user):
    if user.is_staff or user.is_superuser:
        return 'Administrador'
    return user.perfil.nome if user.perfil_id else 'Usuário'

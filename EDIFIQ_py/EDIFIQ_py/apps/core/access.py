"""Acceso basado en rol (sin rol_permiso): el rol se resuelve desde la tabla original `usuario`."""
from functools import wraps

from django.shortcuts import redirect

from apps.residentes.models import ApartamentoPersona

ROLE_SLUGS = {
    'Administrador': 'administrador',
    'Vigilante': 'vigilante',
    'Residente': 'residente',
}
SLUG_TO_ROLE = {slug: name for name, slug in ROLE_SLUGS.items()}
MODULE_SLUGS = (
    'personas', 'residentes', 'residentes_apartamentos', 'torres', 'apartamentos', 'visitas',
    'paquetes', 'recibos', 'zonas', 'reservas', 'usuarios',
)

# MÃ³dulos permitidos por rol (acceso dividido por rol, sin tabla rol_permiso).
ROLE_MODULES = {
    'Administrador': set(MODULE_SLUGS),
    'Vigilante': {
        'personas', 'residentes', 'apartamentos', 'visitas',
        'paquetes', 'recibos', 'zonas', 'reservas',
    },
    'Residente': {
        'residentes', 'apartamentos', 'visitas', 'paquetes',
        'recibos', 'zonas', 'reservas',
    },
}

ROLE_ACTIONS = {
    'torre_masiva': {'Administrador'},
}


def role_slug_for_name(role_name):
    return ROLE_SLUGS.get(role_name)


def role_name_for_slug(slug):
    return SLUG_TO_ROLE.get(slug)


def login_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if getattr(request.user, 'is_authenticated', False):
            return view_func(request, *args, **kwargs)
        return redirect('login')
    return _wrapped


def resolve_schema_role(user):
    """Resuelve el rol del usuario autenticado desde la tabla original `usuario`."""
    if not user or not getattr(user, 'is_authenticated', False):
        return None, None, None
    usuario = getattr(user, 'usuario_esquema', None) or getattr(user, '_usuario', None)
    rol = getattr(usuario, 'rol', None) if usuario is not None else getattr(user, 'rol', None)
    nombre = getattr(rol, 'nombre', None) or getattr(user, 'rol_nombre', None)
    slug = role_slug_for_name(nombre)
    if slug:
        return rol, nombre, slug
    return None, None, None


def has_permission(user, code):
    """Compatibilidad: interpreta cÃ³digos modulo:<slug>:<accion> y accion:<nombre> por rol."""
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if code.startswith('modulo:'):
        parts = code.split(':', 2)
        if len(parts) == 3:
            _prefix, slug, action = parts
            return can_module(user, slug, action)
    if code.startswith('accion:'):
        return has_action(user, code.split(':', 1)[1])
    _rol, nombre, _slug = resolve_schema_role(user)
    return bool(nombre)


def can_module(user, slug, action='ver'):
    _rol, nombre, _slug = resolve_schema_role(user)
    if not nombre:
        return False
    modules = ROLE_MODULES.get(nombre, set())
    if slug not in modules:
        return False
    return action in ('ver', 'crear', 'editar', 'eliminar', 'reporte')


def has_action(user, action_name):
    _rol, nombre, _slug = resolve_schema_role(user)
    if not nombre:
        return False
    allowed_roles = ROLE_ACTIONS.get(action_name)
    if allowed_roles is None:
        return True
    return nombre in allowed_roles


def has_any_permission(user):
    _rol, nombre, _slug = resolve_schema_role(user)
    return bool(nombre)


def apartamentos_autorizados(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return []
    _rol, rol_nombre, _slug = resolve_schema_role(user)
    if rol_nombre != 'Residente':
        return []
    persona_id = getattr(user, 'persona_id', None)
    if not persona_id:
        return []
    return list(
        ApartamentoPersona.objects.filter(
            persona_id=persona_id,
            fecha_salida__isnull=True,
            tipo_residente__nombre__in=('Propietario', 'Arrendatario'),
            apartamento__activo=True,
        ).values_list('apartamento_id', flat=True).distinct()
    )

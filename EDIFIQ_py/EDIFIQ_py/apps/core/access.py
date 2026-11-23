"""Acceso, resolución de rol (esquema) y permisos (rol_permiso, solo lectura)."""
from apps.core.models import RolPermiso, Usuario as UsuarioEsquema
from apps.residentes.models import ApartamentoPersona

ROLE_SLUGS = {
    'Administrador': 'administrador',
    'Vigilante': 'vigilante',
    'Residente': 'residente',
}
SLUG_TO_ROLE = {slug: name for name, slug in ROLE_SLUGS.items()}
MODULE_SLUGS = (
    'personas', 'residentes', 'torres', 'apartamentos', 'visitas',
    'paquetes', 'recibos', 'zonas', 'reservas', 'usuarios',
)


def role_slug_for_name(role_name):
    return ROLE_SLUGS.get(role_name)


def role_name_for_slug(slug):
    return SLUG_TO_ROLE.get(slug)


def resolve_schema_role(user):
    """Resuelve el rol del esquema vía Perfil.persona -> usuario (esquema) -> rol.
    Sin bypass de superusuario. Retorna (rol_obj, rol_nombre, rol_slug) o (None, None, None)."""
    if not user or not getattr(user, 'is_authenticated', False):
        return None, None, None
    perfil = getattr(user, 'perfil', None)
    persona_id = getattr(perfil, 'persona_id', None)
    if not persona_id:
        return None, None, None
    usuario_esquema = (
        UsuarioEsquema.objects.select_related('rol')
        .filter(persona_id=persona_id)
        .first()
    )
    if not usuario_esquema or not usuario_esquema.rol_id:
        return None, None, None
    rol = usuario_esquema.rol
    nombre = getattr(rol, 'nombre', None)
    slug = role_slug_for_name(nombre)
    if not slug:
        return rol, nombre, None
    return rol, nombre, slug


def has_permission(user, code):
    """Permiso exclusivo desde rol_permiso (lectura)."""
    rol, _nombre, _slug = resolve_schema_role(user)
    if not rol:
        return False
    return RolPermiso.objects.filter(rol_id=rol.pk, permiso__nombre=code).exists()


def can_module(user, slug, action='ver'):
    return has_permission(user, f'modulo:{slug}:{action}')


def has_action(user, action_name):
    return has_permission(user, f'accion:{action_name}')


def has_any_permission(user):
    rol, _nombre, _slug = resolve_schema_role(user)
    if not rol:
        return False
    return RolPermiso.objects.filter(rol_id=rol.pk).exists()


def apartamentos_autorizados(user):
    if not user.is_authenticated:
        return []
    perfil = getattr(user, 'perfil', None)
    if not perfil or not getattr(perfil, 'persona_id', None):
        return []
    _rol, rol_nombre, _slug = resolve_schema_role(user)
    if rol_nombre != 'Residente':
        return []
    # Esquema: vínculo vigente = sin fecha_salida; tipos Propietario/Arrendatario en catálogo.
    return list(
        ApartamentoPersona.objects.filter(
            persona_id=perfil.persona_id,
            fecha_salida__isnull=True,
            tipo_residente__nombre__in=('Propietario', 'Arrendatario'),
            apartamento__activo=True,
        ).values_list('apartamento_id', flat=True).distinct()
    )

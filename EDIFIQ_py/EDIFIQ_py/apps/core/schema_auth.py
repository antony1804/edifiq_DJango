import hmac

from django.contrib.auth.hashers import check_password, identify_hasher, make_password

from apps.core.models import Usuario as UsuarioEsquema

SESSION_USER_KEY = '_schema_user_id'


class AnonymousSchemaUser:
    is_authenticated = False
    is_anonymous = True
    is_active = False
    is_staff = False
    is_superuser = False
    username = ''
    pk = None
    id = None
    id_usuario = None
    persona_id = None
    rol_nombre = None

    def get_username(self):
        return ''

    def __str__(self):
        return 'Anonymous'


class SchemaUser:
    """Usuario autenticado respaldado por la tabla original `usuario` (sin auth_user/Perfil)."""

    is_authenticated = True
    is_anonymous = False
    is_staff = False
    is_superuser = False

    def __init__(self, usuario):
        self._usuario = usuario
        self.pk = usuario.pk
        self.id = usuario.pk
        self.id_usuario = usuario.pk
        self.username = usuario.username or ''
        self.persona_id = getattr(usuario, 'persona_id', None)
        self.persona = getattr(usuario, 'persona', None)
        rol = getattr(usuario, 'rol', None)
        self.rol = rol
        self.rol_nombre = getattr(rol, 'nombre', None)
        estado = getattr(usuario, 'estado_usuario', None)
        estado_nombre = (getattr(estado, 'nombre', '') or '').strip().lower()
        self.is_active = estado_nombre in ('activo', 'active', '1', 'habilitado')

    @property
    def usuario_esquema(self):
        return self._usuario

    def get_username(self):
        return self.username

    def __str__(self):
        return self.username


def check_schema_password(raw_password, encoded_password):
    encoded_password = encoded_password or ''
    if not encoded_password:
        return False
    try:
        identify_hasher(encoded_password)
        return check_password(raw_password, encoded_password)
    except Exception:
        # Compatibilidad con contraseñas en texto plano existentes en la tabla original.
        return hmac.compare_digest(str(encoded_password), str(raw_password))


def set_schema_password(raw_password):
    return make_password(raw_password)


def get_user_from_session(request):
    user_id = request.session.get(SESSION_USER_KEY)
    if not user_id:
        return AnonymousSchemaUser()
    try:
        usuario = (
            UsuarioEsquema.objects.select_related('rol', 'estado_usuario', 'persona')
            .get(pk=user_id)
        )
    except Exception:
        return AnonymousSchemaUser()
    user = SchemaUser(usuario)
    if not user.is_active:
        return AnonymousSchemaUser()
    return user


def login_schema_user(request, usuario):
    if hasattr(request, 'session') and request.session.session_key is None:
        request.session.create()
    request.session[SESSION_USER_KEY] = usuario.pk
    request.session.cycle_key()
    request.user = SchemaUser(usuario)
    return request.user


def logout_schema_user(request):
    request.session.flush()
    request.user = AnonymousSchemaUser()


class SchemaAuthenticationMiddleware:
    """Carga request.user desde la tabla original `usuario` usando sesión firmada en cookie."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.user = get_user_from_session(request)
        return self.get_response(request)

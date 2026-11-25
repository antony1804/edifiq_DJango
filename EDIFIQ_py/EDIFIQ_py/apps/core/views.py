from django.contrib import messages
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from urllib.parse import urlencode

from apps.core.models import EstadoPaquete, EstadoRecibo, EstadoReserva, EstadoUsuario, EstadoVisita, Rol, TipoDocumento, TipoResidente, Usuario as UsuarioEsquema
from apps.core.schema_auth import check_schema_password, login_schema_user, logout_schema_user, set_schema_password
from apps.paquetes.models import Paquete
from apps.personas.models import Persona
from apps.recibos.models import Recibo
from apps.reservas.models import Reserva, ZonaComun
from apps.residentes.models import Apartamento, ApartamentoPersona, Torre
from apps.visitas.models import Visita

from .access import (
    ROLE_SLUGS,
    SLUG_TO_ROLE,
    apartamentos_autorizados,
    can_module,
    has_action,
    has_any_permission,
    login_required,
    resolve_schema_role,
    role_name_for_slug,
    role_slug_for_name,
)
from .forms import AsignacionResidenteForm, PaqueteEntregaForm, TorreMasivaForm, UsuarioForm, form_for
from apps.usuarios.forms import RegistroCuentaForm, RegistroPersonaForm

ROLE_NAMESPACES = ('administrador', 'residente', 'vigilante')

MODULES = {
    'personas': ('Personas', Persona),
    'residentes': ('Residentes', ApartamentoPersona),
    'residentes_apartamentos': ('Residentes / Apartamentos', ApartamentoPersona),
    'torres': ('Torres', Torre),
    'apartamentos': ('Apartamentos', Apartamento),
    'visitas': ('Visitas', Visita),
    'paquetes': ('Paquetes', Paquete),
    'recibos': ('Recibos', Recibo),
    'zonas': ('Zonas comunes', ZonaComun),
    'reservas': ('Reservas', Reserva),
    'usuarios': ('Usuarios', UsuarioEsquema),
}
SEARCH = {
    'personas': ['nombres', 'apellidos', 'numero_documento', 'correo'],
    'residentes': ['persona__nombres', 'persona__apellidos', 'persona__numero_documento', 'apartamento__numero_apartamento', 'tipo_residente__nombre'],
    'residentes_apartamentos': ['persona__nombres', 'persona__apellidos', 'persona__numero_documento', 'apartamento__numero_apartamento', 'apartamento__torre__nombre_torre', 'tipo_residente__nombre'],
    'torres': ['nombre_torre'],
    'apartamentos': ['numero_apartamento', 'torre__nombre_torre'],
    'visitas': ['nombre_visitante', 'documento_visitante', 'tipo_visita__nombre', 'estado_visita__nombre'],
    'paquetes': ['remitente', 'descripcion', 'estado_paquete__nombre'],
    'recibos': ['tipo_servicio__nombre', 'periodo', 'estado_recibo__nombre'],
    'zonas': ['nombre', 'descripcion'],
    'reservas': ['zona__nombre', 'estado_reserva__nombre'],
    'usuarios': ['username', 'persona__nombres', 'persona__apellidos', 'persona__correo', 'rol__nombre', 'estado_usuario__nombre'],
}
STATUS = {
    'visitas': 'estado_visita__nombre',
    'paquetes': 'estado_paquete__nombre',
    'recibos': 'estado_recibo__nombre',
    'reservas': 'estado_reserva__nombre',
}
RELATED = {
    'personas': [('residentes', 'Vínculos', 'persona'), ('usuarios', 'Usuario', 'persona')],
    'torres': [('apartamentos', 'Apartamentos', 'torre')],
    'apartamentos': [('residentes', 'Residentes', 'apartamento'), ('visitas', 'Visitas', 'apartamento'), ('paquetes', 'Paquetes', 'apartamento'), ('reservas', 'Reservas', 'apartamento'), ('recibos', 'Recibos', 'apartamento')],
    'zonas': [('reservas', 'Reservas', 'zona')],
    'residentes': [('personas', 'Persona', 'persona'), ('apartamentos', 'Apartamento', 'apartamento')],
    'residentes_apartamentos': [('personas', 'Persona', 'persona'), ('apartamentos', 'Apartamento', 'apartamento')],
    'visitas': [('apartamentos', 'Apartamento', 'apartamento')],
    'paquetes': [('apartamentos', 'Apartamento', 'apartamento')],
    'recibos': [('apartamentos', 'Apartamento', 'apartamento')],
    'reservas': [('apartamentos', 'Apartamento', 'apartamento'), ('zonas', 'Zona común', 'zona')],
    'usuarios': [('personas', 'Persona', 'persona')],
}
FILTERS = {
    'personas': ('pk',),
    'residentes': ('persona', 'apartamento'),
    'residentes_apartamentos': ('persona', 'apartamento'),
    'usuarios': ('perfil__persona',),
    'apartamentos': ('torre',),
    'visitas': ('apartamento',),
    'paquetes': ('apartamento',),
    'recibos': ('apartamento',),
    'reservas': ('apartamento', 'zona'),
}


def is_composite_model(model):
    return len(getattr(model._meta, 'pk_fields', [])) > 1


def object_key(model, obj):
    if is_composite_model(model):
        return '-'.join(str(getattr(obj, f.attname)) for f in model._meta.pk_fields)
    return str(obj.pk)


def get_object_by_key(model, key):
    if not is_composite_model(model):
        return get_object_or_404(model, pk=key)
    parts = str(key).split('-')
    fields = list(model._meta.pk_fields)
    if len(parts) != len(fields):
        raise Http404
    lookup = {}
    for field, part in zip(fields, parts):
        if not part.isdigit():
            raise Http404
        lookup[field.attname] = int(part)
    return get_object_or_404(model, **lookup)


def _estado_nombre(obj, field_name):
    rel = getattr(obj, field_name, None)
    return getattr(rel, 'nombre', '') if rel else ''


def request_ns(request):
    ns = getattr(getattr(request, 'resolver_match', None), 'namespace', None)
    if ns in ROLE_NAMESPACES:
        return ns
    _rol, _nombre, slug = resolve_schema_role(request.user)
    return slug


def rurl(request, name, *args, **kwargs):
    ns = request_ns(request)
    if ns:
        return reverse(f'{ns}:{name}', args=args, kwargs=kwargs)
    return reverse(name, args=args, kwargs=kwargs)


def role(user):
    """Nombre de rol del esquema (o 'Sin rol')."""
    _rol, nombre, _slug = resolve_schema_role(user)
    return nombre or 'Sin rol'


def deny_no_role_or_no_perms(user):
    """Denegar acceso si el usuario no tiene un rol resoluble."""
    _rol, _nombre, slug = resolve_schema_role(user)
    if not slug:
        return HttpResponseForbidden('Sin rol asignado')
    return None


def allowed(user, slug, action='ver'):
    return can_module(user, slug, action)


def scoped(user, slug, qs):
    _rol, rol_nombre, _slug = resolve_schema_role(user)
    if rol_nombre != 'Residente':
        return qs
    ids = apartamentos_autorizados(user)
    if not ids:
        return qs.none()
    if slug == 'apartamentos':
        return qs.filter(pk__in=ids)
    if slug in ('residentes', 'visitas', 'paquetes', 'recibos', 'reservas'):
        return qs.filter(apartamento_id__in=ids)
    return qs.none()


def context(request):
    _rol, nombre, slug = resolve_schema_role(request.user)
    nav = []
    if slug:
        for s, (t, _m) in MODULES.items():
            if allowed(request.user, s, 'ver'):
                label = 'Mi apartamento' if s == 'apartamentos' and nombre == 'Residente' else t
                nav.append((s, label))
    ns = request_ns(request) or slug
    return {'role': nombre or 'Sin rol', 'role_ns': ns, 'navigation': nav}


def related_links(user, slug, obj, request):
    links = []
    if slug == 'personas':
        for target, label, field in RELATED.get(slug, []):
            if allowed(user, target, 'ver'):
                value = obj.pk
                links.append({'label': label, 'url': rurl(request, 'module', slug=target) + '?' + urlencode({field: value})})
        return links
    if slug in ('torres', 'apartamentos', 'zonas'):
        for target, label, field in RELATED.get(slug, []):
            if allowed(user, target, 'ver'):
                links.append({'label': label, 'url': rurl(request, 'module', slug=target) + '?' + urlencode({field: obj.pk})})
        return links
    if slug == 'usuarios':
        persona_id = getattr(obj, 'persona_id', None)
        if persona_id and allowed(user, 'personas', 'ver'):
            links.append({'label': 'Persona', 'url': rurl(request, 'module', slug='personas') + '?' + urlencode({'pk': persona_id})})
        return links
    for target, label, field in RELATED.get(slug, []):
        if not allowed(user, target, 'ver'):
            continue
        value = getattr(obj, field + '_id', None)
        if value is None:
            continue
        if target == 'apartamentos':
            url = rurl(request, 'apartamento_detalle', pk=value)
        elif target == 'personas':
            url = rurl(request, 'module', slug=target) + '?' + urlencode({'pk': value})
        elif target in FILTERS and field in FILTERS[target]:
            url = rurl(request, 'module', slug=target) + '?' + urlencode({field: value})
        else:
            continue
        links.append({'label': label, 'url': url})
    return links


def login_view(request):
    if getattr(request.user, 'is_authenticated', False):
        _rol, _nombre, slug = resolve_schema_role(request.user)
        if slug:
            return redirect(f'{slug}:dashboard')
        return render(request, 'core/no_role.html', {**context(request), 'message': 'Tu cuenta no tiene un rol asignado.'}, status=403)
    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        password = request.POST.get('password') or ''
        user = None
        if username:
            try:
                user = UsuarioEsquema.objects.select_related('rol', 'estado_usuario', 'persona').get(username__iexact=username)
            except UsuarioEsquema.DoesNotExist:
                user = None
        if user and check_schema_password(password, getattr(user, 'password', '')):
            estado_nombre = (getattr(getattr(user, 'estado_usuario', None), 'nombre', '') or '').strip().lower()
            if estado_nombre and estado_nombre not in ('activo', 'active', '1', 'habilitado'):
                messages.error(request, 'Tu usuario no está activo. Contacta al administrador.')
            elif not getattr(user, 'rol_id', None):
                messages.error(request, 'No tienes rol asignado. Contacta al administrador.')
            else:
                login_schema_user(request, user)
                _rol, _nombre, slug = resolve_schema_role(request.user)
                if slug:
                    return redirect(f'{slug}:dashboard')
                logout_schema_user(request)
                messages.error(request, 'No tienes rol asignado. Contacta al administrador.')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos')
    return render(request, 'usuarios/login.html')


def logout_view(request):
    logout_schema_user(request)
    return redirect('login')


# --- Compatibilidad: rutas genéricas redirigen al prefijo del rol ---

@login_required
def dashboard_redirect(request):
    _rol, _nombre, slug = resolve_schema_role(request.user)
    if not slug:
        return HttpResponseForbidden('Sin rol asignado')
    return redirect(f'{slug}:dashboard')


@login_required
def module_redirect(request, slug):
    _rol, _nombre, rslug = resolve_schema_role(request.user)
    if not rslug:
        return HttpResponseForbidden('Sin rol asignado')
    url = reverse(f'{rslug}:module', kwargs={'slug': slug})
    if request.META.get('QUERY_STRING'):
        url += '?' + request.META['QUERY_STRING']
    return redirect(url)


@login_required
def create_redirect(request, slug):
    _rol, _nombre, rslug = resolve_schema_role(request.user)
    if not rslug:
        return HttpResponseForbidden('Sin rol asignado')
    url = reverse(f'{rslug}:create', kwargs={'slug': slug})
    if request.META.get('QUERY_STRING'):
        url += '?' + request.META['QUERY_STRING']
    return redirect(url)


@login_required
def edit_redirect(request, slug, pk):
    _rol, _nombre, rslug = resolve_schema_role(request.user)
    if not rslug:
        return HttpResponseForbidden('Sin rol asignado')
    return redirect(f'{rslug}:edit', slug=slug, pk=pk)


@login_required
@require_POST
def delete_redirect(request, slug, pk):
    _rol, _nombre, rslug = resolve_schema_role(request.user)
    if not rslug:
        return HttpResponseForbidden('Sin rol asignado')
    ns = getattr(getattr(request, 'resolver_match', None), 'namespace', None)
    if ns not in ROLE_NAMESPACES:
        request.resolver_match.namespace = rslug
    return delete_view(request, slug, pk)


@login_required
@require_POST
def toggle_estado_redirect(request, slug, pk):
    _rol, _nombre, rslug = resolve_schema_role(request.user)
    if not rslug:
        return HttpResponseForbidden('Sin rol asignado')
    ns = getattr(getattr(request, 'resolver_match', None), 'namespace', None)
    if ns not in ROLE_NAMESPACES:
        request.resolver_match.namespace = rslug
    return toggle_estado_view(request, slug, pk)


@login_required
@require_POST
def asignacion_salida_view(request, slug, pk):
    denied = role_required_view(request, request.resolver_match.namespace)
    if denied:
        return denied
    if slug != 'residentes_apartamentos' or slug not in MODULES:
        raise Http404
    if not allowed(request.user, slug, 'editar'):
        return HttpResponseForbidden('Sin permiso para registrar salida')
    obj = get_object_by_key(MODULES[slug][1], pk)
    if obj.fecha_salida is None:
        obj.fecha_salida = timezone.localdate()
        obj.save(update_fields=['fecha_salida'])
        messages.success(request, 'Salida registrada correctamente.')
    else:
        messages.info(request, 'Esta asignación ya tenía registrada una fecha de salida.')
    return redirect(f"{request.resolver_match.namespace}:module", slug=slug)


@login_required
@require_POST
def asignacion_salida_redirect(request, slug, pk):
    _rol, _nombre, rslug = resolve_schema_role(request.user)
    if not rslug:
        return HttpResponseForbidden('Sin rol asignado')
    ns = getattr(getattr(request, 'resolver_match', None), 'namespace', None)
    if ns not in ROLE_NAMESPACES:
        request.resolver_match.namespace = rslug
    return asignacion_salida_view(request, slug, pk)


@login_required
@require_POST
def asignacion_reasignar_view(request, slug, pk):
    denied = role_required_view(request, request.resolver_match.namespace)
    if denied:
        return denied
    if slug != 'residentes_apartamentos' or slug not in MODULES:
        raise Http404
    if not allowed(request.user, slug, 'editar'):
        return HttpResponseForbidden('Sin permiso para reasignar')
    obj = get_object_by_key(MODULES[slug][1], pk)
    if obj.fecha_salida is not None:
        obj.fecha_salida = None
        obj.fecha_ingreso = timezone.localdate()
        obj.save(update_fields=['fecha_salida', 'fecha_ingreso'])
        messages.success(request, 'Asignación reactivada correctamente.')
    else:
        messages.info(request, 'Esta asignación ya se encuentra activa.')
    return redirect(f"{request.resolver_match.namespace}:module", slug=slug)


@login_required
@require_POST
def asignacion_reasignar_redirect(request, slug, pk):
    _rol, _nombre, rslug = resolve_schema_role(request.user)
    if not rslug:
        return HttpResponseForbidden('Sin rol asignado')
    ns = getattr(getattr(request, 'resolver_match', None), 'namespace', None)
    if ns not in ROLE_NAMESPACES:
        request.resolver_match.namespace = rslug
    return asignacion_reasignar_view(request, slug, pk)


@login_required
def paquete_entregar_view(request, slug, pk):
    denied = role_required_view(request, request.resolver_match.namespace)
    if denied:
        return denied
    if slug != 'paquetes' or slug not in MODULES:
        raise Http404
    _rol_obj, rol_nombre, _slug_role = resolve_schema_role(request.user)
    if rol_nombre == 'Residente':
        return HttpResponseForbidden('No tienes permiso para entregar paquetes')
    if not allowed(request.user, slug, 'editar'):
        return HttpResponseForbidden('Sin permiso para entregar paquetes')
    obj = get_object_by_key(MODULES[slug][1], pk)
    estado_nombre = getattr(getattr(obj, 'estado_paquete', None), 'nombre', '')
    if request.method == 'GET' and estado_nombre == 'Entregado' and (request.GET.get('modal') == '1'):
        # Si ya está entregado, mostrar igualmente el formulario (solo lectura práctica no requerida) o info; permitimos ver/ajustar no es necesario.
        pass

    modal = request.GET.get('modal') == '1' or request.POST.get('modal') == '1'
    if request.method == 'POST':
        form = PaqueteEntregaForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Paquete marcado como entregado.')
            if modal:
                return redirect(f"{request.resolver_match.namespace}:module", slug=slug)
            return redirect(f"{request.resolver_match.namespace}:module", slug=slug)
    else:
        # precargar entrega ahora si no tiene
        initial = {}
        if not getattr(obj, 'fecha_entrega', None):
            initial['fecha_entrega'] = timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M')
        form = PaqueteEntregaForm(instance=obj, initial=initial)

    title = 'Entregar paquete'
    if modal:
        status_code = 400 if request.method == 'POST' else 200
        resp = render(request, 'paquetes/entregar_modal.html', {
            **context(request), 'title': title, 'form': form, 'slug': slug, 'obj': obj, 'modal_paquete_entrega': True,
        })
        resp.status_code = status_code
        return resp
    return render(request, 'paquetes/entregar_modal.html', {**context(request), 'title': title, 'form': form, 'slug': slug, 'obj': obj})


@login_required
def paquete_entregar_redirect(request, slug, pk):
    _rol, _nombre, rslug = resolve_schema_role(request.user)
    if not rslug:
        return HttpResponseForbidden('Sin rol asignado')
    ns = getattr(getattr(request, 'resolver_match', None), 'namespace', None)
    if ns not in ROLE_NAMESPACES:
        request.resolver_match.namespace = rslug
    return paquete_entregar_view(request, slug, pk)


@login_required
def reporte_redirect(request, slug):
    _rol, _nombre, rslug = resolve_schema_role(request.user)
    if not rslug:
        return HttpResponseForbidden('Sin rol asignado')
    url = reverse(f'{rslug}:reporte_pdf', kwargs={'slug': slug})
    if request.META.get('QUERY_STRING'):
        url += '?' + request.META['QUERY_STRING']
    return redirect(url)


@login_required
def apartamento_detalle_redirect(request, pk):
    _rol, _nombre, rslug = resolve_schema_role(request.user)
    if not rslug:
        return HttpResponseForbidden('Sin rol asignado')
    return redirect(f'{rslug}:apartamento_detalle', pk=pk)



# --- Vistas por rol (prefijo completo) ---

def role_required_view(request, expected_role_slug):
    """Verifica namespace/rol esperado; el acceso requiere solo rol (sin rol_permiso)."""
    if not request.user.is_authenticated:
        return redirect('login')
    denied = deny_no_role_or_no_perms(request.user)
    if denied:
        return denied
    _rol, _nombre, slug = resolve_schema_role(request.user)
    if slug != expected_role_slug:
        if slug:
            return redirect(f'{slug}:dashboard')
        return HttpResponseForbidden('Sin rol asignado')
    return None


def _dashboard_impl(request, role_slug):
    denied = role_required_view(request, role_slug)
    if denied:
        return denied
    counts = {}
    for slug in ('personas', 'residentes', 'visitas', 'paquetes', 'reservas', 'recibos'):
        if allowed(request.user, slug, 'ver'):
            counts[slug] = scoped(request.user, slug, MODULES[slug][1].objects.all()).count()
    recent = []
    for slug in ('visitas', 'paquetes', 'reservas'):
        if allowed(request.user, slug, 'ver'):
            recent.extend([{'module': MODULES[slug][0], 'text': str(o), 'id': getattr(o, 'pk', None)} for o in scoped(request.user, slug, MODULES[slug][1].objects.all()).order_by('-pk')[:5]])
    today = timezone.localdate()
    alerts = []
    if role_slug == 'administrador':
        if allowed(request.user, 'visitas', 'ver'):
            alerts.append(('Visitas pendientes', scoped(request.user, 'visitas', Visita.objects.filter(estado_visita__nombre='Pendiente')).count()))
        if allowed(request.user, 'paquetes', 'ver'):
            alerts.append(('Paquetes por entregar', scoped(request.user, 'paquetes', Paquete.objects.filter(estado_paquete__nombre='Recibido')).count()))
        if allowed(request.user, 'recibos', 'ver'):
            alerts.append(('Recibos pendientes', scoped(request.user, 'recibos', Recibo.objects.filter(estado_recibo__nombre='Pendiente')).count()))
        if allowed(request.user, 'reservas', 'ver'):
            alerts.append(('Reservas del día', scoped(request.user, 'reservas', Reserva.objects.filter(fecha_reserva=today)).count()))
    elif role_slug == 'vigilante':
        if allowed(request.user, 'visitas', 'ver'):
            alerts.append(('Visitas hoy', scoped(request.user, 'visitas', Visita.objects.filter(fecha_ingreso__date=today)).count()))
            alerts.append(('Visitas pendientes', scoped(request.user, 'visitas', Visita.objects.filter(estado_visita__nombre='Pendiente')).count()))
        if allowed(request.user, 'paquetes', 'ver'):
            alerts.append(('Paquetes por entregar', scoped(request.user, 'paquetes', Paquete.objects.filter(estado_paquete__nombre='Recibido')).count()))
        if allowed(request.user, 'recibos', 'ver'):
            alerts.append(('Recibos pagados', scoped(request.user, 'recibos', Recibo.objects.filter(estado_recibo__nombre='Pagado')).count()))
    elif role_slug == 'residente':
        if allowed(request.user, 'paquetes', 'ver'):
            alerts.append(('Paquetes pendientes', scoped(request.user, 'paquetes', Paquete.objects.filter(estado_paquete__nombre='Recibido')).count()))
        if allowed(request.user, 'recibos', 'ver'):
            alerts.append(('Recibos pendientes', scoped(request.user, 'recibos', Recibo.objects.filter(estado_recibo__nombre='Pendiente')).count()))
        if allowed(request.user, 'reservas', 'ver'):
            alerts.append(('Mis reservas (hoy en adelante)', scoped(request.user, 'reservas', Reserva.objects.filter(fecha_reserva__gte=today)).exclude(estado_reserva__nombre='Cancelada').count()))
        if allowed(request.user, 'visitas', 'ver'):
            alerts.append(('Visitas pendientes', scoped(request.user, 'visitas', Visita.objects.filter(estado_visita__nombre='Pendiente')).count()))
    else:
        if allowed(request.user, 'visitas', 'ver'):
            alerts.append(('Visitas pendientes', scoped(request.user, 'visitas', Visita.objects.filter(estado_visita__nombre='Pendiente')).count()))
    ctx = {**context(request), 'counts': counts, 'recent': recent[:10], 'alerts': alerts, 'role_slug': role_slug}
    return render(request, f'dashboards/{role_slug}.html', ctx)


@login_required
def dashboard_administrador(request):
    return _dashboard_impl(request, 'administrador')


@login_required
def dashboard_vigilante(request):
    return _dashboard_impl(request, 'vigilante')


@login_required
def dashboard_residente(request):
    return _dashboard_impl(request, 'residente')


@login_required
def module_view(request, slug):
    denied = role_required_view(request, request.resolver_match.namespace)
    if denied:
        return denied
    if slug == 'perfiles':
        return redirect(f"{request.resolver_match.namespace}:module", slug='usuarios')
    if slug not in MODULES:
        raise Http404
    if not allowed(request.user, slug, 'ver'):
        return HttpResponseForbidden('Sin permiso para este módulo')

    _rol_obj, rol_nombre, _slug_role = resolve_schema_role(request.user)
    if slug == 'apartamentos' and rol_nombre == 'Residente':
        persona_id = getattr(request.user, 'persona_id', None)
        mis_links = []
        familiares = []
        qf = request.GET.get('qf', '').strip()[:100]
        if persona_id:
            mis_links = list(
                ApartamentoPersona.objects.filter(
                    persona_id=persona_id,
                    fecha_salida__isnull=True,
                ).select_related('apartamento', 'apartamento__torre', 'tipo_residente')
                .order_by('apartamento__torre__nombre_torre', 'apartamento__numero_apartamento')
            )
            apartamento_ids = [v.apartamento_id for v in mis_links]
            if apartamento_ids:
                fq = ApartamentoPersona.objects.filter(
                    apartamento_id__in=apartamento_ids,
                    tipo_residente__nombre='Familiar',
                    fecha_salida__isnull=True,
                ).select_related('persona', 'persona__tipo_documento', 'tipo_residente', 'apartamento')
                if qf:
                    fq = fq.filter(
                        Q(persona__numero_documento__icontains=qf)
                        | Q(persona__nombres__icontains=qf)
                        | Q(persona__apellidos__icontains=qf)
                        | Q(persona__telefono__icontains=qf)
                        | Q(persona__correo__icontains=qf)
                    )
                familiares = list(fq.order_by('persona__apellidos', 'persona__nombres'))
                for f in familiares:
                    f.row_key = object_key(ApartamentoPersona, f)
        return render(request, 'residentes/mi_apartamento.html', {
            **context(request),
            'title': 'Mi apartamento',
            'slug': slug,
            'mis_apartamento_links': mis_links,
            'familiares': familiares,
            'qf': qf,
            'can_manage_familiares': allowed(request.user, 'residentes', 'editar') or allowed(request.user, 'residentes', 'eliminar'),
            'can_edit_familiares': allowed(request.user, 'residentes', 'editar'),
            'can_delete_familiares': allowed(request.user, 'residentes', 'eliminar'),
        })

    title, model = MODULES[slug]
    qs = scoped(request.user, slug, model.objects.all())
    q = request.GET.get('q', '').strip()[:100]
    status = request.GET.get('estado', '').strip()[:30]
    persona_tipo_documento = request.GET.get('tipo_documento', '').strip()
    persona_estado = request.GET.get('estado_persona', '').strip().lower()
    apartamento_torre = request.GET.get('torre', '').strip()
    apartamento_estado = request.GET.get('estado_apartamento', '').strip().lower()
    asignacion_torre = request.GET.get('asignacion_torre', '').strip()
    asignacion_tipo = request.GET.get('tipo_residente', '').strip()
    asignacion_estado = request.GET.get('estado_asignacion_residente', '').strip().lower()
    paquete_torre = request.GET.get('paquete_torre', '').strip()
    paquete_estado = request.GET.get('paquete_estado', request.GET.get('estado', '')).strip()
    recibido_desde = request.GET.get('recibido_desde', '').strip()
    recibido_hasta = request.GET.get('recibido_hasta', '').strip()

    if q:
        condition = Q()
        for field in SEARCH.get(slug, []):
            condition |= Q(**{field + '__icontains': q})
        qs = qs.filter(condition)

    if slug == 'personas':
        if persona_tipo_documento.isdecimal():
            qs = qs.filter(tipo_documento_id=int(persona_tipo_documento))
        if persona_estado in ('activo', 'activa', '1', 'true', 'si', 'sí'):
            qs = qs.filter(activo=True)
        elif persona_estado in ('inactivo', 'inactiva', '0', 'false', 'no'):
            qs = qs.filter(activo=False)
    elif slug == 'apartamentos':
        # Estado de ocupación (asignado/no asignado) calculado por vínculos vigentes.
        vigente_qs = ApartamentoPersona.objects.filter(apartamento=OuterRef('pk'), fecha_salida__isnull=True)
        qs = qs.annotate(tiene_asignacion=Exists(vigente_qs))
        if apartamento_torre.isdecimal():
            qs = qs.filter(torre_id=int(apartamento_torre))
        if apartamento_estado in ('asignado', 'asignada', '1', 'si', 'sí', 'true'):
            qs = qs.filter(tiene_asignacion=True)
        elif apartamento_estado in ('no_asignado', 'no asignado', 'no_asignada', 'sin_asignar', '0', 'no', 'false'):
            qs = qs.filter(tiene_asignacion=False)
    elif slug == 'residentes_apartamentos':
        if asignacion_torre.isdecimal():
            qs = qs.filter(apartamento__torre_id=int(asignacion_torre))
        if asignacion_tipo.isdecimal():
            qs = qs.filter(tipo_residente_id=int(asignacion_tipo))
        if asignacion_estado in ('activo', 'activa', 'en_apartamento', 'vigente', '1', 'si', 'sí', 'true'):
            qs = qs.filter(fecha_salida__isnull=True)
        elif asignacion_estado in ('inactivo', 'inactiva', 'salida', 'retirado', '0', 'no', 'false'):
            qs = qs.filter(fecha_salida__isnull=False)
    elif slug == 'paquetes':
        if paquete_torre.isdecimal():
            qs = qs.filter(apartamento__torre_id=int(paquete_torre))
        if paquete_estado:
            qs = qs.filter(estado_paquete__nombre=paquete_estado)
        import datetime
        def _parse_date(s):
            try:
                return datetime.date.fromisoformat(s)
            except Exception:
                return None
        d1 = _parse_date(recibido_desde)
        d2 = _parse_date(recibido_hasta)
        if d1:
            qs = qs.filter(fecha_recepcion__date__gte=d1)
        if d2:
            qs = qs.filter(fecha_recepcion__date__lte=d2)
    elif status and slug in STATUS:
        qs = qs.filter(**{STATUS[slug]: status})

    active_relations = {}
    for field in FILTERS.get(slug, ()):
        if slug == 'personas' and field == 'pk':
            # Personas se filtra por id explícitamente en la barra/listado solo cuando aplica; evitamos UI de relación oculta aquí.
            pass
        if slug == 'apartamentos' and field == 'torre':
            # Se maneja con filtro dedicado de UI.
            continue
        if slug == 'residentes_apartamentos':
            # Filtros dedicados en UI (torre, tipo, estado).
            continue
        if slug == 'paquetes':
            # Filtros dedicados en UI (estado, torre, recibido desde/hasta).
            continue
        raw = request.GET.get(field, '')
        if raw.isdecimal():
            lookup = field if field.endswith('_id') else f'{field}_id'
            qs = qs.filter(**{lookup: int(raw)})
            active_relations[field] = raw

    resident_groups = None
    if slug == 'residentes':
        person_ids = list(qs.order_by('persona_id').values_list('persona_id', flat=True).distinct()[:100])
        relations = list(
            qs.filter(persona_id__in=person_ids)
            .select_related('persona', 'apartamento__torre', 'tipo_residente')
            .order_by('persona__nombres', 'persona__apellidos', 'apartamento__torre__nombre_torre', 'apartamento__numero_apartamento')
        )
        groups_by_person = {}
        for relation in relations:
            group = groups_by_person.setdefault(relation.persona_id, {'persona': relation.persona, 'relations': [], 'types': set()})
            relation.display_tipo = getattr(relation.tipo_residente, 'nombre', '')
            relation.display_activo = relation.fecha_salida is None
            relation.row_key = object_key(model, relation)
            group['relations'].append(relation)
            group['types'].add(relation.display_tipo)
        resident_groups = list(groups_by_person.values())
        for group in resident_groups:
            group['types_label'] = ', '.join(sorted(t for t in group['types'] if t))
        items = []
    else:
        if slug == 'personas':
            items = list(qs.select_related('tipo_documento').order_by('id_persona')[:100])
        elif slug == 'apartamentos':
            items = list(qs.select_related('torre').order_by('torre__nombre_torre', 'numero_apartamento')[:100])
            # Asegurar estado de asignación disponible aunque no se haya filtrado/annotado antes.
            ids = [a.pk for a in items]
            asignados = set(
                ApartamentoPersona.objects.filter(apartamento_id__in=ids, fecha_salida__isnull=True)
                .values_list('apartamento_id', flat=True).distinct()
            ) if ids else set()
            for a in items:
                a.estado_asignacion = 'Asignado' if (getattr(a, 'tiene_asignacion', a.pk in asignados)) else 'No asignado'
        elif slug == 'residentes_apartamentos':
            items = list(
                qs.select_related('apartamento', 'apartamento__torre', 'persona', 'tipo_residente')
                .order_by('apartamento__torre__nombre_torre', 'apartamento__numero_apartamento', '-fecha_ingreso', 'persona__apellidos', 'persona__nombres')[:100]
            )
        elif slug == 'paquetes':
            items = list(
                qs.select_related('apartamento', 'apartamento__torre', 'estado_paquete', 'persona', 'persona__tipo_documento')
                .order_by('-fecha_recepcion', '-pk')[:100]
            )
        elif is_composite_model(model):
            items = list(qs[:100])
        else:
            items = list(qs.order_by('-pk')[:100])

    states = []
    if slug == 'visitas':
        states = [(e.nombre, e.nombre) for e in EstadoVisita.objects.all().order_by('id_estado_visita')]
    elif slug == 'paquetes':
        states = [(e.nombre, e.nombre) for e in EstadoPaquete.objects.all().order_by('id_estado_paquete')]
    elif slug == 'recibos':
        states = [(e.nombre, e.nombre) for e in EstadoRecibo.objects.all().order_by('id_estado_recibo')]
    elif slug == 'reservas':
        states = [(e.nombre, e.nombre) for e in EstadoReserva.objects.all().order_by('id_estado_reserva')]

    rows = []
    for obj in items:
        rows.append({'item': obj, 'key': object_key(model, obj), 'links': related_links(request.user, slug, obj, request)})

    persona_tipo_documentos = list(TipoDocumento.objects.all().order_by('id_tipo_documento')) if slug == 'personas' else []
    persona_estado_choices = [('activo', 'Activo'), ('inactivo', 'Inactivo')] if slug == 'personas' else []
    apartamento_torres = list(Torre.objects.all().order_by('nombre_torre')) if slug == 'apartamentos' else []
    apartamento_estado_choices = [('asignado', 'Asignado'), ('no_asignado', 'No asignado')] if slug == 'apartamentos' else []
    asignacion_torres = list(Torre.objects.all().order_by('nombre_torre')) if slug == 'residentes_apartamentos' else []
    asignacion_tipos = list(TipoResidente.objects.filter(nombre__in=['Propietario', 'Arrendatario', 'Familiar']).order_by('id_tipo_residente')) if slug == 'residentes_apartamentos' else []
    asignacion_estado_choices = [('activo', 'Activo (en apartamento)'), ('salida', 'Con salida / inactivo')] if slug == 'residentes_apartamentos' else []
    paquete_torres = list(Torre.objects.all().order_by('nombre_torre')) if slug == 'paquetes' else []
    paquete_estado_choices = [(e.nombre, e.nombre) for e in EstadoPaquete.objects.all().order_by('id_estado_paquete')] if slug == 'paquetes' else []

    can_create = allowed(request.user, slug, 'crear')
    can_edit = allowed(request.user, slug, 'editar')
    can_delete = allowed(request.user, slug, 'eliminar')
    if slug == 'personas':
        can_delete = False  # Historial: no se eliminan personas, se inactivan.
    _rol_obj, _rol_nombre, _slug_role = resolve_schema_role(request.user)
    if slug == 'paquetes' and _rol_nombre == 'Residente':
        # El residente solo consulta sus paquetes (no registra, edita ni elimina).
        can_create = False
        can_edit = False
        can_delete = False

    return render(request, 'module.html', {
        **context(request), 'title': title, 'slug': slug, 'rows': rows,
        'resident_groups': resident_groups, 'active_relations': active_relations,
        'q': q, 'estado': status, 'states': states,
        'can_create': can_create,
        'can_edit': can_edit,
        'can_delete': can_delete,
        'can_report': allowed(request.user, slug, 'reporte'),
        'can_bulk': slug == 'torres' and has_action(request.user, 'torre_masiva'),
        'composite': is_composite_model(model),
        'persona_tipo_documentos': persona_tipo_documentos,
        'persona_tipo_documento': persona_tipo_documento,
        'persona_estado': persona_estado,
        'persona_estado_choices': persona_estado_choices,
        'apartamento_torres': apartamento_torres,
        'apartamento_torre': apartamento_torre,
        'apartamento_estado': apartamento_estado,
        'apartamento_estado_choices': apartamento_estado_choices,
        'asignacion_torres': asignacion_torres,
        'asignacion_tipos': asignacion_tipos,
        'asignacion_torre': asignacion_torre,
        'asignacion_tipo': asignacion_tipo,
        'asignacion_estado': asignacion_estado,
        'asignacion_estado_choices': asignacion_estado_choices,
        'paquete_torres': paquete_torres,
        'paquete_estado_choices': paquete_estado_choices,
        'paquete_torre': paquete_torre,
        'paquete_estado': paquete_estado,
        'recibido_desde': recibido_desde,
        'recibido_hasta': recibido_hasta,
    })


@transaction.atomic
def save_form(request, slug, instance=None):
    denied = role_required_view(request, request.resolver_match.namespace)
    if denied:
        return denied
    if slug == 'perfiles':
        return redirect(f"{request.resolver_match.namespace}:module", slug='usuarios')
    if slug not in MODULES:
        raise Http404
    action = 'editar' if instance else 'crear'
    if not allowed(request.user, slug, action):
        return HttpResponseForbidden('Sin permiso para modificar este módulo')
    title, model = MODULES[slug]
    _rol_obj, rol_nombre, _slug_role = resolve_schema_role(request.user)
    if instance and rol_nombre == 'Residente' and slug == 'reservas':
        return HttpResponseForbidden('No puedes modificar reservas existentes')

    if slug == 'usuarios':
        Form = UsuarioForm
    elif slug == 'residentes_apartamentos':
        Form = AsignacionResidenteForm
    else:
        Form = form_for(model)

    initial = {}
    if instance is None and request.method != 'POST':
        for field in FILTERS.get(slug, ()):
            raw = request.GET.get(field, '')
            if raw.isdecimal():
                initial[field] = int(raw)
    if slug == 'residentes' and rol_nombre == 'Residente':
        ids = apartamentos_autorizados(request.user)
        if not ids:
            return HttpResponseForbidden('No tienes un vínculo activo como propietario o arrendatario')
        if instance and instance.apartamento_id not in ids:
            return HttpResponseForbidden('No puedes modificar vínculos de otro apartamento')
        if len(ids) == 1:
            initial['apartamento'] = ids[0]

    form_kwargs = {'instance': instance, 'initial': initial}
    if slug in ('residentes', 'paquetes'):
        form_kwargs['usuario'] = request.user
    if slug == 'usuarios':
        form_kwargs['rol_actual'] = rol_nombre
    if slug == 'paquetes' and rol_nombre == 'Residente':
        return HttpResponseForbidden('No puedes registrar ni modificar paquetes')
    form = Form(request.POST or None, **form_kwargs)
    if slug == 'visitas':
        apply_visit_rules(form, rol_nombre)
        if 'autorizada' in form.fields:
            form.fields['autorizada'].initial = bool(instance and _estado_nombre(instance, 'estado_visita') != 'Pendiente')

    if slug == 'residentes' and rol_nombre == 'Residente':
        ids = apartamentos_autorizados(request.user)
        if len(ids) == 1 and 'apartamento' in form.fields:
            form.fields['apartamento'].disabled = True
            form.fields['apartamento'].initial = ids[0]
    if slug == 'visitas' and rol_nombre == 'Residente':
        ids = apartamentos_autorizados(request.user)
        if not ids:
            return HttpResponseForbidden('No tienes un vínculo activo como propietario o arrendatario')
        if 'apartamento' in form.fields:
            form.fields['apartamento'].queryset = Apartamento.objects.filter(pk__in=ids)
            if len(ids) == 1:
                form.fields['apartamento'].disabled = True
                form.fields['apartamento'].initial = ids[0]
        if 'estado_visita' in form.fields:
            form.fields['estado_visita'].queryset = EstadoVisita.objects.filter(nombre__in=['Pendiente'])
    if slug == 'visitas' and rol_nombre == 'Vigilante':
        if instance and 'apartamento' in form.fields:
            form.fields['apartamento'].disabled = True
        if 'estado_visita' in form.fields:
            form.fields['estado_visita'].queryset = EstadoVisita.objects.filter(nombre__in=['Pendiente', 'Ingresó', 'Finalizada'])
    if rol_nombre == 'Residente' and slug == 'reservas':
        ids = apartamentos_autorizados(request.user)
        if not ids:
            return HttpResponseForbidden('No tienes un apartamento autorizado')
        if 'apartamento' in form.fields:
            form.fields['apartamento'].queryset = Apartamento.objects.filter(pk__in=ids)
            if len(ids) == 1:
                form.fields['apartamento'].disabled = True
                form.fields['apartamento'].initial = ids[0]
        if 'estado_reserva' in form.fields:
            form.fields['estado_reserva'].queryset = EstadoReserva.objects.filter(nombre='Pendiente')
            pendiente = EstadoReserva.objects.filter(nombre='Pendiente').first()
            if pendiente:
                form.fields['estado_reserva'].initial = pendiente

    modal_persona = slug == 'personas' and (request.GET.get('modal') == '1' or request.POST.get('modal') == '1')
    modal_torre = slug == 'torres' and bool(instance) and (request.GET.get('modal') == '1' or request.POST.get('modal') == '1')
    modal_apartamento = slug == 'apartamentos' and (request.GET.get('modal') == '1' or request.POST.get('modal') == '1')
    modal_asignacion = slug == 'residentes_apartamentos' and (request.GET.get('modal') == '1' or request.POST.get('modal') == '1')
    modal_paquete = slug == 'paquetes' and (request.GET.get('modal') == '1' or request.POST.get('modal') == '1')

    if request.method == 'POST' and form.is_valid():
        if slug == 'usuarios':
            with transaction.atomic():
                obj = form.save()
            messages.success(request, 'Usuario guardado correctamente')
            return redirect(f"{request.resolver_match.namespace}:module", slug='usuarios')

        obj = form.save(commit=False)
        if rol_nombre == 'Residente' and slug in ('residentes', 'residentes_apartamentos', 'visitas', 'reservas'):
            ids = apartamentos_autorizados(request.user)
            if getattr(obj, 'apartamento_id', None) not in ids:
                return HttpResponseForbidden('Apartamento no autorizado')

        if rol_nombre == 'Residente' and slug == 'reservas':
            pendiente = EstadoReserva.objects.filter(nombre='Pendiente').first()
            if pendiente:
                obj.estado_reserva = pendiente

        if slug == 'visitas':
            estado_nombre = getattr(getattr(obj, 'estado_visita', None), 'nombre', '')
            if rol_nombre == 'Residente':
                obj.autorizada = bool(form.cleaned_data.get('autorizada'))
                if estado_nombre not in ('Pendiente',):
                    pendiente = EstadoVisita.objects.filter(nombre='Pendiente').first()
                    if pendiente:
                        obj.estado_visita = pendiente
                        estado_nombre = 'Pendiente'
            elif rol_nombre == 'Vigilante':
                if estado_nombre == 'Ingresó':
                    if not (obj.autorizada or (instance and getattr(instance, 'estado_visita', None) and instance.estado_visita.nombre == 'Ingresó')):
                        form.add_error('estado_visita', 'La visita debe estar autorizada antes del ingreso.')
                        if modal_persona:
                            resp = render(request, 'personas/edit_modal_form.html', {**context(request), 'title': title, 'form': form, 'slug': slug, 'editing': bool(instance), 'modal_persona': True})
                            resp.status_code = 400
                            return resp
                        return render(request, 'form.html', {**context(request), 'title': title, 'form': form, 'slug': slug, 'editing': bool(instance)})
                if estado_nombre == 'Finalizada' and (not instance or not getattr(instance, 'estado_visita', None) or instance.estado_visita.nombre != 'Ingresó'):
                    form.add_error('estado_visita', 'Primero registra el ingreso.')
                    if modal_persona:
                        resp = render(request, 'personas/edit_modal_form.html', {**context(request), 'title': title, 'form': form, 'slug': slug, 'editing': bool(instance), 'modal_persona': True})
                        resp.status_code = 400
                        return resp
                    return render(request, 'form.html', {**context(request), 'title': title, 'form': form, 'slug': slug, 'editing': bool(instance)})
            if estado_nombre == 'Ingresó' and not obj.fecha_ingreso:
                obj.fecha_ingreso = timezone.now()
            if estado_nombre == 'Finalizada' and not obj.fecha_salida:
                obj.fecha_salida = timezone.now()

        if slug == 'paquetes':
            estado_nombre = getattr(getattr(obj, 'estado_paquete', None), 'nombre', '')
            # Recepción: al registrar debe quedar con hora real si no viene informada.
            if not instance and not getattr(obj, 'fecha_recepcion', None):
                obj.fecha_recepcion = timezone.now()
            if estado_nombre == 'Entregado' and not obj.fecha_entrega:
                obj.fecha_entrega = timezone.now()
            # Si sigue recibido/pendiente, no debe tener fecha de entrega.
            if estado_nombre == 'Recibido':
                obj.fecha_entrega = None
                obj.persona = None

        obj.save()
        if hasattr(form, 'save_m2m'):
            try:
                form.save_m2m()
            except Exception:
                pass
        messages.success(request, 'Registro guardado correctamente')
        return redirect(f"{request.resolver_match.namespace}:module", slug=slug)

    if modal_persona:
        status_code = 400 if request.method == 'POST' else 200
        resp = render(request, 'personas/edit_modal_form.html', {
            **context(request), 'title': title, 'form': form, 'slug': slug, 'editing': bool(instance), 'modal_persona': True,
        })
        resp.status_code = status_code
        return resp

    if modal_torre:
        status_code = 400 if request.method == 'POST' else 200
        resp = render(request, 'torres/edit_modal_form.html', {
            **context(request), 'title': title, 'form': form, 'slug': slug, 'editing': bool(instance), 'modal_torre': True,
        })
        resp.status_code = status_code
        return resp

    if modal_apartamento:
        status_code = 400 if request.method == 'POST' else 200
        resp = render(request, 'apartamentos/form_modal.html', {
            **context(request), 'title': title, 'form': form, 'slug': slug, 'editing': bool(instance), 'modal_apartamento': True,
        })
        resp.status_code = status_code
        return resp

    if modal_asignacion:
        status_code = 400 if request.method == 'POST' else 200
        resp = render(request, 'residentes_asignaciones/form_modal.html', {
            **context(request), 'title': title, 'form': form, 'slug': slug, 'editing': bool(instance), 'modal_asignacion': True,
        })
        resp.status_code = status_code
        return resp

    if modal_paquete:
        status_code = 400 if request.method == 'POST' else 200
        resp = render(request, 'paquetes/form_modal.html', {
            **context(request), 'title': title, 'form': form, 'slug': slug, 'editing': bool(instance), 'modal_paquete': True,
        })
        resp.status_code = status_code
        return resp

    return render(request, 'form.html', {**context(request), 'title': title, 'form': form, 'slug': slug, 'editing': bool(instance)})


@login_required
def create_view(request, slug):
    return save_form(request, slug)


@login_required
def edit_view(request, slug, pk):
    if slug not in MODULES:
        raise Http404
    if not allowed(request.user, slug, 'editar'):
        return HttpResponseForbidden('Sin permiso')
    obj = get_object_by_key(MODULES[slug][1], pk)
    _rol_obj, rol_nombre, _slug_role = resolve_schema_role(request.user)
    if rol_nombre == 'Residente':
        apt_id = getattr(obj, 'apartamento_id', None)
        if apt_id and apt_id not in apartamentos_autorizados(request.user):
            return HttpResponseForbidden('Registro de otro apartamento')
    return save_form(request, slug, obj)


@login_required
@require_POST
def delete_view(request, slug, pk):
    denied = role_required_view(request, request.resolver_match.namespace)
    if denied:
        return denied
    if slug not in MODULES:
        raise Http404
    if slug == 'personas':
        messages.error(request, 'Las personas no se eliminan; desactívalas desde la edición o con el botón de estado para conservar el historial.')
        return redirect(f"{request.resolver_match.namespace}:module", slug=slug)
    _rol_obj, rol_nombre, _slug_role = resolve_schema_role(request.user)
    if slug == 'paquetes' and rol_nombre == 'Residente':
        return HttpResponseForbidden('No puedes eliminar paquetes')
    if not allowed(request.user, slug, 'eliminar'):
        return HttpResponseForbidden('Sin permiso')
    obj = get_object_by_key(MODULES[slug][1], pk)
    if slug == 'usuarios' and obj.pk == getattr(request.user, 'pk', None):
        return HttpResponseForbidden('No puedes eliminar tu propia cuenta')
    from django.db.models.deletion import ProtectedError
    try:
        obj.delete()
        messages.success(request, 'Registro eliminado')
    except ProtectedError:
        messages.error(request, 'No se puede eliminar: existen registros relacionados.')
    return redirect(f"{request.resolver_match.namespace}:module", slug=slug)


@login_required
@require_POST
def toggle_estado_view(request, slug, pk):
    denied = role_required_view(request, request.resolver_match.namespace)
    if denied:
        return denied
    if slug != 'personas' or slug not in MODULES:
        raise Http404
    if not allowed(request.user, slug, 'editar'):
        return HttpResponseForbidden('Sin permiso')
    obj = get_object_by_key(MODULES[slug][1], pk)
    obj.activo = not bool(getattr(obj, 'activo', False))
    obj.save(update_fields=['activo', 'fecha_actualizacion'] if hasattr(obj, 'fecha_actualizacion') else ['activo'])
    if obj.activo:
        messages.success(request, f'Persona "{obj}" activada correctamente.')
    else:
        messages.success(request, f'Persona "{obj}" desactivada correctamente.')
    return redirect(f"{request.resolver_match.namespace}:module", slug=slug)


@login_required
def apartamento_detalle(request, pk):
    denied = role_required_view(request, request.resolver_match.namespace)
    if denied:
        return denied
    if not allowed(request.user, 'apartamentos', 'ver'):
        return HttpResponseForbidden('Sin permiso para consultar apartamentos')
    apartamento = get_object_or_404(scoped(request.user, 'apartamentos', Apartamento.objects.select_related('torre')), pk=pk)
    sections = []
    for slug, title, model in (
        ('residentes', 'Vínculos (residentes)', ApartamentoPersona),
        ('visitas', 'Visitas', Visita),
        ('paquetes', 'Paquetes', Paquete),
        ('reservas', 'Reservas', Reserva),
        ('recibos', 'Recibos', Recibo),
    ):
        if not allowed(request.user, slug, 'ver'):
            continue
        qs = scoped(request.user, slug, model.objects.filter(apartamento_id=apartamento.pk))
        url = rurl(request, 'module', slug=slug) + '?' + urlencode({'apartamento': apartamento.pk})
        create_url = rurl(request, 'create', slug=slug) + '?' + urlencode({'apartamento': apartamento.pk})
        sections.append({
            'slug': slug, 'title': title, 'count': qs.count(),
            'items': list(qs[:10]),
            'url': url,
            'can_create': allowed(request.user, slug, 'crear'),
            'create_url': create_url,
        })
    return render(request, 'apartamento_detalle.html', {
        **context(request), 'apartamento': apartamento, 'sections': sections,
        'can_edit': allowed(request.user, 'apartamentos', 'editar'),
    })


@login_required
def apartamento_ver_modal(request, pk):
    denied = role_required_view(request, request.resolver_match.namespace)
    if denied:
        return denied
    if not allowed(request.user, 'apartamentos', 'ver'):
        return HttpResponseForbidden('Sin permiso para consultar apartamentos')
    apartamento = get_object_or_404(
        scoped(request.user, 'apartamentos', Apartamento.objects.select_related('torre')),
        pk=pk,
    )
    vinculos = list(
        ApartamentoPersona.objects.filter(apartamento_id=apartamento.pk, fecha_salida__isnull=True)
        .select_related('persona', 'persona__tipo_documento', 'tipo_residente')
        .order_by('tipo_residente__nombre', 'persona__apellidos', 'persona__nombres')
    )
    residentes = [v for v in vinculos if (getattr(getattr(v, 'tipo_residente', None), 'nombre', '') or '').strip().lower() != 'familiar']
    familiares = [v for v in vinculos if (getattr(getattr(v, 'tipo_residente', None), 'nombre', '') or '').strip().lower() == 'familiar']
    estado_asignacion = 'Asignado' if vinculos else 'No asignado'
    return render(request, 'apartamentos/ver_modal.html', {
        **context(request),
        'apartamento': apartamento,
        'estado_asignacion': estado_asignacion,
        'residentes_vinculos': residentes,
        'familiares_vinculos': familiares,
    })


@login_required
def apartamento_ver_modal_redirect(request, pk):
    _rol, _nombre, rslug = resolve_schema_role(request.user)
    if not rslug:
        return HttpResponseForbidden('Sin rol asignado')
    ns = getattr(getattr(request, 'resolver_match', None), 'namespace', None)
    if ns not in ROLE_NAMESPACES:
        request.resolver_match.namespace = rslug
    return apartamento_ver_modal(request, pk)


@login_required
def torre_masiva(request):
    denied = role_required_view(request, request.resolver_match.namespace)
    if denied:
        return denied
    if not has_action(request.user, 'torre_masiva'):
        return HttpResponseForbidden('Sin permiso')
    modal = request.GET.get('modal') == '1' or request.POST.get('modal') == '1'
    form = TorreMasivaForm(request.POST or None)
    template = 'torres/masiva_modal_form.html' if modal else 'torre_masiva.html'
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        with transaction.atomic():
            torre, _ = Torre.objects.get_or_create(nombre_torre=d['nombre_torre'])
            created = 0
            for piso in range(d['primer_piso'], d['primer_piso'] + d['pisos']):
                for num in range(1, d['apartamentos_por_piso'] + 1):
                    numero = f"{piso}{num:02d}"
                    apt, new = Apartamento.objects.get_or_create(torre=torre, numero_apartamento=numero, defaults={'piso': piso})
                    if apt.piso != piso:
                        form.add_error(None, f'Conflicto: el apartamento {numero} ya existe en otro piso.')
                        transaction.set_rollback(True)
                        resp = render(request, template, {**context(request), 'form': form, 'modal_torre': modal})
                        if modal:
                            resp.status_code = 400
                        return resp
                    created += int(new)
        messages.success(request, f'Torre {torre.nombre_torre}: {created} apartamentos nuevos; los existentes se conservaron.')
        return redirect(f"{request.resolver_match.namespace}:module", slug='apartamentos')
    resp = render(request, template, {**context(request), 'form': form, 'modal_torre': modal})
    if modal and request.method == 'POST':
        resp.status_code = 400
    return resp


@login_required
def reporte_pdf(request, slug):
    denied = role_required_view(request, request.resolver_match.namespace)
    if denied:
        return denied
    if slug not in MODULES:
        raise Http404
    if not allowed(request.user, slug, 'reporte'):
        return HttpResponseForbidden('Sin permiso')
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from django.utils.html import escape

    title, model = MODULES[slug]
    qs = scoped(request.user, slug, model.objects.all())
    q = request.GET.get('q', '').strip()[:100]
    if q:
        cond = Q()
        for field in SEARCH.get(slug, []):
            cond |= Q(**{field + '__icontains': q})
        qs = qs.filter(cond)
    status = request.GET.get('estado', '').strip()[:30]
    if status and slug in STATUS:
        qs = qs.filter(**{STATUS[slug]: status})
    for field in FILTERS.get(slug, ()):
        raw = request.GET.get(field, '')
        if raw.isdecimal():
            lookup = field if field.endswith('_id') else f'{field}_id'
            qs = qs.filter(**{lookup: int(raw)})

    fields = {
        'personas': ['tipo_documento', 'numero_documento', 'nombres', 'apellidos', 'telefono', 'correo'],
        'residentes': ['persona', 'apartamento', 'tipo_residente', 'fecha_ingreso', 'fecha_salida'],
        'residentes_apartamentos': ['apartamento', 'persona', 'tipo_residente', 'fecha_ingreso', 'fecha_salida'],
        'torres': ['nombre_torre'],
        'apartamentos': ['torre', 'numero_apartamento', 'piso', 'activo'],
        'visitas': ['nombre_visitante', 'documento_visitante', 'tipo_visita', 'apartamento', 'estado_visita', 'autorizada', 'fecha_ingreso'],
        'paquetes': ['descripcion', 'remitente', 'apartamento', 'persona', 'estado_paquete', 'fecha_recepcion', 'fecha_entrega'],
        'reservas': ['zona', 'apartamento', 'fecha_reserva', 'hora_inicio', 'hora_fin', 'cantidad_invitados', 'estado_reserva'],
        'recibos': ['apartamento', 'tipo_servicio', 'periodo', 'valor', 'fecha_emision', 'fecha_vencimiento', 'estado_recibo'],
        'zonas': ['nombre', 'descripcion'],
        'usuarios': ['username', 'first_name', 'last_name', 'email', 'is_active'],
    }.get(slug, [])
    qs = qs[:2000]
    buffer = BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=25, rightMargin=25, topMargin=32, bottomMargin=32)
    styles = getSampleStyleSheet()
    font = 'Helvetica'
    fontfile = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    if not __import__('os').path.exists(fontfile):
        fontfile = r'C:\Windows\Fonts\arial.ttf'
    if __import__('os').path.exists(fontfile):
        pdfmetrics.registerFont(TTFont('EdifiqUnicode', fontfile))
        font = 'EdifiqUnicode'
    styles['Normal'].fontName = font
    styles['Title'].fontName = font
    story = [Paragraph('EDIFIQ | Reporte de ' + escape(title), styles['Title']), Spacer(1, 10), Paragraph('Generado: ' + timezone.localtime().strftime('%Y-%m-%d %H:%M'), styles['Normal']), Spacer(1, 14)]

    header = ['ID'] + [model._meta.get_field(x).verbose_name.title() for x in fields]
    table_data = [[Paragraph(escape(str(h)), styles['Normal']) for h in header]]
    for obj in qs:
        row = [escape(object_key(model, obj))]
        for field in fields:
            value = getattr(obj, field, '')
            if value is None:
                value = ''
            if isinstance(value, bool):
                value = 'Sí' if value else 'No'
            row.append(str(value)[:95])
        table_data.append([Paragraph(escape(str(v)), styles['Normal']) for v in row])

    widths = [50] + [(landscape(A4)[0] - 100) / max(len(fields), 1)] * len(fields)
    table = Table(table_data, colWidths=widths, repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d9e9e8')), ('GRID', (0, 0), (-1, -1), .35, colors.HexColor('#d4dce2')), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f8fa')]), ('BOTTOMPADDING', (0, 0), (-1, -1), 7), ('TOPPADDING', (0, 0), (-1, -1), 7)]))
    story.append(table)
    pdf.build(story)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="edifiq_{slug}.pdf"'
    return response

def registro_view(request):
    """Registro público en 2 pasos: 1) validar datos de Persona, 2) crear cuenta vinculada.
    La persona NO se guarda en BD en el paso 1; se persiste junto con la cuenta al finalizar."""
    if getattr(request.user, 'is_authenticated', False):
        _rol, _nombre, slug = resolve_schema_role(request.user)
        if slug and has_any_permission(request.user):
            return redirect(f'{slug}:dashboard')
        return redirect('login')

    session_key = 'registro_persona_data'
    step = request.GET.get('paso') or request.POST.get('step') or '1'
    if step not in ('1', '2'):
        step = '1'

    persona_data = request.session.get(session_key) or {}
    if step == '2' and not persona_data:
        step = '1'

    persona_preview = None
    if persona_data:
        persona_preview = {
            'nombres': persona_data.get('nombres', ''),
            'apellidos': persona_data.get('apellidos', ''),
            'numero_documento': persona_data.get('numero_documento', ''),
        }

    if request.method == 'POST':
        if request.POST.get('action') == 'guardar_persona' or (step == '1' and 'password1' not in request.POST):
            form = RegistroPersonaForm(request.POST)
            if form.is_valid():
                cleaned = form.cleaned_data
                request.session[session_key] = {
                    'tipo_documento': cleaned['tipo_documento'].pk,
                    'numero_documento': cleaned['numero_documento'],
                    'nombres': cleaned['nombres'],
                    'apellidos': cleaned['apellidos'],
                    'telefono': cleaned.get('telefono') or '',
                    'correo': cleaned.get('correo') or '',
                }
                messages.success(request, 'Datos validados. Completa la creación de tu cuenta para finalizar el registro.')
                return redirect(f"{reverse('registro')}?paso=2")
            step = '1'
            return render(request, 'usuarios/registro.html', {'form': form, 'step': 1, 'persona': None})

        if request.POST.get('action') == 'crear_cuenta' or step == '2':
            if not persona_data:
                messages.error(request, 'Primero debes completar los datos de la persona.')
                return redirect('registro')
            cuenta_form = RegistroCuentaForm(request.POST)
            persona_form = RegistroPersonaForm(data=persona_data)
            persona_ok = persona_form.is_valid()
            cuenta_ok = cuenta_form.is_valid()
            if cuenta_ok and persona_ok:
                username = cuenta_form.cleaned_data['username']
                password = cuenta_form.cleaned_data['password1']
                try:
                    with transaction.atomic():
                        persona = persona_form.save(commit=False)
                        persona.activo = True
                        persona.save()
                        rol_residente = Rol.objects.filter(nombre__iexact='Residente').first() or Rol.objects.filter(nombre='Residente').first()
                        estado_activo = (
                            EstadoUsuario.objects.filter(nombre__iexact='Activo').first()
                            or EstadoUsuario.objects.filter(nombre__iexact='ACTIVO').first()
                            or EstadoUsuario.objects.first()
                        )
                        if not rol_residente or not estado_activo:
                            raise ValueError('Faltan catálogos requeridos (rol/estado_usuario).')
                        UsuarioEsquema.objects.create(
                            username=username[:50],
                            password=set_schema_password(password),
                            estado_usuario=estado_activo,
                            persona=persona,
                            rol=rol_residente,
                        )
                except Exception:
                    cuenta_form.add_error(None, 'No fue posible completar el registro. Verifica los datos e intenta nuevamente.')
                else:
                    request.session.pop(session_key, None)
                    messages.success(request, 'Cuenta creada correctamente. Ya puedes iniciar sesión.')
                    return redirect('login')
            if not persona_ok:
                request.session[session_key] = persona_data
                messages.error(request, 'Revisa los datos de la persona antes de finalizar el registro.')
            step = '2'
            return render(request, 'usuarios/registro.html', {'form': cuenta_form, 'step': 2, 'persona': persona_preview})

    if step == '2':
        form = RegistroCuentaForm()
        return render(request, 'usuarios/registro.html', {'form': form, 'step': 2, 'persona': persona_preview})

    initial = None
    if persona_data:
        initial = {
            'tipo_documento': persona_data.get('tipo_documento'),
            'numero_documento': persona_data.get('numero_documento', ''),
            'nombres': persona_data.get('nombres', ''),
            'apellidos': persona_data.get('apellidos', ''),
            'telefono': persona_data.get('telefono', ''),
            'correo': persona_data.get('correo', ''),
        }
    form = RegistroPersonaForm(initial=initial)
    return render(request, 'usuarios/registro.html', {'form': form, 'step': 1, 'persona': None})

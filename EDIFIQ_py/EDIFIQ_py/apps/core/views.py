from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from urllib.parse import urlencode

from apps.core.models import EstadoPaquete, EstadoRecibo, EstadoReserva, EstadoVisita
from apps.paquetes.models import Paquete
from apps.personas.models import Persona
from apps.recibos.models import Recibo
from apps.reservas.models import Reserva, ZonaComun
from apps.residentes.models import Apartamento, ApartamentoPersona, Torre
from apps.usuarios.models import Perfil
from apps.visitas.models import Visita

from .access import (
    ROLE_SLUGS,
    SLUG_TO_ROLE,
    apartamentos_autorizados,
    can_module,
    has_action,
    has_any_permission,
    resolve_schema_role,
    role_name_for_slug,
    role_slug_for_name,
)
from .forms import TorreMasivaForm, UsuarioForm, form_for

ROLE_NAMESPACES = ('administrador', 'residente', 'vigilante')

MODULES = {
    'personas': ('Personas', Persona),
    'residentes': ('Residentes', ApartamentoPersona),
    'torres': ('Torres', Torre),
    'apartamentos': ('Apartamentos', Apartamento),
    'visitas': ('Visitas', Visita),
    'paquetes': ('Paquetes', Paquete),
    'recibos': ('Recibos', Recibo),
    'zonas': ('Zonas comunes', ZonaComun),
    'reservas': ('Reservas', Reserva),
    'usuarios': ('Usuarios', get_user_model()),
}
SEARCH = {
    'personas': ['nombres', 'apellidos', 'numero_documento', 'correo'],
    'residentes': ['persona__nombres', 'persona__apellidos', 'persona__numero_documento', 'apartamento__numero_apartamento', 'tipo_residente__nombre'],
    'torres': ['nombre_torre'],
    'apartamentos': ['numero_apartamento', 'torre__nombre_torre'],
    'visitas': ['nombre_visitante', 'documento_visitante', 'tipo_visita__nombre', 'estado_visita__nombre'],
    'paquetes': ['remitente', 'descripcion', 'estado_paquete__nombre'],
    'recibos': ['tipo_servicio__nombre', 'periodo', 'estado_recibo__nombre'],
    'zonas': ['nombre', 'descripcion'],
    'reservas': ['zona__nombre', 'estado_reserva__nombre'],
    'usuarios': ['username', 'first_name', 'last_name', 'email'],
}
STATUS = {
    'visitas': 'estado_visita__nombre',
    'paquetes': 'estado_paquete__nombre',
    'recibos': 'estado_recibo__nombre',
    'reservas': 'estado_reserva__nombre',
}
RELATED = {
    'personas': [('residentes', 'Vínculos', 'persona'), ('usuarios', 'Usuario', 'perfil__persona')],
    'torres': [('apartamentos', 'Apartamentos', 'torre')],
    'apartamentos': [('residentes', 'Residentes', 'apartamento'), ('visitas', 'Visitas', 'apartamento'), ('paquetes', 'Paquetes', 'apartamento'), ('reservas', 'Reservas', 'apartamento'), ('recibos', 'Recibos', 'apartamento')],
    'zonas': [('reservas', 'Reservas', 'zona')],
    'residentes': [('personas', 'Persona', 'persona'), ('apartamentos', 'Apartamento', 'apartamento')],
    'visitas': [('apartamentos', 'Apartamento', 'apartamento')],
    'paquetes': [('apartamentos', 'Apartamento', 'apartamento')],
    'recibos': [('apartamentos', 'Apartamento', 'apartamento')],
    'reservas': [('apartamentos', 'Apartamento', 'apartamento'), ('zonas', 'Zona común', 'zona')],
    'usuarios': [('personas', 'Persona', 'persona'), ('apartamentos', 'Apartamento', 'apartamento')],
}
FILTERS = {
    'personas': ('pk',),
    'residentes': ('persona', 'apartamento'),
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
    """Denegar acceso si sin rol resoluble o sin permisos en rol_permiso."""
    _rol, _nombre, slug = resolve_schema_role(user)
    if not slug:
        return HttpResponseForbidden('Sin rol o sin permisos asignados')
    if not has_any_permission(user):
        return HttpResponseForbidden('Sin rol o sin permisos asignados')
    return None


def allowed(user, slug, action='ver'):
    if slug == 'usuarios' and not has_action(user, 'ver_usuarios'):
        return False
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
    if slug and has_any_permission(request.user):
        for s, (t, _m) in MODULES.items():
            if allowed(request.user, s, 'ver'):
                nav.append((s, t))
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
        perfil = Perfil.objects.filter(usuario_id=obj.pk).first()
        if perfil and perfil.persona_id and allowed(user, 'personas', 'ver'):
            links.append({'label': 'Persona', 'url': rurl(request, 'module', slug='personas') + '?' + urlencode({'pk': perfil.persona_id})})
        if perfil and perfil.apartamento_id and allowed(user, 'apartamentos', 'ver'):
            links.append({'label': 'Apartamento', 'url': rurl(request, 'apartamento_detalle', pk=perfil.apartamento_id)})
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
    if request.user.is_authenticated:
        _rol, _nombre, slug = resolve_schema_role(request.user)
        if slug and has_any_permission(request.user):
            return redirect(f'{slug}:dashboard')
        return redirect('dashboard')
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username', ''), password=request.POST.get('password', ''))
        if user:
            login(request, user)
            _rol, _nombre, slug = resolve_schema_role(user)
            if slug and has_any_permission(user):
                return redirect(f'{slug}:dashboard')
            return redirect('dashboard')
        messages.error(request, 'Usuario o contraseña incorrectos')
    return render(request, 'usuarios/login.html')


@require_POST
def logout_view(request):
    logout(request)
    return redirect('login')


# --- Compatibilidad: rutas genéricas redirigen al prefijo del rol ---

@login_required
def dashboard_redirect(request):
    _rol, _nombre, slug = resolve_schema_role(request.user)
    if not slug or not has_any_permission(request.user):
        return HttpResponseForbidden('Sin rol o sin permisos asignados')
    return redirect(f'{slug}:dashboard')


@login_required
def module_redirect(request, slug):
    _rol, _nombre, rslug = resolve_schema_role(request.user)
    if not rslug or not has_any_permission(request.user):
        return HttpResponseForbidden('Sin rol o sin permisos asignados')
    url = reverse(f'{rslug}:module', kwargs={'slug': slug})
    if request.META.get('QUERY_STRING'):
        url += '?' + request.META['QUERY_STRING']
    return redirect(url)


@login_required
def create_redirect(request, slug):
    _rol, _nombre, rslug = resolve_schema_role(request.user)
    if not rslug or not has_any_permission(request.user):
        return HttpResponseForbidden('Sin rol o sin permisos asignados')
    url = reverse(f'{rslug}:create', kwargs={'slug': slug})
    if request.META.get('QUERY_STRING'):
        url += '?' + request.META['QUERY_STRING']
    return redirect(url)


@login_required
def edit_redirect(request, slug, pk):
    _rol, _nombre, rslug = resolve_schema_role(request.user)
    if not rslug or not has_any_permission(request.user):
        return HttpResponseForbidden('Sin rol o sin permisos asignados')
    return redirect(f'{rslug}:edit', slug=slug, pk=pk)


@login_required
@require_POST
def delete_redirect(request, slug, pk):
    _rol, _nombre, rslug = resolve_schema_role(request.user)
    if not rslug or not has_any_permission(request.user):
        return HttpResponseForbidden('Sin rol o sin permisos asignados')
    return redirect(f'{rslug}:delete', slug=slug, pk=pk)


@login_required
def reporte_redirect(request, slug):
    _rol, _nombre, rslug = resolve_schema_role(request.user)
    if not rslug or not has_any_permission(request.user):
        return HttpResponseForbidden('Sin rol o sin permisos asignados')
    url = reverse(f'{rslug}:reporte_pdf', kwargs={'slug': slug})
    if request.META.get('QUERY_STRING'):
        url += '?' + request.META['QUERY_STRING']
    return redirect(url)


@login_required
def apartamento_detalle_redirect(request, pk):
    _rol, _nombre, rslug = resolve_schema_role(request.user)
    if not rslug or not has_any_permission(request.user):
        return HttpResponseForbidden('Sin rol o sin permisos asignados')
    return redirect(f'{rslug}:apartamento_detalle', pk=pk)



# --- Vistas por rol (prefijo completo) ---

def role_required_view(request, expected_role_slug):
    """Verifica namespace/rol esperado y política sin rol o sin permisos."""
    denied = deny_no_role_or_no_perms(request.user)
    if denied:
        return denied
    _rol, _nombre, slug = resolve_schema_role(request.user)
    if slug != expected_role_slug:
        if slug and has_any_permission(request.user):
            return redirect(f'{slug}:dashboard')
        return HttpResponseForbidden('Sin rol o sin permisos asignados')
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
    title, model = MODULES[slug]
    qs = scoped(request.user, slug, model.objects.all())
    q = request.GET.get('q', '').strip()[:100]
    status = request.GET.get('estado', '').strip()[:30]
    if q:
        condition = Q()
        for field in SEARCH.get(slug, []):
            condition |= Q(**{field + '__icontains': q})
        qs = qs.filter(condition)
    if status and slug in STATUS:
        qs = qs.filter(**{STATUS[slug]: status})
    active_relations = {}
    for field in FILTERS.get(slug, ()):
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
        if is_composite_model(model):
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

    return render(request, 'module.html', {
        **context(request), 'title': title, 'slug': slug, 'rows': rows,
        'resident_groups': resident_groups, 'active_relations': active_relations,
        'q': q, 'estado': status, 'states': states,
        'can_create': allowed(request.user, slug, 'crear'),
        'can_edit': allowed(request.user, slug, 'editar'),
        'can_delete': allowed(request.user, slug, 'eliminar'),
        'can_report': allowed(request.user, slug, 'reporte'),
        'can_bulk': slug == 'torres' and has_action(request.user, 'torre_masiva'),
        'composite': is_composite_model(model),
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

    Form = UsuarioForm if slug == 'usuarios' else form_for(model)
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
    if slug == 'residentes':
        form_kwargs['usuario'] = request.user
    form = Form(request.POST or None, **form_kwargs)

    if slug == 'residentes' and rol_nombre == 'Residente':
        ids = apartamentos_autorizados(request.user)
        if len(ids) == 1 and 'apartamento' in form.fields:
            form.fields['apartamento'].disabled = True
            form.fields['apartamento'].initial = ids[0]
    if slug == 'visitas' and rol_nombre == 'Residente':
        ids = apartamentos_autorizados(request.user)
        if not ids:
            return HttpResponseForbidden('No tienes un vínculo activo como propietario o arrendatario')
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
        form.fields['apartamento'].queryset = Apartamento.objects.filter(pk__in=ids)
        if len(ids) == 1:
            form.fields['apartamento'].disabled = True
            form.fields['apartamento'].initial = ids[0]
        if 'estado_reserva' in form.fields:
            form.fields['estado_reserva'].queryset = EstadoReserva.objects.filter(nombre='Pendiente')
            pendiente = EstadoReserva.objects.filter(nombre='Pendiente').first()
            if pendiente:
                form.fields['estado_reserva'].initial = pendiente

    if request.method == 'POST' and form.is_valid():
        if slug == 'usuarios':
            with transaction.atomic():
                obj = form.save(commit=False)
                if form.cleaned_data.get('password1'):
                    obj.set_password(form.cleaned_data['password1'])
                if instance and instance.pk == request.user.pk:
                    obj.is_active = True
                obj.save()
                persona = form.cleaned_data['persona']
                obj.first_name = persona.nombres[:150]
                obj.last_name = persona.apellidos[:150]
                obj.email = persona.correo or ''
                obj.save(update_fields=['first_name', 'last_name', 'email'])
                Perfil.objects.update_or_create(
                    usuario=obj,
                    defaults={
                        'persona': persona,
                        'rol': form.cleaned_data['rol'],
                        'apartamento': form.cleaned_data.get('apartamento') if form.cleaned_data['rol'] == 'Residente' else None,
                    },
                )
            messages.success(request, 'Usuario, persona y rol guardados correctamente')
            return redirect(f"{request.resolver_match.namespace}:module", slug='usuarios')

        obj = form.save(commit=False)
        if rol_nombre == 'Residente' and slug in ('residentes', 'visitas', 'reservas'):
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
                        return render(request, 'form.html', {**context(request), 'title': title, 'form': form, 'slug': slug, 'editing': bool(instance)})
                if estado_nombre == 'Finalizada' and (not instance or not getattr(instance, 'estado_visita', None) or instance.estado_visita.nombre != 'Ingresó'):
                    form.add_error('estado_visita', 'Primero registra el ingreso.')
                    return render(request, 'form.html', {**context(request), 'title': title, 'form': form, 'slug': slug, 'editing': bool(instance)})
            if estado_nombre == 'Ingresó' and not obj.fecha_ingreso:
                obj.fecha_ingreso = timezone.now()
            if estado_nombre == 'Finalizada' and not obj.fecha_salida:
                obj.fecha_salida = timezone.now()

        if slug == 'paquetes':
            estado_nombre = getattr(getattr(obj, 'estado_paquete', None), 'nombre', '')
            if estado_nombre == 'Entregado' and not obj.fecha_entrega:
                obj.fecha_entrega = timezone.now()
            if estado_nombre == 'Recibido':
                obj.fecha_entrega = None

        obj.save()
        if hasattr(form, 'save_m2m'):
            try:
                form.save_m2m()
            except Exception:
                pass
        messages.success(request, 'Registro guardado correctamente')
        return redirect(f"{request.resolver_match.namespace}:module", slug=slug)

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
    if not allowed(request.user, slug, 'eliminar'):
        return HttpResponseForbidden('Sin permiso')
    obj = get_object_by_key(MODULES[slug][1], pk)
    if slug == 'usuarios' and obj.pk == request.user.pk:
        return HttpResponseForbidden('No puedes eliminar tu propia cuenta')
    from django.db.models.deletion import ProtectedError
    try:
        obj.delete()
        messages.success(request, 'Registro eliminado')
    except ProtectedError:
        messages.error(request, 'No se puede eliminar: existen registros relacionados.')
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
def torre_masiva(request):
    denied = role_required_view(request, request.resolver_match.namespace)
    if denied:
        return denied
    if not has_action(request.user, 'torre_masiva'):
        return HttpResponseForbidden('Sin permiso')
    form = TorreMasivaForm(request.POST or None)
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
                        return render(request, 'torre_masiva.html', {**context(request), 'form': form})
                    created += int(new)
        messages.success(request, f'Torre {torre.nombre_torre}: {created} apartamentos nuevos; los existentes se conservaron.')
        return redirect(f"{request.resolver_match.namespace}:module", slug='apartamentos')
    return render(request, 'torre_masiva.html', {**context(request), 'form': form})


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

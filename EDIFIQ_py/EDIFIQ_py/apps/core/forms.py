from datetime import datetime, timedelta
from pathlib import Path

from django import forms
from django.utils import timezone

from apps.core.access import resolve_schema_role
from apps.core.models import EstadoPaquete, EstadoRecibo, EstadoReserva, EstadoUsuario, EstadoVisita, Rol, TipoDocumento, TipoResidente, TipoServicio, Usuario
from apps.paquetes.models import Paquete
from apps.personas.models import Persona
from apps.recibos.models import Recibo
from apps.reservas.models import Reserva, ZonaComun
from apps.residentes.models import Apartamento, ApartamentoPersona, Torre
from apps.visitas.models import Visita


class StyledForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'field-input')
            if isinstance(field, forms.DateTimeField):
                field.widget = forms.DateTimeInput(
                    attrs={'type': 'datetime-local', 'class': 'field-input'},
                    format='%Y-%m-%dT%H:%M',
                )
                field.input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S']
            elif isinstance(field, forms.DateField):
                field.widget = forms.DateInput(attrs={'type': 'date', 'class': 'field-input'}, format='%Y-%m-%d')
            elif isinstance(field, forms.TimeField):
                field.widget = forms.TimeInput(attrs={'type': 'time', 'class': 'field-input'}, format='%H:%M')
                field.input_formats = ['%H:%M', '%H:%M:%S']
        for name, field in self.fields.items():
            if isinstance(field, forms.DateTimeField) and getattr(self.instance, 'pk', None):
                val = getattr(self.instance, name, None)
                if val:
                    try:
                        self.initial[name] = timezone.localtime(val).strftime('%Y-%m-%dT%H:%M')
                    except Exception:
                        self.initial[name] = val.strftime('%Y-%m-%dT%H:%M')


class PersonaForm(StyledForm):
    class Meta:
        model = Persona
        fields = ['tipo_documento', 'numero_documento', 'nombres', 'apellidos', 'telefono', 'correo', 'activo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if getattr(self.instance, 'pk', None):
            # Edición (admin/personas): no se permiten cambios en datos sensibles de identidad.
            for name in ('tipo_documento', 'numero_documento', 'nombres', 'apellidos'):
                if name in self.fields:
                    self.fields[name].disabled = True
                    self.fields[name].required = False
            self.fields['activo'].label = 'Persona activa'

    def clean_numero_documento(self):
        import re
        if getattr(self.instance, 'pk', None):
            return self.instance.numero_documento
        val = (self.cleaned_data.get('numero_documento') or '').strip()
        if not re.fullmatch(r'\d{1,10}', val):
            raise forms.ValidationError('Documento: máximo 10 dígitos numéricos.')
        return val

    def clean_tipo_documento(self):
        if getattr(self.instance, 'pk', None):
            return self.instance.tipo_documento
        return self.cleaned_data.get('tipo_documento')

    def clean_nombres(self):
        if getattr(self.instance, 'pk', None):
            return self.instance.nombres
        return (self.cleaned_data.get('nombres') or '').strip()

    def clean_apellidos(self):
        if getattr(self.instance, 'pk', None):
            return self.instance.apellidos
        return (self.cleaned_data.get('apellidos') or '').strip()

    def clean_telefono(self):
        import re
        val = (self.cleaned_data.get('telefono') or '').strip()
        if val and not re.fullmatch(r'\d{1,10}', val):
            raise forms.ValidationError('Teléfono: máximo 10 dígitos numéricos.')
        return val or None

    def clean_correo(self):
        val = (self.cleaned_data.get('correo') or '').strip().lower()
        return val or None

    def clean(self):
        data = super().clean()
        td = data.get('tipo_documento') or getattr(self.instance, 'tipo_documento', None)
        nd = data.get('numero_documento') or getattr(self.instance, 'numero_documento', None)
        if td and nd and not getattr(self.instance, 'pk', None):
            qs = Persona.objects.filter(tipo_documento=td, numero_documento=nd)
            if qs.exists():
                self.add_error('numero_documento', 'Ya existe una persona con ese tipo y número de documento.')
        return data


class VisitaForm(StyledForm):
    estado_display = forms.CharField(
        label='Estado de la visita',
        required=False,
        disabled=True,
    )

    class Meta:
        model = Visita
        fields = [
            'tipo_visita', 'tipo_documento', 'nombre_visitante', 'documento_visitante',
            'motivo_visita', 'apartamento', 'fecha_ingreso', 'fecha_salida',
        ]

    def __init__(self, *args, rol_actual=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.rol_actual = rol_actual
        if not getattr(self.instance, 'pk', None):
            self.fields['fecha_ingreso'].initial = timezone.localtime(
                timezone.now()
            ).strftime('%Y-%m-%dT%H:%M')
            self.fields['estado_display'].initial = (
                'Autorizada' if rol_actual == 'Residente' else 'Pendiente por autorizar'
            )
        else:
            estado_nombre = getattr(
                getattr(self.instance, 'estado_visita', None),
                'nombre',
                '',
            )
            if estado_nombre in ('Finalizada', 'Cancelada'):
                display = estado_nombre
            elif getattr(self.instance, 'autorizada', False):
                display = 'Autorizada'
            else:
                display = 'Pendiente por autorizar'
            self.fields['estado_display'].initial = display
        if rol_actual == 'Residente':
            self.fields['fecha_salida'].disabled = True

    def clean_documento_visitante(self):
        import re
        val = (self.cleaned_data.get('documento_visitante') or '').strip()
        if not re.fullmatch(r'\d{1,10}', val):
            raise forms.ValidationError('Máximo 10 dígitos numéricos.')
        return val

    def clean(self):
        d = super().clean()
        if d.get('fecha_ingreso') and d.get('fecha_salida') and d['fecha_salida'] < d['fecha_ingreso']:
            raise forms.ValidationError('La salida no puede ser anterior al ingreso.')
        return d


class PaqueteForm(StyledForm):
    """Registro/edición de paquetes (admin/vigilante). La recepción se registra con fecha y hora."""

    class Meta:
        model = Paquete
        fields = ['descripcion', 'remitente', 'apartamento', 'estado_paquete', 'fecha_recepcion']
        labels = {
            'descripcion': 'Paquete / descripción',
            'fecha_recepcion': 'Fecha y hora de recepción',
            'estado_paquete': 'Estado',
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        if 'estado_paquete' in self.fields:
            self.fields['estado_paquete'].queryset = EstadoPaquete.objects.all().order_by('id_estado_paquete')
            recibido = EstadoPaquete.objects.filter(nombre__iexact='Recibido').first()
            if not getattr(self.instance, 'pk', None):
                # Registrar: siempre se recibe ahora; estado inicial Recibido (pendiente por entregar).
                if 'fecha_recepcion' in self.fields:
                    self.fields['fecha_recepcion'].initial = timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M')
                    self.fields['fecha_recepcion'].required = True
                if recibido:
                    self.fields['estado_paquete'].initial = recibido
        if 'apartamento' in self.fields:
            self.fields['apartamento'].queryset = Apartamento.objects.select_related('torre').order_by('torre__nombre_torre', 'numero_apartamento')
        # En edición no se modifica la recepción original ni el apartamento/estado desde este form básico;
        # la entrega se gestiona con la acción "Entregar".
        if getattr(self.instance, 'pk', None):
            if 'fecha_recepcion' in self.fields:
                self.fields['fecha_recepcion'].disabled = True
            if 'estado_paquete' in self.fields:
                self.fields['estado_paquete'].disabled = True

    def clean(self):
        data = super().clean()
        # Asegurar estado Recibido al crear si no se envió.
        if not getattr(self.instance, 'pk', None) and not data.get('estado_paquete'):
            recibido = EstadoPaquete.objects.filter(nombre__iexact='Recibido').first()
            if recibido:
                data['estado_paquete'] = recibido
        return data


class PaqueteEntregaForm(StyledForm):
    """Entrega de paquete: persona que recibe (del apartamento), fecha/hora exacta y observación opcional."""

    observacion = forms.CharField(
        label='Observación (opcional)',
        required=False,
        widget=forms.Textarea(attrs={'class': 'field-input', 'rows': 3, 'placeholder': 'Observación de la entrega (si es necesario)'}),
    )

    class Meta:
        model = Paquete
        fields = ['persona', 'fecha_entrega', 'observacion']
        labels = {
            'persona': 'Persona que recibe',
            'fecha_entrega': 'Fecha y hora de entrega',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        now_local = timezone.localtime(timezone.now())
        min_dt = now_local.replace(hour=0, minute=0, second=0, microsecond=0).strftime('%Y-%m-%dT%H:%M')
        if 'fecha_entrega' in self.fields:
            self.fields['fecha_entrega'].required = True
            self.fields['fecha_entrega'].widget.attrs['min'] = min_dt
            self.fields['fecha_entrega'].widget.attrs['step'] = '60'
            if not self.initial.get('fecha_entrega') and not getattr(self.instance, 'fecha_entrega', None):
                self.initial['fecha_entrega'] = now_local.strftime('%Y-%m-%dT%H:%M')

        apt_id = getattr(self.instance, 'apartamento_id', None)
        persona_ids = []
        if apt_id:
            persona_ids = list(
                ApartamentoPersona.objects.filter(apartamento_id=apt_id, fecha_salida__isnull=True)
                .values_list('persona_id', flat=True).distinct()
            )
        qs = Persona.objects.select_related('tipo_documento').filter(pk__in=persona_ids).order_by('apellidos', 'nombres')
        if 'persona' in self.fields:
            self.fields['persona'].queryset = qs
            self.fields['persona'].required = True
            self.fields['persona'].label = 'Persona que recibe'
            self.fields['persona'].empty_label = 'Seleccione la persona que recibe'
            # incluir persona actual si ya estaba asignada (histórico)
            if getattr(self.instance, 'persona_id', None) and not qs.filter(pk=self.instance.persona_id).exists():
                self.fields['persona'].queryset = (Persona.objects.filter(pk=self.instance.persona_id) | qs).distinct()

    def clean_fecha_entrega(self):
        val = self.cleaned_data.get('fecha_entrega')
        if not val:
            return val
        now_local = timezone.localtime(timezone.now())
        today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        # comparar en hora local
        try:
            val_local = timezone.localtime(val) if timezone.is_aware(val) else val
        except Exception:
            val_local = val
        if val_local < today_start:
            raise forms.ValidationError('La fecha/hora de entrega no puede ser anterior a hoy.')
        recep = getattr(self.instance, 'fecha_recepcion', None)
        if recep:
            try:
                r_local = timezone.localtime(recep) if timezone.is_aware(recep) else recep
                if val_local < r_local:
                    raise forms.ValidationError('La entrega no puede ser anterior a la recepción del paquete.')
            except Exception:
                pass
        return val

    def save(self, commit=True):
        obj = super().save(commit=False)
        obs = (self.cleaned_data.get('observacion') or '').strip()
        # Sin columna de observación en esquema: se anexa a la descripción si se proporciona.
        if obs:
            base = (obj.descripcion or '').strip()
            marker = f"Observación entrega: {obs}"
            if marker not in base:
                obj.descripcion = (base + ("\n" if base else "") + marker).strip()[:200]
        entregado = EstadoPaquete.objects.filter(nombre__iexact='Entregado').first()
        if entregado:
            obj.estado_paquete = entregado
        if commit:
            obj.save()
        return obj


class ReciboForm(StyledForm):
    class Meta:
        model = Recibo
        fields = [
            'tipo_servicio', 'apartamento', 'periodo', 'valor',
            'fecha_emision', 'fecha_vencimiento',
        ]
        labels = {
            'tipo_servicio': 'Servicio',
            'apartamento': 'Apartamento',
            'periodo': 'Periodo',
            'valor': 'Valor',
            'fecha_emision': 'Fecha de emisión',
            'fecha_vencimiento': 'Fecha de vencimiento',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo_servicio'].queryset = TipoServicio.objects.filter(
            nombre__in=('Administración', 'Agua', 'Luz', 'Gas', 'Internet')
        ).order_by('id_tipo_servicio')
        self.fields['apartamento'].queryset = Apartamento.objects.filter(
            activo=True
        ).select_related('torre').order_by('torre__nombre_torre', 'numero_apartamento')
        self.fields['periodo'].widget.attrs['placeholder'] = 'Ej.: 2026-11'
        self.fields['valor'].min_value = 0.01
        self.fields['valor'].widget.attrs['min'] = '0.01'
        self.fields['valor'].widget.attrs['step'] = '0.01'

    def clean(self):
        data = super().clean()
        emision = data.get('fecha_emision')
        vencimiento = data.get('fecha_vencimiento')
        if emision and vencimiento and vencimiento < emision:
            self.add_error(
                'fecha_vencimiento',
                'La fecha de vencimiento no puede ser anterior a la fecha de emisión.',
            )
        return data


class ReciboComprobanteForm(forms.Form):
    comprobante = forms.FileField(
        label='Comprobante de pago (imagen)',
        widget=forms.ClearableFileInput(attrs={
            'class': 'field-input',
            'accept': 'image/jpeg,image/png,image/webp',
        }),
    )

    def clean_comprobante(self):
        archivo = self.cleaned_data['comprobante']
        if archivo.size > 5 * 1024 * 1024:
            raise forms.ValidationError('La imagen no puede superar los 5 MB.')

        extension = Path(archivo.name).suffix.lower()
        firmas = {
            '.jpg': lambda data: data.startswith(b'\xff\xd8\xff'),
            '.jpeg': lambda data: data.startswith(b'\xff\xd8\xff'),
            '.png': lambda data: data.startswith(b'\x89PNG\r\n\x1a\n'),
            '.webp': lambda data: data.startswith(b'RIFF') and data[8:12] == b'WEBP',
        }
        validar_firma = firmas.get(extension)
        firma = archivo.read(12)
        archivo.seek(0)
        if not validar_firma or not validar_firma(firma):
            raise forms.ValidationError('Sube una imagen JPG, PNG o WEBP válida.')
        return archivo


class ReservaForm(StyledForm):
    class Meta:
        model = Reserva
        fields = [
            'zona', 'apartamento', 'fecha_reserva', 'cantidad_invitados',
            'hora_inicio', 'hora_fin', 'estado_reserva',
        ]

    def __init__(self, *args, rol_actual=None, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.rol_actual = rol_actual
        self.fields['zona'].queryset = ZonaComun.objects.all().order_by('nombre')
        self.fields['zona'].label = 'Zona común'
        self.fields['apartamento'].queryset = Apartamento.objects.filter(activo=True).select_related(
            'torre'
        ).order_by('torre__nombre_torre', 'numero_apartamento')
        self.fields['apartamento'].label = 'Apartamento'
        self.fields['fecha_reserva'].label = 'Fecha'
        self.fields['fecha_reserva'].widget.attrs['min'] = timezone.localdate().isoformat()
        self.fields['cantidad_invitados'].label = 'Número de invitados'
        self.fields['hora_inicio'].label = 'Hora de inicio'
        self.fields['hora_fin'].label = 'Hora de fin'
        self.fields['hora_fin'].help_text = (
            'Si la hora de fin es menor que la de inicio, se entiende que termina al día siguiente.'
        )
        if rol_actual == 'Residente':
            from apps.core.access import apartamentos_autorizados

            apartment_ids = apartamentos_autorizados(usuario)
            self.fields['apartamento'].queryset = Apartamento.objects.filter(
                pk__in=apartment_ids, activo=True
            ).select_related('torre').order_by('torre__nombre_torre', 'numero_apartamento')
            self.fields.pop('estado_reserva')
            if len(apartment_ids) == 1:
                self.fields.pop('apartamento')
                self.order_fields([
                    'zona', 'fecha_reserva', 'hora_inicio',
                    'hora_fin', 'cantidad_invitados',
                ])
            else:
                self.order_fields([
                    'zona', 'apartamento', 'fecha_reserva', 'hora_inicio',
                    'hora_fin', 'cantidad_invitados',
                ])
        else:
            if rol_actual == 'Administrador':
                apartamentos_con_residentes = ApartamentoPersona.objects.filter(
                    fecha_salida__isnull=True,
                    apartamento__activo=True,
                    persona__activo=True,
                ).values_list('apartamento_id', flat=True)
                self.fields['apartamento'].queryset = self.fields['apartamento'].queryset.filter(
                    pk__in=apartamentos_con_residentes
                )
            self.fields['estado_reserva'].queryset = EstadoReserva.objects.filter(
                nombre__in=('Pendiente', 'Aprobada', 'Cancelada')
            ).order_by('id_estado_reserva')
            self.fields['estado_reserva'].label = 'Estado'
            if not getattr(self.instance, 'pk', None):
                self.fields['estado_reserva'].initial = EstadoReserva.objects.filter(
                    nombre__iexact='Pendiente'
                ).first()
            self.order_fields([
                'zona', 'apartamento', 'fecha_reserva', 'cantidad_invitados',
                'hora_inicio', 'hora_fin', 'estado_reserva',
            ])

    def clean(self):
        data = super().clean()
        fecha = data.get('fecha_reserva')
        hi = data.get('hora_inicio')
        hf = data.get('hora_fin')
        zona = data.get('zona')
        estado = data.get('estado_reserva') or getattr(self.instance, 'estado_reserva', None)
        if fecha and fecha < timezone.localdate():
            self.add_error('fecha_reserva', 'La fecha no puede ser anterior a hoy.')
        if hi and hf and hf == hi:
            raise forms.ValidationError('La hora de inicio y de fin no pueden ser iguales.')
        cancelada = bool(estado and getattr(estado, 'nombre', '').lower() == 'cancelada')
        if zona and fecha and hi and hf and fecha >= timezone.localdate() and not cancelada:
            if reserva_tiene_conflicto_aprobado(
                zona,
                fecha,
                hi,
                hf,
                exclude_pk=getattr(self.instance, 'pk', None),
            ):
                raise forms.ValidationError(
                    'La zona ya tiene una reserva aprobada que se cruza con ese horario.'
                )
        return data


def reserva_tiene_conflicto_aprobado(zona, fecha, hora_inicio, hora_fin, exclude_pk=None):
    inicio = datetime.combine(fecha, hora_inicio)
    fin = datetime.combine(fecha, hora_fin)
    if hora_fin <= hora_inicio:
        fin += timedelta(days=1)

    conflictos = Reserva.objects.filter(
        zona=zona,
        fecha_reserva__gte=fecha - timedelta(days=1),
        fecha_reserva__lte=fecha + timedelta(days=1),
        estado_reserva__nombre__iexact='Aprobada',
    )
    if exclude_pk is not None:
        conflictos = conflictos.exclude(pk=exclude_pk)
    for reserva in conflictos:
        reserva_inicio = datetime.combine(reserva.fecha_reserva, reserva.hora_inicio)
        reserva_fin = datetime.combine(reserva.fecha_reserva, reserva.hora_fin)
        if reserva.hora_fin <= reserva.hora_inicio:
            reserva_fin += timedelta(days=1)
        if inicio < reserva_fin and fin > reserva_inicio:
            return True
    return False


class ApartamentoForm(StyledForm):
    class Meta:
        model = Apartamento
        fields = ['torre', 'numero_apartamento', 'piso', 'activo']
        labels = {
            'numero_apartamento': 'Número de apartamento',
            'activo': 'Activo',
        }

    def clean_numero_apartamento(self):
        val = (self.cleaned_data.get('numero_apartamento') or '').strip()
        if not val:
            raise forms.ValidationError('Ingresa el número de apartamento.')
        return val

    def clean(self):
        data = super().clean()
        torre = data.get('torre')
        numero = data.get('numero_apartamento')
        if torre and numero:
            qs = Apartamento.objects.filter(torre=torre, numero_apartamento=numero)
            if self.instance and getattr(self.instance, 'pk', None):
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('numero_apartamento', 'Ya existe un apartamento con ese número en la torre seleccionada.')
        return data


class ApartamentoPersonaForm(StyledForm):
    class Meta:
        model = ApartamentoPersona
        fields = ['apartamento', 'persona', 'tipo_residente', 'fecha_ingreso', 'fecha_salida']


class AsignacionResidenteForm(StyledForm):
    class Meta:
        model = ApartamentoPersona
        fields = ['apartamento', 'persona', 'tipo_residente', 'fecha_ingreso', 'fecha_salida']
        labels = {
            'fecha_ingreso': 'Fecha de ingreso',
            'fecha_salida': 'Fecha de salida (opcional)',
        }
        widgets = {
            'fecha_ingreso': forms.DateInput(attrs={'type': 'date'}),
            'fecha_salida': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario

        self.fields['apartamento'].queryset = Apartamento.objects.select_related('torre').order_by(
            'torre__nombre_torre', 'numero_apartamento'
        )
        self.fields['persona'].queryset = Persona.objects.select_related('tipo_documento').order_by('apellidos', 'nombres')
        tipos = TipoResidente.objects.filter(
            nombre__in=['Propietario', 'Arrendatario', 'Familiar']
        ).order_by('id_tipo_residente')
        self.fields['tipo_residente'].queryset = tipos if tipos.exists() else TipoResidente.objects.all().order_by('id_tipo_residente')
        self.fields['fecha_salida'].required = False

        rol_nombre = None
        if usuario is not None:
            try:
                from apps.core.access import resolve_schema_role
                _rol, rol_nombre, _slug = resolve_schema_role(usuario)
            except Exception:
                rol_nombre = getattr(usuario, 'rol_nombre', None)
        if usuario and rol_nombre == 'Residente':
            try:
                from apps.core.access import apartamentos_autorizados
                ids = apartamentos_autorizados(usuario)
                self.fields['apartamento'].queryset = Apartamento.objects.filter(pk__in=ids).select_related('torre').order_by(
                    'torre__nombre_torre', 'numero_apartamento'
                )
            except Exception:
                pass

        if getattr(self.instance, 'apartamento_id', None) and getattr(self.instance, 'persona_id', None):
            self.fields['apartamento'].disabled = True
            self.fields['persona'].disabled = True

    def clean(self):
        data = super().clean()
        apartamento = data.get('apartamento')
        persona = data.get('persona')
        fecha_ingreso = data.get('fecha_ingreso')
        fecha_salida = data.get('fecha_salida')

        if fecha_ingreso and fecha_salida and fecha_salida < fecha_ingreso:
            self.add_error('fecha_salida', 'La fecha de salida no puede ser anterior a la fecha de ingreso.')

        if apartamento and persona:
            qs = ApartamentoPersona.objects.filter(apartamento=apartamento, persona=persona)
            if getattr(self.instance, 'apartamento_id', None) and getattr(self.instance, 'persona_id', None):
                qs = qs.exclude(apartamento_id=self.instance.apartamento_id, persona_id=self.instance.persona_id)
            if qs.exists():
                self.add_error(None, 'Ya existe una asignación para esta persona en el apartamento seleccionado.')

        rol_nombre = None
        if getattr(self, 'usuario', None) is not None:
            try:
                from apps.core.access import resolve_schema_role, apartamentos_autorizados
                _rol, rol_nombre, _slug = resolve_schema_role(self.usuario)
                if rol_nombre == 'Residente' and apartamento and apartamento.pk not in apartamentos_autorizados(self.usuario):
                    self.add_error('apartamento', 'No puedes modificar otro apartamento.')
            except Exception:
                pass

        return data


class FamiliarForm(forms.Form):
    tipo_documento = forms.ModelChoiceField(
        label='Tipo de documento',
        queryset=TipoDocumento.objects.all().order_by('id_tipo_documento'),
        widget=forms.Select(attrs={'class': 'field-input'}),
    )
    numero_documento = forms.CharField(
        label='Número de documento',
        max_length=10,
        widget=forms.TextInput(attrs={'class': 'field-input', 'inputmode': 'numeric'}),
    )
    nombres = forms.CharField(
        label='Nombres',
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'field-input'}),
    )
    apellidos = forms.CharField(
        label='Apellidos',
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'field-input'}),
    )
    telefono = forms.CharField(
        label='Teléfono',
        max_length=10,
        required=False,
        widget=forms.TextInput(attrs={'class': 'field-input', 'inputmode': 'numeric'}),
    )
    correo = forms.EmailField(
        label='Correo electrónico',
        max_length=100,
        required=False,
        widget=forms.EmailInput(attrs={'class': 'field-input'}),
    )

    def __init__(self, *args, apartment_ids=(), instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        if not instance and len(apartment_ids) > 1:
            self.fields['apartamento'] = forms.ModelChoiceField(
                label='Apartamento',
                queryset=Apartamento.objects.filter(pk__in=apartment_ids)
                .select_related('torre')
                .order_by('torre__nombre_torre', 'numero_apartamento'),
                widget=forms.Select(attrs={'class': 'field-input'}),
            )
        if instance:
            persona = instance.persona
            self.initial.update({
                'tipo_documento': persona.tipo_documento_id,
                'numero_documento': persona.numero_documento,
                'nombres': persona.nombres,
                'apellidos': persona.apellidos,
                'telefono': persona.telefono or '',
                'correo': persona.correo or '',
            })

    def clean_numero_documento(self):
        import re

        value = (self.cleaned_data.get('numero_documento') or '').strip()
        if not re.fullmatch(r'\d{1,10}', value):
            raise forms.ValidationError('El documento debe tener máximo 10 dígitos numéricos.')
        return value

    def clean_nombres(self):
        return (self.cleaned_data.get('nombres') or '').strip()

    def clean_apellidos(self):
        return (self.cleaned_data.get('apellidos') or '').strip()

    def clean_telefono(self):
        import re

        value = (self.cleaned_data.get('telefono') or '').strip()
        if value and not re.fullmatch(r'\d{1,10}', value):
            raise forms.ValidationError('El teléfono debe tener máximo 10 dígitos numéricos.')
        return value or None

    def clean_correo(self):
        return (self.cleaned_data.get('correo') or '').strip().lower() or None

    def clean(self):
        data = super().clean()
        tipo_documento = data.get('tipo_documento')
        numero_documento = data.get('numero_documento')
        if tipo_documento and numero_documento and self.instance:
            duplicate = Persona.objects.filter(
                tipo_documento=tipo_documento,
                numero_documento=numero_documento,
            ).exclude(pk=self.instance.persona_id).exists()
            if duplicate:
                self.add_error('numero_documento', 'Ya existe una persona con ese tipo y número de documento.')
        return data


class PerfilForm(StyledForm):
    """Obsoleto: la aplicación usa la tabla original `usuario` (sin Perfil)."""
    pass


def form_for(model):
    special = {
        Persona: PersonaForm,
        Apartamento: ApartamentoForm,
        ApartamentoPersona: ApartamentoPersonaForm,
        Reserva: ReservaForm,
        Visita: VisitaForm,
        Paquete: PaqueteForm,
        Recibo: ReciboForm,
        Usuario: UsuarioForm,
    }
    if model in special:
        return special[model]
    Meta = type('Meta', (), {'model': model, 'fields': '__all__'})
    return type(model.__name__ + 'Form', (StyledForm,), {'Meta': Meta})


class UsuarioForm(StyledForm):
    """Alta y edición de cuentas usando la tabla original `usuario` (sin auth_user/Perfil)."""
    password1 = forms.CharField(label='Contraseña', widget=forms.PasswordInput(attrs={'class': 'field-input'}), required=False)
    password2 = forms.CharField(label='Confirmar contraseña', widget=forms.PasswordInput(attrs={'class': 'field-input'}), required=False)

    class Meta:
        model = Usuario
        fields = ['username', 'estado_usuario', 'persona', 'rol']

    def __init__(self, *args, rol_actual=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.rol_actual = rol_actual
        if 'persona' in self.fields:
            used = Usuario.objects.exclude(pk=getattr(self.instance, 'pk', None)).values_list('persona_id', flat=True)
            qs = Persona.objects.filter(activo=True).exclude(pk__in=used).select_related(
                'tipo_documento'
            ).order_by('apellidos', 'nombres')
            if self.instance and getattr(self.instance, 'persona_id', None):
                actual = Persona.objects.filter(pk=self.instance.persona_id).select_related('tipo_documento')
                qs = (actual | qs).distinct()
            self.fields['persona'].queryset = qs
            self.fields['persona'].widget.attrs['class'] = 'field-input'
            self.fields['persona'].label = 'Persona registrada'
            self.fields['persona'].empty_label = 'Seleccione una persona registrada'
            self.fields['persona'].label_from_instance = self._persona_label
        if 'rol' in self.fields:
            self.fields['rol'].queryset = Rol.objects.all().order_by('id_rol')
        if 'estado_usuario' in self.fields:
            self.fields['estado_usuario'].queryset = EstadoUsuario.objects.all().order_by('id_estado_usuario')
            activo = EstadoUsuario.objects.filter(nombre__iexact='Activo').first() or EstadoUsuario.objects.first()
            if not self.instance.pk and activo:
                self.fields['estado_usuario'].initial = activo
        if self.instance.pk:
            self.fields['password1'].help_text = 'Déjalo en blanco para conservar la contraseña actual.'
        else:
            self.fields['password1'].required = True
            self.fields['password2'].required = True

    @staticmethod
    def _persona_label(persona):
        tipo_documento = getattr(persona.tipo_documento, 'abreviatura', '') or persona.tipo_documento.nombre
        return (
            f'{persona.nombres} {persona.apellidos} · '
            f'{tipo_documento} {persona.numero_documento}'
        )

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        if not username:
            raise forms.ValidationError('Ingresa un nombre de usuario.')
        qs = Usuario.objects.filter(username__iexact=username)
        if self.instance and getattr(self.instance, 'pk', None):
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Este nombre de usuario ya está en uso.')
        return username

    def clean(self):
        data = super().clean()
        p1, p2 = data.get('password1'), data.get('password2')
        if p1 != p2:
            self.add_error('password2', 'Las contraseñas no coinciden.')
        if not self.instance.pk and not p1:
            self.add_error('password1', 'La contraseña es obligatoria.')
        if p1 and not self.errors.get('password1'):
            from django.contrib.auth.password_validation import validate_password
            try:
                validate_password(p1)
            except forms.ValidationError as error:
                self.add_error('password1', error)
        persona = data.get('persona')
        if persona:
            linked = Usuario.objects.filter(persona=persona).exclude(pk=getattr(self.instance, 'pk', None)).exists()
            if linked:
                self.add_error('persona', 'Esta persona ya tiene un usuario asignado.')
        return data

    def save(self, commit=True):
        from apps.core.schema_auth import set_schema_password
        obj = super().save(commit=False)
        p1 = self.cleaned_data.get('password1')
        if p1:
            obj.password = set_schema_password(p1)
        if commit:
            obj.save()
        return obj


class TorreMasivaForm(forms.Form):
    nombre_torre = forms.CharField(label='Nombre de torre', max_length=20, help_text='Ejemplo: Torre A')
    pisos = forms.IntegerField(label='Número de pisos', min_value=1, max_value=100, initial=5)
    apartamentos_por_piso = forms.IntegerField(label='Apartamentos por piso', min_value=1, max_value=100, initial=4)
    primer_piso = forms.IntegerField(label='Primer piso', min_value=1, max_value=100, initial=1)

    def clean(self):
        data = super().clean()
        if data.get('pisos') and data.get('apartamentos_por_piso') and data['pisos'] * data['apartamentos_por_piso'] > 1000:
            raise forms.ValidationError('Máximo 1000 apartamentos por operación.')
        if data.get('nombre_torre'):
            data['nombre_torre'] = data['nombre_torre'].strip()
        return data

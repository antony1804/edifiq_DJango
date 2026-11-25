from django import forms
from django.utils import timezone

from apps.core.access import resolve_schema_role
from apps.core.models import EstadoPaquete, EstadoRecibo, EstadoReserva, EstadoUsuario, EstadoVisita, Rol, TipoResidente, Usuario
from apps.paquetes.models import Paquete
from apps.personas.models import Persona
from apps.recibos.models import Recibo
from apps.reservas.models import Reserva
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
    class Meta:
        model = Visita
        fields = [
            'tipo_visita', 'tipo_documento', 'nombre_visitante', 'documento_visitante',
            'motivo_visita', 'apartamento', 'fecha_ingreso', 'fecha_salida', 'estado_visita', 'autorizada',
        ]

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
        fields = ['tipo_servicio', 'periodo', 'valor', 'fecha_emision', 'fecha_vencimiento', 'estado_recibo', 'apartamento']


class ReservaForm(StyledForm):
    class Meta:
        model = Reserva
        fields = ['fecha_reserva', 'hora_inicio', 'hora_fin', 'cantidad_invitados', 'estado_reserva', 'zona', 'apartamento']

    def clean(self):
        data = super().clean()
        fecha = data.get('fecha_reserva')
        hi = data.get('hora_inicio')
        hf = data.get('hora_fin')
        zona = data.get('zona')
        estado = data.get('estado_reserva')
        if hi and hf and hf <= hi:
            raise forms.ValidationError('La hora de fin debe ser posterior a la hora de inicio.')
        cancelada = bool(estado and getattr(estado, 'nombre', '') == 'Cancelada')
        if zona and fecha and hi and hf and not cancelada:
            overlaps = Reserva.objects.filter(
                zona=zona,
                fecha_reserva=fecha,
                hora_inicio__lt=hf,
                hora_fin__gt=hi,
            ).exclude(estado_reserva__nombre='Cancelada')
            if self.instance and getattr(self.instance, 'pk', None):
                overlaps = overlaps.exclude(pk=self.instance.pk)
            if overlaps.exists():
                raise forms.ValidationError('Esta zona ya tiene una reserva en ese horario.')
        return data


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


class PersonaSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        if value and hasattr(value, 'instance'):
            persona = value.instance
            option['attrs'].update({
                'data-nombres': persona.nombres,
                'data-apellidos': persona.apellidos,
                'data-correo': persona.correo or '',
            })
        return option


class UsuarioForm(StyledForm):
    """Alta y edición de cuentas usando la tabla original `usuario` (sin auth_user/Perfil)."""
    password1 = forms.CharField(label='Contraseña', widget=forms.PasswordInput(attrs={'class': 'field-input'}), required=False)
    password2 = forms.CharField(label='Confirmar contraseña', widget=forms.PasswordInput(attrs={'class': 'field-input'}), required=False)

    class Meta:
        model = Usuario
        fields = ['username', 'password', 'estado_usuario', 'persona', 'rol']
        widgets = {
            'password': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password'].required = False
        if 'persona' in self.fields:
            used = Usuario.objects.exclude(pk=getattr(self.instance, 'pk', None)).values_list('persona_id', flat=True)
            qs = Persona.objects.filter(activo=True).exclude(pk__in=used).order_by('apellidos', 'nombres')
            if self.instance and getattr(self.instance, 'persona_id', None):
                qs = (Persona.objects.filter(pk=self.instance.persona_id) | qs).distinct()
            self.fields['persona'].queryset = qs
            self.fields['persona'].widget = PersonaSelect(attrs={'class': 'field-input'})
            self.fields['persona'].label = 'Persona registrada'
            self.fields['persona'].empty_label = 'Seleccione una persona registrada'
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

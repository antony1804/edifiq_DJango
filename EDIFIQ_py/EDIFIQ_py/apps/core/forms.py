from django import forms
from django.contrib.auth.models import User
from django.utils import timezone

from apps.core.access import resolve_schema_role
from apps.core.models import EstadoPaquete, EstadoRecibo, EstadoReserva, EstadoVisita, Rol
from apps.paquetes.models import Paquete
from apps.personas.models import Persona
from apps.recibos.models import Recibo
from apps.reservas.models import Reserva
from apps.residentes.models import Apartamento, ApartamentoPersona, Torre
from apps.usuarios.models import Perfil
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

    def clean_numero_documento(self):
        import re
        val = (self.cleaned_data.get('numero_documento') or '').strip()
        if not re.fullmatch(r'\d{1,10}', val):
            raise forms.ValidationError('Documento: máximo 10 dígitos numéricos.')
        return val

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
        td = data.get('tipo_documento')
        nd = data.get('numero_documento')
        if td and nd:
            qs = Persona.objects.filter(tipo_documento=td, numero_documento=nd)
            if self.instance and getattr(self.instance, 'pk', None):
                qs = qs.exclude(pk=self.instance.pk)
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
    class Meta:
        model = Paquete
        fields = ['descripcion', 'remitente', 'fecha_recepcion', 'fecha_entrega', 'estado_paquete', 'apartamento', 'persona']


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


class ApartamentoPersonaForm(StyledForm):
    class Meta:
        model = ApartamentoPersona
        fields = ['apartamento', 'persona', 'tipo_residente', 'fecha_ingreso', 'fecha_salida']

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        _rol, rol_nombre, _slug = resolve_schema_role(usuario) if usuario else (None, None, None)
        if usuario and rol_nombre == 'Residente':
            from apps.core.access import apartamentos_autorizados
            ids = apartamentos_autorizados(usuario)
            self.fields['apartamento'].queryset = Apartamento.objects.filter(pk__in=ids)
        if getattr(self.instance, 'pk', None):
            self.fields['apartamento'].disabled = True
            self.fields['persona'].disabled = True

    def clean(self):
        d = super().clean()
        apt = d.get('apartamento')
        _rol, rol_nombre, _slug = resolve_schema_role(self.usuario) if self.usuario else (None, None, None)
        if self.usuario and rol_nombre == 'Residente':
            from apps.core.access import apartamentos_autorizados
            if apt and apt.pk not in apartamentos_autorizados(self.usuario):
                self.add_error('apartamento', 'No puedes modificar otro apartamento.')
        return d


class PerfilForm(StyledForm):
    class Meta:
        model = Perfil
        fields = ['usuario', 'rol', 'apartamento']

    def clean(self):
        d = super().clean()
        if d.get('rol') == 'Residente' and not d.get('apartamento'):
            self.add_error('apartamento', 'Asigna un apartamento al residente.')
        return d


def form_for(model):
    special = {
        Persona: PersonaForm,
        ApartamentoPersona: ApartamentoPersonaForm,
        Reserva: ReservaForm,
        Visita: VisitaForm,
        Paquete: PaqueteForm,
        Recibo: ReciboForm,
        Perfil: PerfilForm,
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


class UsuarioForm(forms.ModelForm):
    """Alta y edición de cuentas; nunca se almacena una clave sin hash."""
    password1 = forms.CharField(label='Contraseña', widget=forms.PasswordInput(attrs={'class': 'field-input'}), required=False)
    password2 = forms.CharField(label='Confirmar contraseña', widget=forms.PasswordInput(attrs={'class': 'field-input'}), required=False)
    persona = forms.ModelChoiceField(label='Persona registrada', queryset=Persona.objects.none(), required=True, empty_label='Seleccione una persona registrada', widget=PersonaSelect)
    rol = forms.ChoiceField(label='Rol', choices=[])
    apartamento = forms.ModelChoiceField(label='Apartamento', queryset=Apartamento.objects.all(), required=False)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.fields['rol'].choices = [(r.nombre, r.nombre) for r in Rol.objects.all().order_by('id_rol')]
        except Exception:
            self.fields['rol'].choices = list(Perfil.ROLES)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'field-input')
        for name in ('first_name', 'last_name', 'email'):
            self.fields[name].disabled = True
            self.fields[name].help_text = 'Se obtiene de la persona registrada.'
        used = Perfil.objects.exclude(usuario_id=self.instance.pk).exclude(persona__isnull=True).values_list('persona_id', flat=True)
        self.fields['persona'].queryset = Persona.objects.filter(activo=True).exclude(pk__in=used).order_by('apellidos', 'nombres')
        if self.instance.pk:
            perfil = Perfil.objects.filter(usuario_id=self.instance.pk).first()
            if perfil:
                self.fields['persona'].initial = perfil.persona
                self.fields['rol'].initial = perfil.rol
                self.fields['apartamento'].initial = perfil.apartamento
        else:
            self.fields['password1'].required = True
            self.fields['password2'].required = True
            self.fields['is_active'].initial = True

    def clean(self):
        data = super().clean()
        p1, p2 = data.get('password1'), data.get('password2')
        if p1 != p2:
            self.add_error('password2', 'Las contraseñas no coinciden.')
        if p1:
            from django.contrib.auth.password_validation import validate_password
            try:
                validate_password(p1, self.instance if self.instance.pk else None)
            except forms.ValidationError as error:
                self.add_error('password1', error)
        persona = data.get('persona')
        if persona:
            linked = Perfil.objects.filter(persona=persona).exclude(usuario_id=self.instance.pk).exists()
            if linked:
                self.add_error('persona', 'Esta persona ya tiene un usuario asignado.')
        return data


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

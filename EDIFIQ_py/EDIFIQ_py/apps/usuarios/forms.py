from django import forms
from django.contrib.auth.password_validation import validate_password

from apps.core.models import TipoDocumento, Usuario as UsuarioEsquema
from apps.personas.models import Persona


class RegistroPersonaForm(forms.ModelForm):
    """Paso 1: creaciÃ³n de Persona (no otorga acceso al sistema)."""

    tipo_documento = forms.ModelChoiceField(
        label='Tipo de documento',
        queryset=TipoDocumento.objects.none(),
        empty_label='Seleccione un tipo de documento',
    )

    class Meta:
        model = Persona
        fields = ['tipo_documento', 'numero_documento', 'nombres', 'apellidos', 'telefono', 'correo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo_documento'].queryset = TipoDocumento.objects.all().order_by('nombre')
        self.fields['tipo_documento'].label_from_instance = self._label_tipo_documento
        placeholders = {
            'numero_documento': 'Ej: 1234567890',
            'nombres': 'Nombres',
            'apellidos': 'Apellidos',
            'telefono': 'Ej: 3001234567',
            'correo': 'correo@ejemplo.com',
        }
        for name, field in self.fields.items():
            field.widget.attrs.setdefault('class', 'field-input')
            if name in placeholders:
                field.widget.attrs['placeholder'] = placeholders[name]
        self.fields['numero_documento'].help_text = 'Solo nÃºmeros, mÃ¡ximo 10 dÃ­gitos.'
        self.fields['telefono'].help_text = 'Opcional. Solo nÃºmeros, mÃ¡ximo 10 dÃ­gitos.'
        self.fields['correo'].required = False

    @staticmethod
    def _label_tipo_documento(obj):
        abrev = (getattr(obj, 'abreviatura', '') or '').strip()
        nombre = (getattr(obj, 'nombre', '') or '').strip()
        if abrev and nombre and abrev.lower() != nombre.lower():
            return f"{abrev} - {nombre}"
        return nombre or abrev or str(obj.pk)

    def clean_numero_documento(self):
        import re
        val = (self.cleaned_data.get('numero_documento') or '').strip()
        if not re.fullmatch(r'\d{1,10}', val):
            raise forms.ValidationError('El nÃºmero de documento debe tener solo dÃ­gitos (mÃ¡ximo 10). Ej: 1234567890.')
        return val

    def clean_telefono(self):
        import re
        val = (self.cleaned_data.get('telefono') or '').strip()
        if val and not re.fullmatch(r'\d{1,10}', val):
            raise forms.ValidationError('El telÃ©fono debe tener solo dÃ­gitos (mÃ¡ximo 10).')
        return val or None

    def clean_correo(self):
        val = (self.cleaned_data.get('correo') or '').strip().lower()
        if val:
            forms.EmailField().clean(val)
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
                self.add_error('numero_documento', 'Ya existe una persona con ese tipo y nÃºmero de documento.')
        return data


class RegistroCuentaForm(forms.Form):
    """Paso 2: creaciÃ³n de cuenta de acceso vinculada a una Persona existente."""

    username = forms.CharField(
        label='Nombre de usuario',
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'field-input', 'placeholder': 'Nombre de usuario', 'autocomplete': 'username'}),
    )
    password1 = forms.CharField(
        label='ContraseÃ±a',
        widget=forms.PasswordInput(attrs={'class': 'field-input', 'placeholder': 'ContraseÃ±a', 'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label='Confirmar contraseÃ±a',
        widget=forms.PasswordInput(attrs={'class': 'field-input', 'placeholder': 'Confirmar contraseÃ±a', 'autocomplete': 'new-password'}),
    )

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        if not username:
            raise forms.ValidationError('Ingresa un nombre de usuario.')
        if UsuarioEsquema.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('Este nombre de usuario ya está en uso.')
        return username

    def clean(self):
        data = super().clean()
        p1 = data.get('password1')
        p2 = data.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'Las contraseñas no coinciden.')
        if p1 and not self.errors.get('password1') and not self.errors.get('password2'):
            try:
                validate_password(p1)
            except forms.ValidationError as e:
                self.add_error('password1', e)
        return data


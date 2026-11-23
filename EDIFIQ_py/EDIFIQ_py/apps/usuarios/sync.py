"""Create a linked Persona for superusers that have no existing linked person."""
from django.db import transaction

from apps.core.models import TipoDocumento
from apps.personas.models import Persona
from apps.usuarios.models import Perfil


def _tipo_documento_sistema():
    tipo = TipoDocumento.objects.filter(nombre__iexact='CC').first() or TipoDocumento.objects.filter(abreviatura__iexact='CC').first()
    if tipo:
        return tipo
    return TipoDocumento.objects.create(nombre='CC', abreviatura='CC')


def vincular_administrador(usuario):
    if not usuario.pk or not usuario.is_superuser:
        return None
    with transaction.atomic():
        perfil, _ = Perfil.objects.get_or_create(usuario=usuario, defaults={'rol': 'Administrador'})
        if perfil.persona_id:
            return perfil.persona
        # Internal identifier is distinct from a real identity document.
        documento = f'SYS-USER-{usuario.pk}'
        tipo_documento = _tipo_documento_sistema()
        persona, created = Persona.objects.get_or_create(
            tipo_documento=tipo_documento,
            numero_documento=documento,
            defaults={
                'nombres': (usuario.first_name or '').strip() or usuario.username,
                'apellidos': (usuario.last_name or '').strip() or 'Administrador',
                'correo': usuario.email or '',
                'activo': usuario.is_active,
            },
        )
        # Prevent assigning an already linked person to a second user.
        if Perfil.objects.filter(persona=persona).exclude(pk=perfil.pk).exists():
            return None
        perfil.persona = persona
        perfil.rol = 'Administrador'
        perfil.save(update_fields=['persona', 'rol'])
        return persona

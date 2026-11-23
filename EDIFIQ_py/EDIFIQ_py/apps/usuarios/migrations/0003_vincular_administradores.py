from django.conf import settings
from django.db import migrations


def vincular_existentes(apps, schema_editor):
    db = schema_editor.connection.alias
    app, model = settings.AUTH_USER_MODEL.split('.')
    Usuario = apps.get_model(app, model)
    Perfil = apps.get_model('usuarios', 'Perfil')
    Persona = apps.get_model('personas', 'Persona')
    try:
        for usuario in Usuario.objects.using(db).filter(is_superuser=True):
            perfil, _ = Perfil.objects.using(db).get_or_create(usuario_id=usuario.pk, defaults={'rol': 'Administrador'})
            if perfil.persona_id:
                continue
            documento = f'SYS-USER-{usuario.pk}'
            persona = Persona.objects.using(db).filter(numero_documento=documento).first()
            if not persona:
                # Compatible con esquemas históricos y esquema actual (tipo_documento FK en modelo actual).
                try:
                    persona = Persona.objects.using(db).create(
                        numero_documento=documento,
                        tipo_documento_id=1,
                        nombres=(usuario.first_name or '').strip() or usuario.username,
                        apellidos=(usuario.last_name or '').strip() or 'Administrador',
                        correo=usuario.email or '',
                        activo=usuario.is_active,
                    )
                except Exception:
                    continue
            if Perfil.objects.using(db).filter(persona_id=persona.pk).exclude(pk=perfil.pk).exists():
                continue
            perfil.persona_id = persona.pk
            perfil.rol = 'Administrador'
            perfil.save(using=db, update_fields=['persona', 'rol'])
    except Exception:
        # Migración de datos defensiva: no debe bloquear creación de BD de pruebas/esquema.
        return


class Migration(migrations.Migration):
    dependencies = [('usuarios', '0002_perfil_persona')]
    operations = [migrations.RunPython(vincular_existentes, migrations.RunPython.noop)]

from django.test import TestCase

from apps.core.forms import UsuarioForm
from apps.core.models import EstadoUsuario, Rol, TipoDocumento, Usuario
from apps.personas.models import Persona


class UsuariosIntegracionTests(TestCase):
    def setUp(self):
        self.tipo_doc = TipoDocumento.objects.create(nombre='CC', abreviatura='CC')
        self.estado = EstadoUsuario.objects.create(nombre='Activo')
        self.rol_admin = Rol.objects.create(nombre='Administrador')
        self.persona = Persona.objects.create(
            tipo_documento=self.tipo_doc,
            numero_documento='900000001',
            nombres='Ana',
            apellidos='Admin',
            correo='ana@example.com',
            activo=True,
        )

    def test_formulario_usuario_usa_tabla_original(self):
        form = UsuarioForm()
        self.assertIn('persona', form.fields)
        self.assertIn('username', form.fields)
        self.assertIn('rol', form.fields)
        self.assertIn('estado_usuario', form.fields)
        self.assertEqual(form._meta.model, Usuario)

    def test_formulario_usuario_crea_registro_en_tabla_usuario(self):
        form = UsuarioForm(data={
            'username': 'ana_admin',
            'password1': 'ClaveSegura123!',
            'password2': 'ClaveSegura123!',
            'estado_usuario': self.estado.pk,
            'persona': self.persona.pk,
            'rol': self.rol_admin.pk,
        })
        self.assertTrue(form.is_valid(), form.errors)
        usuario = form.save()
        self.assertEqual(Usuario.objects.filter(pk=usuario.pk, username='ana_admin').count(), 1)
        self.assertEqual(usuario.persona_id, self.persona.pk)
        self.assertEqual(usuario.rol_id, self.rol_admin.pk)

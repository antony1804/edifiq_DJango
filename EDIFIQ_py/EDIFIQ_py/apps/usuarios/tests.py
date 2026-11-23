from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.forms import UsuarioForm
from apps.personas.models import Persona
from apps.usuarios.models import Perfil
from apps.usuarios.sync import vincular_administrador


class UsuariosIntegracionTests(TestCase):
    def test_formulario_nuevo_no_consulta_usuario_sin_guardar(self):
        form = UsuarioForm()
        self.assertIn('persona', form.fields)

    def test_superusuario_aparece_en_personas_sin_duplicados(self):
        user = get_user_model().objects.create_superuser('admin_prueba', 'admin@example.com', 'clave-de-prueba-2026')
        vincular_administrador(user)
        vincular_administrador(user)
        self.assertEqual(Persona.objects.filter(numero_documento=f'SYS-USER-{user.pk}').count(), 1)
        perfil = Perfil.objects.get(usuario=user)
        self.assertEqual(perfil.rol, 'Administrador')
        self.assertEqual(perfil.persona.numero_documento, f'SYS-USER-{user.pk}')

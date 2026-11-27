from django.conf import settings
from django.test import TestCase

from apps.core.forms import UsuarioForm
from apps.core.models import EstadoUsuario, Rol, TipoDocumento, Usuario
from apps.core.schema_auth import check_schema_password, set_schema_password
from apps.personas.models import Persona


class UsuariosIntegracionTests(TestCase):
    def setUp(self):
        self.tipo_doc = TipoDocumento.objects.create(nombre='CC', abreviatura='CC')
        self.estado = EstadoUsuario.objects.create(nombre='Activo')
        self.estado_inactivo = EstadoUsuario.objects.create(nombre='Inactivo')
        self.rol_admin = Rol.objects.create(nombre='Administrador')
        self.rol_residente = Rol.objects.create(nombre='Residente')
        self.persona = Persona.objects.create(
            tipo_documento=self.tipo_doc,
            numero_documento='900000001',
            nombres='Ana',
            apellidos='Admin',
            correo='ana@example.com',
            activo=True,
        )
        self.admin_persona = Persona.objects.create(
            tipo_documento=self.tipo_doc,
            numero_documento='900000002',
            nombres='Admin',
            apellidos='Prueba',
            activo=True,
        )
        self.admin = Usuario.objects.create(
            username='admin_usuarios_test',
            password=set_schema_password('ClaveSegura123!'),
            estado_usuario=self.estado,
            persona=self.admin_persona,
            rol=self.rol_admin,
        )

    def login_admin(self):
        session = self.client.session
        session['_schema_user_id'] = self.admin.pk
        session.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

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
        self.assertTrue(check_schema_password('ClaveSegura123!', usuario.password))

    def test_administrador_puede_crear_usuario_y_el_hash_no_se_expone_en_formulario(self):
        self.login_admin()
        listado = self.client.get('/administrador/modulo/usuarios/')
        self.assertEqual(listado.status_code, 200)
        self.assertContains(listado, 'js-open-usuario-form')
        self.assertContains(listado, 'usuario-form-modal')

        formulario = self.client.get('/administrador/modulo/usuarios/nuevo/?modal=1')

        self.assertEqual(formulario.status_code, 200)
        self.assertContains(formulario, 'class="usuario-form"')
        self.assertContains(formulario, 'CC 900000001')
        self.assertNotContains(formulario, 'name="password"')

        response = self.client.post(
            '/administrador/modulo/usuarios/nuevo/?modal=1',
            {
                'modal': '1',
                'username': 'ana_residente',
                'password1': 'ClaveSegura123!',
                'password2': 'ClaveSegura123!',
                'estado_usuario': self.estado.pk,
                'persona': self.persona.pk,
                'rol': self.rol_residente.pk,
            },
        )

        self.assertEqual(response.status_code, 302)
        usuario = Usuario.objects.get(username='ana_residente')
        self.assertEqual(usuario.persona, self.persona)
        self.assertEqual(usuario.rol, self.rol_residente)
        self.assertTrue(check_schema_password('ClaveSegura123!', usuario.password))

    def test_editar_usuario_conserva_password_si_se_deja_vacio_y_permite_cambiarlo(self):
        usuario = Usuario.objects.create(
            username='ana_residente',
            password=set_schema_password('ClaveSegura123!'),
            estado_usuario=self.estado,
            persona=self.persona,
            rol=self.rol_residente,
        )
        self.login_admin()

        formulario = self.client.get(
            f'/administrador/modulo/usuarios/{usuario.pk}/editar/?modal=1'
        )
        self.assertEqual(formulario.status_code, 200)
        self.assertContains(formulario, 'class="usuario-form"')
        self.assertContains(formulario, 'CC 900000001')
        self.assertNotContains(formulario, usuario.password)

        response = self.client.post(
            f'/administrador/modulo/usuarios/{usuario.pk}/editar/?modal=1',
            {
                'modal': '1',
                'username': 'ana_residente_actualizada',
                'password1': '',
                'password2': '',
                'estado_usuario': self.estado_inactivo.pk,
                'persona': self.persona.pk,
                'rol': self.rol_admin.pk,
            },
        )

        self.assertEqual(response.status_code, 302)
        usuario.refresh_from_db()
        self.assertEqual(usuario.username, 'ana_residente_actualizada')
        self.assertEqual(usuario.estado_usuario, self.estado_inactivo)
        self.assertEqual(usuario.rol, self.rol_admin)
        self.assertTrue(check_schema_password('ClaveSegura123!', usuario.password))

        response = self.client.post(
            f'/administrador/modulo/usuarios/{usuario.pk}/editar/?modal=1',
            {
                'modal': '1',
                'username': usuario.username,
                'password1': 'OtraClave123!',
                'password2': 'OtraClave123!',
                'estado_usuario': self.estado_inactivo.pk,
                'persona': self.persona.pk,
                'rol': self.rol_admin.pk,
            },
        )

        self.assertEqual(response.status_code, 302)
        usuario.refresh_from_db()
        self.assertTrue(check_schema_password('OtraClave123!', usuario.password))
        self.assertFalse(check_schema_password('ClaveSegura123!', usuario.password))

    def test_listado_filtra_por_persona_y_reporte_pdf_usa_campos_del_esquema(self):
        Usuario.objects.create(
            username='ana_residente',
            password=set_schema_password('ClaveSegura123!'),
            estado_usuario=self.estado,
            persona=self.persona,
            rol=self.rol_residente,
        )
        self.login_admin()

        listado = self.client.get(
            '/administrador/modulo/usuarios/',
            {'persona': str(self.persona.pk)},
        )
        self.assertEqual(listado.status_code, 200)
        self.assertEqual(
            [row['item'].username for row in listado.context['rows']],
            ['ana_residente'],
        )

        reporte = self.client.get(
            '/administrador/modulo/usuarios/reporte.pdf',
            {'persona': str(self.persona.pk)},
        )
        self.assertEqual(reporte.status_code, 200)
        self.assertEqual(reporte['Content-Type'], 'application/pdf')

    def test_rechaza_username_duplicado_y_persona_ya_asignada(self):
        Usuario.objects.create(
            username='ana_residente',
            password=set_schema_password('ClaveSegura123!'),
            estado_usuario=self.estado,
            persona=self.persona,
            rol=self.rol_residente,
        )
        self.login_admin()

        response = self.client.post(
            '/administrador/modulo/usuarios/nuevo/?modal=1',
            {
                'modal': '1',
                'username': 'ANA_RESIDENTE',
                'password1': 'ClaveSegura123!',
                'password2': 'ClaveSegura123!',
                'estado_usuario': self.estado.pk,
                'persona': self.admin_persona.pk,
                'rol': self.rol_residente.pk,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'nombre de usuario ya está en uso', status_code=400)

        response = self.client.post(
            '/administrador/modulo/usuarios/nuevo/?modal=1',
            {
                'modal': '1',
                'username': 'otro_usuario',
                'password1': 'ClaveSegura123!',
                'password2': 'ClaveSegura123!',
                'estado_usuario': self.estado.pk,
                'persona': self.persona.pk,
                'rol': self.rol_residente.pk,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.context['form'].errors['persona'])

from datetime import date

from django.test import TestCase

from apps.core.access import apartamentos_autorizados
from apps.core.models import EstadoUsuario, Rol, TipoDocumento, TipoResidente, Usuario
from apps.core.schema_auth import SchemaUser, set_schema_password
from apps.personas.models import Persona
from apps.residentes.models import Apartamento, ApartamentoPersona, Torre


class PermisosResidencialesTests(TestCase):
    def login_schema_user(self, usuario):
        session = self.client.session
        session['_schema_user_id'] = usuario.pk
        session.save()

    def setUp(self):
        self.tipo_doc = TipoDocumento.objects.create(nombre='CC', abreviatura='CC')
        self.estado_activo = EstadoUsuario.objects.create(nombre='Activo')
        self.rol_admin = Rol.objects.create(nombre='Administrador')
        self.rol_residente = Rol.objects.create(nombre='Residente')
        self.tipo_prop = TipoResidente.objects.create(nombre='Propietario')
        self.tipo_arr = TipoResidente.objects.create(nombre='Arrendatario')
        self.tipo_fam = TipoResidente.objects.create(nombre='Familiar')

        torre = Torre.objects.create(nombre_torre='Torre pruebas')
        self.a1 = Apartamento.objects.create(torre=torre, numero_apartamento='101', piso=1)
        self.a2 = Apartamento.objects.create(torre=torre, numero_apartamento='102', piso=1)

        self.propietario = Persona.objects.create(
            tipo_documento=self.tipo_doc, numero_documento='100000001', nombres='Propietario', apellidos='Uno'
        )
        self.arrendatario = Persona.objects.create(
            tipo_documento=self.tipo_doc, numero_documento='100000002', nombres='Arrendatario', apellidos='Dos'
        )
        self.familiar = Persona.objects.create(
            tipo_documento=self.tipo_doc, numero_documento='100000003', nombres='Familiar', apellidos='Tres'
        )
        self.admin_persona = Persona.objects.create(
            tipo_documento=self.tipo_doc, numero_documento='100000099', nombres='Admin', apellidos='Sistema'
        )

        self.owner_user = Usuario.objects.create(
            username='propietario_test', password=set_schema_password('prueba-segura-123'),
            estado_usuario=self.estado_activo, persona=self.propietario, rol=self.rol_residente,
        )
        self.tenant_user = Usuario.objects.create(
            username='arrendatario_test', password=set_schema_password('prueba-segura-123'),
            estado_usuario=self.estado_activo, persona=self.arrendatario, rol=self.rol_residente,
        )
        self.admin_user = Usuario.objects.create(
            username='admin_test', password=set_schema_password('prueba-segura-123'),
            estado_usuario=self.estado_activo, persona=self.admin_persona, rol=self.rol_admin,
        )

        ApartamentoPersona.objects.create(persona=self.propietario, apartamento=self.a1, tipo_residente=self.tipo_prop, fecha_ingreso=date(2024, 1, 1))
        ApartamentoPersona.objects.create(persona=self.propietario, apartamento=self.a2, tipo_residente=self.tipo_prop, fecha_ingreso=date(2024, 1, 1))
        ApartamentoPersona.objects.create(persona=self.arrendatario, apartamento=self.a1, tipo_residente=self.tipo_arr, fecha_ingreso=date(2024, 2, 1))
        ApartamentoPersona.objects.create(persona=self.familiar, apartamento=self.a2, tipo_residente=self.tipo_fam, fecha_ingreso=date(2024, 3, 1))

    def test_apartamentos_autorizados_por_vinculo_vigente(self):
        self.assertEqual(set(apartamentos_autorizados(SchemaUser(self.owner_user))), {self.a1.pk, self.a2.pk})
        self.assertEqual(apartamentos_autorizados(SchemaUser(self.tenant_user)), [self.a1.pk])

    def test_listado_residentes_agrupa_personas_y_conserva_apartamentos(self):
        self.login_schema_user(self.admin_user)
        response = self.client.get('/residente/residentes/', follow=True)
        # Administrador será redirigido por namespace si entra a /residente, así que usar ruta de rol admin
        response = self.client.get('/administrador/residentes/', follow=True)
        self.assertEqual(response.status_code, 200)
        groups = response.context['resident_groups']
        owner_groups = [g for g in groups if g['persona'].pk == self.propietario.pk]
        self.assertEqual(len(owner_groups), 1)
        self.assertEqual({r.apartamento_id for r in owner_groups[0]['relations']}, {self.a1.pk, self.a2.pk})

    def test_listado_residentes_filtra_apartamento_sin_duplicar(self):
        self.login_schema_user(self.admin_user)
        response = self.client.get('/administrador/residentes/', {'apartamento': str(self.a1.pk)}, follow=True)
        self.assertEqual(response.status_code, 200)
        groups = response.context['resident_groups']
        self.assertEqual({r.apartamento_id for g in groups for r in g['relations']}, {self.a1.pk})

    def test_residente_no_puede_editar_vinculo_de_otro_apartamento(self):
        self.login_schema_user(self.tenant_user)
        key = f'{self.a2.pk}-{self.familiar.pk}'
        response = self.client.get(f'/residente/residentes/{key}/editar/', follow=True)
        self.assertEqual(response.status_code, 403)

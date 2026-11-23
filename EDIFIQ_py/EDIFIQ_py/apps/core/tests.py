from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.access import apartamentos_autorizados
from apps.core.models import TipoDocumento, TipoResidente
from apps.personas.models import Persona
from apps.residentes.models import Apartamento, ApartamentoPersona, Torre
from apps.usuarios.models import Perfil


class PermisosResidencialesTests(TestCase):
    def setUp(self):
        self.tipo_doc = TipoDocumento.objects.create(nombre='CC', abreviatura='CC')
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

        User = get_user_model()
        self.owner_user = User.objects.create_user('propietario_test', password='prueba-segura-123')
        self.tenant_user = User.objects.create_user('arrendatario_test', password='prueba-segura-123')
        self.admin_user = User.objects.create_superuser('admin_test', 'admin_test@example.com', 'prueba-segura-123')

        Perfil.objects.create(usuario=self.owner_user, persona=self.propietario, rol='Residente', apartamento=self.a1)
        Perfil.objects.create(usuario=self.tenant_user, persona=self.arrendatario, rol='Residente', apartamento=self.a1)
        Perfil.objects.create(usuario=self.admin_user, rol='Administrador')

        ApartamentoPersona.objects.create(persona=self.propietario, apartamento=self.a1, tipo_residente=self.tipo_prop, fecha_ingreso=date(2024, 1, 1))
        ApartamentoPersona.objects.create(persona=self.propietario, apartamento=self.a2, tipo_residente=self.tipo_prop, fecha_ingreso=date(2024, 1, 1))
        ApartamentoPersona.objects.create(persona=self.arrendatario, apartamento=self.a1, tipo_residente=self.tipo_arr, fecha_ingreso=date(2024, 2, 1))
        ApartamentoPersona.objects.create(persona=self.familiar, apartamento=self.a2, tipo_residente=self.tipo_fam, fecha_ingreso=date(2024, 3, 1))

    def test_apartamentos_autorizados_por_vinculo_vigente(self):
        self.assertEqual(set(apartamentos_autorizados(self.owner_user)), {self.a1.pk, self.a2.pk})
        self.assertEqual(apartamentos_autorizados(self.tenant_user), [self.a1.pk])

    def test_listado_residentes_agrupa_personas_y_conserva_apartamentos(self):
        self.client.force_login(self.admin_user)
        response = self.client.get('/modulo/residentes/')
        self.assertEqual(response.status_code, 200)
        groups = response.context['resident_groups']
        owner_groups = [g for g in groups if g['persona'].pk == self.propietario.pk]
        self.assertEqual(len(owner_groups), 1)
        self.assertEqual({r.apartamento_id for r in owner_groups[0]['relations']}, {self.a1.pk, self.a2.pk})

    def test_listado_residentes_filtra_apartamento_sin_duplicar(self):
        self.client.force_login(self.admin_user)
        response = self.client.get('/modulo/residentes/', {'apartamento': str(self.a1.pk)})
        self.assertEqual(response.status_code, 200)
        groups = response.context['resident_groups']
        self.assertEqual({r.apartamento_id for g in groups for r in g['relations']}, {self.a1.pk})

    def test_residente_no_puede_editar_vinculo_de_otro_apartamento(self):
        # vínculo del familiar en a2 (no autorizado para arrendatario de a1)
        self.client.force_login(self.tenant_user)
        key = f'{self.a2.pk}-{self.familiar.pk}'
        response = self.client.get(f'/modulo/residentes/{key}/editar/')
        self.assertEqual(response.status_code, 403)

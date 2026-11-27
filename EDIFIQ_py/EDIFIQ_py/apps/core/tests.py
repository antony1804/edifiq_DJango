import tempfile
from datetime import date, timedelta

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.core.access import apartamentos_autorizados
from apps.core.models import EstadoRecibo, EstadoReserva, EstadoVisita, EstadoUsuario, Rol, TipoDocumento, TipoResidente, TipoServicio, TipoVisita, Usuario
from apps.core.schema_auth import SchemaUser, set_schema_password
from apps.personas.models import Persona
from apps.recibos.models import Recibo
from apps.residentes.models import Apartamento, ApartamentoPersona, Torre
from apps.reservas.models import Reserva, ZonaComun
from apps.visitas.models import Visita


class PermisosResidencialesTests(TestCase):
    def login_schema_user(self, usuario):
        session = self.client.session
        session['_schema_user_id'] = usuario.pk
        session.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    def crear_visita(self, *, autorizada=False):
        return Visita.objects.create(
            tipo_visita=self.tipo_visita,
            tipo_documento=self.tipo_doc,
            nombre_visitante='Visitante de prueba',
            documento_visitante='12345678',
            motivo_visita='Prueba funcional',
            fecha_ingreso=timezone.now() - timedelta(days=1),
            estado_visita=self.estado_visita_pendiente,
            autorizada=autorizada,
            apartamento=self.a1,
        )

    def setUp(self):
        self.tipo_doc = TipoDocumento.objects.create(nombre='CC', abreviatura='CC')
        self.estado_activo = EstadoUsuario.objects.create(nombre='Activo')
        self.rol_admin = Rol.objects.create(nombre='Administrador')
        self.rol_residente = Rol.objects.create(nombre='Residente')
        self.tipo_prop = TipoResidente.objects.create(nombre='Propietario')
        self.tipo_arr = TipoResidente.objects.create(nombre='Arrendatario')
        self.tipo_fam = TipoResidente.objects.create(nombre='Familiar')
        self.tipo_visita = TipoVisita.objects.create(nombre='Visitante')
        self.estado_visita_pendiente = EstadoVisita.objects.create(nombre='Pendiente')
        self.estado_visita_finalizada = EstadoVisita.objects.create(nombre='Finalizada')
        self.estado_visita_cancelada = EstadoVisita.objects.create(nombre='Cancelada')
        self.estado_reserva_pendiente = EstadoReserva.objects.create(nombre='Pendiente')
        self.estado_reserva_aprobada = EstadoReserva.objects.create(nombre='Aprobada')
        self.estado_reserva_cancelada = EstadoReserva.objects.create(nombre='Cancelada')
        self.zona_comun = ZonaComun.objects.create(nombre='Salón social', descripcion='Zona de prueba')

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
        response = self.client.get('/administrador/modulo/residentes/', follow=True)
        self.assertEqual(response.status_code, 200)
        groups = response.context['resident_groups']
        owner_groups = [g for g in groups if g['persona'].pk == self.propietario.pk]
        self.assertEqual(len(owner_groups), 1)
        self.assertEqual({r.apartamento_id for r in owner_groups[0]['relations']}, {self.a1.pk, self.a2.pk})

    def test_listado_residentes_filtra_apartamento_sin_duplicar(self):
        self.login_schema_user(self.admin_user)
        response = self.client.get(
            '/administrador/modulo/residentes/',
            {'apartamento': str(self.a1.pk)},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        groups = response.context['resident_groups']
        self.assertEqual({r.apartamento_id for g in groups for r in g['relations']}, {self.a1.pk})

    def test_residente_no_puede_editar_vinculo_de_otro_apartamento(self):
        self.login_schema_user(self.tenant_user)
        key = f'{self.a2.pk}-{self.familiar.pk}'
        response = self.client.get(
            f'/residente/modulo/residentes/{key}/editar/',
            follow=True,
        )
        self.assertEqual(response.status_code, 403)

    def test_residente_gestiona_familiares_desde_modal_y_apartamento(self):
        self.login_schema_user(self.tenant_user)
        listado = self.client.get('/residente/modulo/residentes/')
        self.assertEqual(listado.status_code, 200)
        self.assertContains(listado, 'Familiares')
        self.assertContains(listado, 'js-open-familiar-form')
        self.assertIn(('residentes', 'Familiares'), listado.context['navigation'])

        response = self.client.get('/residente/modulo/residentes/nuevo/?modal=1')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Registrar familiar')
        self.assertNotContains(response, 'name="apartamento"')

        response = self.client.post(
            '/residente/modulo/residentes/nuevo/?modal=1',
            {
                'modal': '1',
                'tipo_documento': str(self.tipo_doc.pk),
                'numero_documento': '200000001',
                'nombres': 'Familiar Nuevo',
                'apellidos': 'Prueba',
                'telefono': '3001234567',
                'correo': 'familiar@example.com',
            },
        )
        self.assertEqual(response.status_code, 302)
        persona = Persona.objects.get(numero_documento='200000001')
        vinculo = ApartamentoPersona.objects.get(apartamento=self.a1, persona=persona)
        self.assertEqual(vinculo.tipo_residente, self.tipo_fam)

        lista_familiares = self.client.get('/residente/modulo/residentes/', {'q': '200000001'})
        self.assertEqual(lista_familiares.status_code, 200)
        self.assertContains(lista_familiares, '3001234567')
        self.assertContains(lista_familiares, 'familiar@example.com')
        self.assertContains(lista_familiares, 'Editar')

        mis_apartamentos = self.client.get('/residente/modulo/apartamentos/')
        self.assertEqual(mis_apartamentos.status_code, 200)
        self.assertContains(mis_apartamentos, 'Familiar Nuevo')

        key = f'{self.a1.pk}-{persona.pk}'
        response = self.client.get(f'/residente/modulo/residentes/{key}/editar/?modal=1')
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            f'/residente/modulo/residentes/{key}/editar/?modal=1',
            {
                'modal': '1',
                'tipo_documento': str(self.tipo_doc.pk),
                'numero_documento': '200000001',
                'nombres': 'Familiar Editado',
                'apellidos': 'Prueba',
                'telefono': '3001234567',
                'correo': 'familiar@example.com',
            },
        )
        self.assertEqual(response.status_code, 302)
        persona.refresh_from_db()
        self.assertEqual(persona.nombres, 'Familiar Editado')

        response = self.client.post(
            f'/residente/modulo/residentes/{key}/eliminar/',
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ApartamentoPersona.objects.filter(apartamento=self.a1, persona=persona).exists())
        self.assertTrue(Persona.objects.filter(pk=persona.pk).exists())

    def test_residente_con_varios_apartamentos_puede_elegir_donde_vincular_familiar(self):
        self.login_schema_user(self.owner_user)
        response = self.client.get('/residente/modulo/residentes/nuevo/?modal=1')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="apartamento"')

        response = self.client.post(
            '/residente/modulo/residentes/nuevo/?modal=1',
            {
                'modal': '1',
                'apartamento': str(self.a2.pk),
                'tipo_documento': str(self.tipo_doc.pk),
                'numero_documento': '200000002',
                'nombres': 'Familiar Dos',
                'apellidos': 'Prueba',
                'telefono': '',
                'correo': '',
            },
        )
        self.assertEqual(response.status_code, 302)
        persona = Persona.objects.get(numero_documento='200000002')
        self.assertTrue(ApartamentoPersona.objects.filter(apartamento=self.a2, persona=persona).exists())

    def test_residente_solicita_reserva_en_modal_y_puede_editarla(self):
        self.login_schema_user(self.tenant_user)
        listado = self.client.get('/residente/modulo/reservas/')
        self.assertEqual(listado.status_code, 200)
        self.assertContains(listado, 'js-open-reserva-form')
        self.assertContains(listado, 'Estado de reserva')

        formulario = self.client.get('/residente/modulo/reservas/nuevo/?modal=1')
        self.assertEqual(formulario.status_code, 200)
        self.assertContains(formulario, 'name="zona"')
        self.assertContains(formulario, 'name="fecha_reserva"')
        self.assertNotContains(formulario, 'name="estado_reserva"')
        self.assertNotContains(formulario, 'name="apartamento"')

        fecha_reserva = (date.today() + timedelta(days=3)).isoformat()
        response = self.client.post(
            '/residente/modulo/reservas/nuevo/?modal=1',
            {
                'modal': '1',
                'zona': str(self.zona_comun.pk),
                'fecha_reserva': fecha_reserva,
                'hora_inicio': '12:00',
                'hora_fin': '13:00',
                'cantidad_invitados': '4',
            },
        )
        self.assertEqual(response.status_code, 302)
        reserva = Reserva.objects.get(apartamento=self.a1)
        self.assertEqual(reserva.estado_reserva, self.estado_reserva_pendiente)
        self.assertEqual(reserva.cantidad_invitados, 4)

        key = str(reserva.pk)
        edit_form = self.client.get(f'/residente/modulo/reservas/{key}/editar/?modal=1')
        self.assertEqual(edit_form.status_code, 200)
        response = self.client.post(
            f'/residente/modulo/reservas/{key}/editar/?modal=1',
            {
                'modal': '1',
                'zona': str(self.zona_comun.pk),
                'fecha_reserva': fecha_reserva,
                'hora_inicio': '13:00',
                'hora_fin': '14:00',
                'cantidad_invitados': '5',
            },
        )
        self.assertEqual(response.status_code, 302)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado_reserva, self.estado_reserva_pendiente)
        self.assertEqual(reserva.hora_inicio.strftime('%H:%M'), '13:00')
        self.assertEqual(reserva.cantidad_invitados, 5)

    def test_residente_con_varios_apartamentos_puede_elegir_apartamento_para_reserva(self):
        self.login_schema_user(self.owner_user)
        formulario = self.client.get('/residente/modulo/reservas/nuevo/?modal=1')
        self.assertEqual(formulario.status_code, 200)
        self.assertContains(formulario, 'name="apartamento"')

        response = self.client.post(
            '/residente/modulo/reservas/nuevo/?modal=1',
            {
                'modal': '1',
                'zona': str(self.zona_comun.pk),
                'apartamento': str(self.a2.pk),
                'fecha_reserva': (date.today() + timedelta(days=8)).isoformat(),
                'hora_inicio': '12:00',
                'hora_fin': '13:00',
                'cantidad_invitados': '2',
            },
        )

        self.assertEqual(response.status_code, 302)
        reserva = Reserva.objects.get()
        self.assertEqual(reserva.apartamento, self.a2)
        self.assertEqual(reserva.estado_reserva, self.estado_reserva_pendiente)

    def test_reserva_rechaza_horas_de_inicio_y_fin_iguales(self):
        self.login_schema_user(self.tenant_user)
        response = self.client.post(
            '/residente/modulo/reservas/nuevo/?modal=1',
            {
                'modal': '1',
                'zona': str(self.zona_comun.pk),
                'fecha_reserva': (date.today() + timedelta(days=9)).isoformat(),
                'hora_inicio': '13:00',
                'hora_fin': '13:00',
                'cantidad_invitados': '2',
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'no pueden ser iguales', status_code=400)
        self.assertFalse(Reserva.objects.exists())

    def test_reserva_permite_horario_que_cruza_medianoche(self):
        self.login_schema_user(self.tenant_user)
        fecha_reserva = date.today() + timedelta(days=9)

        response = self.client.post(
            '/residente/modulo/reservas/nuevo/?modal=1',
            {
                'modal': '1',
                'zona': str(self.zona_comun.pk),
                'fecha_reserva': fecha_reserva.isoformat(),
                'hora_inicio': '19:30',
                'hora_fin': '03:00',
                'cantidad_invitados': '2',
            },
        )

        self.assertEqual(response.status_code, 302)
        reserva = Reserva.objects.get()
        self.assertEqual(reserva.hora_inicio.strftime('%H:%M'), '19:30')
        self.assertEqual(reserva.hora_fin.strftime('%H:%M'), '03:00')

    def test_reserva_detecta_solapamiento_entre_dias_consecutivos(self):
        fecha_reserva = date.today() + timedelta(days=10)
        Reserva.objects.create(
            fecha_reserva=fecha_reserva,
            hora_inicio='23:00',
            hora_fin='03:00',
            cantidad_invitados=2,
            estado_reserva=self.estado_reserva_aprobada,
            zona=self.zona_comun,
            apartamento=self.a2,
        )
        self.login_schema_user(self.tenant_user)

        response = self.client.post(
            '/residente/modulo/reservas/nuevo/?modal=1',
            {
                'modal': '1',
                'zona': str(self.zona_comun.pk),
                'fecha_reserva': (fecha_reserva + timedelta(days=1)).isoformat(),
                'hora_inicio': '02:00',
                'hora_fin': '04:00',
                'cantidad_invitados': '2',
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'reserva aprobada', status_code=400)

    def test_reserva_detecta_conflicto_que_comienza_al_dia_siguiente(self):
        fecha_reserva = date.today() + timedelta(days=11)
        Reserva.objects.create(
            fecha_reserva=fecha_reserva + timedelta(days=1),
            hora_inicio='01:00',
            hora_fin='03:00',
            cantidad_invitados=2,
            estado_reserva=self.estado_reserva_aprobada,
            zona=self.zona_comun,
            apartamento=self.a2,
        )
        self.login_schema_user(self.tenant_user)

        response = self.client.post(
            '/residente/modulo/reservas/nuevo/?modal=1',
            {
                'modal': '1',
                'zona': str(self.zona_comun.pk),
                'fecha_reserva': fecha_reserva.isoformat(),
                'hora_inicio': '22:00',
                'hora_fin': '02:00',
                'cantidad_invitados': '2',
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'reserva aprobada', status_code=400)

    def test_reservas_rechazan_fechas_pasadas_para_admin_y_residente(self):
        fecha_pasada = (timezone.localdate() - timedelta(days=1)).isoformat()
        for usuario, ruta, apartamento in (
            (self.admin_user, '/administrador', self.a1),
            (self.tenant_user, '/residente', None),
        ):
            self.login_schema_user(usuario)
            datos = {
                'modal': '1',
                'zona': str(self.zona_comun.pk),
                'fecha_reserva': fecha_pasada,
                'hora_inicio': '10:00',
                'hora_fin': '11:00',
                'cantidad_invitados': '2',
            }
            if apartamento:
                datos['apartamento'] = str(apartamento.pk)
                datos['estado_reserva'] = str(self.estado_reserva_pendiente.pk)

            response = self.client.post(
                f'{ruta}/modulo/reservas/nuevo/?modal=1',
                datos,
            )

            self.assertEqual(response.status_code, 400)
            self.assertContains(response, 'fecha no puede ser anterior a hoy', status_code=400)
        self.assertFalse(Reserva.objects.exists())

    def test_formulario_admin_solo_muestra_apartamentos_con_residentes_asignados(self):
        apartamento_vacio = Apartamento.objects.create(
            torre=self.a1.torre,
            numero_apartamento='103',
            piso=1,
        )
        self.login_schema_user(self.admin_user)

        response = self.client.get('/administrador/modulo/reservas/nuevo/?modal=1')

        self.assertEqual(response.status_code, 200)
        apartamento_ids = set(
            response.context['form'].fields['apartamento'].queryset.values_list('pk', flat=True)
        )
        self.assertEqual(apartamento_ids, {self.a1.pk, self.a2.pk})
        self.assertNotIn(apartamento_vacio.pk, apartamento_ids)

    def test_administrador_aprueba_y_residente_cancela_reserva_aprobada(self):
        self.login_schema_user(self.admin_user)
        response = self.client.get('/administrador/modulo/reservas/nuevo/?modal=1')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="apartamento"')
        self.assertContains(response, 'name="estado_reserva"')

        response = self.client.post(
            '/administrador/modulo/reservas/nuevo/?modal=1',
            {
                'modal': '1',
                'zona': str(self.zona_comun.pk),
                'apartamento': str(self.a1.pk),
                'fecha_reserva': (date.today() + timedelta(days=4)).isoformat(),
                'hora_inicio': '10:00',
                'hora_fin': '11:00',
                'cantidad_invitados': '3',
                'estado_reserva': str(self.estado_reserva_pendiente.pk),
            },
        )
        self.assertEqual(response.status_code, 302)
        reserva = Reserva.objects.get(apartamento=self.a1)

        response = self.client.post(
            f'/administrador/modulo/reservas/{reserva.pk}/aprobar-reserva/'
        )
        self.assertEqual(response.status_code, 302)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado_reserva, self.estado_reserva_aprobada)

        self.login_schema_user(self.tenant_user)
        response = self.client.post(
            f'/residente/modulo/reservas/{reserva.pk}/cancelar-reserva/'
        )
        self.assertEqual(response.status_code, 302)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado_reserva, self.estado_reserva_cancelada)

    def test_reserva_solo_bloquea_solapamientos_con_reservas_aprobadas(self):
        fecha_reserva = date.today() + timedelta(days=5)
        Reserva.objects.create(
            fecha_reserva=fecha_reserva,
            hora_inicio='10:00',
            hora_fin='11:00',
            cantidad_invitados=2,
            estado_reserva=self.estado_reserva_pendiente,
            zona=self.zona_comun,
            apartamento=self.a2,
        )
        self.login_schema_user(self.tenant_user)
        response = self.client.post(
            '/residente/modulo/reservas/nuevo/?modal=1',
            {
                'modal': '1',
                'zona': str(self.zona_comun.pk),
                'fecha_reserva': fecha_reserva.isoformat(),
                'hora_inicio': '10:30',
                'hora_fin': '11:30',
                'cantidad_invitados': '2',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Reserva.objects.filter(fecha_reserva=fecha_reserva).count(), 2)

        Reserva.objects.create(
            fecha_reserva=fecha_reserva,
            hora_inicio='10:00',
            hora_fin='11:00',
            cantidad_invitados=2,
            estado_reserva=self.estado_reserva_aprobada,
            zona=self.zona_comun,
            apartamento=self.a2,
        )
        response = self.client.post(
            '/residente/modulo/reservas/nuevo/?modal=1',
            {
                'modal': '1',
                'zona': str(self.zona_comun.pk),
                'fecha_reserva': fecha_reserva.isoformat(),
                'hora_inicio': '10:30',
                'hora_fin': '11:30',
                'cantidad_invitados': '2',
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'reserva aprobada', status_code=400)
        self.assertEqual(Reserva.objects.filter(fecha_reserva=fecha_reserva).count(), 3)

    def test_administrador_no_puede_aprobar_un_solapamiento(self):
        fecha_reserva = date.today() + timedelta(days=7)
        aprobada = Reserva.objects.create(
            fecha_reserva=fecha_reserva,
            hora_inicio='09:00',
            hora_fin='10:00',
            cantidad_invitados=2,
            estado_reserva=self.estado_reserva_aprobada,
            zona=self.zona_comun,
            apartamento=self.a1,
        )
        pendiente = Reserva.objects.create(
            fecha_reserva=fecha_reserva,
            hora_inicio='09:30',
            hora_fin='10:30',
            cantidad_invitados=2,
            estado_reserva=self.estado_reserva_pendiente,
            zona=self.zona_comun,
            apartamento=self.a2,
        )
        self.login_schema_user(self.admin_user)

        response = self.client.post(
            f'/administrador/modulo/reservas/{pendiente.pk}/aprobar-reserva/',
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'No puedes aprobar esta reserva porque ya hay una reserva aprobada en ese horario.',
        )
        self.assertContains(response, 'class="notice notice-error"')
        aprobada.refresh_from_db()
        pendiente.refresh_from_db()
        self.assertEqual(aprobada.estado_reserva, self.estado_reserva_aprobada)
        self.assertEqual(pendiente.estado_reserva, self.estado_reserva_pendiente)

    def test_filtros_de_reservas_por_zona_estado_fecha_y_minimo_de_invitados(self):
        Reserva.objects.create(
            fecha_reserva=date.today() + timedelta(days=6),
            hora_inicio='15:00',
            hora_fin='16:00',
            cantidad_invitados=8,
            estado_reserva=self.estado_reserva_aprobada,
            zona=self.zona_comun,
            apartamento=self.a1,
        )
        self.login_schema_user(self.admin_user)
        response = self.client.get(
            '/administrador/modulo/reservas/',
            {
                'reserva_zona': str(self.zona_comun.pk),
                'reserva_estado': 'Aprobada',
                'reserva_desde': (date.today() + timedelta(days=6)).isoformat(),
                'reserva_hasta': (date.today() + timedelta(days=6)).isoformat(),
                'invitados_minimos': '8',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['rows']), 1)

    def test_administrador_puede_abrir_formulario_nueva_visita(self):
        self.login_schema_user(self.admin_user)

        response = self.client.get('/administrador/modulo/visitas/nuevo/?modal=1')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Registrar visita')

    def test_administrador_registra_zona_comun_desde_modal(self):
        self.login_schema_user(self.admin_user)

        listado = self.client.get('/administrador/modulo/zonas/')
        formulario = self.client.get('/administrador/modulo/zonas/nuevo/?modal=1')

        self.assertEqual(listado.status_code, 200)
        self.assertContains(listado, 'js-open-zona-form')
        self.assertContains(listado, 'zona-form-modal')
        self.assertEqual(formulario.status_code, 200)
        self.assertContains(formulario, 'name="modal" value="1"')
        self.assertContains(formulario, 'Registrar zona')

        response = self.client.post(
            '/administrador/modulo/zonas/nuevo/?modal=1',
            {'modal': '1', 'nombre': 'Salón social', 'descripcion': 'Espacio común'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(ZonaComun.objects.filter(nombre='Salón social').exists())

    def test_residente_abre_formulario_de_visita_en_modal(self):
        self.login_schema_user(self.tenant_user)

        listado = self.client.get('/residente/modulo/visitas/')
        formulario = self.client.get('/residente/modulo/visitas/nuevo/?modal=1')

        self.assertEqual(listado.status_code, 200)
        self.assertContains(listado, 'visita-form-modal')
        self.assertContains(listado, 'js-open-visita-form')
        self.assertEqual(formulario.status_code, 200)
        self.assertContains(formulario, 'name="modal" value="1"')
        self.assertContains(formulario, 'Registrar visita')

    def test_visita_creada_por_administrador_espera_autorizacion(self):
        self.login_schema_user(self.admin_user)
        fecha_pasada = timezone.localtime(
            timezone.now() - timedelta(days=1)
        ).strftime('%Y-%m-%dT%H:%M')

        response = self.client.post(
            '/administrador/modulo/visitas/nuevo/?modal=1',
            {
                'modal': '1',
                'tipo_visita': str(self.tipo_visita.pk),
                'tipo_documento': str(self.tipo_doc.pk),
                'nombre_visitante': 'Visita Admin',
                'documento_visitante': '12345678',
                'motivo_visita': 'Prueba',
                'apartamento': str(self.a1.pk),
                'fecha_ingreso': fecha_pasada,
                'fecha_salida': '',
            },
        )

        self.assertEqual(response.status_code, 302)
        visita = Visita.objects.get(nombre_visitante='Visita Admin')
        self.assertEqual(visita.estado_visita.nombre, 'Pendiente')
        self.assertFalse(visita.autorizada)
        self.assertIsNone(visita.fecha_salida)

    def test_visita_creada_por_residente_queda_autorizada(self):
        self.login_schema_user(self.tenant_user)
        fecha_pasada = timezone.localtime(
            timezone.now() - timedelta(days=1)
        ).strftime('%Y-%m-%dT%H:%M')

        response = self.client.post(
            '/residente/modulo/visitas/nuevo/?modal=1',
            {
                'modal': '1',
                'tipo_visita': str(self.tipo_visita.pk),
                'tipo_documento': str(self.tipo_doc.pk),
                'nombre_visitante': 'Visita Residente',
                'documento_visitante': '12345678',
                'motivo_visita': 'Prueba',
                'apartamento': str(self.a1.pk),
                'fecha_ingreso': fecha_pasada,
                'fecha_salida': '',
            },
        )

        self.assertEqual(response.status_code, 302)
        visita = Visita.objects.get(nombre_visitante='Visita Residente')
        self.assertEqual(visita.estado_visita.nombre, 'Pendiente')
        self.assertTrue(visita.autorizada)

    def test_administrador_vigilante_y_residente_pueden_cancelar_visita(self):
        vigilante_role = Rol.objects.create(nombre='Vigilante')
        vigilante_persona = Persona.objects.create(
            tipo_documento=self.tipo_doc,
            numero_documento='100000098',
            nombres='Vigilante',
            apellidos='Prueba',
        )
        vigilante = Usuario.objects.create(
            username='vigilante_cancel_test',
            password=set_schema_password('prueba-segura-123'),
            estado_usuario=self.estado_activo,
            persona=vigilante_persona,
            rol=vigilante_role,
        )
        for usuario, namespace in (
            (self.admin_user, 'administrador'),
            (vigilante, 'vigilante'),
            (self.tenant_user, 'residente'),
        ):
            visita = self.crear_visita()
            self.login_schema_user(usuario)
            response = self.client.post(
                f'/{namespace}/modulo/visitas/{visita.pk}/cancelar-visita/'
            )

            self.assertEqual(response.status_code, 302)
            visita.refresh_from_db()
            self.assertEqual(visita.estado_visita, self.estado_visita_cancelada)
            self.assertIsNone(visita.fecha_salida)

    def test_residente_no_puede_cancelar_visita_de_otro_apartamento(self):
        visita = self.crear_visita()
        visita.apartamento = self.a2
        visita.save(update_fields=['apartamento'])
        self.login_schema_user(self.tenant_user)

        response = self.client.post(
            f'/residente/modulo/visitas/{visita.pk}/cancelar-visita/'
        )

        self.assertEqual(response.status_code, 403)
        visita.refresh_from_db()
        self.assertEqual(visita.estado_visita, self.estado_visita_pendiente)

    def test_residente_autoriza_y_vigilante_finaliza_visita(self):
        visita = self.crear_visita()
        self.login_schema_user(self.tenant_user)

        response = self.client.post(
            f'/residente/modulo/visitas/{visita.pk}/autorizar-visita/'
        )

        self.assertEqual(response.status_code, 302)
        visita.refresh_from_db()
        self.assertTrue(visita.autorizada)
        self.assertEqual(visita.estado_visita.nombre, 'Pendiente')

        response = self.client.post(
            f'/residente/modulo/visitas/{visita.pk}/finalizar-visita/'
        )
        self.assertEqual(response.status_code, 403)
        visita.refresh_from_db()
        self.assertIsNone(visita.fecha_salida)

        vigilante_role = Rol.objects.create(nombre='Vigilante')
        vigilante_persona = Persona.objects.create(
            tipo_documento=self.tipo_doc,
            numero_documento='100000098',
            nombres='Vigilante',
            apellidos='Prueba',
        )
        vigilante = Usuario.objects.create(
            username='vigilante_test',
            password=set_schema_password('prueba-segura-123'),
            estado_usuario=self.estado_activo,
            persona=vigilante_persona,
            rol=vigilante_role,
        )
        self.login_schema_user(vigilante)
        response = self.client.post(
            f'/vigilante/modulo/visitas/{visita.pk}/finalizar-visita/'
        )

        self.assertEqual(response.status_code, 302)
        visita.refresh_from_db()
        self.assertEqual(visita.estado_visita.nombre, 'Finalizada')
        self.assertIsNotNone(visita.fecha_salida)

    def test_filtros_de_visitas_y_reporte_pdf(self):
        self.crear_visita()
        self.login_schema_user(self.admin_user)
        fecha_desde = '2000-01-01'
        filtros = {
            'visita_tipo': str(self.tipo_visita.pk),
            'visita_estado': 'pendiente',
            'visita_torre': str(self.a1.torre_id),
            'ingreso_desde': fecha_desde,
        }
        for key, value in filtros.items():
            response = self.client.get('/administrador/modulo/visitas/', {key: value})
            self.assertEqual(
                len(response.context['rows']),
                1,
                f'El filtro {key} no devolvió la visita esperada.',
            )

        response = self.client.get('/administrador/modulo/visitas/', filtros)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['rows']), 1)

        filtros['salida_desde'] = fecha_desde
        response = self.client.get('/administrador/modulo/visitas/', filtros)
        self.assertEqual(len(response.context['rows']), 0)

        filtros.pop('salida_desde')
        response = self.client.get('/administrador/modulo/visitas/reporte.pdf', filtros)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_administrador_puede_eliminar_vinculo_con_clave_compuesta(self):
        self.login_schema_user(self.admin_user)
        key = f'{self.a2.pk}-{self.familiar.pk}'

        response = self.client.post(
            f'/administrador/modulo/residentes/{key}/eliminar/',
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            ApartamentoPersona.objects.filter(
                apartamento_id=self.a2.pk,
                persona_id=self.familiar.pk,
            ).exists()
        )


class RecibosComprobantesTests(TestCase):
    def setUp(self):
        self.media_directory = tempfile.TemporaryDirectory()
        media_settings = override_settings(MEDIA_ROOT=self.media_directory.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)
        self.addCleanup(self.media_directory.cleanup)

        self.estado_pendiente = EstadoRecibo.objects.create(nombre='Pendiente')
        self.estado_revision = EstadoRecibo.objects.create(nombre='Pendiente por revisar')
        self.estado_pagado = EstadoRecibo.objects.create(nombre='Pagado')
        self.servicio = TipoServicio.objects.create(nombre='Agua')
        self.estado_usuario = EstadoUsuario.objects.create(nombre='Activo')
        self.rol_admin = Rol.objects.create(nombre='Administrador')
        self.rol_vigilante = Rol.objects.create(nombre='Vigilante')
        self.rol_residente = Rol.objects.create(nombre='Residente')
        self.tipo_documento = TipoDocumento.objects.create(nombre='Cédula', abreviatura='CC')
        self.tipo_propietario = TipoResidente.objects.create(nombre='Propietario')
        self.torre = Torre.objects.create(nombre_torre='Torre recibos')
        self.apartamento = Apartamento.objects.create(
            torre=self.torre, numero_apartamento='201', piso=2, activo=True
        )
        self.otro_apartamento = Apartamento.objects.create(
            torre=self.torre, numero_apartamento='202', piso=2, activo=True
        )
        self.persona_residente = Persona.objects.create(
            tipo_documento=self.tipo_documento,
            numero_documento='200000001',
            nombres='Residente',
            apellidos='Prueba',
        )
        self.persona_admin = Persona.objects.create(
            tipo_documento=self.tipo_documento,
            numero_documento='200000002',
            nombres='Admin',
            apellidos='Prueba',
        )
        self.persona_vigilante = Persona.objects.create(
            tipo_documento=self.tipo_documento,
            numero_documento='200000003',
            nombres='Vigilante',
            apellidos='Prueba',
        )
        self.residente = Usuario.objects.create(
            username='recibo_residente',
            password=set_schema_password('prueba-segura-123'),
            estado_usuario=self.estado_usuario,
            persona=self.persona_residente,
            rol=self.rol_residente,
        )
        self.admin = Usuario.objects.create(
            username='recibo_admin',
            password=set_schema_password('prueba-segura-123'),
            estado_usuario=self.estado_usuario,
            persona=self.persona_admin,
            rol=self.rol_admin,
        )
        self.vigilante = Usuario.objects.create(
            username='recibo_vigilante',
            password=set_schema_password('prueba-segura-123'),
            estado_usuario=self.estado_usuario,
            persona=self.persona_vigilante,
            rol=self.rol_vigilante,
        )
        ApartamentoPersona.objects.create(
            persona=self.persona_residente,
            apartamento=self.apartamento,
            tipo_residente=self.tipo_propietario,
            fecha_ingreso=date(2024, 1, 1),
        )

    def login_schema_user(self, usuario):
        session = self.client.session
        session['_schema_user_id'] = usuario.pk
        session.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    def crear_recibo(self, apartamento=None):
        return Recibo.objects.create(
            tipo_servicio=self.servicio,
            periodo='2026-11',
            valor='85000.00',
            fecha_emision=date(2026, 11, 1),
            fecha_vencimiento=date(2026, 11, 15),
            estado_recibo=self.estado_pendiente,
            apartamento=apartamento or self.apartamento,
        )

    def imagen_png(self):
        return SimpleUploadedFile(
            'comprobante.png',
            b'\x89PNG\r\n\x1a\n' + (b'\x00' * 24),
            content_type='image/png',
        )

    def test_staff_crea_recibo_pendiente_desde_modal_sin_campo_estado(self):
        self.login_schema_user(self.admin)
        response = self.client.get('/administrador/modulo/recibos/nuevo/?modal=1')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('estado_recibo', response.context['form'].fields)

        response = self.client.post(
            '/administrador/modulo/recibos/nuevo/?modal=1',
            {
                'modal': '1',
                'tipo_servicio': str(self.servicio.pk),
                'apartamento': str(self.apartamento.pk),
                'periodo': '2026-11',
                'valor': '85000',
                'fecha_emision': '2026-11-01',
                'fecha_vencimiento': '2026-11-15',
                'estado_recibo': str(self.estado_pagado.pk),
            },
        )

        self.assertEqual(response.status_code, 302)
        recibo = Recibo.objects.get()
        self.assertEqual(recibo.estado_recibo, self.estado_pendiente)

    def test_residente_sube_y_cancela_comprobante(self):
        recibo = self.crear_recibo()
        self.login_schema_user(self.residente)

        response = self.client.get(f'/residente/modulo/recibos/{recibo.pk}/subir-comprobante/')
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            f'/residente/modulo/recibos/{recibo.pk}/subir-comprobante/',
            {'comprobante': self.imagen_png()},
        )

        self.assertEqual(response.status_code, 302)
        recibo.refresh_from_db()
        self.assertEqual(recibo.estado_recibo, self.estado_revision)
        self.assertTrue(default_storage.exists(recibo.comprobante))

        response = self.client.post(
            f'/residente/modulo/recibos/{recibo.pk}/cancelar-comprobante/'
        )
        self.assertEqual(response.status_code, 302)
        recibo.refresh_from_db()
        self.assertEqual(recibo.estado_recibo, self.estado_pendiente)
        self.assertIsNone(recibo.comprobante)

    def test_admin_aprueba_o_rechaza_comprobante_y_residente_no_accede_a_otro_apartamento(self):
        recibo = self.crear_recibo()
        self.login_schema_user(self.residente)
        response = self.client.post(
            f'/residente/modulo/recibos/{recibo.pk}/subir-comprobante/',
            {'comprobante': self.imagen_png()},
        )
        self.assertEqual(response.status_code, 302)
        recibo.refresh_from_db()

        self.login_schema_user(self.admin)
        response = self.client.get('/administrador/modulo/recibos/?vista=revision')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['item'].pk for row in response.context['rows']], [recibo.pk])
        self.assertContains(response, '<th>Comprobante</th>')
        self.assertContains(response, 'Torre recibos - 201')
        response = self.client.get(f'/administrador/modulo/recibos/{recibo.pk}/comprobante/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('image/png'))
        self.assertTrue(b''.join(response.streaming_content).startswith(b'\x89PNG\r\n\x1a\n'))
        response = self.client.post(
            f'/administrador/modulo/recibos/{recibo.pk}/revision/aprobar/'
        )
        self.assertEqual(response.status_code, 302)
        recibo.refresh_from_db()
        self.assertEqual(recibo.estado_recibo, self.estado_pagado)

        recibo_rechazo = self.crear_recibo()
        self.login_schema_user(self.residente)
        response = self.client.post(
            f'/residente/modulo/recibos/{recibo_rechazo.pk}/subir-comprobante/',
            {'comprobante': self.imagen_png()},
        )
        self.assertEqual(response.status_code, 302)

        self.login_schema_user(self.admin)
        response = self.client.post(
            f'/administrador/modulo/recibos/{recibo_rechazo.pk}/revision/rechazar/'
        )
        self.assertEqual(response.status_code, 302)
        recibo_rechazo.refresh_from_db()
        self.assertEqual(recibo_rechazo.estado_recibo, self.estado_pendiente)
        self.assertIsNone(recibo_rechazo.comprobante)

        self.login_schema_user(self.residente)
        recibo_ajeno = self.crear_recibo(self.otro_apartamento)
        response = self.client.post(
            f'/residente/modulo/recibos/{recibo_ajeno.pk}/subir-comprobante/',
            {'comprobante': self.imagen_png()},
        )
        self.assertEqual(response.status_code, 403)

    def test_comprobante_invalido_no_cambia_estado(self):
        recibo = self.crear_recibo()
        self.login_schema_user(self.residente)
        response = self.client.post(
            f'/residente/modulo/recibos/{recibo.pk}/subir-comprobante/',
            {'comprobante': SimpleUploadedFile('no-es-imagen.txt', b'archivo no valido')},
        )
        self.assertEqual(response.status_code, 400)
        recibo.refresh_from_db()
        self.assertEqual(recibo.estado_recibo, self.estado_pendiente)
        self.assertIsNone(recibo.comprobante)

    def test_eliminar_recibo_borra_el_comprobante_privado(self):
        recibo = self.crear_recibo()
        self.login_schema_user(self.residente)
        response = self.client.post(
            f'/residente/modulo/recibos/{recibo.pk}/subir-comprobante/',
            {'comprobante': self.imagen_png()},
        )
        self.assertEqual(response.status_code, 302)
        recibo.refresh_from_db()
        ruta_comprobante = recibo.comprobante
        self.assertTrue(default_storage.exists(ruta_comprobante))

        self.login_schema_user(self.admin)
        response = self.client.post(f'/administrador/modulo/recibos/{recibo.pk}/eliminar/')
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Recibo.objects.filter(pk=recibo.pk).exists())
        self.assertFalse(default_storage.exists(ruta_comprobante))

    def test_vigilante_puede_ver_todos_pero_no_revisar_comprobantes(self):
        recibo = self.crear_recibo()
        self.login_schema_user(self.vigilante)
        response = self.client.get('/vigilante/modulo/recibos/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['item'].pk for row in response.context['rows']], [recibo.pk])
        response = self.client.post(
            f'/vigilante/modulo/recibos/{recibo.pk}/revision/aprobar/'
        )
        self.assertEqual(response.status_code, 404)

    def test_filtros_de_recibos_por_estado_servicio_torre_vencimiento_y_valor(self):
        recibo_esperado = self.crear_recibo()
        servicio_gas = TipoServicio.objects.create(nombre='Gas')
        otro_recibo = Recibo.objects.create(
            tipo_servicio=servicio_gas,
            periodo='2026-12',
            valor='150000.00',
            fecha_emision=date(2026, 12, 1),
            fecha_vencimiento=date(2026, 12, 20),
            estado_recibo=self.estado_pagado,
            apartamento=self.otro_apartamento,
        )
        filtros = {
            'recibo_servicio': str(self.servicio.pk),
            'recibo_estado': 'Pendiente',
            'recibo_torre': str(self.torre.pk),
            'vence_desde': '2026-11-01',
            'vence_hasta': '2026-11-30',
            'valor_minimo': '80000',
        }

        self.login_schema_user(self.admin)
        response = self.client.get('/administrador/modulo/recibos/', filtros)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['item'].pk for row in response.context['rows']], [recibo_esperado.pk])
        self.assertContains(response, '<th>Vencimiento</th>')
        self.assertContains(response, '<th>Estado</th>')
        self.assertContains(response, '<td>85000,00</td>')
        self.assertContains(response, 'Torre recibos - 201')

        self.login_schema_user(self.residente)
        response = self.client.get('/residente/modulo/recibos/', {
            'recibo_estado': 'Pendiente',
            'vence_desde': '2026-11-01',
            'vence_hasta': '2026-11-30',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['item'].pk for row in response.context['rows']], [recibo_esperado.pk])
        self.assertNotIn(otro_recibo.pk, [row['item'].pk for row in response.context['rows']])

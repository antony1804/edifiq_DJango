from datetime import date
from unittest.mock import patch

from django.conf import settings
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.core.models import (
    EstadoPaquete,
    EstadoUsuario,
    Rol,
    TipoDocumento,
    TipoResidente,
    Usuario,
)
from apps.core.package_notifications import (
    schedule_package_received_email,
    send_package_received_emails,
)
from apps.core.schema_auth import set_schema_password
from apps.paquetes.models import Paquete
from apps.personas.models import Persona
from apps.residentes.models import Apartamento, ApartamentoPersona, Torre


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='pruebas@example.test',
)
class NotificacionesPaquetesTests(TestCase):
    def setUp(self):
        self.tipo_documento = TipoDocumento.objects.create(nombre='Cédula', abreviatura='CC')
        self.tipo_propietario = TipoResidente.objects.create(nombre='Propietario')
        self.tipo_arrendatario = TipoResidente.objects.create(nombre='Arrendatario')
        self.tipo_familiar = TipoResidente.objects.create(nombre='Familiar')
        self.estado_paquete = EstadoPaquete.objects.create(nombre='Recibido')
        self.estado_usuario = EstadoUsuario.objects.create(nombre='Activo')
        self.rol_admin = Rol.objects.create(nombre='Administrador')

        self.torre = Torre.objects.create(nombre_torre='Torre A')
        self.apartamento = Apartamento.objects.create(
            torre=self.torre,
            numero_apartamento='101',
            piso=1,
        )
        self.otro_apartamento = Apartamento.objects.create(
            torre=self.torre,
            numero_apartamento='102',
            piso=1,
        )

        self.residente_con_correo = self.crear_persona(
            '100000001', 'Ana', 'ana@example.test'
        )
        self.residente_sin_correo = self.crear_persona(
            '100000002', 'Bruno', None
        )
        self.residente_correo_invalido = self.crear_persona(
            '100000003', 'Carla', 'no-es-un-correo'
        )
        self.residente_otro_apartamento = self.crear_persona(
            '100000004', 'Diego', 'diego@example.test'
        )
        self.residente_persona_inactiva = self.crear_persona(
            '100000005', 'Elena', 'elena@example.test', activo=False
        )
        self.residente_vinculo_finalizado = self.crear_persona(
            '100000006', 'Fabio', 'fabio@example.test'
        )
        self.persona_admin = self.crear_persona(
            '100000099', 'Admin', 'admin@example.test'
        )
        self.admin = Usuario.objects.create(
            username='admin_paquetes',
            password=set_schema_password('prueba-segura-123'),
            estado_usuario=self.estado_usuario,
            persona=self.persona_admin,
            rol=self.rol_admin,
        )

        self.vincular(self.residente_con_correo, self.tipo_propietario)
        self.vincular(self.residente_sin_correo, self.tipo_arrendatario)
        self.vincular(self.residente_correo_invalido, self.tipo_familiar)
        self.vincular(self.residente_persona_inactiva, self.tipo_familiar)
        vinculo_finalizado = self.vincular(
            self.residente_vinculo_finalizado,
            self.tipo_familiar,
        )
        vinculo_finalizado.fecha_salida = date(2026, 1, 1)
        vinculo_finalizado.save(update_fields=['fecha_salida'])
        ApartamentoPersona.objects.create(
            apartamento=self.otro_apartamento,
            persona=self.residente_otro_apartamento,
            tipo_residente=self.tipo_propietario,
            fecha_ingreso=date(2025, 1, 1),
        )

    def crear_persona(self, documento, nombre, correo, activo=True):
        return Persona.objects.create(
            tipo_documento=self.tipo_documento,
            numero_documento=documento,
            nombres=nombre,
            apellidos='Prueba',
            correo=correo,
            activo=activo,
        )

    def vincular(self, persona, tipo_residente):
        return ApartamentoPersona.objects.create(
            apartamento=self.apartamento,
            persona=persona,
            tipo_residente=tipo_residente,
            fecha_ingreso=date(2025, 1, 1),
        )

    def crear_paquete(self):
        return Paquete.objects.create(
            descripcion='Caja de prueba',
            remitente='Tienda de prueba',
            fecha_recepcion=timezone.now(),
            estado_paquete=self.estado_paquete,
            apartamento=self.apartamento,
        )

    def iniciar_sesion_admin(self):
        session = self.client.session
        session['_schema_user_id'] = self.admin.pk
        session.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    def test_envia_a_residentes_activos_validos_del_apartamento(self):
        paquete = self.crear_paquete()

        send_package_received_emails(paquete.pk)

        self.assertEqual(len(mail.outbox), 1)
        mensaje = mail.outbox[0]
        self.assertEqual(mensaje.to, ['ana@example.test'])
        self.assertEqual(
            mensaje.subject,
            'Llegó un paquete para tu apartamento Torre A-101',
        )
        self.assertIn('Hola Ana', mensaje.body)
        self.assertIn('Remitente: Tienda de prueba', mensaje.body)
        self.assertIn('Descripción: Caja de prueba', mensaje.body)
        self.assertIn('Puedes recogerlo en la portería.', mensaje.body)

    def test_al_crear_o_cambiar_a_recibido_programa_envio_y_editar_no(self):
        paquete = self.crear_paquete()
        with patch(
            'apps.core.package_notifications.dispatch_package_received_email'
        ) as dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                self.assertTrue(schedule_package_received_email(
                    paquete.pk,
                    created=True,
                    previous_status='',
                    current_status='Recibido',
                ))
            dispatch.assert_called_once_with(paquete.pk)

            dispatch.reset_mock()
            with self.captureOnCommitCallbacks(execute=True):
                self.assertFalse(schedule_package_received_email(
                    paquete.pk,
                    created=False,
                    previous_status='Recibido',
                    current_status='Recibido',
                ))
            dispatch.assert_not_called()

            with self.captureOnCommitCallbacks(execute=True):
                self.assertTrue(schedule_package_received_email(
                    paquete.pk,
                    created=False,
                    previous_status='Entregado',
                    current_status='Recibido',
                ))
            dispatch.assert_called_once_with(paquete.pk)
        self.assertEqual(mail.outbox, [])

    def test_error_de_correo_no_afecta_el_paquete_guardado(self):
        paquete = self.crear_paquete()

        with patch(
            'apps.core.package_notifications.send_mail',
            side_effect=OSError('SMTP no disponible'),
        ):
            send_package_received_emails(paquete.pk)

        self.assertTrue(Paquete.objects.filter(pk=paquete.pk).exists())
        self.assertEqual(mail.outbox, [])

    def test_guardar_paquete_notifica_al_crear_pero_no_al_editar(self):
        self.iniciar_sesion_admin()
        create_url = reverse('administrador:create', kwargs={'slug': 'paquetes'})
        datos_creacion = {
            'descripcion': 'Sobre de prueba',
            'remitente': 'Proveedor',
            'apartamento': str(self.apartamento.pk),
            'estado_paquete': str(self.estado_paquete.pk),
            'fecha_recepcion': timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M'),
        }

        with patch(
            'apps.core.package_notifications.dispatch_package_received_email'
        ) as dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(create_url, datos_creacion)

            self.assertEqual(response.status_code, 302)
            paquete = Paquete.objects.get(descripcion='Sobre de prueba')
            dispatch.assert_called_once_with(paquete.pk)

            dispatch.reset_mock()
            edit_url = reverse(
                'administrador:edit',
                kwargs={'slug': 'paquetes', 'pk': str(paquete.pk)},
            )
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    edit_url,
                    {
                        'descripcion': 'Sobre actualizado',
                        'remitente': paquete.remitente,
                        'apartamento': str(self.apartamento.pk),
                    },
                )

            self.assertEqual(response.status_code, 302)
            self.assertEqual(
                Paquete.objects.get(pk=paquete.pk).descripcion,
                'Sobre actualizado',
            )
            dispatch.assert_not_called()

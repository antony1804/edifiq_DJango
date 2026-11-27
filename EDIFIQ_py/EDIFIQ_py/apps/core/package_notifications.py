import logging
from threading import Thread

from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import EmailValidator
from django.db import close_old_connections, transaction

from apps.paquetes.models import Paquete
from apps.residentes.models import ApartamentoPersona

logger = logging.getLogger(__name__)


def schedule_package_received_email(package_id, *, created, previous_status, current_status):
    current_is_received = (current_status or '').strip().casefold() == 'recibido'
    previous_was_received = (previous_status or '').strip().casefold() == 'recibido'
    if not current_is_received or (not created and previous_was_received):
        return False

    transaction.on_commit(lambda: dispatch_package_received_email(package_id))
    return True


def dispatch_package_received_email(package_id):
    try:
        Thread(
            target=_send_package_received_emails_in_thread,
            args=(package_id,),
            name=f'package-email-{package_id}',
            daemon=True,
        ).start()
    except Exception:
        logger.exception('No se pudo iniciar el envío de correo para el paquete %s', package_id)


def _send_package_received_emails_in_thread(package_id):
    close_old_connections()
    try:
        send_package_received_emails(package_id)
    finally:
        close_old_connections()


def send_package_received_emails(package_id):
    try:
        try:
            package = (
                Paquete.objects.select_related('apartamento__torre')
                .get(pk=package_id)
            )
        except Paquete.DoesNotExist:
            logger.error('No se encontró el paquete %s para enviar la notificación', package_id)
            return

        subject = (
            f'Llegó un paquete para tu apartamento '
            f'{package.apartamento.torre.nombre_torre}-{package.apartamento.numero_apartamento}'
        )
        links = (
            ApartamentoPersona.objects.filter(
                apartamento_id=package.apartamento_id,
                fecha_salida__isnull=True,
                persona__activo=True,
            )
            .select_related('persona')
            .order_by('persona__id_persona')
        )
        sent_addresses = set()
        for link in links:
            person = link.persona
            email = (person.correo or '').strip()
            if not email:
                continue
            try:
                EmailValidator()(email)
            except ValidationError:
                logger.info(
                    'Se omite correo inválido de la persona %s para el paquete %s',
                    person.pk,
                    package_id,
                )
                continue

            address_key = email.casefold()
            if address_key in sent_addresses:
                continue
            sent_addresses.add(address_key)

            body = (
                f'Hola {person.nombres},\n\n'
                f'Ha llegado un paquete para tu apartamento.\n'
                f'Remitente: {package.remitente}\n'
                f'Descripción: {package.descripcion}\n\n'
                'Puedes recogerlo en la portería.'
            )
            try:
                send_mail(
                    subject,
                    body,
                    None,
                    [email],
                    fail_silently=False,
                )
            except Exception:
                logger.exception(
                    'Falló el envío de correo para la persona %s y el paquete %s',
                    person.pk,
                    package_id,
                )
    except Exception:
        logger.exception('Falló la notificación del paquete %s', package_id)

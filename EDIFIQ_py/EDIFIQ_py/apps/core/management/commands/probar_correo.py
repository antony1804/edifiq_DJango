from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import EmailValidator


class Command(BaseCommand):
    help = 'Envía un correo de prueba usando la configuración actual de Django.'

    def add_arguments(self, parser):
        parser.add_argument('destinatario')

    def handle(self, *args, **options):
        recipient = options['destinatario'].strip()
        try:
            EmailValidator()(recipient)
        except ValidationError as exc:
            raise CommandError(f'El destinatario no es un correo válido: {exc}')

        try:
            sent = send_mail(
                'Prueba de correo EDIFIQ',
                'Este es un correo de prueba enviado con la configuración actual de Django.',
                None,
                [recipient],
                fail_silently=False,
            )
        except Exception as exc:
            raise CommandError(f'No se pudo enviar el correo: {exc}') from exc

        if sent != 1:
            raise CommandError('El backend no confirmó el envío del correo.')
        self.stdout.write(self.style.SUCCESS(f'Correo de prueba enviado a {recipient}.'))

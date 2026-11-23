from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from django.db import connections

class Command(BaseCommand):
    help = 'Comprueba tablas y cantidades de filas en la BD original sin modificarla.'
    def handle(self, *args, **options):
        if 'legado' not in connections.databases:
            raise CommandError('Configura EDIFIQ_LEGACY_DB=mysql antes de auditar.')
        connection = connections['legado']
        models = list(apps.get_app_config('legado').get_models())
        with connection.cursor() as cursor:
            existing = set(connection.introspection.table_names(cursor))
            missing = []
            for model in models:
                table = model._meta.db_table
                if table not in existing:
                    missing.append(table)
                    self.stdout.write(self.style.ERROR(f'FALTA {table}'))
                    continue
                cursor.execute(f'SELECT COUNT(*) FROM `{table}`')
                n = cursor.fetchone()[0]
                self.stdout.write(f'{table}: {n} filas')
            if missing:
                raise CommandError(f'Faltan {len(missing)} tablas originales')
        self.stdout.write(self.style.SUCCESS(f'Comprobadas {len(models)} tablas. No se modificó ningún dato.'))

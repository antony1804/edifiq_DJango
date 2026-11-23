from django.apps import apps
from django.conf import settings
from django.db import connections
from django.test.runner import DiscoverRunner


STUBBED_APPS = {
    'personas': 'edifiq.test_migrations.personas',
    'residentes': 'edifiq.test_migrations.residentes',
    'visitas': 'edifiq.test_migrations.visitas',
    'paquetes': 'edifiq.test_migrations.paquetes',
    'reservas': 'edifiq.test_migrations.reservas',
    'recibos': 'edifiq.test_migrations.recibos',
    'legado': 'edifiq.test_migrations.legado',
    'usuarios': 'edifiq.test_migrations.usuarios',
}

# Managed app models needed for tests but whose migrations are stubbed to avoid
# coupling to schema-mapped tables during migrate.
EXTRA_MANAGED_MODELS = [
    ('usuarios', 'Perfil'),
]


class SchemaManagedTestRunner(DiscoverRunner):
    """Materialize schema-mapped and required app tables in the ephemeral test DB.

    External business tables are managed=False and must not be created/altered in
    the real schema. For tests only (authorized), we:
    - disable incompatible/stub historical migrations for schema-mapped apps and
      usuarios (to avoid resolving schema relations during migrate),
    - run Django migrations for contrib apps (auth, admin, sessions, contenttypes),
    - create required managed app tables (e.g. usuarios.Perfil) and unmanaged
      schema tables from current model definitions in the test database.
    """

    def setup_databases(self, **kwargs):
        modules = dict(getattr(settings, 'MIGRATION_MODULES', {}) or {})
        modules.update(STUBBED_APPS)
        settings.MIGRATION_MODULES = modules
        old_config = super().setup_databases(**kwargs)
        self._materialize_tables()
        return old_config

    def _materialize_tables(self):
        for connection in connections.all():
            if connection.vendor == 'sqlite':
                with connection.cursor() as cursor:
                    cursor.execute('PRAGMA foreign_keys=OFF')
            try:
                self._create_models(connection, self._models_to_create())
            finally:
                if connection.vendor == 'sqlite':
                    with connection.cursor() as cursor:
                        cursor.execute('PRAGMA foreign_keys=ON')

    def _models_to_create(self):
        models_to_create = []
        for app_label, model_name in EXTRA_MANAGED_MODELS:
            try:
                models_to_create.append(apps.get_model(app_label, model_name))
            except LookupError:
                pass
        for model in apps.get_models():
            if not model._meta.managed and not model._meta.proxy and not model._meta.swapped:
                models_to_create.append(model)
        # de-duplicate preserving order
        seen = set()
        unique = []
        for m in models_to_create:
            key = (m._meta.app_label, m._meta.model_name)
            if key not in seen:
                seen.add(key)
                unique.append(m)
        return unique

    def _create_models(self, connection, models_to_create):
        pending = list(models_to_create)
        for _ in range(len(pending) + 4):
            next_pending = []
            existing = set(connection.introspection.table_names())
            for model in pending:
                if model._meta.db_table in existing:
                    continue
                try:
                    with connection.schema_editor() as schema_editor:
                        schema_editor.create_model(model)
                except Exception:
                    next_pending.append(model)
            if not next_pending:
                return
            pending = next_pending
        # Surface remaining errors for models still missing.
        existing = set(connection.introspection.table_names())
        for model in pending:
            if model._meta.db_table not in existing:
                with connection.schema_editor() as schema_editor:
                    schema_editor.create_model(model)

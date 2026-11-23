from django.apps import AppConfig

class LegadoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.legado'
    verbose_name = 'Tablas originales de EDIFIQ (solo lectura)'

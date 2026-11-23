class LegacyRouter:
    """Mantiene los modelos originales fuera de la BD Django y sus migraciones."""
    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'legado':
            return 'legado'
        return None
    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'legado':
            raise RuntimeError('La base original se consulta solo en lectura.')
        return None
    def allow_relation(self, obj1, obj2, **hints):
        if 'legado' in (obj1._meta.app_label, obj2._meta.app_label):
            return obj1._meta.app_label == obj2._meta.app_label
        return None
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == 'legado':
            return False
        if db == 'legado':
            return False
        return None

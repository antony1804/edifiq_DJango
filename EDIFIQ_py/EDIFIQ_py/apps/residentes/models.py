from django.db import models
from apps.personas.models import Persona


class Torre(models.Model):
    id_torre = models.AutoField(primary_key=True)
    nombre_torre = models.CharField(max_length=20, unique=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'torre'

    def __str__(self):
        return self.nombre_torre


class Apartamento(models.Model):
    id_apartamento = models.AutoField(primary_key=True)
    numero_apartamento = models.CharField(max_length=10)
    piso = models.IntegerField()
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    torre = models.ForeignKey(
        Torre,
        on_delete=models.PROTECT,
        db_column='id_torre',
        related_name='apartamentos',
    )

    class Meta:
        managed = False
        db_table = 'apartamento'
        constraints = [
            models.UniqueConstraint(
                fields=['torre', 'numero_apartamento'],
                name='apartamento_torre_numero_uniq',
            )
        ]

    def __str__(self):
        return f'{self.torre} - {self.numero_apartamento}'


class ApartamentoPersona(models.Model):
    """Vínculo persona-apartamento según esquema (PK compuesta). Sin columnas extra (activo/parentesco/responsable)."""
    pk = models.CompositePrimaryKey('apartamento', 'persona')
    apartamento = models.ForeignKey(
        Apartamento,
        on_delete=models.PROTECT,
        db_column='id_apartamento',
        related_name='vinculos_persona',
    )
    persona = models.ForeignKey(
        Persona,
        on_delete=models.PROTECT,
        db_column='id_persona',
        related_name='vinculos_apartamento',
    )
    tipo_residente = models.ForeignKey(
        'core.TipoResidente',
        on_delete=models.PROTECT,
        db_column='id_tipo_residente',
        related_name='vinculos',
    )
    fecha_ingreso = models.DateField()
    fecha_salida = models.DateField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'apartamento_persona'

    def __str__(self):
        return f'{self.persona} · {self.apartamento} ({self.tipo_residente})'


# Compatibilidad temporal de nombre para imports durante la adaptación por etapas.
# El esquema no tiene tabla/modelo "residente" separado; el vínculo real es ApartamentoPersona.
Residente = ApartamentoPersona
Familiar = None  # eliminado: usar ApartamentoPersona con tipo_residente "Familiar" (decisión 1)

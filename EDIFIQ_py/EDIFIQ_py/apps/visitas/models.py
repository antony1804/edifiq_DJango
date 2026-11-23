from django.db import models


class Visita(models.Model):
    id_visita = models.AutoField(primary_key=True)
    tipo_visita = models.ForeignKey(
        'core.TipoVisita',
        on_delete=models.PROTECT,
        db_column='id_tipo_visita',
    )
    tipo_documento = models.ForeignKey(
        'core.TipoDocumento',
        on_delete=models.PROTECT,
        db_column='id_tipo_documento',
    )
    nombre_visitante = models.CharField(max_length=100)
    documento_visitante = models.CharField(max_length=30)
    motivo_visita = models.CharField(max_length=150, blank=True, null=True)
    fecha_ingreso = models.DateTimeField()
    fecha_salida = models.DateTimeField(null=True, blank=True)
    estado_visita = models.ForeignKey(
        'core.EstadoVisita',
        on_delete=models.PROTECT,
        db_column='id_estado_visita',
    )
    autorizada = models.BooleanField(default=False)
    apartamento = models.ForeignKey(
        'residentes.Apartamento',
        on_delete=models.PROTECT,
        db_column='id_apartamento',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'visita'

    def __str__(self):
        return self.nombre_visitante

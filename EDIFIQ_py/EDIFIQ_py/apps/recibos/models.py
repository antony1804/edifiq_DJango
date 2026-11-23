from django.db import models


class Recibo(models.Model):
    id_recibo = models.AutoField(primary_key=True)
    tipo_servicio = models.ForeignKey(
        'core.TipoServicio',
        on_delete=models.PROTECT,
        db_column='id_tipo_servicio',
    )
    periodo = models.CharField(max_length=20)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_emision = models.DateField()
    fecha_vencimiento = models.DateField()
    estado_recibo = models.ForeignKey(
        'core.EstadoRecibo',
        on_delete=models.PROTECT,
        db_column='id_estado_recibo',
    )
    apartamento = models.ForeignKey(
        'residentes.Apartamento',
        on_delete=models.PROTECT,
        db_column='id_apartamento',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'recibo'

    def __str__(self):
        return f'{self.tipo_servicio} {self.periodo}'

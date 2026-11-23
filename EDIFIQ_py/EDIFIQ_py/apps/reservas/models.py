from django.db import models


class ZonaComun(models.Model):
    id_zona = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)
    descripcion = models.CharField(max_length=200)

    class Meta:
        managed = False
        db_table = 'zona_comun'

    def __str__(self):
        return self.nombre


class Reserva(models.Model):
    id_reserva = models.AutoField(primary_key=True)
    fecha_reserva = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    cantidad_invitados = models.IntegerField(null=True, blank=True)
    estado_reserva = models.ForeignKey(
        'core.EstadoReserva',
        on_delete=models.PROTECT,
        db_column='id_estado_reserva',
    )
    zona = models.ForeignKey(
        ZonaComun,
        on_delete=models.PROTECT,
        db_column='id_zona',
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
        db_table = 'reserva_zona'

    def __str__(self):
        return f'{self.zona} - {self.apartamento} ({self.fecha_reserva})'

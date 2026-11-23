from django.db import models


class Paquete(models.Model):
    id_paquete = models.AutoField(primary_key=True)
    descripcion = models.CharField(max_length=200)
    remitente = models.CharField(max_length=100)
    fecha_recepcion = models.DateTimeField()
    fecha_entrega = models.DateTimeField(null=True, blank=True)
    estado_paquete = models.ForeignKey(
        'core.EstadoPaquete',
        on_delete=models.PROTECT,
        db_column='id_estado_paquete',
    )
    apartamento = models.ForeignKey(
        'residentes.Apartamento',
        on_delete=models.PROTECT,
        db_column='id_apartamento',
    )
    persona = models.ForeignKey(
        'personas.Persona',
        on_delete=models.PROTECT,
        db_column='id_persona',
        null=True,
        blank=True,
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'paquete'

    def __str__(self):
        return self.descripcion

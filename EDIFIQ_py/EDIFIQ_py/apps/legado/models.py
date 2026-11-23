"""Representación de las 24 tablas del SQL original. No gestionadas por migraciones.
No usar para escribir hasta completar validación de relaciones y contraseñas."""
from django.db import models

class TipoDocumento(models.Model):
    id_tipo_documento = models.AutoField(primary_key=True)
    class Meta:
        managed = False
        db_table = 'tipo_documento'

class TipoResidente(models.Model):
    id_tipo_residente = models.AutoField(primary_key=True)
    class Meta:
        managed = False
        db_table = 'tipo_residente'

class TipoVisita(models.Model):
    id_tipo_visita = models.AutoField(primary_key=True)
    class Meta:
        managed = False
        db_table = 'tipo_visita'

class TipoServicio(models.Model):
    id_tipo_servicio = models.AutoField(primary_key=True)
    class Meta:
        managed = False
        db_table = 'tipo_servicio'

class EstadoUsuario(models.Model):
    id_estado_usuario = models.AutoField(primary_key=True)
    class Meta:
        managed = False
        db_table = 'estado_usuario'

class EstadoVisita(models.Model):
    id_estado_visita = models.AutoField(primary_key=True)
    class Meta:
        managed = False
        db_table = 'estado_visita'

class EstadoPaquete(models.Model):
    id_estado_paquete = models.AutoField(primary_key=True)
    class Meta:
        managed = False
        db_table = 'estado_paquete'

class EstadoRecibo(models.Model):
    id_estado_recibo = models.AutoField(primary_key=True)
    class Meta:
        managed = False
        db_table = 'estado_recibo'

class EstadoReserva(models.Model):
    id_estado_reserva = models.AutoField(primary_key=True)
    class Meta:
        managed = False
        db_table = 'estado_reserva'

class Rol(models.Model):
    id_rol = models.AutoField(primary_key=True)
    class Meta:
        managed = False
        db_table = 'rol'

class Permiso(models.Model):
    id_permiso = models.AutoField(primary_key=True)
    class Meta:
        managed = False
        db_table = 'permiso'

class RolPermiso(models.Model):
    pk = models.CompositePrimaryKey('id_rol', 'id_permiso')
    id_rol = models.IntegerField(null=False, blank=False)
    id_permiso = models.IntegerField(null=False, blank=False)
    class Meta:
        managed = False
        db_table = 'rol_permiso'

class Torre(models.Model):
    id_torre = models.AutoField(primary_key=True)
    fecha_creacion = models.DateTimeField(null=True, blank=True)
    class Meta:
        managed = False
        db_table = 'torre'

class Apartamento(models.Model):
    id_apartamento = models.AutoField(primary_key=True)
    piso = models.IntegerField(null=False, blank=False)
    activo = models.BooleanField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(null=True, blank=True)
    fecha_actualizacion = models.DateTimeField(null=True, blank=True)
    id_torre = models.IntegerField(null=False, blank=False)
    class Meta:
        managed = False
        db_table = 'apartamento'

class Persona(models.Model):
    id_persona = models.AutoField(primary_key=True)
    id_tipo_documento = models.IntegerField(null=False, blank=False)
    activo = models.BooleanField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(null=True, blank=True)
    fecha_actualizacion = models.DateTimeField(null=True, blank=True)
    class Meta:
        managed = False
        db_table = 'persona'

class ApartamentoPersona(models.Model):
    pk = models.CompositePrimaryKey('id_apartamento', 'id_persona')
    id_apartamento = models.IntegerField(null=False, blank=False)
    id_persona = models.IntegerField(null=False, blank=False)
    id_tipo_residente = models.IntegerField(null=False, blank=False)
    fecha_ingreso = models.DateField(null=False, blank=False)
    fecha_salida = models.DateField(null=True, blank=True)
    class Meta:
        managed = False
        db_table = 'apartamento_persona'

class Usuario(models.Model):
    id_usuario = models.AutoField(primary_key=True)
    id_estado_usuario = models.IntegerField(null=False, blank=False)
    id_persona = models.IntegerField(null=False, blank=False)
    id_rol = models.IntegerField(null=False, blank=False)
    fecha_creacion = models.DateTimeField(null=True, blank=True)
    fecha_actualizacion = models.DateTimeField(null=True, blank=True)
    class Meta:
        managed = False
        db_table = 'usuario'

class Visita(models.Model):
    id_visita = models.AutoField(primary_key=True)
    id_tipo_visita = models.IntegerField(null=False, blank=False)
    id_tipo_documento = models.IntegerField(null=False, blank=False)
    fecha_ingreso = models.DateTimeField(null=False, blank=False)
    fecha_salida = models.DateTimeField(null=True, blank=True)
    id_estado_visita = models.IntegerField(null=False, blank=False)
    autorizada = models.BooleanField(null=False, blank=False)
    id_apartamento = models.IntegerField(null=False, blank=False)
    fecha_creacion = models.DateTimeField(null=True, blank=True)
    fecha_actualizacion = models.DateTimeField(null=True, blank=True)
    class Meta:
        managed = False
        db_table = 'visita'

class Paquete(models.Model):
    id_paquete = models.AutoField(primary_key=True)
    fecha_recepcion = models.DateTimeField(null=False, blank=False)
    fecha_entrega = models.DateTimeField(null=True, blank=True)
    id_estado_paquete = models.IntegerField(null=False, blank=False)
    id_apartamento = models.IntegerField(null=False, blank=False)
    id_persona = models.IntegerField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(null=True, blank=True)
    fecha_actualizacion = models.DateTimeField(null=True, blank=True)
    class Meta:
        managed = False
        db_table = 'paquete'

class Recibo(models.Model):
    id_recibo = models.AutoField(primary_key=True)
    id_tipo_servicio = models.IntegerField(null=False, blank=False)
    fecha_emision = models.DateField(null=False, blank=False)
    fecha_vencimiento = models.DateField(null=False, blank=False)
    id_estado_recibo = models.IntegerField(null=False, blank=False)
    id_apartamento = models.IntegerField(null=False, blank=False)
    fecha_creacion = models.DateTimeField(null=True, blank=True)
    fecha_actualizacion = models.DateTimeField(null=True, blank=True)
    class Meta:
        managed = False
        db_table = 'recibo'

class ZonaComun(models.Model):
    id_zona = models.AutoField(primary_key=True)
    class Meta:
        managed = False
        db_table = 'zona_comun'

class ReservaZona(models.Model):
    id_reserva = models.AutoField(primary_key=True)
    fecha_reserva = models.DateField(null=False, blank=False)
    hora_inicio = models.TimeField(null=False, blank=False)
    hora_fin = models.TimeField(null=False, blank=False)
    cantidad_invitados = models.IntegerField(null=True, blank=True)
    id_estado_reserva = models.IntegerField(null=False, blank=False)
    id_zona = models.IntegerField(null=False, blank=False)
    id_apartamento = models.IntegerField(null=False, blank=False)
    fecha_creacion = models.DateTimeField(null=True, blank=True)
    fecha_actualizacion = models.DateTimeField(null=True, blank=True)
    class Meta:
        managed = False
        db_table = 'reserva_zona'

class Notificacion(models.Model):
    id_notificacion = models.AutoField(primary_key=True)
    mensaje = models.TextField(null=False, blank=False)
    leida = models.BooleanField(null=True, blank=True)
    fecha = models.DateTimeField(null=True, blank=True)
    id_usuario = models.IntegerField(null=False, blank=False)
    class Meta:
        managed = False
        db_table = 'notificacion'

class Historial(models.Model):
    id_historial = models.AutoField(primary_key=True)
    id_registro = models.IntegerField(null=False, blank=False)
    valor_anterior = models.TextField(null=True, blank=True)
    valor_nuevo = models.TextField(null=True, blank=True)
    descripcion = models.TextField(null=True, blank=True)
    fecha = models.DateTimeField(null=True, blank=True)
    id_usuario = models.IntegerField(null=False, blank=False)
    class Meta:
        managed = False
        db_table = 'historial'


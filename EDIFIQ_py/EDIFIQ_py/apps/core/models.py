from django.db import models


class TipoDocumento(models.Model):
    id_tipo_documento = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)
    abreviatura = models.CharField(max_length=10)

    class Meta:
        managed = False
        db_table = 'tipo_documento'

    def __str__(self):
        return self.abreviatura or self.nombre


class TipoResidente(models.Model):
    id_tipo_residente = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)

    class Meta:
        managed = False
        db_table = 'tipo_residente'

    def __str__(self):
        return self.nombre


class TipoVisita(models.Model):
    id_tipo_visita = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)

    class Meta:
        managed = False
        db_table = 'tipo_visita'

    def __str__(self):
        return self.nombre


class TipoServicio(models.Model):
    id_tipo_servicio = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)

    class Meta:
        managed = False
        db_table = 'tipo_servicio'

    def __str__(self):
        return self.nombre


class EstadoUsuario(models.Model):
    id_estado_usuario = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=30)

    class Meta:
        managed = False
        db_table = 'estado_usuario'

    def __str__(self):
        return self.nombre


class EstadoVisita(models.Model):
    id_estado_visita = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=30)

    class Meta:
        managed = False
        db_table = 'estado_visita'

    def __str__(self):
        return self.nombre


class EstadoPaquete(models.Model):
    id_estado_paquete = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=30)

    class Meta:
        managed = False
        db_table = 'estado_paquete'

    def __str__(self):
        return self.nombre


class EstadoRecibo(models.Model):
    id_estado_recibo = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=30)

    class Meta:
        managed = False
        db_table = 'estado_recibo'

    def __str__(self):
        return self.nombre


class EstadoReserva(models.Model):
    id_estado_reserva = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=30)

    class Meta:
        managed = False
        db_table = 'estado_reserva'

    def __str__(self):
        return self.nombre


class Rol(models.Model):
    id_rol = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=30)

    class Meta:
        managed = False
        db_table = 'rol'

    def __str__(self):
        return self.nombre


class Permiso(models.Model):
    id_permiso = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'permiso'

    def __str__(self):
        return self.nombre


class RolPermiso(models.Model):
    pk = models.CompositePrimaryKey('rol', 'permiso')
    rol = models.ForeignKey(
        Rol,
        on_delete=models.PROTECT,
        db_column='id_rol',
    )
    permiso = models.ForeignKey(
        Permiso,
        on_delete=models.PROTECT,
        db_column='id_permiso',
    )

    class Meta:
        managed = False
        db_table = 'rol_permiso'

    def __str__(self):
        return f'{self.rol} - {self.permiso}'


class Usuario(models.Model):
    """Modelo de esquema (managed=False) para referencias; el login Django usa auth_user por ahora (decisión 5)."""
    id_usuario = models.AutoField(primary_key=True)
    username = models.CharField(max_length=50, unique=True)
    password = models.CharField(max_length=255)
    estado_usuario = models.ForeignKey(
        EstadoUsuario,
        on_delete=models.PROTECT,
        db_column='id_estado_usuario',
    )
    persona = models.OneToOneField(
        'personas.Persona',
        on_delete=models.PROTECT,
        db_column='id_persona',
    )
    rol = models.ForeignKey(
        Rol,
        on_delete=models.PROTECT,
        db_column='id_rol',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'usuario'

    def __str__(self):
        return self.username


class Notificacion(models.Model):
    id_notificacion = models.AutoField(primary_key=True)
    titulo = models.CharField(max_length=100)
    mensaje = models.TextField()
    leida = models.BooleanField(default=False)
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        db_column='id_usuario',
    )

    class Meta:
        managed = False
        db_table = 'notificacion'

    def __str__(self):
        return self.titulo


class Historial(models.Model):
    id_historial = models.AutoField(primary_key=True)
    accion = models.CharField(max_length=50)
    tabla_afectada = models.CharField(max_length=50)
    id_registro = models.IntegerField()
    valor_anterior = models.TextField(null=True, blank=True)
    valor_nuevo = models.TextField(null=True, blank=True)
    descripcion = models.TextField(null=True, blank=True)
    ip_usuario = models.CharField(max_length=50, null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        db_column='id_usuario',
    )

    class Meta:
        managed = False
        db_table = 'historial'

    def __str__(self):
        return f'{self.accion} {self.tabla_afectada}'

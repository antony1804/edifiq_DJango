from django.db import models
from django.core.validators import RegexValidator


class Persona(models.Model):
    id_persona = models.AutoField(primary_key=True)
    tipo_documento = models.ForeignKey(
        'core.TipoDocumento',
        on_delete=models.PROTECT,
        db_column='id_tipo_documento',
    )
    numero_documento = models.CharField(
        max_length=20,
        validators=[RegexValidator(r"^\d{1,10}$", "El documento debe tener máximo 10 dígitos.")],
    )
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    telefono = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        validators=[RegexValidator(r"^\d{1,10}$", "El teléfono debe tener máximo 10 dígitos.")],
    )
    correo = models.CharField(max_length=100, blank=True, null=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'persona'
        constraints = [
            models.UniqueConstraint(
                fields=['tipo_documento', 'numero_documento'],
                name='persona_tipo_documento_numero_documento_uniq',
            )
        ]

    def clean(self):
        # Validaciones de formato en formulario/capa de aplicación; el esquema es la fuente de verdad.
        if self.correo:
            self.correo = self.correo.strip().lower()

    def __str__(self):
        return f'{self.nombres} {self.apellidos}'

from django.db import models


class Perfil(models.Model):
    """Obsoleto: la autenticación usa la tabla original `usuario` (sin Django auth ni `usuarios_perfil`)."""
    ROLES = [('Administrador', 'Administrador'), ('Residente', 'Residente'), ('Vigilante', 'Vigilante')]
    id = models.BigAutoField(primary_key=True)
    usuario_id = models.IntegerField(null=True, blank=True)
    persona_id = models.IntegerField(null=True, blank=True)
    rol = models.CharField(max_length=20, null=True, blank=True)
    apartamento_id = models.IntegerField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'usuarios_perfil'

    def __str__(self):
        return f'Perfil obsoleto ({self.pk})'

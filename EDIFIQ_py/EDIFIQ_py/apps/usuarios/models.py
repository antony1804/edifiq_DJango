from django.db import models
from django.conf import settings

class Perfil(models.Model):
    ROLES = [('Administrador', 'Administrador'), ('Residente', 'Residente'), ('Vigilante', 'Vigilante')]
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    persona = models.OneToOneField('personas.Persona', null=True, blank=True, on_delete=models.PROTECT, db_constraint=False, related_name='perfil_usuario')
    rol = models.CharField(max_length=20, choices=ROLES, default='Residente')
    apartamento = models.ForeignKey('residentes.Apartamento', null=True, blank=True, on_delete=models.SET_NULL, db_constraint=False)

    def __str__(self):
        return f'{self.usuario.username} ({self.rol})'

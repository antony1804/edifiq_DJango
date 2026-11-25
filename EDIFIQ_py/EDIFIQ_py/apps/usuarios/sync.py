"""Compatibilidad: la autenticación usa directamente la tabla original `usuario` (sin Perfil/superusuario Django)."""

def vincular_administrador(usuario):
    return None

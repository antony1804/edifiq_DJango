# Usuarios y roles — EDIFIQ

La sección **Usuarios** permite a un superusuario crear cuentas con contraseña cifrada, asignar rol y apartamento, editar y desactivar cuentas. La sección **Asignación de roles** permite modificar perfiles existentes.

1. Configura DB_PASSWORD en CMD como antes.
2. `python manage.py check`
3. `python manage.py runserver`
4. Entra como superusuario y abre **Usuarios** en el menú.

No requiere migraciones nuevas: utiliza auth.User y usuarios.Perfil existentes.

Seguridad: solo superusuarios administran cuentas; los residentes requieren apartamento; no se puede eliminar la propia cuenta desde la interfaz. El formulario de edición deja la contraseña intacta si se deja vacía.

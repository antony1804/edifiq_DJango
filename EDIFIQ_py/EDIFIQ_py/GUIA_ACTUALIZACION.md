# EDIFIQ: personas vinculadas, reportes PDF y torres masivas

## Instalar en Windows CMD
1. Respaldar proyecto y MySQL antes de reemplazar archivos.
2. Descomprimir en una carpeta de pruebas; conservar la configuración MySQL 8.4 puerto 3307.
3. Activar `venv\Scripts\activate`.
4. Ejecutar `python -m pip install -r requirements.txt`.
5. Establecer la variable `DB_PASSWORD` en la misma consola, sin publicar la contraseña.
6. `python manage.py check`
7. `python manage.py migrate --database=default` (añade la relación opcional Persona-Perfil; conserva los datos existentes).
8. `python manage.py runserver`.

## Nuevas funciones
- **Usuarios > Registrar:** seleccionar una persona activa registrada. Los datos de nombre, apellidos y correo se copian de la persona al guardar; cada persona solo puede vincularse a una cuenta.
- **Torres > Crear torre masiva:** Torre A, 5 pisos, 4 apartamentos por piso produce 20 apartamentos: 101-104, 201-204, 301-304, 401-404, 501-504. Idempotente: no duplica existentes. No asigna residentes automáticamente.
- **Todos los listados > Descargar PDF:** exporta datos según filtros y permisos, hasta 2000 registros. No incluye contraseñas.
- **Usuarios y roles:** acceso solo para superusuarios.

## Nota
No se modifica la base `legado`. Las pruebas de integración con MySQL y los flujos de interfaz deben ejecutarse en el equipo local. No se incluyen contraseñas ni bases de datos en este ZIP.

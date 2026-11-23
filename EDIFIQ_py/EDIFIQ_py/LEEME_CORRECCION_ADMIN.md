# Corrección Personas / Usuarios

- Se corrige el error de formulario de usuario nuevo causado por filtrar usando un User no guardado.
- Los superusuarios existentes se vinculan a un registro Persona mediante migración de datos 0003.
- El ingreso y acceso al dashboard/listado sincroniza superusuarios nuevos que aún no tengan Persona.
- El documento `SYS-USER-<id>` es un identificador interno provisional, NO una cédula real. El administrador puede editar posteriormente su información desde Personas.
- No se eliminan ni duplican personas ya vinculadas a perfiles.

## Instalación
1. Respaldar código y base de datos. Copiar archivos de este ZIP sobre EDIFIQ_py, conservando la configuración MySQL y el entorno virtual.
2. Configurar DB_PASSWORD y ejecutar `python manage.py check`.
3. Ejecutar `python manage.py migrate --database=default`.
4. Ejecutar `python manage.py runserver`.
5. Revisar Personas y Registrar usuario.

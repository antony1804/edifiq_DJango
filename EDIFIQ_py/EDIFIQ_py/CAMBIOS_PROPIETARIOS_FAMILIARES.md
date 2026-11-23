# EDIFIQ — Relaciones y permisos corregidos

- El selector de familiares excluye cuentas de usuario y personas con vínculos de propietario o arrendatario. No presenta administradores como candidatos.
- Una persona propietaria puede estar vinculada a varios apartamentos mediante registros `Residente` (uno por apartamento); el campo `Perfil.apartamento` se mantiene por compatibilidad, pero el acceso del residente se determina por todos sus vínculos activos de propietario/arrendatario.
- Los familiares no obtienen acceso de propietario ni arrendatario; la inactivación de titulares está reservada a administración.
- Los residentes solo pueden administrar familiares, visitas y reservas de apartamentos con vínculo activo. Los permisos se verifican también en el servidor.
- Un documento existente no se duplica al registrar familiares: la administración debe verificar el vínculo.

## Instalación
1. Respaldar carpeta y base de datos.
2. Sustituir archivos manteniendo `venv` y variables de entorno.
3. Ejecutar `python manage.py check`, `python manage.py makemigrations --check --dry-run` y `python manage.py test apps.core.tests --keepdb` (la prueba requiere una base de datos de pruebas configurada).
4. Iniciar servidor y probar con propietario de dos apartamentos, arrendatario y administrador.

Esta entrega no modifica el esquema ni requiere migraciones nuevas. No se ha probado con la base MySQL del usuario.

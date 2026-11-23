# EDIFIQ: Familiares, visitas y validaciones

- Familiares es una tabla nueva relacionada con Personas, Apartamentos y un Residente responsable opcional.
- Los residentes pueden crear, consultar, editar e inactivar familiares de su apartamento. El vigilante solo consulta familiares activos.
- Las visitas creadas por residentes pueden quedar Pendientes o Autorizadas. Un vigilante no puede marcar una visita pendiente como Ingresó; necesita autorización del residente. Las visitas nuevas registradas por vigilantes quedan Pendientes.
- Documento y teléfono: hasta 10 dígitos. Correo y teléfono no repetidos en Personas; correo se normaliza a minúsculas.
- Antes de migrar, respaldar MySQL. Comandos: `python manage.py check`, `python manage.py makemigrations --check --dry-run`, `python manage.py migrate --database=default`.
- Datos antiguos con documentos o teléfonos no conformes deben limpiarse. Las validaciones no reescriben registros existentes.
- La unicidad del teléfono/correo se comprueba a nivel de formulario y modelo. Para unicidad concurrente garantizada en BD se requiere migración de índices tras depurar datos antiguos.
- No está verificado en el MySQL local del usuario. Probar todos los flujos con administrador, residente y vigilante antes de desplegar.

- El formulario de Familiares permite seleccionar una Persona existente o ingresar datos de una persona nueva; no se deben llenar ambas opciones.
- Si hay teléfonos/correos repetidos anteriores, se deben resolver antes de agregar restricciones UNIQUE a MySQL.
- La autorización de familiares activos se comprueba por documento y apartamento cuando un vigilante registra su ingreso.
- Para asegurar integridad completa, aún faltan pruebas funcionales de permisos y restricciones UNIQUE físicas para teléfono/correo.

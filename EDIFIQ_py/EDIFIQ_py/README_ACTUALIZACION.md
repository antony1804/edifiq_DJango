# EDIFIQ — actualización de 8 módulos

Se conserva la configuración MySQL 8.4 (`edifiq_django`, puerto 3307), login y modelos existentes. Se añade `Residente` como vínculo entre Persona y Apartamento; requiere migración `residentes.0002_residente`.

## Instalación en Windows CMD
1. Realiza una copia de seguridad de tu proyecto y de `edifiq_django`.
2. Descomprime esta versión en una carpeta nueva, no encima del proyecto en uso.
3. Activa tu entorno virtual existente o crea uno e instala `pip install Django mysqlclient`.
4. Configura `DB_PASSWORD` en la misma terminal CMD (no lo incluyas en archivos compartidos).
5. Ejecuta `python manage.py check` y `python manage.py migrate --database=default`.
6. Ejecuta `python manage.py runserver`.

## Funciones
- Dashboard: métricas, alertas y actividad recientes según rol.
- Personas y residentes: altas, consultas, búsqueda, edición y eliminación protegida por relaciones.
- Visitas: estados y fechas de entrada/salida automáticas al editar estado.
- Paquetes: recepción, seguimiento y fecha de entrega automática.
- Reservas: validación de fechas y conflictos horarios; residentes pueden solicitar reservas para su apartamento.
- Recibos: importes, vencimiento y estados.
- Perfiles: asignación de rol y apartamento por superusuario.
- Permisos: administrador gestiona todos los módulos; vigilante gestiona visitas y paquetes; residente consulta datos de su apartamento y crea reservas pendientes.

## Limitaciones y notas
- Se conservan los modelos actuales; los gráficos del dashboard son indicadores visuales sencillos, no gráficos analíticos complejos.
- La cuenta de usuario se crea desde `/admin/` por un superusuario; el módulo Perfiles asigna el rol.
- No se borran las tablas de la base original `legado`. El router no sustituye los permisos SQL de solo lectura.
- El borrado de registros con dependencias queda bloqueado; no usar para datos contables en producción sin políticas de auditoría.
- No se ejecutó una prueba real contra tu servidor MySQL local; comprueba el sistema antes de reemplazar tu proyecto.

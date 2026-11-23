EDIFIQ - Primera etapa Django + HTML

IMPORTANTE: Es una base funcional nueva, NO una migracion completa del proyecto Java ni una importacion de los datos SQL.
El archivo SQL original se conserva en referencia/edifiq-2.0.sql; NO lo ejecutes contra la base SQLite.

INSTALACION (CMD Windows):
1. Descomprime esta carpeta en una ubicacion nueva. No reemplaces tu proyecto actual sin copia de seguridad.
2. cd ruta\EDIFIQ_Django_HTML
3. python -m venv venv
4. venv\Scripts\activate
5. pip install Django
6. python manage.py makemigrations usuarios residentes personas visitas paquetes reservas recibos
7. python manage.py migrate
8. python manage.py createsuperuser
9. python manage.py runserver
10. Abre http://127.0.0.1:8000/

FUNCIONA: login Django, panel, modelos basicos, listado, registro, admin, roles preliminares.
PENDIENTE: migracion de todas las columnas y relaciones del SQL original, importacion de datos MySQL, reglas completas de negocio, filtros, edicion, notificaciones, reservas sin solapamiento, permisos granulares y pruebas.

MySQL: configurable en settings.py mediante EDIFIQ_DB=mysql y variables DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT. Requiere mysqlclient y una estrategia de migracion antes de usar la base original. No ejecutar migraciones automaticamente sobre una base existente.

EDIFIQ - ETAPA 2: AUDITORÍA SEGURA DE LAS 24 TABLAS ORIGINALES

Esta etapa NO importa los datos ni reemplaza la autenticación Django.
Agrega apps.legado con 24 modelos no administrados, conexión MySQL independiente
y comando de auditoría de tablas. Las pantallas actuales siguen usando la base
Django (SQLite por defecto).

PASOS EN CMD (Windows)
1. Descomprime en carpeta NUEVA; no sobrescribas tu proyecto sin respaldo.
2. cd RUTA\EDIFIQ_Django_HTML_etapa2
3. python -m venv venv
4. venv\Scripts\activate
5. pip install -r requirements.txt
6. python manage.py makemigrations usuarios residentes personas visitas paquetes reservas recibos
7. python manage.py migrate
8. python manage.py createsuperuser
9. python manage.py check
10. python manage.py runserver

PARA AUDITAR MYSQL EXISTENTE (opcional, SOLO LECTURA)
Usa MySQL con una cuenta que tenga SOLO permiso SELECT sobre la base original.
En CMD, ejecuta en la misma ventana:
  set EDIFIQ_LEGACY_DB=mysql
  set LEGACY_DB_NAME=edifiq
  set LEGACY_DB_USER=edifiq_lectura
  set LEGACY_DB_PASSWORD=TU_CLAVE
  python manage.py auditar_legado

ADVERTENCIAS
- No ejecutes el SQL original sobre tu base existente: comienza con DROP DATABASE.
- No ejecutes migrate --database legado.
- La tabla usuario original tiene contraseñas bcrypt ($2y$); no se importan
  directamente como usuarios Django sin una estrategia segura de conversión.
- El archivo edifiq-esquema-sin-drop.sql conserva INSERT y CREATE TABLE: SOLO
  se debe ejecutar en una base NUEVA y vacía, nunca sobre datos existentes.
- La tabla rol_permiso y apartamento_persona tienen clave primaria compuesta.
- La conexión original no es el almacenamiento de las pantallas actuales.
- Próxima etapa: plan de correspondencia y migración de datos con respaldo,
  pruebas de integridad y asignación segura de usuarios.

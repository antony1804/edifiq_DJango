# Notificaciones de paquetes por correo

Al registrar un paquete como `Recibido`, EDIFIQ envía en segundo plano un aviso a cada persona activa y vinculada al apartamento. Los correos vacíos o inválidos se omiten. El envío no altera el esquema de la base de datos.

## Variables de entorno

El backend predeterminado es consola: los mensajes aparecen en la terminal y no se conectan a SMTP. Para probar SMTP, define estas variables antes de ejecutar Django:

**CMD**

```bat
set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
set EMAIL_HOST=smtp.example.com
set EMAIL_PORT=587
set EMAIL_USE_TLS=True
set EMAIL_HOST_USER=tu-cuenta@example.com
set EMAIL_HOST_PASSWORD=tu-clave
set DEFAULT_FROM_EMAIL=tu-cuenta@example.com
set EMAIL_TIMEOUT=15
```

**PowerShell**

```powershell
$env:EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
$env:EMAIL_HOST = "smtp.example.com"
$env:EMAIL_PORT = "587"
$env:EMAIL_USE_TLS = "True"
$env:EMAIL_HOST_USER = "tu-cuenta@example.com"
$env:EMAIL_HOST_PASSWORD = "tu-clave"
$env:DEFAULT_FROM_EMAIL = "tu-cuenta@example.com"
$env:EMAIL_TIMEOUT = "15"
```

Reemplaza los valores de ejemplo por los datos SMTP de tu proveedor. No guardes credenciales en archivos del proyecto. Las variables de consola/PowerShell solo duran en esa ventana.

## Comprobar

Con el entorno SMTP configurado y la ventana correspondiente aún abierta, ejecuta:

```text
python manage.py probar_correo destinatario@example.com
```

Después registra un paquete con estado `Recibido` para un apartamento que tenga residentes activos con correo válido. La edición posterior del paquete no vuelve a enviar el aviso. Para desarrollo sin SMTP, omite `EMAIL_BACKEND` o usa `django.core.mail.backends.console.EmailBackend`; el mensaje se imprimirá en la terminal.
